# 03 - Normalize 层技术方案（最终版）

> 本文档定义数据标准化的设计，包括 FieldSpec 单位规范、版本化存储和月度压实。
> 依赖文档：01-data-pipeline-architecture.md、02-data-collector.md

---

## 1. 核心原则

1. **FieldSpec：** 每个字段显式定义源单位和标准单位
2. **版本化：** 保留历史版本，不覆盖旧数据
3. **双视图：** latest view（最新）+ 版本历史
4. **月度压实：** Normalize 层按月合并分区

---

## 2. FieldSpec 单位规范

### 2.1 为什么需要 FieldSpec

Tushare 不同接口字段单位不统一：
- 有的字段是百分数（如 `pct_chg`）
- 有的是比例（如 `adj_factor`）
- 有的是万元（如 `total_mv`）
- 有的是千股（如 `vol`）
- 有的是元（如 `close`）

**不能根据字段名称模糊判断，否则因子可能相差 100 倍。**

### 2.2 FieldSpec 定义

```python
@dataclass
class FieldSpec:
    """字段规范"""
    name: str                    # 字段名
    source_unit: str             # 源单位（Tushare 原始单位）
    canonical_unit: str          # 标准单位（系统内部单位）
    multiplier: float            # 转换乘数
    nullable: bool               # 是否可为空
    description: str             # 描述
    
    def convert(self, value) -> float:
        """转换单位"""
        if value is None or pd.isna(value):
            return None
        return value * self.multiplier
```

### 2.3 各接口 FieldSpec

```python
# 日线行情
DAILY_FIELDS = {
    "ts_code": FieldSpec("ts_code", "string", "string", 1.0, False, "股票代码"),
    "trade_date": FieldSpec("trade_date", "YYYYMMDD", "YYYYMMDD", 1.0, False, "交易日期"),
    "open": FieldSpec("open", "元", "元", 1.0, False, "开盘价"),
    "high": FieldSpec("high", "元", "元", 1.0, False, "最高价"),
    "low": FieldSpec("low", "元", "元", 1.0, False, "最低价"),
    "close": FieldSpec("close", "元", "元", 1.0, False, "收盘价"),
    "pre_close": FieldSpec("pre_close", "元", "元", 1.0, False, "昨收价"),
    "change": FieldSpec("change", "元", "元", 1.0, False, "涨跌额"),
    "pct_chg": FieldSpec("pct_chg", "%", "ratio", 0.01, False, "涨跌幅"),
    "vol": FieldSpec("vol", "手", "手", 1.0, False, "成交量"),
    "amount": FieldSpec("amount", "千元", "元", 1000.0, False, "成交额"),
}

# 每日指标
DAILY_BASIC_FIELDS = {
    "ts_code": FieldSpec("ts_code", "string", "string", 1.0, False, "股票代码"),
    "trade_date": FieldSpec("trade_date", "YYYYMMDD", "YYYYMMDD", 1.0, False, "交易日期"),
    "close": FieldSpec("close", "元", "元", 1.0, False, "收盘价"),
    "turnover_rate": FieldSpec("turnover_rate", "%", "ratio", 0.01, False, "换手率"),
    "turnover_rate_f": FieldSpec("turnover_rate_f", "%", "ratio", 0.01, False, "换手率(自由流通)"),
    "volume_ratio": FieldSpec("volume_ratio", "ratio", "ratio", 1.0, True, "量比"),
    "pe": FieldSpec("pe", "ratio", "ratio", 1.0, True, "市盈率(总)"),
    "pe_ttm": FieldSpec("pe_ttm", "ratio", "ratio", 1.0, True, "市盈率TTM"),
    "pb": FieldSpec("pb", "ratio", "ratio", 1.0, True, "市净率"),
    "ps": FieldSpec("ps", "ratio", "ratio", 1.0, True, "市销率"),
    "ps_ttm": FieldSpec("ps_ttm", "ratio", "ratio", 1.0, True, "市销率TTM"),
    "dv_ratio": FieldSpec("dv_ratio", "%", "ratio", 0.01, True, "股息率"),
    "dv_ttm": FieldSpec("dv_ttm", "%", "ratio", 0.01, True, "股息率TTM"),
    "total_share": FieldSpec("total_share", "万股", "股", 10000.0, False, "总股本"),
    "float_share": FieldSpec("float_share", "万股", "股", 10000.0, False, "流通股本"),
    "free_share": FieldSpec("free_share", "万股", "股", 10000.0, False, "自由流通股本"),
    "total_mv": FieldSpec("total_mv", "万元", "元", 10000.0, False, "总市值"),
    "circ_mv": FieldSpec("circ_mv", "万元", "元", 10000.0, False, "流通市值"),
}

# 复权因子
ADJ_FACTOR_FIELDS = {
    "ts_code": FieldSpec("ts_code", "string", "string", 1.0, False, "股票代码"),
    "trade_date": FieldSpec("trade_date", "YYYYMMDD", "YYYYMMDD", 1.0, False, "交易日期"),
    "adj_factor": FieldSpec("adj_factor", "ratio", "ratio", 1.0, False, "复权因子"),
}

# 财务指标（部分字段）
FINA_INDICATOR_FIELDS = {
    "ts_code": FieldSpec("ts_code", "string", "string", 1.0, False, "股票代码"),
    "ann_date": FieldSpec("ann_date", "YYYYMMDD", "YYYYMMDD", 1.0, False, "公告日期"),
    "f_ann_date": FieldSpec("f_ann_date", "YYYYMMDD", "YYYYMMDD", 1.0, True, "实际公告日期"),
    "end_date": FieldSpec("end_date", "YYYYMMDD", "YYYYMMDD", 1.0, False, "报告期"),
    "report_type": FieldSpec("report_type", "int", "int", 1.0, False, "报告类型"),
    "roe": FieldSpec("roe", "%", "ratio", 0.01, True, "净资产收益率"),
    "roa": FieldSpec("roa", "%", "ratio", 0.01, True, "总资产报酬率"),
    "grossprofit_margin": FieldSpec("grossprofit_margin", "%", "ratio", 0.01, True, "毛利率"),
    "debt_to_assets": FieldSpec("debt_to_assets", "%", "ratio", 0.01, True, "资产负债率"),
    "op_yoy": FieldSpec("op_yoy", "%", "ratio", 0.01, True, "营收同比增速"),
    "netprofit_yoy": FieldSpec("netprofit_yoy", "%", "ratio", 0.01, True, "归母净利润同比增速"),
}

# 指数成分权重
INDEX_WEIGHT_FIELDS = {
    "index_code": FieldSpec("index_code", "string", "string", 1.0, False, "指数代码"),
    "con_code": FieldSpec("con_code", "string", "string", 1.0, False, "成分股代码"),
    "trade_date": FieldSpec("trade_date", "YYYYMMDD", "YYYYMMDD", 1.0, False, "交易日期"),
    "weight": FieldSpec("weight", "%", "%", 1.0, False, "权重"),
}
```

### 2.4 单位测试

```python
def test_field_specs():
    """测试 FieldSpec 单位转换"""
    # 日线
    assert DAILY_FIELDS["pct_chg"].convert(5.0) == 0.05  # 5% → 0.05
    assert DAILY_FIELDS["amount"].convert(1000.0) == 1000000.0  # 千元 → 元
    
    # 每日指标
    assert DAILY_BASIC_FIELDS["total_mv"].convert(10000.0) == 100000000.0  # 万元 → 元
    assert DAILY_BASIC_FIELDS["turnover_rate"].convert(5.0) == 0.05  # 5% → 0.05
    
    # 财务指标
    assert FINA_INDICATOR_FIELDS["roe"].convert(15.0) == 0.15  # 15% → 0.15
```

---

## 3. 版本化存储

### 3.1 为什么不覆盖旧数据

| 场景 | 覆盖式 | 版本化 |
|------|--------|--------|
| 财务数据更正 | 丢失原始版本 | 保留所有版本 |
| 回测可复现性 | 不同时间结果不同 | 相同版本结果相同 |
| 数据质量问题 | 无法定位 | 可以定位问题版本 |

### 3.2 存储结构

```
data/normalized/
├── latest/                    # Latest View（最新版本）
│   ├── daily/
│   │   └── trade_year=2026/
│   │       ├── trade_month=07/
│   │       │   └── data.parquet
│   │       └── ...
│   └── ...
└── versions/                  # 版本历史
    ├── daily/
    │   ├── ingest_date=20260710/
    │   │   └── batch_id=xxx/
    │   │       └── data.parquet
    │   └── ingest_date=20260711/
    │       └── batch_id=yyy/
    │           └── data.parquet
    └── ...
```

### 3.3 Latest View 生成

```python
def generate_latest_view(interface: str):
    """
    生成 Latest View。
    
    逻辑：
    1. 读取所有版本的数据
    2. 按主键去重，保留最新版本（max ingested_at）
    3. 写入 latest/ 目录
    """
    versions_dir = Path(f"data/normalized/versions/{interface}")
    latest_dir = Path(f"data/normalized/latest/{interface}")
    
    # 读取所有版本
    all_dfs = []
    for batch_dir in versions_dir.rglob("data.parquet"):
        df = pd.read_parquet(batch_dir)
        all_dfs.append(df)
    
    if not all_dfs:
        return
    
    merged = pd.concat(all_dfs, ignore_index=True)
    
    # 按主键去重
    pk = get_primary_key(interface)
    merged = merged.sort_values("ingested_at", ascending=False)
    merged = merged.drop_duplicates(subset=pk, keep="first")
    
    # 按月分区写入
    if "trade_date" in merged.columns:
        merged["trade_year"] = merged["trade_date"].str[:4]
        merged["trade_month"] = merged["trade_date"].str[4:6]
        merged.to_parquet(latest_dir, partition_cols=["trade_year", "trade_month"])
    else:
        merged.to_parquet(latest_dir / "data.parquet")
```

---

## 4. 数据转换

### 4.1 转换流程

```python
def normalize_interface(interface: str):
    """标准化单个接口"""
    raw_dir = Path(f"data/raw/{interface}")
    norm_dir = Path(f"data/normalized/versions/{interface}")
    
    fields = get_field_specs(interface)
    
    # 扫描 Raw 层新批次
    for batch_dir in raw_dir.rglob("manifest.json"):
        manifest = read_manifest(batch_dir)
        
        if manifest.status != "success":
            continue
        
        # 检查是否已处理
        target_dir = norm_dir / f"ingest_date={manifest.ingested_at[:8]}" / f"batch_id={manifest.batch_id}"
        if target_dir.exists():
            continue
        
        # 读取数据
        df = pd.read_parquet(batch_dir / "data.parquet")
        
        # 应用 FieldSpec 转换
        df = apply_field_specs(df, fields)
        
        # 日期类型转换
        df = convert_dates(df)
        
        # 写入
        target_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(target_dir / "data.parquet", index=False)
    
    # 更新 Latest View
    generate_latest_view(interface)
```

### 4.2 FieldSpec 转换

```python
def apply_field_specs(df: pd.DataFrame, fields: dict[str, FieldSpec]) -> pd.DataFrame:
    """应用 FieldSpec 转换"""
    result = df.copy()
    
    for col_name, spec in fields.items():
        if col_name not in result.columns:
            continue
        
        if spec.source_unit != spec.canonical_unit:
            result[col_name] = result[col_name].apply(spec.convert)
    
    return result
```

### 4.3 日期类型转换

```python
def convert_dates(df: pd.DataFrame) -> pd.DataFrame:
    """将日期字符串转换为 DATE 类型"""
    result = df.copy()
    
    date_columns = [col for col in result.columns if "date" in col.lower()]
    
    for col in date_columns:
        if result[col].dtype == object:
            # YYYYMMDD 字符串 → DATE
            result[col] = pd.to_datetime(result[col], format="%Y%m%d", errors="coerce")
    
    return result
```

---

## 5. 月度压实

### 5.1 为什么需要压实

Raw 层按批次存储会产生大量小文件：
- 每日下载 3 个接口 × 每月 22 个交易日 = 66 个批次/月
- 三年 = 2376 个批次

DuckDB 查询大量小文件会变慢。

### 5.2 压实逻辑

```python
def compact_monthly(interface: str, year: int, month: int):
    """
    月度压实：将一个月的数据合并为一个文件。
    """
    latest_dir = Path(f"data/normalized/latest/{interface}")
    month_dir = latest_dir / f"trade_year={year}" / f"trade_month={month:02d}"
    
    if not month_dir.exists():
        return
    
    # 读取该月所有 Parquet 文件
    dfs = []
    for f in month_dir.glob("*.parquet"):
        dfs.append(pd.read_parquet(f))
    
    if not dfs:
        return
    
    merged = pd.concat(dfs, ignore_index=True)
    
    # 去重
    pk = get_primary_key(interface)
    merged = merged.drop_duplicates(subset=pk, keep="last")
    
    # 写入单个文件
    merged.to_parquet(month_dir / "data.parquet", index=False)
    
    # 删除旧文件
    for f in month_dir.glob("part-*.parquet"):
        f.unlink()
```

---

## 6. 主键定义

```python
PRIMARY_KEYS = {
    "daily": ["ts_code", "trade_date"],
    "adj_factor": ["ts_code", "trade_date"],
    "daily_basic": ["ts_code", "trade_date"],
    "income": ["ts_code", "ann_date", "end_date", "report_type"],
    "balancesheet": ["ts_code", "ann_date", "end_date", "report_type"],
    "cashflow": ["ts_code", "ann_date", "end_date", "report_type"],
    "fina_indicator": ["ts_code", "ann_date", "end_date", "report_type"],
    "forecast": ["ts_code", "ann_date", "end_date"],
    "express": ["ts_code", "ann_date", "end_date"],
    "dividend": ["ts_code", "ann_date", "end_date", "div_proc"],
    "index_weight": ["index_code", "con_code", "trade_date"],
    "trade_cal": ["exchange_id", "cal_date"],
    "stock_basic": ["ts_code"],
}

def get_primary_key(interface: str) -> list[str]:
    """获取接口的主键"""
    return PRIMARY_KEYS.get(interface, [])
```

---

## 7. 使用示例

```python
from app.data.normalize import DataNormalizer

# 标准化所有接口
normalizer = DataNormalizer()
normalizer.normalize_all()

# 月度压实
normalizer.compact_monthly("daily", 2026, 7)

# 查询 Latest View
df = pd.read_parquet("data/normalized/latest/daily/trade_year=2026/trade_month=07/data.parquet")
```
