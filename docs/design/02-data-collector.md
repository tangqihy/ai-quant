# 02 - 数据采集层技术方案

> 本文档定义 Tushare 数据下载器的接口设计、存储策略、增量逻辑和调度机制。
> 依赖文档：01-data-pipeline-architecture.md

---

## 1. 模块职责

数据采集层（Collector）负责：
1. 调用 Tushare API 获取数据
2. 将原始数据写入 Parquet（Raw 层）
3. 增量更新：只下载缺失的数据
4. 频率控制：遵守 Tushare 的调用限制
5. 错误重试：网络异常时自动重试

---

## 2. 接口设计

### 2.1 核心类

```python
# app/data/collector.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import tushare as ts
import pyarrow as pa
import pyarrow.parquet as pq

class TushareCollector:
    """Tushare 数据采集器"""
    
    def __init__(self, token: str, raw_dir: str = "data/raw"):
        self.pro = ts.pro_api(token)
        self.raw_dir = Path(raw_dir)
        self._last_call_time = 0
        self._call_interval = 0.3  # 每次调用间隔 300ms（约200次/分钟）
    
    def download(
        self,
        interface: str,
        params: dict,
        fields: Optional[list[str]] = None,
        partition_by: Optional[str] = None,
        force: bool = False,
    ) -> Path:
        """
        下载单个接口的数据并写入 Parquet。
        
        Args:
            interface: Tushare 接口名（如 'daily', 'income'）
            params: 接口参数（如 {'trade_date': '20260709'}）
            fields: 指定返回字段，None 表示全部
            partition_by: 分区字段名（如 'trade_date'）
            force: 是否强制重新下载（覆盖已有文件）
        
        Returns:
            写入的 Parquet 文件/目录路径
        """
        ...
    
    def download_range(
        self,
        interface: str,
        date_field: str,
        start_date: str,
        end_date: str,
        other_params: Optional[dict] = None,
        fields: Optional[list[str]] = None,
        partition_by: Optional[str] = None,
    ) -> list[Path]:
        """
        按日期范围批量下载。
        
        自动按天（日线）或按季（财务）拆分请求。
        """
        ...
    
    def _throttle(self):
        """频率控制，确保不超过 Tushare 调用限制"""
        ...
    
    def _write_parquet(
        self,
        data: list[dict],
        path: Path,
        partition_by: Optional[str] = None,
    ):
        """将数据写入 Parquet，支持分区"""
        ...
```

### 2.2 接口注册表

```python
# app/data/schemas.py

INTERFACE_CONFIG = {
    # ===== 第一梯队：日线行情 =====
    "daily": {
        "description": "A股日线行情",
        "params": ["trade_date"],  # 或 ts_code
        "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
        "partition_by": "trade_date",
        "primary_key": ("ts_code", "trade_date"),
        "frequency": "daily",  # 每个交易日
    },
    "adj_factor": {
        "description": "复权因子",
        "params": ["trade_date"],  # 或 ts_code
        "fields": "ts_code,trade_date,adj_factor",
        "partition_by": "trade_date",
        "primary_key": ("ts_code", "trade_date"),
        "frequency": "daily",
    },
    "daily_basic": {
        "description": "每日指标（PE/PB/市值等）",
        "params": ["trade_date"],  # 或 ts_code
        "fields": "ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv",
        "partition_by": "trade_date",
        "primary_key": ("ts_code", "trade_date"),
        "frequency": "daily",
    },
    
    # ===== 第一梯队：交易日历 =====
    "trade_cal": {
        "description": "交易日历",
        "params": ["exchange_id"],
        "fields": "exchange_id,cal_date,is_open,pretrade_date",
        "partition_by": None,  # 全量，不分区
        "primary_key": ("exchange_id", "cal_date"),
        "frequency": "full",  # 全量更新
    },
    
    # ===== 第一梯队：股票基础信息 =====
    "stock_basic": {
        "description": "股票基础信息",
        "params": [],
        "fields": "ts_code,symbol,name,area,industry,market,exchange,list_date,delist_date,is_hs,list_status",
        "partition_by": None,
        "primary_key": ("ts_code",),
        "frequency": "full",
    },
    
    # ===== 第一梯队：财务报表 =====
    "income": {
        "description": "利润表",
        "params": ["period"],  # 如 20260331
        "fields": None,  # 全部字段
        "partition_by": "period",
        "primary_key": ("ts_code", "ann_date", "end_date", "report_type"),
        "frequency": "quarterly",
    },
    "balancesheet": {
        "description": "资产负债表",
        "params": ["period"],
        "fields": None,
        "partition_by": "period",
        "primary_key": ("ts_code", "ann_date", "end_date", "report_type"),
        "frequency": "quarterly",
    },
    "cashflow": {
        "description": "现金流量表",
        "params": ["period"],
        "fields": None,
        "partition_by": "period",
        "primary_key": ("ts_code", "ann_date", "end_date", "report_type"),
        "frequency": "quarterly",
    },
    "fina_indicator": {
        "description": "财务指标",
        "params": ["period"],
        "fields": None,
        "partition_by": "period",
        "primary_key": ("ts_code", "ann_date", "end_date", "report_type"),
        "frequency": "quarterly",
    },
    "forecast": {
        "description": "业绩预告",
        "params": ["period"],
        "fields": None,
        "partition_by": "period",
        "primary_key": ("ts_code", "ann_date", "end_date"),
        "frequency": "quarterly",
    },
    "express": {
        "description": "业绩快报",
        "params": ["period"],
        "fields": None,
        "partition_by": "period",
        "primary_key": ("ts_code", "ann_date", "end_date"),
        "frequency": "quarterly",
    },
    "dividend": {
        "description": "分红送股",
        "params": [],
        "fields": None,
        "partition_by": None,
        "primary_key": ("ts_code", "ann_date", "end_date", "div_proc"),
        "frequency": "full",
    },
    "disclosure_date": {
        "description": "财报披露日期",
        "params": [],
        "fields": None,
        "partition_by": None,
        "primary_key": ("ts_code", "end_date"),
        "frequency": "full",
    },
    
    # ===== 第一梯队：指数 =====
    "index_weight": {
        "description": "指数成分和权重",
        "params": ["index_code", "start_date", "end_date"],
        "fields": None,
        "partition_by": "index_code",
        "primary_key": ("index_code", "con_code", "trade_date"),
        "frequency": "monthly",
    },
    "index_member_all": {
        "description": "申万行业成分",
        "params": [],
        "fields": None,
        "partition_by": None,
        "primary_key": ("stock_code", "index_code"),
        "frequency": "full",
    },
    "index_classify": {
        "description": "申万行业分类",
        "params": [],
        "fields": "index_code,industry_name,level,src",
        "partition_by": None,
        "primary_key": ("index_code",),
        "frequency": "full",
    },
    
    # ===== 第二梯队（按需）=====
    "suspend_d": {
        "description": "停复牌信息",
        "params": ["trade_date"],
        "fields": None,
        "partition_by": "trade_date",
        "primary_key": ("ts_code", "trade_date"),
        "frequency": "daily",
    },
    "stk_limit": {
        "description": "每日涨跌停价格",
        "params": ["trade_date"],
        "fields": None,
        "partition_by": "trade_date",
        "primary_key": ("ts_code", "trade_date"),
        "frequency": "daily",
    },
}
```

---

## 3. 存储策略

### 3.1 Parquet 分区规则

| 接口类型 | 分区字段 | 目录结构 | 说明 |
|----------|----------|----------|------|
| 日线行情 | `trade_date` | `daily/trade_date=20260709/` | 每个交易日一个目录 |
| 复权因子 | `trade_date` | `adj_factor/trade_date=20260709/` | 同上 |
| 每日指标 | `trade_date` | `daily_basic/trade_date=20260709/` | 同上 |
| 财务报表 | `period` | `income/period=20260331/` | 每个报告期一个目录 |
| 指数成分 | `index_code` | `index_weight/index_code=000300.SH/` | 每个指数一个目录 |
| 交易日历 | 无 | `trade_cal/trade_cal.parquet` | 单文件全量 |
| 股票基础 | 无 | `stock_basic/stock_basic.parquet` | 单文件全量 |

### 3.2 文件命名

```
data/raw/
├── daily/
│   ├── trade_date=20260707/
│   │   └── part-0.parquet
│   ├── trade_date=20260708/
│   │   └── part-0.parquet
│   └── trade_date=20260709/
│       └── part-0.parquet
├── income/
│   ├── period=20251231/
│   │   └── part-0.parquet
│   └── period=20260331/
│       └── part-0.parquet
├── index_weight/
│   ├── index_code=000300.SH/
│   │   └── part-0.parquet
│   └── index_code=000905.SH/
│       └── part-0.parquet
├── trade_cal/
│   └── trade_cal.parquet
└── stock_basic/
    └── stock_basic.parquet
```

### 3.3 增量判断逻辑

```python
def get_missing_dates(
    interface: str,
    partition_by: str,
    start_date: str,
    end_date: str,
) -> list[str]:
    """获取缺失的分区日期"""
    raw_path = self.raw_dir / interface
    
    # 获取已有分区
    existing = set()
    if raw_path.exists():
        for d in raw_path.iterdir():
            if d.is_dir() and d.name.startswith(f"{partition_by}="):
                date_str = d.name.split("=")[1]
                existing.add(date_str)
    
    # 获取应有日期
    if interface_config[interface]["frequency"] == "daily":
        # 从交易日历获取交易日
        trading_days = self._get_trading_days(start_date, end_date)
    elif interface_config[interface]["frequency"] == "quarterly":
        # 财务数据：按季报周期
        trading_days = self._get_quarter_periods(start_date, end_date)
    elif interface_config[interface]["frequency"] == "monthly":
        # 月度数据：每月最后一个交易日
        trading_days = self._get_month_end_dates(start_date, end_date)
    else:
        # 全量数据：只检查是否存在
        return [] if existing else [start_date]
    
    # 返回缺失的日期
    missing = sorted(set(trading_days) - existing)
    return missing
```

---

## 4. 调度机制

### 4.1 Cron 任务

```bash
# 每日盘后增量下载（17:30，确保 Tushare 数据已更新）
30 17 * * 1-5 cd /root/.openclaw/workspace/ai-quant && python scripts/download_incremental.py

# 每月第一个交易日：下载上月指数成分
0 18 1 * * cd /root/.openclaw/workspace/ai-quant && python scripts/download_index_weight.py

# 每季度财报季：下载最新财务数据（4/8/10/次年4月）
0 19 1 4,8,10,1 * cd /root/.openclaw/workspace/ai-quant && python scripts/download_financial.py
```

### 4.2 下载调度器

```python
# app/data/scheduler.py

class DownloadScheduler:
    """下载调度器"""
    
    def __init__(self, collector: TushareCollector):
        self.collector = collector
    
    def run_daily(self, date: Optional[str] = None):
        """
        每日增量下载。
        
        下载内容：
        1. daily - 日线行情
        2. adj_factor - 复权因子
        3. daily_basic - 每日指标
        4. suspend_d - 停复牌（如果需要）
        5. stk_limit - 涨跌停价格（如果需要）
        """
        if date is None:
            date = self._get_latest_trading_day()
        
        interfaces = ["daily", "adj_factor", "daily_basic"]
        
        for interface in interfaces:
            config = INTERFACE_CONFIG[interface]
            self.collector.download(
                interface=interface,
                params={"trade_date": date},
                fields=config["fields"].split(",") if config["fields"] else None,
                partition_by=config["partition_by"],
            )
    
    def run_financial(self, period: str):
        """
        下载指定报告期的财务数据。
        
        Args:
            period: 报告期，如 '20260331' 表示 2026 年一季报
        """
        interfaces = [
            "income", "balancesheet", "cashflow",
            "fina_indicator", "forecast", "express",
            "dividend", "disclosure_date",
        ]
        
        for interface in interfaces:
            config = INTERFACE_CONFIG[interface]
            self.collector.download(
                interface=interface,
                params={"period": period},
                fields=None,  # 财务数据取全部字段
                partition_by=config["partition_by"],
            )
    
    def run_index_weight(
        self,
        index_codes: list[str] = ["000300.SH", "000905.SH", "000852.SH"],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """
        下载指数成分和权重。
        
        默认下载沪深300、中证500、中证1000。
        """
        if end_date is None:
            end_date = self._get_today()
        if start_date is None:
            start_date = self._get_one_year_ago()
        
        for index_code in index_codes:
            self.collector.download(
                interface="index_weight",
                params={
                    "index_code": index_code,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                partition_by="index_code",
            )
    
    def run_full(self):
        """
        全量下载。首次运行或数据重建时使用。
        
        下载内容：
        1. trade_cal - 交易日历（全量）
        2. stock_basic - 股票基础信息（全量）
        3. index_classify - 申万行业分类（全量）
        4. index_member_all - 申万行业成分（全量）
        5. 近 3 年日线数据
        6. 近 3 年财务数据
        """
        # 全量接口
        full_interfaces = ["trade_cal", "stock_basic", "index_classify", "index_member_all"]
        for interface in full_interfaces:
            config = INTERFACE_CONFIG[interface]
            self.collector.download(
                interface=interface,
                params={},
                fields=config["fields"].split(",") if config["fields"] else None,
                partition_by=config["partition_by"],
            )
        
        # 日线数据：近 3 年
        end_date = self._get_today()
        start_date = self._get_years_ago(3)
        
        for interface in ["daily", "adj_factor", "daily_basic"]:
            self.collector.download_range(
                interface=interface,
                date_field="trade_date",
                start_date=start_date,
                end_date=end_date,
                partition_by=INTERFACE_CONFIG[interface]["partition_by"],
            )
        
        # 财务数据：近 3 年的季报
        periods = self._get_quarter_periods(start_date, end_date)
        for period in periods:
            self.run_financial(period)
        
        # 指数成分
        self.run_index_weight(start_date=start_date, end_date=end_date)
```

---

## 5. Tushare 调用限制处理

### 5.1 积分与频率

| 积分档 | 每分钟限制 | 每次最大条数 | 说明 |
|--------|-----------|-------------|------|
| 2000 | 200 | 5000 | 基础档，大部分接口可用 |
| 5000 | 500 | 8000 | 取消常规总量限制 |

### 5.2 频率控制实现

```python
import time
from functools import wraps

def rate_limit(calls_per_minute: int = 200):
    """装饰器：限制每分钟调用次数"""
    min_interval = 60.0 / calls_per_minute
    
    def decorator(func):
        last_call = [0.0]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_call[0] = time.time()
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class TushareCollector:
    @rate_limit(calls_per_minute=200)
    def _call_api(self, interface: str, params: dict, fields: Optional[str] = None) -> list[dict]:
        """调用 Tushare API，带频率控制和重试"""
        for attempt in range(3):
            try:
                df = self.pro.query(interface, **params, fields=fields)
                return df.to_dict("records") if df is not None else []
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)  # 指数退避
                    continue
                raise
```

### 5.3 大数据量接口处理

部分接口（如 `daily`）单次请求返回数据量大，需要分批：

```python
def download_range(self, interface, date_field, start_date, end_date, ...):
    """按日期范围下载，自动分批"""
    dates = self._get_date_range(start_date, end_date, interface)
    
    for date in dates:
        # 检查是否已下载
        if not force and self._is_downloaded(interface, date):
            continue
        
        # 下载
        data = self._call_api(interface, {date_field: date}, fields)
        
        if data:
            self._write_parquet(data, interface, date)
        
        # 记录下载状态
        self._mark_downloaded(interface, date, len(data))
```

---

## 6. 错误处理

### 6.1 重试策略

```python
RETRY_STRATEGY = {
    "max_retries": 3,
    "base_delay": 1,      # 秒
    "max_delay": 30,       # 秒
    "backoff_factor": 2,   # 指数退避
    "retryable_errors": [
        "ConnectionError",
        "TimeoutError",
        "HTTPError",
        "TushareError",    # Tushare 返回的错误
    ],
}
```

### 6.2 下载状态记录

```python
# data/raw/.download_status.json
{
    "daily": {
        "20260707": {"status": "ok", "rows": 5200, "timestamp": "2026-07-07T18:00:00"},
        "20260708": {"status": "ok", "rows": 5180, "timestamp": "2026-07-08T18:00:00"},
        "20260709": {"status": "ok", "rows": 5190, "timestamp": "2026-07-09T18:00:00"}
    },
    "income": {
        "20260331": {"status": "ok", "rows": 4800, "timestamp": "2026-04-30T19:00:00"},
        "20251231": {"status": "ok", "rows": 5000, "timestamp": "2026-04-30T19:00:00"}
    }
}
```

### 6.3 数据完整性校验

```python
def verify_download(self, interface: str, date: str) -> dict:
    """校验下载数据的完整性"""
    path = self.raw_dir / interface / f"{INTERFACE_CONFIG[interface]['partition_by']}={date}"
    
    if not path.exists():
        return {"status": "missing", "message": "目录不存在"}
    
    parquet_files = list(path.glob("*.parquet"))
    if not parquet_files:
        return {"status": "empty", "message": "目录为空"}
    
    # 读取并校验
    import pyarrow.parquet as pq
    table = pq.read_table(parquet_files[0])
    
    checks = {
        "row_count": len(table),
        "columns": table.column_names,
        "has_ts_code": "ts_code" in table.column_names,
        "null_counts": {col: table.column(col).null_count for col in table.column_names},
    }
    
    # 日线数据特殊校验
    if interface == "daily":
        checks["has_close"] = "close" in table.column_names
        checks["close_range"] = all(
            0 < v < 10000 for v in table.column("close").to_pylist() if v is not None
        )
    
    return {"status": "ok", "checks": checks}
```

---

## 7. 使用示例

### 7.1 手动下载

```python
from app.data.collector import TushareCollector
from app.data.scheduler import DownloadScheduler

collector = TushareCollector(token="your_token")
scheduler = DownloadScheduler(collector)

# 下载单日数据
collector.download("daily", {"trade_date": "20260709"}, partition_by="trade_date")

# 下载某季度财务数据
scheduler.run_financial("20260331")

# 全量下载（首次运行）
scheduler.run_full()
```

### 7.2 脚本调用

```bash
# 增量下载今日数据
python scripts/download_incremental.py

# 全量下载（首次）
python scripts/download_full.py

# 下载指定日期
python scripts/download_incremental.py --date 20260709

# 下载财务数据
python scripts/download_financial.py --period 20260331

# 校验数据完整性
python scripts/verify_data.py --interface daily --date 20260709
```
