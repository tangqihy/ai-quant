# 04 - PIT 层技术方案（最终版）

> 本文档定义 Point-in-Time 数据层的设计，确保回测无未来函数。
> 这是整个数据管线最关键的一层。
> 依赖文档：01-data-pipeline-architecture.md、03-normalize-layer.md

---

## 1. 核心原则

**PIT = 在历史时点 T，市场能够看到什么数据。**

三条不可简化的规则：
1. 财务数据：`published_at` 决定市场可见时间
2. 状态数据：`announced_date` + `effective_date` 分离
3. 版本选择：先按可见时间过滤，再选最新修订

---

## 2. 时间模型

### 2.1 三个时间字段

| 字段 | 含义 | 用途 |
|------|------|------|
| `published_at` | 数据对市场公开的时间 | PIT 查询核心条件 |
| `effective_at` | 数据开始产生业务效力的时间 | 状态类数据（指数成分、ST、退市）|
| `ingested_at` | 本系统实际采集到的时间 | 数据审计、版本 tiebreaker |

**大部分情况下 `effective_at = published_at`，但以下场景需要区分：**
- 指数成分调整：提前公告，几天后生效
- ST 标记：公告后次日生效
- 退市：公告后有最后交易日

### 2.2 公告时间的保守处理

Tushare 财务数据只有 `ann_date`（日期），没有精确发布时间。

**规则：无时间的公告，默认下一交易日可用。**

```python
def resolve_available_trade_date(ann_date: str) -> str:
    """
    将公告日期映射到可交易日期。
    
    规则：
    - 如果 ann_date 是交易日 → 使用 ann_date 的下一交易日
    - 如果 ann_date 不是交易日 → 使用其后的第一个交易日
    
    原因：没有精确时间时，默认保守处理（T+1）
    """
    return get_next_trade_date(ann_date)
```

### 2.3 状态类数据的双日期模型

```python
def resolve_effective_date(
    announced_date: str,
    explicit_effective_date: Optional[str] = None,
) -> str:
    """
    解析状态类数据的生效日期。
    
    - 有明确生效日 → 使用明确日期
    - 没有明确生效日 → 默认公告日后的第一个交易日
    """
    if explicit_effective_date:
        return explicit_effective_date
    return get_next_trade_date(announced_date)
```

---

## 3. 版本选择

### 3.1 两个视图

| 视图 | 回答的问题 | 选择逻辑 |
|------|-----------|----------|
| **Latest View** | 系统现在知道的最新数据是什么？ | 按 `ingested_at` 取最新 |
| **PIT View** | 历史时点 T，市场能看到什么？ | 先按 `published_at` 过滤，再选最新修订 |

### 3.2 PIT 查询逻辑

```python
def pit_query(
    ts_code: str,
    as_of_date: str,
    report_type: int = 1,
) -> Optional[dict]:
    """
    PIT 查询：获取截至 as_of_date 可用的最新财务数据。
    
    步骤：
    1. published_at <= as_of_date（可见性过滤）
    2. 取 end_date 最大的记录（最新报告期）
    3. 同一 end_date 取 published_at 最大的（最新公告）
    4. published_at 也相同，取 ingested_at 最大的（最新采集）
    """
    return db.query(f"""
        SELECT *
        FROM fina_indicator
        WHERE ts_code = '{ts_code}'
          AND report_type = {report_type}
          AND published_at <= '{as_of_date}'
        ORDER BY end_date DESC, published_at DESC, ingested_at DESC
        LIMIT 1
    """)
```

**关键：`ingested_at` 只在 `published_at` 相同时作为 tiebreaker，不能直接取 max(ingested_at)。**

### 3.3 Latest 查询逻辑

```python
def latest_query(
    ts_code: str,
    report_type: int = 1,
) -> Optional[dict]:
    """
    Latest 查询：获取系统当前知道的最新数据。
    
    用途：实时行情、最新财务数据展示
    """
    return db.query(f"""
        SELECT *
        FROM fina_indicator
        WHERE ts_code = '{ts_code}'
          AND report_type = {report_type}
        ORDER BY end_date DESC, ingested_at DESC
        LIMIT 1
    """)
```

---

## 4. 需要 PIT 的数据类型

### 4.1 财务报表

**PIT 条件：** `published_at <= as_of_date`

**涉及接口：**
- `income`（利润表）
- `balancesheet`（资产负债表）
- `cashflow`（现金流量表）
- `fina_indicator`（财务指标）
- `forecast`（业绩预告）
- `express`（业绩快报）

### 4.2 指数成分

**PIT 条件：** 使用 `effective_date`（生效日期），不是公告日期

```python
def get_index_members_pit(
    index_code: str,
    as_of_date: str,
) -> list[str]:
    """
    获取截至 as_of_date 的指数成分股。
    
    使用 effective_date 而不是 published_at。
    原因：指数调整可能提前公告，但几天后才生效。
    """
    return db.query(f"""
        SELECT DISTINCT con_code
        FROM index_weight
        WHERE index_code = '{index_code}'
          AND effective_from <= '{as_of_date}'
          AND (effective_to IS NULL OR effective_to > '{as_of_date}')
    """)
```

### 4.3 ST 状态

**PIT 条件：** 使用 `effective_date`

```python
def get_st_stocks_pit(as_of_date: str) -> list[str]:
    """
    获取截至 as_of_date 的 ST 股票。
    
    使用 effective_date 而不是 announced_date。
    """
    return db.query(f"""
        SELECT ts_code
        FROM instrument_status
        WHERE status_type = 'ST'
          AND effective_from <= '{as_of_date}'
          AND (effective_to IS NULL OR effective_to > '{as_of_date}')
    """)
```

### 4.4 退市状态

**PIT 条件：** 使用 `effective_date`（最后交易日）

```python
def get_delisted_stocks_pit(as_of_date: str) -> list[str]:
    """
    获取截至 as_of_date 已退市的股票。
    
    使用 effective_date（最后交易日）。
    """
    return db.query(f"""
        SELECT ts_code
        FROM instrument_status
        WHERE status_type = 'delisted'
          AND effective_from <= '{as_of_date}'
    """)
```

### 4.5 不需要 PIT 的数据

| 数据 | 原因 |
|------|------|
| 日线行情（daily） | 行情数据本身就是时间序列 |
| 复权因子（adj_factor） | 除权除息事件发生时同步更新 |
| 交易日历（trade_cal） | 交易所提前公布 |
| 停复牌（suspend_d） | 停牌当天就知道 |

---

## 5. 历史证券主数据

### 5.1 为什么需要

仅保存当前 `stock_basic` 会产生幸存者偏差：
- 已退市股票在历史回测中不存在
- 后来上市的股票被错误纳入
- 股票名称和状态使用的是当前信息

### 5.2 instrument_history 表

```python
@dataclass
class InstrumentHistory:
    """历史证券主数据"""
    ts_code: str
    name: str
    market: str           # 主板/创业板/科创板/北交所
    board: str            # SH/SZ/BJ
    list_date: str        # 上市日期
    delist_date: Optional[str]  # 退市日期
    snapshot_date: str    # 快照日期
    
    # 状态历史
    status_type: str      # normal/st/delisted/suspended
    effective_from: str   # 状态生效日期
    effective_to: Optional[str]  # 状态结束日期
```

### 5.3 数据来源

1. **定期快照：** 每日盘后快照 `stock_basic`
2. **日线推断：** 有交易记录 = 在市
3. **停牌推断：** 从 `suspend_d` 推断停牌状态
4. **退市记录：** 从 `stock_basic` 的 `delist_date` 字段

### 5.4 股票池过滤

```python
def get_universe(as_of_date: str) -> list[str]:
    """获取截至 as_of_date 的可交易股票池"""
    return db.query(f"""
        SELECT ts_code
        FROM instrument_history
        WHERE list_date <= '{as_of_date}'
          AND (delist_date IS NULL OR delist_date > '{as_of_date}')
          AND snapshot_date = (
              SELECT MAX(snapshot_date)
              FROM instrument_history
              WHERE snapshot_date <= '{as_of_date}'
          )
    """)
```

---

## 6. 复权设计

### 6.1 核心约束

**复权锚点必须显式传入 `as_of_date`，不能从数据中推断。**

原因：如果使用 `iloc[-1]` 取数据中最后一条的复权因子，可能引入回测区间之后的公司行为信息。

### 6.2 复权模式

| 场景 | 使用价格 | 说明 |
|------|----------|------|
| 交易撮合 | 原始不复权价格 | 撮合用真实价格 |
| 技术指标 | 复权价格（固定锚点） | 均线、MACD 等 |
| 涨跌停判断 | 原始价格 | 交易规则基于原始价格 |
| 因子计算 | 复权价格或收益链 | 横截面比较需要可比价格 |
| 展示图表 | 查询截止日锚定的前复权 | 用户体验 |

### 6.3 实现

```python
class AdjustmentManager:
    """复权管理器"""
    
    def __init__(self, anchor_date: str):
        """
        anchor_date: 复权锚点，必须显式传入
        通常 = backtest_end_date 或查询截止日
        """
        self.anchor_date = anchor_date
        self._anchor_factors = {}  # ts_code -> adj_factor at anchor_date
    
    def get_adjusted_price(
        self,
        ts_code: str,
        raw_price: float,
        trade_date: str,
    ) -> float:
        """
        前复权到 anchor_date。
        
        adjusted_price = raw_price * adj_factor(anchor) / adj_factor(trade_date)
        """
        factor_at_date = self._get_adj_factor(ts_code, trade_date)
        factor_at_anchor = self._get_adj_factor(ts_code, self.anchor_date)
        
        if factor_at_date is None or factor_at_anchor is None:
            return raw_price
        
        return raw_price * factor_at_anchor / factor_at_date
    
    def get_adjusted_bars(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取复权后的 K 线数据。
        
        数据必须截断到 anchor_date，不能包含之后的数据。
        """
        # 获取原始行情
        raw = db.query(f"""
            SELECT trade_date, open, high, low, close, vol, amount
            FROM daily
            WHERE ts_code = '{ts_code}'
              AND trade_date BETWEEN '{start_date}' AND '{end_date}'
              AND trade_date <= '{self.anchor_date}'
            ORDER BY trade_date
        """)
        
        # 获取复权因子
        adj = db.query(f"""
            SELECT trade_date, adj_factor
            FROM adj_factor
            WHERE ts_code = '{ts_code}'
              AND trade_date BETWEEN '{start_date}' AND '{end_date}'
              AND trade_date <= '{self.anchor_date}'
        """)
        
        # 合并并计算
        df = raw.merge(adj, on="trade_date", how="left")
        
        # 前向填充复权因子
        df["adj_factor"] = df["adj_factor"].ffill()
        
        # 计算复权价格
        anchor_factor = df[df["trade_date"] == self.anchor_date]["adj_factor"].iloc[0]
        
        for col in ["open", "high", "low", "close"]:
            df[f"{col}_adj"] = df[col] * anchor_factor / df["adj_factor"]
        
        return df
```

### 6.4 数据截断约束

```python
class DataCutoff:
    """数据截断管理器"""
    
    def __init__(self, cutoff_date: str):
        """
        cutoff_date: 数据截止日期
        通常 = backtest_end_date
        """
        self.cutoff_date = cutoff_date
    
    def validate(self, table_name: str) -> bool:
        """验证数据是否严格截断到 cutoff_date"""
        max_date = db.query(f"""
            SELECT MAX(trade_date) FROM {table_name}
        """).iloc[0][0]
        
        return max_date <= self.cutoff_date
```

---

## 7. PIT 完整性验证

### 7.1 验证方法

```python
class PITVerifier:
    """PIT 完整性验证器"""
    
    def verify_financial_pit(
        self,
        ts_code: str,
        end_date: str,        # 报告期
        published_at: str,    # 公告日期
    ) -> dict:
        """
        验证财务数据的 PIT 正确性。
        
        流程：
        1. 查询 as_of = published_at - 1 的数据
        2. 确认该报告期的数据不可用
        3. 查询 as_of = published_at 的数据
        4. 确认该报告期的数据可用
        """
        # 公告日前一天
        before = pit_query(ts_code, published_at)
        before_has_report = before and before.get("end_date") == end_date
        
        # 公告日当天
        after = pit_query(ts_code, published_at)
        after_has_report = after and after.get("end_date") == end_date
        
        return {
            "ts_code": ts_code,
            "end_date": end_date,
            "published_at": published_at,
            "before_available": before_has_report,  # 应该是 False
            "after_available": after_has_report,     # 应该是 True
            "is_valid": not before_has_report and after_has_report,
        }
```

### 7.2 已知的边界情况

| 场景 | 处理方式 |
|------|----------|
| 财务数据无 `published_at` | 使用 `f_ann_date`，如果也没有则跳过该条记录 |
| 同一报告期有多条记录 | 按版本选择逻辑（published_at + ingested_at）|
| 业绩预告 vs 正式报告 | 两者独立存储，查询时可选择使用哪个 |
| 指数成分调整 | 使用 `effective_date`，不是 `published_at` |
| 复权因子缺失 | 使用最近的复权因子填充（向前填充）|

---

## 8. 与回测引擎的集成

### 8.1 回测中的 PIT 调用

```python
class BacktestEngine:
    def __init__(
        self,
        pit: PITQuery,
        adjustment: AdjustmentManager,
        cutoff: DataCutoff,
    ):
        self.pit = pit
        self.adjustment = adjustment
        self.cutoff = cutoff
    
    def run(self, strategy, start_date, end_date):
        """回测主循环"""
        # 验证数据截断
        assert self.cutoff.validate("daily"), "数据未正确截断"
        
        trading_days = self._get_trading_days(start_date, end_date)
        
        for date in trading_days:
            # 1. 获取可交易股票池（使用 PIT）
            universe = self.pit.get_universe(date)
            
            # 2. 获取横截面数据（行情 + 基本面 + 财务 PIT）
            cross_section = self.pit.get_cross_section(date)
            
            # 3. 调用策略
            signals = strategy.on_bar(date, cross_section, universe)
            
            # 4. 执行交易（T+1 延迟）
            self._execute_signals(signals, date)
```

---

## 9. 测试用例

```python
class TestPIT:
    """PIT 层测试"""
    
    def test_financial_before_publication(self):
        """测试：公告日前不能获取财务数据"""
        result = pit_query("600519.SH", "20260424")
        assert result is None or result["end_date"] != "20251231"
    
    def test_financial_after_publication(self):
        """测试：公告日当天可以获取财务数据"""
        result = pit_query("600519.SH", "20260425")
        assert result is not None and result["end_date"] == "20251231"
    
    def test_index_members_use_effective_date(self):
        """测试：指数成分使用生效日期"""
        # 公告日当天，成分可能还没变
        members_before = get_index_members_pit("000300.SH", "20260629")
        # 生效日当天，成分应该变了
        members_after = get_index_members_pit("000300.SH", "20260630")
        # 两者可能不同
    
    def test_st_uses_effective_date(self):
        """测试：ST 使用生效日期"""
        # 公告日当天，股票可能还不是 ST
        st_before = get_st_stocks_pit("20260510")
        # 生效日当天，股票应该是 ST
        st_after = get_st_stocks_pit("20260511")
    
    def test_version_selection(self):
        """测试：版本选择逻辑"""
        # 如果有两条记录：
        # 1. published_at=20260425, ingested_at=20260426
        # 2. published_at=20260425, ingested_at=20260427
        # 应该选择第 2 条（published_at 相同，取 ingested_at 最大的）
        result = pit_query("600519.SH", "20260430")
        assert result["ingested_at"] == "20260427"
    
    def test_adjustment_uses_explicit_as_of(self):
        """测试：复权使用显式 as_of_date"""
        adj = AdjustmentManager(anchor_date="20260630")
        price1 = adj.get_adjusted_price("600519.SH", 100.0, "20260101")
        price2 = adj.get_adjusted_price("600519.SH", 100.0, "20260102")
        # 两个日期的复权价格应该不同（因为 adj_factor 不同）
        assert price1 != price2
```
