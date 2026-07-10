# 02 - 数据采集层技术方案（最终版）

> 本文档定义 Tushare 数据下载器的设计，包括 append-only 存储、批次 manifest 和 watermark 校验。
> 依赖文档：01-data-pipeline-architecture.md

---

## 1. 核心原则

1. **Append-only：** Raw 层不覆盖旧数据，按批次存储
2. **Manifest：** 每个批次记录请求参数、时间、行数
3. **Watermark：** 数据完整性校验，不能只看 API 是否成功
4. **回看机制：** 财务采集自动回看近期报告期

---

## 2. 存储结构

### 2.1 目录结构

```
data/raw/{interface}/ingest_date=YYYYMMDD/batch_id=xxx/
├── manifest.json
└── data.parquet
```

示例：
```
data/raw/
├── daily/
│   ├── ingest_date=20260710/
│   │   ├── batch_id=a1b2c3d4/
│   │   │   ├── manifest.json
│   │   │   └── data.parquet
│   │   └── batch_id=e5f6g7h8/  (重试或补采)
│   │       ├── manifest.json
│   │       └── data.parquet
│   └── ingest_date=20260711/
│       └── ...
├── income/
│   ├── ingest_date=20260710/
│   │   └── batch_id=.../
│   └── ingest_date=20260801/
│       └── batch_id=.../
└── ...
```

### 2.2 Batch Manifest

```python
@dataclass
class BatchManifest:
    """批次元数据"""
    batch_id: str              # UUID
    interface: str             # "daily", "income", etc.
    params: dict               # {"trade_date": "20260709"} 或 {"period": "20260331"}
    requested_at: str          # ISO timestamp
    completed_at: str          # ISO timestamp
    row_count: int             # 数据行数
    status: str                # "success", "partial", "failed"
    error_message: Optional[str]  # 失败原因
```

**manifest 和数据同目录：**
```
data/raw/daily/ingest_date=20260710/batch_id=a1b2c3d4/
├── manifest.json    # BatchManifest 序列化
└── data.parquet     # 实际数据
```

### 2.3 为什么不覆盖旧数据

| 场景 | 覆盖式 | Append-only |
|------|--------|-------------|
| 财务数据更正 | 丢失原始版本 | 保留所有版本 |
| 数据源修订 | 无法追溯 | 可以对比不同版本 |
| 回测可复现性 | 不同时间运行结果不同 | 相同数据版本结果相同 |
| 数据质量问题 | 无法定位问题批次 | 可以定位问题批次 |

---

## 3. 下载器实现

```python
class TushareCollector:
    """Tushare 数据采集器"""
    
    def __init__(self, token: str, raw_dir: str = "data/raw"):
        self.pro = ts.pro_api(token)
        self.raw_dir = Path(raw_dir)
        self._last_call_time = 0
        self._call_interval = 0.3  # 300ms 间隔（约200次/分钟）
    
    def download(
        self,
        interface: str,
        params: dict,
        fields: Optional[list[str]] = None,
    ) -> BatchManifest:
        """
        下载单个接口的数据。
        
        返回 BatchManifest，包含批次元数据。
        """
        batch_id = str(uuid.uuid4())[:8]
        ingest_date = datetime.now().strftime("%Y%m%d")
        requested_at = datetime.now().isoformat()
        
        # 构建目录
        batch_dir = self.raw_dir / interface / f"ingest_date={ingest_date}" / f"batch_id={batch_id}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 调用 API
            self._throttle()
            df = self.pro.query(interface, **params, fields=",".join(fields) if fields else None)
            
            if df is None or len(df) == 0:
                return BatchManifest(
                    batch_id=batch_id,
                    interface=interface,
                    params=params,
                    requested_at=requested_at,
                    completed_at=datetime.now().isoformat(),
                    row_count=0,
                    status="success",
                    error_message=None,
                )
            
            # 写入 Parquet
            data_path = batch_dir / "data.parquet"
            df.to_parquet(data_path, index=False)
            
            # 写入 manifest
            manifest = BatchManifest(
                batch_id=batch_id,
                interface=interface,
                params=params,
                requested_at=requested_at,
                completed_at=datetime.now().isoformat(),
                row_count=len(df),
                status="success",
                error_message=None,
            )
            self._write_manifest(batch_dir, manifest)
            
            return manifest
            
        except Exception as e:
            # 记录失败
            manifest = BatchManifest(
                batch_id=batch_id,
                interface=interface,
                params=params,
                requested_at=requested_at,
                completed_at=datetime.now().isoformat(),
                row_count=0,
                status="failed",
                error_message=str(e),
            )
            self._write_manifest(batch_dir, manifest)
            raise
    
    def _throttle(self):
        """频率控制"""
        elapsed = time.time() - self._last_call_time
        if elapsed < self._call_interval:
            time.sleep(self._call_interval - elapsed)
        self._last_call_time = time.time()
    
    def _write_manifest(self, batch_dir: Path, manifest: BatchManifest):
        """写入 manifest（原子写入）"""
        manifest_path = batch_dir / "manifest.json"
        tmp_path = batch_dir / "manifest.json.tmp"
        
        with open(tmp_path, "w") as f:
            json.dump(asdict(manifest), f, indent=2)
        
        tmp_path.rename(manifest_path)
```

---

## 4. 调度机制

### 4.1 每日增量下载

```python
class DownloadScheduler:
    """下载调度器"""
    
    def run_daily(self, date: Optional[str] = None):
        """
        每日增量下载。
        
        流程：
        1. 检查目标交易日数据是否已存在
        2. 如果不存在，下载 daily / adj_factor / daily_basic
        3. 校验数据完整性（watermark）
        4. 不完整则重试
        """
        if date is None:
            date = self._get_latest_trading_day()
        
        interfaces = ["daily", "adj_factor", "daily_basic"]
        
        for interface in interfaces:
            # 检查是否已下载
            if self._is_downloaded(interface, date):
                continue
            
            # 下载
            manifest = self.collector.download(
                interface=interface,
                params={"trade_date": date},
            )
            
            # Watermark 校验
            if not self._validate_watermark(interface, date, manifest):
                self._retry(interface, date, max_retries=3)
    
    def run_financial(self, lookback_periods: int = 4):
        """
        财务数据采集。
        
        每次采集时回看最近 N 个报告期，自动捕获更正。
        """
        # 计算最近 N 个报告期
        periods = self._get_recent_periods(lookback_periods)
        
        for period in periods:
            for interface in ["income", "balancesheet", "cashflow", "fina_indicator"]:
                self.collector.download(
                    interface=interface,
                    params={"period": period},
                )
    
    def _get_recent_periods(self, n: int) -> list[str]:
        """获取最近 N 个报告期"""
        today = datetime.now()
        periods = []
        
        # 报告期：3/31, 6/30, 9/30, 12/31
        for year in range(today.year - 1, today.year + 1):
            for month in [3, 6, 9, 12]:
                period = f"{year}{month:02d}31"
                if period <= today.strftime("%Y%m%d"):
                    periods.append(period)
        
        return sorted(periods, reverse=True)[:n]
```

### 4.2 Cron 配置

```bash
# 每日盘后增量下载（17:30 首次尝试）
30 17 * * 1-5 cd /root/.openclaw/workspace/ai-quant && python scripts/download_daily.py

# 18:00 重试（如果 17:30 失败）
0 18 * * 1-5 cd /root/.openclaw/workspace/ai-quant && python scripts/download_daily.py --retry

# 18:30 再次重试
30 18 * * 1-5 cd /root/.openclaw/workspace/ai-quant && python scripts/download_daily.py --retry

# 每周六：财务数据采集（回看 4 个报告期）
0 10 * * 6 cd /root/.openclaw/workspace/ai-quant && python scripts/download_financial.py --lookback 4

# 每月第一个周六：指数成分
0 11 * * 6 cd /root/.openclaw/workspace/ai-quant && python scripts/download_index_weight.py
```

---

## 5. Watermark 校验

### 5.1 校验规则

```python
def validate_watermark(
    interface: str,
    date: str,
    manifest: BatchManifest,
) -> bool:
    """
    Watermark 校验：验证数据完整性。
    
    不能只看 API 是否成功，需要检查数据质量。
    """
    if manifest.status != "success":
        return False
    
    # 读取数据
    df = pd.read_parquet(self._get_data_path(interface, date))
    
    checks = {}
    
    if interface == "daily":
        # 日线数据校验
        checks = {
            "row_count_ok": len(df) >= self._get_rolling_median("daily") * 0.9,
            "trade_date_unique": df["trade_date"].nunique() == 1,
            "ts_code_no_dup": df["ts_code"].is_unique,
            "close_not_null_pct": df["close"].notna().mean() > 0.95,
            "max_date_match": df["trade_date"].max() == date,
        }
    
    elif interface in ("income", "balancesheet", "cashflow", "fina_indicator"):
        # 财务数据校验
        checks = {
            "row_count_ok": len(df) > 0,
            "ts_code_not_null": df["ts_code"].notna().all(),
            "end_date_not_null": df["end_date"].notna().all(),
        }
    
    elif interface == "adj_factor":
        # 复权因子校验
        checks = {
            "row_count_ok": len(df) >= self._get_rolling_median("adj_factor") * 0.9,
            "adj_factor_positive": (df["adj_factor"] > 0).all(),
        }
    
    return all(checks.values())

def _get_rolling_median(self, interface: str, window: int = 20) -> float:
    """获取最近 N 次下载的行数中位数"""
    # 从历史 manifest 中计算
    manifests = self._get_recent_manifests(interface, window)
    row_counts = [m.row_count for m in manifests]
    return np.median(row_counts) if row_counts else 0
```

### 5.2 告警机制

```python
def check_and_alert(self, interface: str, date: str):
    """检查数据并发送告警"""
    manifest = self._get_manifest(interface, date)
    
    if manifest is None:
        self._send_alert(f"数据缺失: {interface} {date}")
        return
    
    if manifest.status == "failed":
        self._send_alert(f"数据下载失败: {interface} {date}, 错误: {manifest.error_message}")
        return
    
    if not self._validate_watermark(interface, date, manifest):
        self._send_alert(f"数据校验失败: {interface} {date}, 行数: {manifest.row_count}")
        return
```

---

## 6. 数据查询

### 6.1 查询最新数据

```python
def get_latest_batch(self, interface: str, params: dict) -> Optional[Path]:
    """
    获取最新批次的数据路径。
    
    用于 Normalize 层读取 Raw 数据。
    """
    interface_dir = self.raw_dir / interface
    
    # 按 ingest_date 降序排列
    ingest_dates = sorted(
        [d.name.replace("ingest_date=", "") for d in interface_dir.iterdir() if d.is_dir()],
        reverse=True,
    )
    
    for ingest_date in ingest_dates:
        ingest_dir = interface_dir / f"ingest_date={ingest_date}"
        
        # 按 batch_id 查找
        for batch_dir in sorted(ingest_dir.iterdir(), reverse=True):
            if not batch_dir.is_dir():
                continue
            
            manifest_path = batch_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            
            manifest = self._read_manifest(manifest_path)
            
            # 检查参数是否匹配
            if manifest.params == params and manifest.status == "success":
                return batch_dir / "data.parquet"
    
    return None
```

---

## 7. 使用示例

```python
from app.data.collector import TushareCollector
from app.data.scheduler import DownloadScheduler

collector = TushareCollector(token="your_token")
scheduler = DownloadScheduler(collector)

# 每日增量
scheduler.run_daily()

# 财务数据（回看 4 个报告期）
scheduler.run_financial(lookback_periods=4)

# 全量下载（首次）
scheduler.run_full()
```
