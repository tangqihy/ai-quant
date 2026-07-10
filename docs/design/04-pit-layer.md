# 04 - PIT 层技术方案

> 本文档定义 Point-in-Time 数据层的设计，确保回测无未来函数。
> 这是整个数据管线最关键的一层。
> 依赖文档：01-data-pipeline-architecture.md、03-normalize-layer.md

---

## 1. 什么是未来函数

**未来函数（Look-Ahead Bias）** 是回测中最常见也最致命的错误：

```
错误示例：
2026年年报（报告期2025-12-31）在 2026-04-30 公布。
如果策略在 2026-01-15 就使用了这份年报数据，
相当于"提前知道了"公司的全年业绩，回测收益虚高。
```

**PIT（Point-in-Time）层的核心目标：**
在回测日期 T，只返回截至 T 日已经公开的数据。

---

## 2. PIT 核心公式

### 2.1 基础公式

```python
available_date = ann_date
```

- `ann_date`：公告日期（Tushare 财务数据中的字段）
- 在回测日期 T，只能使用 `ann_date <= T` 的数据

### 2.2 为什么不用 `actual_download_date`

理论上，`available_date = max(ann_date, actual_download_date)` 更精确：
- 如果我们在 2026-07-10 才下载 2026-04-30 公布的年报
- 那么在回测 2026-05-01 时，这份数据实际上是不可用的（因为我们当时还没下载）

**但在实践中，我们选择只用 `ann_date`，原因：**

1. **回测假设：** 回测时假设我们有能力在公告当天获取数据（这在实际交易中是可行的）
2. **简化实现：** 不需要维护"下载时间"这个额外维度
3. **可复现性：** 同一份数据，不同时间运行回测，结果一致
4. **行业惯例：** 大多数量化框架（Zipline、Qlib）都这么做

### 2.3 `f_ann_date` vs `ann_date`

Tushare 财务数据有两个公告日期字段：
- `ann_date`：公告日期
- `f_ann_date`：实际公告日期（可能比 `ann_date` 早）

**使用 `ann_date` 作为 `available_date`。** 原因：
- `ann_date` 是交易所正式公告日期
- `f_ann_date` 可能包含提前泄露的信息，使用它可能引入幸存者偏差

---

## 3. 需要 PIT 的数据类型

### 3.1 财务报表

**问题：** 同一报告期的财务数据可能在不同时间公告。

```
示例：贵州茅台（600519.SH）2025年年报
- 报告期：2025-12-31
- 公告日期：2026-04-25

回测日期 2026-03-01：不能使用这份年报
回测日期 2026-04-25：可以使用这份年报
```

**涉及接口：**
- `income`（利润表）
- `balancesheet`（资产负债表）
- `cashflow`（现金流量表）
- `fina_indicator`（财务指标）
- `forecast`（业绩预告）
- `express`（业绩快报）

### 3.2 指数成分

**问题：** 指数成分股会定期调整。

```
示例：沪深300成分股调整
- 2026-06-15 公布新成分股名单
- 2026-06-30 生效

回测日期 2026-06-20：应该使用新名单（因为已公布）
回测日期 2026-06-10：应该使用旧名单
```

**涉及接口：**
- `index_weight`（指数成分权重）

### 3.3 ST 状态

**问题：** ST 标记在公告后生效。

```
示例：某公司被 ST
- 2026-05-10 公告被 ST
- 2026-05-13 股票简称变更为 ST

回测日期 2026-05-11：应该标记为 ST
回测日期 2026-05-09：不应该标记为 ST
```

### 3.4 退市状态

**问题：** 退市在公告后生效。

```
示例：某公司退市
- 2026-03-01 公告退市
- 2026-03-15 最后交易日

回测日期 2026-03-05：应该知道即将退市
回测日期 2026-02-28：不应该知道退市信息
```

### 3.5 不需要 PIT 的数据

| 数据 | 原因 |
|------|------|
| 日线行情（daily） | 行情数据本身就是时间序列，不存在"提前知道"的问题 |
| 复权因子（adj_factor） | 复权因子是根据除权除息事件计算的，事件发生时同步更新 |
| 交易日历（trade_cal） | 交易所提前公布，不存在信息不对称 |
| 停复牌（suspend_d） | 停牌当天就知道，不需要 PIT |

---

## 4. PIT 实现

### 4.1 财务数据 PIT

```python
# app/data/pit.py

class PITDataManager:
    """Point-in-Time 数据管理器"""
    
    def __init__(self, db: DuckDBClient):
        self.db = db
    
    def get_financial_pit(
        self,
        ts_code: str,
        as_of_date: str,
        report_type: int = 1,
        fields: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """
        获取截至 as_of_date 可用的最新财务数据。
        
        核心逻辑：
        1. 查找所有 ann_date <= as_of_date 的财务记录
        2. 按 end_date 降序排列（取最新报告期）
        3. 如果同一 end_date 有多条（如更正报告），取 report_type=1
        4. 返回第一条
        
        Args:
            ts_code: 股票代码
            as_of_date: 回测日期（YYYYMMDD）
            report_type: 报告类型（1=合并报表，2=母公司，3=合并更正）
            fields: 指定返回字段，None 表示全部
        
        Returns:
            财务数据字典，如果没有可用数据返回 None
        """
        fields_str = "*" if not fields else ", ".join(fields)
        
        result = self.db.query(f"""
            SELECT {fields_str}
            FROM fina_indicator
            WHERE ts_code = '{ts_code}'
              AND report_type = {report_type}
              AND ann_date <= '{as_of_date}'
            ORDER BY end_date DESC
            LIMIT 1
        """)
        
        if len(result) == 0:
            return None
        
        return result.iloc[0].to_dict()
    
    def get_financial_pit_batch(
        self,
        ts_codes: list[str],
        as_of_date: str,
        report_type: int = 1,
        fields: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        批量获取多只股票的 PIT 财务数据。
        
        用于横截面因子计算（如全市场 ROE 排名）。
        """
        fields_str = "*" if not fields else ", ".join(fields)
        codes_str = ", ".join(f"'{c}'" for c in ts_codes)
        
        # 使用窗口函数获取每只股票的最新财务数据
        result = self.db.query(f"""
            WITH ranked AS (
                SELECT 
                    {fields_str},
                    ROW_NUMBER() OVER (
                        PARTITION BY ts_code 
                        ORDER BY end_date DESC
                    ) as rn
                FROM fina_indicator
                WHERE ts_code IN ({codes_str})
                  AND report_type = {report_type}
                  AND ann_date <= '{as_of_date}'
            )
            SELECT {fields_str}
            FROM ranked
            WHERE rn = 1
        """)
        
        return result
    
    def get_financial_history_pit(
        self,
        ts_code: str,
        as_of_date: str,
        n_periods: int = 4,
        report_type: int = 1,
        fields: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        获取截至 as_of_date 可用的最近 N 个报告期的财务数据。
        
        用于计算财务趋势（如连续 4 个季度 ROE > 15%）。
        """
        fields_str = "*" if not fields else ", ".join(fields)
        
        result = self.db.query(f"""
            SELECT DISTINCT ON (end_date) {fields_str}
            FROM fina_indicator
            WHERE ts_code = '{ts_code}'
              AND report_type = {report_type}
              AND ann_date <= '{as_of_date}'
            ORDER BY end_date DESC
            LIMIT {n_periods}
        """)
        
        return result
```

### 4.2 指数成分 PIT

```python
def get_index_members_pit(
    self,
    index_code: str,
    as_of_date: str,
) -> list[str]:
    """
    获取截至 as_of_date 的指数成分股。
    
    核心逻辑：
    1. 找到 as_of_date 之前最近的交易日
    2. 返回该交易日的成分股列表
    
    注意：指数成分权重通常是月度数据，
    如果 as_of_date 在月中，返回上个月底的成分。
    """
    result = self.db.query(f"""
        SELECT DISTINCT con_code
        FROM index_weight
        WHERE index_code = '{index_code}'
          AND trade_date = (
              SELECT MAX(trade_date)
              FROM index_weight
              WHERE index_code = '{index_code}'
                AND trade_date <= '{as_of_date}'
          )
    """)
    
    return result["con_code"].tolist()

def get_index_weight_pit(
    self,
    index_code: str,
    as_of_date: str,
) -> pd.DataFrame:
    """
    获取截至 as_of_date 的指数成分股权重。
    """
    return self.db.query(f"""
        SELECT con_code, weight
        FROM index_weight
        WHERE index_code = '{index_code}'
          AND trade_date = (
              SELECT MAX(trade_date)
              FROM index_weight
              WHERE index_code = '{index_code}'
                AND trade_date <= '{as_of_date}'
          )
    """)
```

### 4.3 ST 状态 PIT

```python
def get_st_stocks_pit(self, as_of_date: str) -> list[str]:
    """
    获取截至 as_of_date 的 ST 股票列表。
    
    实现方式：
    1. 从 stock_basic 获取 list_status != 'L' 的股票（已退市）
    2. 从 daily 数据中，名称包含 'ST' 或 '*ST' 的股票
    3. 按公告日期过滤
    
    ⚠️ 简化实现：直接用 stock_basic 的当前状态。
    如果需要精确的 PIT ST 状态，需要维护 ST 状态变更表。
    """
    # 简化实现：使用 stock_basic 当前状态
    result = self.db.query("""
        SELECT ts_code FROM stock_basic
        WHERE name LIKE '%ST%'
           OR name LIKE '%*ST%'
    """)
    
    return result["ts_code"].tolist()
```

### 4.4 退市状态 PIT

```python
def get_delisted_stocks_pit(self, as_of_date: str) -> list[str]:
    """
    获取截至 as_of_date 已退市的股票。
    
    使用 stock_basic 的 delist_date 字段。
    """
    result = self.db.query(f"""
        SELECT ts_code FROM stock_basic
        WHERE delist_date IS NOT NULL
          AND delist_date <= '{as_of_date}'
    """)
    
    return result["ts_code"].tolist()
```

---

## 5. 复权价格计算

### 5.1 复权原理

```
前复权：将历史价格调整到当前价格水平
  adjusted_price = raw_price * (adj_factor / latest_adj_factor)

后复权：将当前价格调整到历史价格水平
  adjusted_price = raw_price * (adj_factor / base_adj_factor)
```

### 5.2 实现

```python
def get_adjusted_price(
    self,
    ts_code: str,
    start_date: str,
    end_date: str,
    method: str = "qfq",  # qfq=前复权, hfq=后复权
) -> pd.DataFrame:
    """
    获取复权后的价格数据。
    
    不使用 Tushare 的 pro_bar 接口，而是：
    1. 读取原始不复权行情
    2. 读取复权因子
    3. 本地计算复权价格
    
    原因：pro_bar 的前复权会根据 end_date 动态变化，不可复现。
    """
    # 1. 获取原始行情
    raw = self.db.query(f"""
        SELECT ts_code, trade_date, open, high, low, close, vol, amount
        FROM daily
        WHERE ts_code = '{ts_code}'
          AND trade_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY trade_date
    """)
    
    # 2. 获取复权因子
    adj = self.db.query(f"""
        SELECT trade_date, adj_factor
        FROM adj_factor
        WHERE ts_code = '{ts_code}'
          AND trade_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY trade_date
    """)
    
    # 3. 合并
    df = raw.merge(adj, on=["ts_code", "trade_date"], how="left")
    
    # 4. 计算复权价格
    if method == "qfq":
        # 前复权：用最新的复权因子作为基准
        latest_adj = adj["adj_factor"].iloc[-1]
        for col in ["open", "high", "low", "close"]:
            df[f"{col}_adj"] = df[col] * df["adj_factor"] / latest_adj
    elif method == "hfq":
        # 后复权：用最早的复权因子作为基准
        base_adj = adj["adj_factor"].iloc[0]
        for col in ["open", "high", "low", "close"]:
            df[f"{col}_adj"] = df[col] * df["adj_factor"] / base_adj
    
    return df
```

### 5.3 复权因子的单调性

复权因子应该是单调递增的（随着除权除息事件，因子变大）。

```python
def verify_adj_factor_monotonic(self, ts_code: str) -> dict:
    """验证复权因子的单调性"""
    result = self.db.query(f"""
        SELECT trade_date, adj_factor
        FROM adj_factor
        WHERE ts_code = '{ts_code}'
        ORDER BY trade_date
    """)
    
    factors = result["adj_factor"].tolist()
    
    # 检查是否单调递增（允许相等，即没有除权除息的日子）
    is_monotonic = all(factors[i] <= factors[i+1] for i in range(len(factors)-1))
    
    # 找出异常点（复权因子下降）
    violations = []
    for i in range(len(factors)-1):
        if factors[i] > factors[i+1]:
            violations.append({
                "date": result.iloc[i]["trade_date"],
                "factor": factors[i],
                "next_date": result.iloc[i+1]["trade_date"],
                "next_factor": factors[i+1],
            })
    
    return {
        "ts_code": ts_code,
        "is_monotonic": is_monotonic,
        "total_points": len(factors),
        "violations": violations,
    }
```

---

## 6. PIT 查询的统一接口

### 6.1 PIT 查询封装

```python
class PITQuery:
    """PIT 查询的统一接口"""
    
    def __init__(self, pit: PITDataManager):
        self.pit = pit
    
    def get_universe(
        self,
        as_of_date: str,
        index_code: Optional[str] = None,
        exclude_st: bool = True,
        exclude_delisted: bool = True,
        exclude_suspended: bool = True,
    ) -> list[str]:
        """
        获取截至 as_of_date 的可交易股票池。
        
        Args:
            as_of_date: 回测日期
            index_code: 指数代码（如 '000300.SH'），None 表示全市场
            exclude_st: 是否排除 ST 股票
            exclude_delisted: 是否排除已退市股票
            exclude_suspended: 是否排除停牌股票
        
        Returns:
            可交易的股票代码列表
        """
        # 1. 获取基础股票池
        if index_code:
            universe = self.pit.get_index_members_pit(index_code, as_of_date)
        else:
            # 全市场：获取截至 as_of_date 已上市的股票
            result = self.pit.db.query(f"""
                SELECT ts_code FROM stock_basic
                WHERE list_status = 'L'
                  AND list_date <= '{as_of_date}'
            """)
            universe = result["ts_code"].tolist()
        
        # 2. 排除 ST
        if exclude_st:
            st_stocks = self.pit.get_st_stocks_pit(as_of_date)
            universe = [s for s in universe if s not in st_stocks]
        
        # 3. 排除已退市
        if exclude_delisted:
            delisted = self.pit.get_delisted_stocks_pit(as_of_date)
            universe = [s for s in universe if s not in delisted]
        
        # 4. 排除停牌
        if exclude_suspended:
            suspended = self.pit.get_suspended_stocks(as_of_date)
            universe = [s for s in universe if s not in suspended]
        
        return universe
    
    def get_cross_section(
        self,
        as_of_date: str,
        index_code: Optional[str] = None,
        fields: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        获取截至 as_of_date 的横截面数据。
        
        返回 DataFrame，每行一只股票，包含：
        - 行情数据（daily）
        - 基本面数据（daily_basic）
        - 财务数据（fina_indicator，PIT）
        """
        # 1. 获取可交易股票池
        universe = self.get_universe(as_of_date, index_code)
        codes_str = ", ".join(f"'{c}'" for c in universe)
        
        # 2. 获取行情 + 基本面
        market_data = self.pit.db.query(f"""
            SELECT 
                d.ts_code,
                d.close,
                d.pct_chg,
                d.vol,
                d.amount,
                b.pe_ttm,
                b.pb,
                b.ps_ttm,
                b.dv_ttm,
                b.total_mv,
                b.circ_mv,
                b.turnover_rate
            FROM daily d
            JOIN daily_basic b ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
            WHERE d.ts_code IN ({codes_str})
              AND d.trade_date = '{as_of_date}'
        """)
        
        # 3. 获取财务数据（PIT）
        financial_data = self.pit.get_financial_pit_batch(
            universe, as_of_date,
            fields=["ts_code", "roe", "roa", "grossprofit_margin", "debt_to_assets", "op_yoy", "netprofit_yoy"]
        )
        
        # 4. 合并
        result = market_data.merge(financial_data, on="ts_code", how="left")
        
        return result
```

---

## 7. PIT 完整性验证

### 7.1 验证方法

```python
class PITVerifier:
    """PIT 完整性验证器"""
    
    def verify_no_lookahead(
        self,
        ts_code: str,
        report_date: str,      # 报告期，如 20251231
        announcement_date: str, # 公告日期，如 20260425
        test_fields: list[str], # 要验证的字段
    ) -> dict:
        """
        验证在公告日期之前，财务数据不可用。
        
        流程：
        1. 查询 as_of_date = announcement_date - 1 的数据
        2. 确认该报告期的数据不可用
        3. 查询 as_of_date = announcement_date 的数据
        4. 确认该报告期的数据可用
        """
        pit = PITDataManager(self.db)
        
        # 公告日前一天
        before = pit.get_financial_pit(ts_code, announcement_date)
        before_has_report = before and before.get("end_date") == report_date
        
        # 公告日当天
        after = pit.get_financial_pit(ts_code, announcement_date)
        after_has_report = after and after.get("end_date") == report_date
        
        return {
            "ts_code": ts_code,
            "report_date": report_date,
            "announcement_date": announcement_date,
            "before_available": before_has_report,  # 应该是 False
            "after_available": after_has_report,     # 应该是 True
            "is_valid": not before_has_report and after_has_report,
        }
    
    def verify_batch(self, sample_size: int = 100) -> dict:
        """
        批量验证 PIT 的正确性。
        
        随机抽样一批财务数据，验证 PIT 逻辑。
        """
        # 获取一批有明确公告日期的财务数据
        samples = self.db.query(f"""
            SELECT ts_code, end_date, ann_date
            FROM fina_indicator
            WHERE report_type = 1
              AND ann_date IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {sample_size}
        """)
        
        results = []
        for _, row in samples.iterrows():
            result = self.verify_no_lookahead(
                ts_code=row["ts_code"],
                report_date=row["end_date"],
                announcement_date=row["ann_date"],
                test_fields=["roe", "netprofit_yoy"],
            )
            results.append(result)
        
        valid_count = sum(1 for r in results if r["is_valid"])
        
        return {
            "total": len(results),
            "valid": valid_count,
            "invalid": len(results) - valid_count,
            "valid_rate": valid_count / len(results) if results else 0,
            "failures": [r for r in results if not r["is_valid"]],
        }
```

### 7.2 已知的边界情况

| 场景 | 处理方式 |
|------|----------|
| 财务数据无 `ann_date` | 使用 `f_ann_date`，如果也没有则跳过该条记录 |
| 同一报告期有多条记录 | 取 `report_type=1`（合并报表），如果有更正报告则取最新的 |
| 业绩预告 vs 正式报告 | 两者独立存储，查询时可选择使用哪个 |
| 指数成分调整 | 使用 `trade_date` 作为可用日期（成分权重数据自带日期） |
| 复权因子缺失 | 使用最近的复权因子填充（向前填充） |

---

## 8. 与回测引擎的集成

### 8.1 回测中的 PIT 调用

```python
class BacktestEngine:
    def __init__(self, pit: PITQuery):
        self.pit = pit
    
    def run(self, strategy, start_date, end_date):
        """回测主循环"""
        trading_days = self._get_trading_days(start_date, end_date)
        
        for date in trading_days:
            # 1. 获取可交易股票池
            universe = self.pit.get_universe(date)
            
            # 2. 获取横截面数据（行情 + 基本面 + 财务）
            cross_section = self.pit.get_cross_section(date)
            
            # 3. 调用策略
            signals = strategy.on_bar(date, cross_section, universe)
            
            # 4. 执行交易（T+1 延迟）
            self._execute_signals(signals, date)
```

### 8.2 PIT 数据缓存

```python
class PITCache:
    """PIT 数据缓存，避免重复查询"""
    
    def __init__(self, pit: PITDataManager):
        self.pit = pit
        self._cache = {}  # key: (ts_code, as_of_date, data_type)
    
    def get_financial(self, ts_code: str, as_of_date: str) -> Optional[dict]:
        key = (ts_code, as_of_date, "financial")
        if key not in self._cache:
            self._cache[key] = self.pit.get_financial_pit(ts_code, as_of_date)
        return self._cache[key]
    
    def get_universe(self, as_of_date: str, index_code: Optional[str] = None) -> list[str]:
        key = (as_of_date, index_code, "universe")
        if key not in self._cache:
            self._cache[key] = self.pit.get_universe(as_of_date, index_code)
        return self._cache[key]
    
    def clear(self):
        self._cache.clear()
```

---

## 9. 测试用例

```python
# tests/test_pit.py

class TestPIT:
    """PIT 层测试"""
    
    def test_financial_before_announcement(self):
        """测试：公告日前不能获取财务数据"""
        # 假设 600519.SH 的 2025 年报在 2026-04-25 公布
        result = pit.get_financial_pit("600519.SH", "20260424")
        # 应该返回 2025-09-30 的三季报，而不是 2025-12-31 的年报
        assert result["end_date"] != "20251231"
    
    def test_financial_after_announcement(self):
        """测试：公告日当天可以获取财务数据"""
        result = pit.get_financial_pit("600519.SH", "20260425")
        # 应该返回 2025-12-31 的年报
        assert result["end_date"] == "20251231"
    
    def test_index_members_before_adjustment(self):
        """测试：成分调整前使用旧成分"""
        # 假设沪深300在 2026-06-30 调整成分
        members_before = pit.get_index_members_pit("000300.SH", "20260629")
        members_after = pit.get_index_members_pit("000300.SH", "20260630")
        # 两者可能不同
        # 具体断言需要根据实际数据
    
    def test_adj_factor_monotonic(self):
        """测试：复权因子单调性"""
        result = pit.verify_adj_factor_monotonic("600519.SH")
        assert result["is_monotonic"] is True
    
    def test_no_lookahead_batch(self):
        """测试：批量验证无未来函数"""
        result = pit_verifier.verify_batch(sample_size=100)
        assert result["valid_rate"] == 1.0  # 100% 通过
```
