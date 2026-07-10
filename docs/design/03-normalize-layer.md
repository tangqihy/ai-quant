# 03 - Normalize 层技术方案

> 本文档定义数据标准化的 schema、转换规则、去重逻辑和 DuckDB 查询层。
> 依赖文档：01-data-pipeline-architecture.md、02-data-collector.md

---

## 1. 模块职责

Normalize 层负责：
1. 将 Raw 层的原始 Parquet 转换为统一格式
2. 日期类型统一
3. 股票代码格式统一
4. 财务金额单位统一
5. 空值语义明确
6. 按主键去重
7. 提供 DuckDB 查询视图

---

## 2. Schema 定义

### 2.1 日线行情 (daily)

```python
DAILY_SCHEMA = {
    "ts_code": {"type": "string", "description": "股票代码", "format": "600519.SH"},
    "trade_date": {"type": "string", "description": "交易日期", "format": "YYYYMMDD"},
    "open": {"type": "float64", "description": "开盘价", "unit": "元"},
    "high": {"type": "float64", "description": "最高价", "unit": "元"},
    "low": {"type": "float64", "description": "最低价", "unit": "元"},
    "close": {"type": "float64", "description": "收盘价", "unit": "元"},
    "pre_close": {"type": "float64", "description": "昨收价", "unit": "元"},
    "change": {"type": "float64", "description": "涨跌额", "unit": "元"},
    "pct_chg": {"type": "float64", "description": "涨跌幅", "unit": "%"},
    "vol": {"type": "float64", "description": "成交量", "unit": "手"},
    "amount": {"type": "float64", "description": "成交额", "unit": "千元"},
}
# 主键: (ts_code, trade_date)
# 分区: trade_date
```

### 2.2 复权因子 (adj_factor)

```python
ADJ_FACTOR_SCHEMA = {
    "ts_code": {"type": "string", "description": "股票代码"},
    "trade_date": {"type": "string", "description": "交易日期", "format": "YYYYMMDD"},
    "adj_factor": {"type": "float64", "description": "复权因子"},
}
# 主键: (ts_code, trade_date)
# 分区: trade_date
```

### 2.3 每日指标 (daily_basic)

```python
DAILY_BASIC_SCHEMA = {
    "ts_code": {"type": "string", "description": "股票代码"},
    "trade_date": {"type": "string", "description": "交易日期", "format": "YYYYMMDD"},
    "close": {"type": "float64", "description": "收盘价", "unit": "元"},
    "turnover_rate": {"type": "float64", "description": "换手率", "unit": "%"},
    "turnover_rate_f": {"type": "float64", "description": "换手率(自由流通股本)", "unit": "%"},
    "volume_ratio": {"type": "float64", "description": "量比"},
    "pe": {"type": "float64", "description": "市盈率(总)", "nullable": True},
    "pe_ttm": {"type": "float64", "description": "市盈率TTM", "nullable": True},
    "pb": {"type": "float64", "description": "市净率", "nullable": True},
    "ps": {"type": "float64", "description": "市销率", "nullable": True},
    "ps_ttm": {"type": "float64", "description": "市销率TTM", "nullable": True},
    "dv_ratio": {"type": "float64", "description": "股息率", "unit": "%", "nullable": True},
    "dv_ttm": {"type": "float64", "description": "股息率TTM", "unit": "%", "nullable": True},
    "total_share": {"type": "float64", "description": "总股本", "unit": "万股"},
    "float_share": {"type": "float64", "description": "流通股本", "unit": "万股"},
    "free_share": {"type": "float64", "description": "自由流通股本", "unit": "万股"},
    "total_mv": {"type": "float64", "description": "总市值", "unit": "万元"},
    "circ_mv": {"type": "float64", "description": "流通市值", "unit": "万元"},
}
# 主键: (ts_code, trade_date)
# 分区: trade_date
```

### 2.4 利润表 (income)

```python
INCOME_SCHEMA = {
    "ts_code": {"type": "string", "description": "股票代码"},
    "ann_date": {"type": "string", "description": "公告日期", "format": "YYYYMMDD"},
    "f_ann_date": {"type": "string", "description": "实际公告日期", "format": "YYYYMMDD"},
    "end_date": {"type": "string", "description": "报告期", "format": "YYYYMMDD"},
    "report_type": {"type": "int32", "description": "报告类型(1合并报表2母公司3合并更正)"},
    "basic_eps": {"type": "float64", "description": "基本每股收益", "unit": "元"},
    "diluted_eps": {"type": "float64", "description": "稀释每股收益", "unit": "元"},
    "total_revenue": {"type": "float64", "description": "营业总收入", "unit": "元"},
    "revenue": {"type": "float64", "description": "营业收入", "unit": "元"},
    "total_cogs": {"type": "float64", "description": "营业总成本", "unit": "元"},
    "oper_cost": {"type": "float64", "description": "营业成本", "unit": "元"},
    "operate_profit": {"type": "float64", "description": "营业利润", "unit": "元"},
    "n_income": {"type": "float64", "description": "净利润", "unit": "元"},
    "n_income_attr_p": {"type": "float64", "description": "归母净利润", "unit": "元"},
    # ... 更多字段
}
# 主键: (ts_code, ann_date, end_date, report_type)
# 分区: period (= end_date)
# ⚠️ report_type 不能省略：同一公司同一报告期可能有合并报表、母公司报表、更正报表
```

### 2.5 财务指标 (fina_indicator)

```python
FINA_INDICATOR_SCHEMA = {
    "ts_code": {"type": "string", "description": "股票代码"},
    "ann_date": {"type": "string", "description": "公告日期", "format": "YYYYMMDD"},
    "end_date": {"type": "string", "description": "报告期", "format": "YYYYMMDD"},
    "report_type": {"type": "int32", "description": "报告类型"},
    "eps": {"type": "float64", "description": "基本每股收益", "unit": "元"},
    "dt_eps": {"type": "float64", "description": "稀释每股收益", "unit": "元"},
    "total_revenue_ps": {"type": "float64", "description": "每股营业总收入", "unit": "元"},
    "revenue_ps": {"type": "float64", "description": "每股营业收入", "unit": "元"},
    "capital_rese_ps": {"type": "float64", "description": "每股资本公积", "unit": "元"},
    "surplus_rese_ps": {"type": "float64", "description": "每股盈余公积", "unit": "元"},
    "undist_profit_ps": {"type": "float64", "description": "每股未分配利润", "unit": "元"},
    "extra_item": {"type": "float64", "description": "非经常性损益", "unit": "元"},
    "profit_dedt": {"type": "float64", "description": "扣除非经常性损益后的净利润", "unit": "元"},
    "gross_margin": {"type": "float64", "description": "毛利", "unit": "元"},
    "current_ratio": {"type": "float64", "description": "流动比率"},
    "quick_ratio": {"type": "float64", "description": "速动比率"},
    "cash_ratio": {"type": "float64", "description": "现金比率"},
    "invturn_days": {"type": "float64", "description": "存货周转天数"},
    "arturn_days": {"type": "float64", "description": "应收账款周转天数"},
    "assets_turn": {"type": "float64", "description": "总资产周转率"},
    "op_income": {"type": "float64", "description": "经营活动净收益", "unit": "元"},
    "ebit": {"type": "float64", "description": "息税前利润", "unit": "元"},
    "ebitda": {"type": "float64", "description": "息税折旧摊销前利润", "unit": "元"},
    "fcff": {"type": "float64", "description": "企业自由现金流量", "unit": "元"},
    "fcfe": {"type": "float64", "description": "股权自由现金流量", "unit": "元"},
    "roe": {"type": "float64", "description": "净资产收益率", "unit": "%"},
    "roe_waa": {"type": "float64", "description": "加权平均净资产收益率", "unit": "%"},
    "roe_dt": {"type": "float64", "description": "净资产收益率(扣除非经常性损益)", "unit": "%"},
    "roa": {"type": "float64", "description": "总资产报酬率", "unit": "%"},
    "npta": {"type": "float64", "description": "总资产净利润", "unit": "%"},
    "roic": {"type": "float64", "description": "投入资本回报率", "unit": "%"},
    "roe_yearly": {"type": "float64", "description": "年化净资产收益率", "unit": "%"},
    "roa2_yearly": {"type": "float64", "description": "年化总资产报酬率", "unit": "%"},
    "debt_to_assets": {"type": "float64", "description": "资产负债率", "unit": "%"},
    "op_yoy": {"type": "float64", "description": "营收同比增速", "unit": "%"},
    "tr_yoy": {"type": "float64", "description": "营业总收入同比增速", "unit": "%"},
    "netprofit_yoy": {"type": "float64", "description": "归母净利润同比增速", "unit": "%"},
    "dt_netprofit_yoy": {"type": "float64", "description": "扣非净利润同比增速", "unit": "%"},
    "ocf_yoy": {"type": "float64", "description": "经营活动现金流同比增速", "unit": "%"},
    # ... 更多字段
}
# 主键: (ts_code, ann_date, end_date, report_type)
# 分区: period (= end_date)
```

### 2.6 指数成分权重 (index_weight)

```python
INDEX_WEIGHT_SCHEMA = {
    "index_code": {"type": "string", "description": "指数代码", "format": "000300.SH"},
    "con_code": {"type": "string", "description": "成分股代码", "format": "600519.SH"},
    "trade_date": {"type": "string", "description": "交易日期", "format": "YYYYMMDD"},
    "weight": {"type": "float64", "description": "权重", "unit": "%"},
}
# 主键: (index_code, con_code, trade_date)
# 分区: index_code
```

### 2.7 交易日历 (trade_cal)

```python
TRADE_CAL_SCHEMA = {
    "exchange_id": {"type": "string", "description": "交易所代码", "format": "SSE/SHFE等"},
    "cal_date": {"type": "string", "description": "日期", "format": "YYYYMMDD"},
    "is_open": {"type": "int32", "description": "是否交易日(1是0否)"},
    "pretrade_date": {"type": "string", "description": "上一交易日", "format": "YYYYMMDD", "nullable": True},
}
# 主键: (exchange_id, cal_date)
# 无分区，单文件全量
```

### 2.8 股票基础信息 (stock_basic)

```python
STOCK_BASIC_SCHEMA = {
    "ts_code": {"type": "string", "description": "股票代码"},
    "symbol": {"type": "string", "description": "股票代码(无交易所后缀)"},
    "name": {"type": "string", "description": "股票名称"},
    "area": {"type": "string", "description": "地域", "nullable": True},
    "industry": {"type": "string", "description": "行业", "nullable": True},
    "market": {"type": "string", "description": "市场(主板/创业板/科创板/北交所)"},
    "exchange": {"type": "string", "description": "交易所(SSE/SZSE/BSE)"},
    "list_date": {"type": "string", "description": "上市日期", "format": "YYYYMMDD", "nullable": True},
    "delist_date": {"type": "string", "description": "退市日期", "format": "YYYYMMDD", "nullable": True},
    "is_hs": {"type": "string", "description": "是否沪深港通(H/S/N)", "nullable": True},
    "list_status": {"type": "string", "description": "上市状态(L/D/P)"},
}
# 主键: (ts_code)
# 无分区，单文件全量
```

---

## 3. 转换规则

### 3.1 日期统一

```python
def normalize_date(value) -> str:
    """统一日期格式为 YYYYMMDD 字符串"""
    if value is None:
        return None
    
    # 已经是 YYYYMMDD 字符串
    if isinstance(value, str) and len(value) == 8 and value.isdigit():
        return value
    
    # Pandas Timestamp
    if hasattr(value, 'strftime'):
        return value.strftime('%Y%m%d')
    
    # 带横杠的日期字符串
    if isinstance(value, str) and '-' in value:
        return value.replace('-', '')
    
    raise ValueError(f"无法解析日期: {value}")
```

### 3.2 股票代码统一

```python
def normalize_ts_code(value: str) -> str:
    """
    统一股票代码为 ts_code 格式（600519.SH）
    
    输入可能有：
    - 600519.SH (标准格式，直接返回)
    - 600519 (需要补交易所后缀)
    - SH600519 (需要重排)
    """
    if '.' in value:
        return value.upper()
    
    # 纯数字，需要判断交易所
    if value.isdigit():
        code = value.zfill(6)
        if code.startswith(('6', '9')):
            return f"{code}.SH"
        elif code.startswith(('0', '2', '3')):
            return f"{code}.SZ"
        elif code.startswith(('4', '8')):
            return f"{code}.BJ"
    
    # SH600519 格式
    if value[:2] in ('SH', 'SZ', 'BJ'):
        return f"{value[2:]}.{value[:2]}"
    
    raise ValueError(f"无法解析股票代码: {value}")
```

### 3.3 财务金额单位统一

Tushare 财务数据的金额单位不统一（有的是元，有的是万元），需要确认后统一：

```python
# Tushare 财务报表金额单位确认
# income/balancesheet/cashflow: 元
# fina_indicator: 元（部分字段）或百分比
# daily_basic: 万元（total_mv, circ_mv）、万股（total_share等）

FINANCIAL_UNIT_MAP = {
    # 利润表/资产负债表/现金流量表：已经是元，不需要转换
    "income": {},
    "balancesheet": {},
    "cashflow": {},
    
    # 财务指标：已经是元/百分比，不需要转换
    "fina_indicator": {},
    
    # 每日指标：需要转换
    "daily_basic": {
        "total_share": 10000,      # 万股 → 股
        "float_share": 10000,      # 万股 → 股
        "free_share": 10000,       # 万股 → 股
        "total_mv": 10000,         # 万元 → 元
        "circ_mv": 10000,          # 万元 → 元
    },
}
```

**⚠️ 注意：** 单位转换是可选的。如果下游代码（因子计算、回测）习惯用 Tushare 原始单位，可以不转换，但在 schema 中明确标注单位。

### 3.4 空值处理

```python
NULL_POLICY = {
    # 缺失（无数据）→ NaN
    "missing": [
        "pe", "pe_ttm",  # 亏损股无 PE
        "pb",             # 净资产为负时无 PB
        "dv_ratio", "dv_ttm",  # 未分红时无股息率
        "delist_date",    # 未退市时为空
    ],
    
    # 真实零值 → 0
    "zero": [
        "change",         # 涨跌额为 0
        "pct_chg",        # 涨跌幅为 0
        "amount",         # 成交额为 0（停牌）
    ],
    
    # 必须有值 → 抛异常
    "required": [
        "ts_code",
        "trade_date",
        "close",
    ],
}
```

---

## 4. 去重逻辑

### 4.1 去重策略

```python
def dedup_by_primary_key(
    df: pd.DataFrame,
    primary_key: tuple[str, ...],
    keep: str = "last",  # 保留最后一条（最新下载的）
) -> pd.DataFrame:
    """
    按主键去重。
    
    对于同一主键的多条记录，保留最新的一条。
    "最新"的判断：
    - 如果有 download_time 字段，按 download_time 排序
    - 否则按原始行顺序（后下载的在后面）
    """
    if "download_time" in df.columns:
        df = df.sort_values(list(primary_key) + ["download_time"])
    
    return df.drop_duplicates(subset=list(primary_key), keep=keep)
```

### 4.2 财务数据去重特殊处理

财务数据的主键是 `(ts_code, ann_date, end_date, report_type)`，但同一家公司同一报告期可能有：
1. 业绩预告（forecast）
2. 业绩快报（express）
3. 正式报告（income/balancesheet/cashflow）
4. 更正报告（report_type=3）

这些是不同的数据，不应该互相覆盖。去重只在同一张表内进行。

---

## 5. Normalize 流程

```python
# app/data/normalize.py

class DataNormalizer:
    """数据标准化处理器"""
    
    def __init__(self, raw_dir: str = "data/raw", normalized_dir: str = "data/normalized"):
        self.raw_dir = Path(raw_dir)
        self.normalized_dir = Path(normalized_dir)
    
    def normalize_interface(self, interface: str, force: bool = False):
        """
        标准化单个接口的所有数据。
        
        流程：
        1. 扫描 raw 目录下该接口的所有 Parquet 文件
        2. 对每个文件：
           a. 读取
           b. 应用 schema 转换
           c. 去重
           d. 写入 normalized 目录
        """
        raw_path = self.raw_dir / interface
        norm_path = self.normalized_dir / interface
        
        config = INTERFACE_CONFIG[interface]
        schema = SCHEMA_MAP[interface]
        
        # 扫描所有分区
        for partition_dir in sorted(raw_path.iterdir()):
            if not partition_dir.is_dir():
                continue
            
            partition_name = partition_dir.name  # 如 "trade_date=20260709"
            
            # 检查是否已处理
            target_dir = norm_path / partition_name
            if target_dir.exists() and not force:
                continue
            
            # 读取该分区的所有 Parquet 文件
            dfs = []
            for parquet_file in partition_dir.glob("*.parquet"):
                df = pd.read_parquet(parquet_file)
                dfs.append(df)
            
            if not dfs:
                continue
            
            df = pd.concat(dfs, ignore_index=True)
            
            # 应用转换
            df = self._apply_schema(df, schema, interface)
            
            # 去重
            df = dedup_by_primary_key(df, config["primary_key"])
            
            # 写入
            target_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(target_dir / "part-0.parquet", index=False)
    
    def _apply_schema(self, df: pd.DataFrame, schema: dict, interface: str) -> pd.DataFrame:
        """应用 schema 转换"""
        result = df.copy()
        
        # 1. 日期列标准化
        date_columns = [col for col, meta in schema.items() if meta.get("type") == "string" and "format" in meta and "YYYYMMDD" in meta["format"]]
        for col in date_columns:
            if col in result.columns:
                result[col] = result[col].apply(normalize_date)
        
        # 2. 股票代码标准化
        code_columns = [col for col in ["ts_code", "con_code", "stock_code"] if col in result.columns]
        for col in code_columns:
            result[col] = result[col].apply(normalize_ts_code)
        
        # 3. 数值列类型转换
        numeric_columns = [col, meta for col, meta in schema.items() if meta.get("type") in ("float64", "int32")]
        for col, meta in numeric_columns:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce")
        
        # 4. 单位转换（如果需要）
        unit_map = FINANCIAL_UNIT_MAP.get(interface, {})
        for col, factor in unit_map.items():
            if col in result.columns:
                result[col] = result[col] * factor
        
        return result
    
    def normalize_all(self, force: bool = False):
        """标准化所有接口"""
        for interface in INTERFACE_CONFIG:
            self.normalize_interface(interface, force)
```

---

## 6. DuckDB 查询层

### 6.1 初始化

```python
# app/data/duckdb_client.py

import duckdb

class DuckDBClient:
    """DuckDB 查询客户端"""
    
    def __init__(self, normalized_dir: str = "data/normalized"):
        self.normalized_dir = Path(normalized_dir)
        self.conn = duckdb.connect(":memory:")  # 内存模式，不持久化
        
        # 注册 Parquet 文件的视图
        self._register_views()
    
    def _register_views(self):
        """为每个接口注册 DuckDB 视图"""
        for interface in INTERFACE_CONFIG:
            path = self.normalized_dir / interface
            if path.exists():
                # DuckDB 直接读取分区 Parquet
                self.conn.execute(f"""
                    CREATE OR REPLACE VIEW {interface} AS
                    SELECT * FROM read_parquet('{path}/**/*.parquet', hive_partitioning=true)
                """)
    
    def query(self, sql: str) -> pd.DataFrame:
        """执行 SQL 查询"""
        return self.conn.execute(sql).fetchdf()
    
    def get_latest_daily(self, ts_code: str, n: int = 60) -> pd.DataFrame:
        """获取最近 N 个交易日的日线数据"""
        return self.query(f"""
            SELECT * FROM daily
            WHERE ts_code = '{ts_code}'
            ORDER BY trade_date DESC
            LIMIT {n}
        """)
    
    def get_financial_pit(
        self,
        ts_code: str,
        as_of_date: str,
        report_type: int = 1,
    ) -> dict:
        """获取截至指定日期可用的最新财务数据（PIT）"""
        result = self.query(f"""
            SELECT * FROM fina_indicator
            WHERE ts_code = '{ts_code}'
              AND report_type = {report_type}
              AND ann_date <= '{as_of_date}'
            ORDER BY end_date DESC
            LIMIT 1
        """)
        return result.iloc[0].to_dict() if len(result) > 0 else None
    
    def get_index_members(
        self,
        index_code: str,
        as_of_date: str,
    ) -> list[str]:
        """获取截至指定日期的指数成分股（PIT）"""
        result = self.query(f"""
            SELECT DISTINCT con_code FROM index_weight
            WHERE index_code = '{index_code}'
              AND trade_date = (
                  SELECT MAX(trade_date) FROM index_weight
                  WHERE index_code = '{index_code}'
                    AND trade_date <= '{as_of_date}'
              )
        """)
        return result["con_code"].tolist()
```

### 6.2 常用查询模板

```python
# 获取某只股票的完整行情（已复权）
"""
SELECT 
    d.ts_code,
    d.trade_date,
    d.open * a.adj_factor / latest_adj.adj_factor AS open_adj,
    d.high * a.adj_factor / latest_adj.adj_factor AS high_adj,
    d.low * a.adj_factor / latest_adj.adj_factor AS low_adj,
    d.close * a.adj_factor / latest_adj.adj_factor AS close_adj,
    d.vol,
    d.amount
FROM daily d
JOIN adj_factor a ON d.ts_code = a.ts_code AND d.trade_date = a.trade_date
CROSS JOIN (
    SELECT adj_factor AS adj_factor 
    FROM adj_factor 
    WHERE ts_code = '{ts_code}' 
    ORDER BY trade_date DESC 
    LIMIT 1
) latest_adj
WHERE d.ts_code = '{ts_code}'
  AND d.trade_date BETWEEN '{start}' AND '{end}'
ORDER BY d.trade_date
"""

# 获取指定日期的所有 A 股行情 + 基本面（横截面）
"""
SELECT 
    d.ts_code,
    d.trade_date,
    d.close,
    d.pct_chg,
    d.vol,
    d.amount,
    b.pe_ttm,
    b.pb,
    b.total_mv,
    b.turnover_rate
FROM daily d
JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
WHERE d.trade_date = '{date}'
  AND d.close > 0
"""

# 获取指定日期的财务数据（PIT）
"""
SELECT 
    f.ts_code,
    f.end_date,
    f.roe,
    f.roa,
    f.grossprofit_margin,
    f.debt_to_assets,
    f.op_yoy,
    f.netprofit_yoy
FROM fina_indicator f
WHERE f.report_type = 1
  AND f.ann_date <= '{as_of_date}'
  AND f.end_date = (
      SELECT MAX(end_date) FROM fina_indicator
      WHERE ts_code = f.ts_code
        AND report_type = 1
        AND ann_date <= '{as_of_date}'
  )
"""
```

---

## 7. 数据质量校验

```python
# app/data/quality.py

class DataQualityChecker:
    """数据质量校验"""
    
    def check_interface(self, interface: str) -> dict:
        """校验单个接口的数据质量"""
        checks = {}
        
        # 1. 空值检查
        checks["null_check"] = self._check_nulls(interface)
        
        # 2. 主键唯一性
        checks["pk_unique"] = self._check_pk_unique(interface)
        
        # 3. 日期连续性（日线数据）
        if interface in ("daily", "adj_factor", "daily_basic"):
            checks["date_continuity"] = self._check_date_continuity(interface)
        
        # 4. 数值范围
        checks["value_range"] = self._check_value_range(interface)
        
        return checks
    
    def _check_nulls(self, interface: str) -> dict:
        """检查必填字段的空值"""
        schema = SCHEMA_MAP[interface]
        required_cols = [col for col, meta in schema.items() if col in NULL_POLICY["required"]]
        
        result = self.db.query(f"""
            SELECT 
                {', '.join(f'SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS {col}_nulls' for col in required_cols)}
            FROM {interface}
        """)
        
        return result.iloc[0].to_dict()
    
    def _check_pk_unique(self, interface: str) -> dict:
        """检查主键唯一性"""
        pk = INTERFACE_CONFIG[interface]["primary_key"]
        
        result = self.db.query(f"""
            SELECT COUNT(*) as total, COUNT(DISTINCT {','.join(pk)}) as unique_count
            FROM {interface}
        """)
        
        total = result.iloc[0]["total"]
        unique = result.iloc[0]["unique_count"]
        
        return {
            "total_rows": total,
            "unique_pk": unique,
            "duplicates": total - unique,
            "is_valid": total == unique,
        }
    
    def _check_date_continuity(self, interface: str) -> dict:
        """检查日期连续性（是否有缺失的交易日）"""
        # 获取交易日历
        trading_days = self.db.query("""
            SELECT cal_date FROM trade_cal 
            WHERE exchange_id = 'SSE' AND is_open = 1
            ORDER BY cal_date
        """)["cal_date"].tolist()
        
        # 获取该接口实际有的日期
        actual_dates = self.db.query(f"""
            SELECT DISTINCT trade_date FROM {interface}
            ORDER BY trade_date
        """)["trade_date"].tolist()
        
        # 找出缺失的日期
        missing = sorted(set(trading_days) - set(actual_dates))
        
        return {
            "expected_dates": len(trading_days),
            "actual_dates": len(actual_dates),
            "missing_dates": missing[:10],  # 最多显示 10 个
            "missing_count": len(missing),
        }
    
    def _check_value_range(self, interface: str) -> dict:
        """检查数值范围"""
        if interface == "daily":
            result = self.db.query("""
                SELECT 
                    MIN(close) as min_close,
                    MAX(close) as max_close,
                    MIN(pct_chg) as min_pct_chg,
                    MAX(pct_chg) as max_pct_chg,
                    COUNT(*) as total
                FROM daily
                WHERE close IS NOT NULL
            """)
            return result.iloc[0].to_dict()
        
        return {}
```

---

## 8. 使用示例

```python
from app.data.normalize import DataNormalizer
from app.data.duckdb_client import DuckDBClient
from app.data.quality import DataQualityChecker

# 1. 标准化数据
normalizer = DataNormalizer()
normalizer.normalize_all()

# 2. 查询
db = DuckDBClient()
df = db.get_latest_daily("600519.SH", n=60)
financial = db.get_financial_pit("600519.SH", "20260630")

# 3. 质量校验
checker = DataQualityChecker()
report = checker.check_interface("daily")
print(report)
```
