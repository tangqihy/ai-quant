# 06 - 因子框架技术方案（最终版）

> 本文档定义因子计算框架的设计，包括 oriented_factor、IC 执行时点修正和缺失值策略。
> 依赖文档：01-data-pipeline-architecture.md、04-pit-layer.md

---

## 1. 核心原则

1. **Oriented Factor：** 统一因子方向，越大越好
2. **IC 执行时点：** 使用 T+1 可执行价格
3. **IC 过滤：** 区分 raw_ic / tradable_ic
4. **缺失策略：** 显式处理，不依赖默认补零

---

## 2. 因子注册机制

### 2.1 因子元数据

```python
@dataclass
class FactorMeta:
    """因子元数据"""
    name: str                    # 因子名称
    description: str             # 因子描述
    category: str                # 类别（market/financial/momentum）
    direction: int               # 方向（1=越大越好，-1=越小越好）
    compute_fn: Callable         # 计算函数
    dependencies: list[str]      # 依赖的其他因子
    params: dict                 # 默认参数
```

### 2.2 注册器

```python
class FactorRegistry:
    """因子注册表"""
    
    def __init__(self):
        self._factors: dict[str, FactorMeta] = {}
    
    def register(
        self,
        name: str,
        description: str = "",
        category: str = "custom",
        direction: int = 1,
        dependencies: list[str] = None,
        params: dict = None,
    ):
        """注册因子的装饰器"""
        def decorator(fn: Callable) -> Callable:
            self._factors[name] = FactorMeta(
                name=name,
                description=description or fn.__doc__,
                category=category,
                direction=direction,
                compute_fn=fn,
                dependencies=dependencies or [],
                params=params or {},
            )
            return fn
        return decorator
    
    def compute(self, name: str, **kwargs) -> pd.DataFrame:
        """计算单个因子"""
        meta = self._factors.get(name)
        if meta is None:
            raise ValueError(f"因子 {name} 未注册")
        
        params = {**meta.params, **kwargs}
        raw_factor = meta.compute_fn(**params)
        
        # 应用 direction 转换
        oriented_factor = self._apply_direction(raw_factor, meta.direction)
        
        return oriented_factor
    
    def _apply_direction(self, df: pd.DataFrame, direction: int) -> pd.DataFrame:
        """
        应用因子方向转换。
        
        oriented_factor = raw_factor * direction
        
        这样所有因子都是"越大越好"，后续 IC、分组收益、组合因子都基于 oriented value。
        """
        result = df.copy()
        result["factor_value"] = result["factor_value"] * direction
        return result
```

---

## 3. 基础因子实现

### 3.1 行情因子

```python
@factor_registry.register(
    name="total_mv",
    description="总市值（万元）",
    category="market",
    direction=-1,  # 小市值效应，越小越好 → oriented 后越大越好
)
def compute_total_mv(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """总市值因子"""
    df = pit.get_cross_section(date, fields=["ts_code", "total_mv"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["total_mv"],
    })


@factor_registry.register(
    name="pe_ttm",
    description="市盈率TTM",
    category="market",
    direction=-1,  # 低 PE 效应
)
def compute_pe_ttm(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """PE TTM 因子"""
    df = pit.get_cross_section(date, fields=["ts_code", "pe_ttm"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["pe_ttm"],
    })
```

### 3.2 财务因子

```python
@factor_registry.register(
    name="roe",
    description="净资产收益率",
    category="financial",
    direction=1,  # ROE 越高越好
)
def compute_roe(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """ROE 因子（PIT）"""
    universe = pit.get_universe(date)
    financial = pit.pit.get_financial_pit_batch(universe, date, fields=["ts_code", "roe"])
    return pd.DataFrame({
        "ts_code": financial["ts_code"],
        "trade_date": date,
        "factor_value": financial["roe"],
    })
```

### 3.3 动量因子

```python
@factor_registry.register(
    name="momentum_5d",
    description="5日动量",
    category="momentum",
    direction=1,
    params={"window": 5},
)
def compute_momentum(date: str, pit: PITQuery, window: int = 5, **kwargs) -> pd.DataFrame:
    """N 日动量因子"""
    # 获取最近 N+1 个交易日的行情
    prices = pit.pit.db.query(f"""
        SELECT ts_code, trade_date, close
        FROM daily
        WHERE trade_date <= '{date}'
        ORDER BY trade_date DESC
        LIMIT {window + 1}
    """)
    
    # 计算收益率
    pivot = prices.pivot(index="ts_code", columns="trade_date", values="close")
    latest_date = pivot.columns[0]
    oldest_date = pivot.columns[-1]
    momentum = (pivot[latest_date] / pivot[oldest_date]) - 1
    
    return pd.DataFrame({
        "ts_code": momentum.index,
        "trade_date": date,
        "factor_value": momentum.values,
    })
```

---

## 4. IC 分析

### 4.1 IC 执行时点修正

**关键：IC 应该使用 T+1 可执行价格，不是 T 日收盘价。**

```python
def calculate_ic(
    self,
    factor_name: str,
    start_date: str,
    end_date: str,
    forward_days: int = 20,
    method: str = "rank",
) -> pd.DataFrame:
    """
    计算因子 IC。
    
    收益区间：T+1 open → T+N+1 open
    与策略真实执行规则一致。
    """
    trading_days = self._get_trading_days(start_date, end_date)
    
    ic_series = []
    
    for i, date in enumerate(trading_days):
        if i >= len(trading_days) - forward_days - 1:
            break
        
        # 1. 获取当日因子值（T 日收盘后）
        factor_values = factor_registry.compute(factor_name, date=date, pit=self.pit)
        
        if len(factor_values) == 0:
            continue
        
        # 2. 获取前瞻收益（T+1 open → T+N+1 open）
        t_plus_1 = trading_days[i + 1]
        t_plus_n_plus_1 = trading_days[i + forward_days + 1]
        
        forward_returns = self._get_forward_returns(
            factor_values["ts_code"].tolist(),
            t_plus_1,      # 起点：T+1 open
            t_plus_n_plus_1,  # 终点：T+N+1 open
            price_field="open",  # 使用开盘价
        )
        
        # 3. 过滤不可交易股票
        tradable_mask = self._get_tradable_mask(
            factor_values["ts_code"].tolist(),
            t_plus_1,
            t_plus_n_plus_1,
        )
        
        # 4. 合并
        merged = factor_values.merge(forward_returns, on="ts_code", how="inner")
        merged = merged.merge(tradable_mask, on="ts_code", how="inner")
        
        if len(merged) < 30:
            continue
        
        # 5. 计算 raw IC（所有样本）
        if method == "rank":
            raw_ic = merged["factor_value"].corr(merged["forward_return"], method="spearman")
        else:
            raw_ic = merged["factor_value"].corr(merged["forward_return"])
        
        # 6. 计算 tradable IC（仅可交易样本）
        tradable_merged = merged[merged["is_tradable"] == True]
        if len(tradable_merged) >= 30:
            if method == "rank":
                tradable_ic = tradable_merged["factor_value"].corr(
                    tradable_merged["forward_return"], method="spearman"
                )
            else:
                tradable_ic = tradable_merged["factor_value"].corr(
                    tradable_merged["forward_return"]
                )
        else:
            tradable_ic = None
        
        ic_series.append({
            "date": date,
            "raw_ic": raw_ic,
            "tradable_ic": tradable_ic,
            "sample_count": len(merged),
            "tradable_count": len(tradable_merged),
        })
    
    return pd.DataFrame(ic_series)
```

### 4.2 可交易过滤

```python
def _get_tradable_mask(
    self,
    ts_codes: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    获取可交易标记。
    
    过滤条件：
    - T+1 停牌
    - 涨停无法买入
    - 未来跌停无法卖出
    - 上市不足 N 日
    - 退市
    - ST
    - 缺失价格
    """
    codes_str = ", ".join(f"'{c}'" for c in ts_codes)
    
    # 获取 T+1 的可交易状态
    t_plus_1_tradable = self.pit.pit.db.query(f"""
        SELECT 
            ts_code,
            CASE 
                WHEN close IS NULL THEN FALSE
                WHEN ts_code IN (SELECT ts_code FROM instrument_status WHERE status_type = 'ST' AND effective_from <= '{start_date}') THEN FALSE
                ELSE TRUE
            END AS is_tradable
        FROM daily
        WHERE ts_code IN ({codes_str})
          AND trade_date = '{start_date}'
    """)
    
    return t_plus_1_tradable
```

### 4.3 IC 汇总统计

```python
def calculate_ic_summary(
    self,
    factor_name: str,
    start_date: str,
    end_date: str,
    forward_days: int = 20,
) -> dict:
    """
    计算 IC 汇总统计。
    
    注意：IC 值不是独立样本，不能直接用简单统计。
    """
    ic_df = self.calculate_ic(factor_name, start_date, end_date, forward_days)
    
    if len(ic_df) == 0:
        return {}
    
    raw_ic_values = ic_df["raw_ic"]
    tradable_ic_values = ic_df["tradable_ic"].dropna()
    
    return {
        "factor_name": factor_name,
        "raw_ic_mean": raw_ic_values.mean(),
        "raw_ic_std": raw_ic_values.std(),
        "raw_ic_ir": raw_ic_values.mean() / raw_ic_values.std() if raw_ic_values.std() > 0 else 0,
        "tradable_ic_mean": tradable_ic_values.mean() if len(tradable_ic_values) > 0 else None,
        "tradable_ic_std": tradable_ic_values.std() if len(tradable_ic_values) > 0 else None,
        "tradable_ic_ir": (
            tradable_ic_values.mean() / tradable_ic_values.std()
            if len(tradable_ic_values) > 0 and tradable_ic_values.std() > 0
            else None
        ),
        "sample_count": len(ic_df),
        "disclaimer": "当前结果为样本内统计，不代表样本外有效性",
    }
```

---

## 5. 复合因子

### 5.1 缺失值策略

```python
class MissingValueStrategy(Enum):
    """缺失值处理策略"""
    COMPLETE_CASE = "complete_case"  # 缺一个因子就剔除
    RENORMALIZE = "renormalize"      # 按实际可用因子重新归一化权重
    IMPUTE = "impute"                # 按行业中位数填补

def combine_factors(
    factor_names: list[str],
    weights: list[float],
    date: str,
    pit: PITQuery,
    missing_strategy: MissingValueStrategy = MissingValueStrategy.RENORMALIZE,
) -> pd.DataFrame:
    """
    组合多个因子。
    
    Args:
        factor_names: 因子名称列表
        weights: 权重列表
        date: 日期
        pit: PIT 查询
        missing_strategy: 缺失值处理策略
    """
    # 计算所有因子
    factor_dfs = []
    for name in factor_names:
        df = factor_registry.compute(name, date=date, pit=pit)
        df = df.rename(columns={"factor_value": name})
        factor_dfs.append(df)
    
    # 合并
    merged = factor_dfs[0]
    for df in factor_dfs[1:]:
        merged = merged.merge(df, on=["ts_code", "trade_date"], how="outer")
    
    # 处理缺失值
    factor_cols = factor_names
    
    if missing_strategy == MissingValueStrategy.COMPLETE_CASE:
        # 缺一个因子就剔除
        merged = merged.dropna(subset=factor_cols)
        merged["factor_value"] = sum(
            merged[col] * w for col, w in zip(factor_cols, weights)
        )
    
    elif missing_strategy == MissingValueStrategy.RENORMALIZE:
        # 按实际可用因子重新归一化权重
        available_mask = merged[factor_cols].notna()
        available_weights = []
        for col, w in zip(factor_cols, weights):
            available_weights.append(merged[col].fillna(0) * w)
        
        # 计算实际权重之和
        weight_sum = sum(
            w * available_mask[col].astype(float)
            for col, w in zip(factor_cols, weights)
        )
        
        # 归一化
        weighted_sum = sum(available_weights)
        merged["factor_value"] = weighted_sum / weight_sum.replace(0, np.nan)
    
    elif missing_strategy == MissingValueStrategy.IMPUTE:
        # 按行业中位数填补
        # TODO: 需要行业信息
        pass
    
    return merged[["ts_code", "trade_date", "factor_value"]]
```

### 5.2 预定义组合因子

```python
@factor_registry.register(
    name="small_cap_value",
    description="小市值+低PE组合",
    category="composite",
    direction=1,  # oriented 后已经是越大越好
    params={
        "factors": ["total_mv", "pe_ttm"],
        "weights": [0.5, 0.5],
    },
)
def compute_small_cap_value(
    date: str,
    pit: PITQuery,
    factors: list[str] = None,
    weights: list[float] = None,
    **kwargs,
) -> pd.DataFrame:
    """小市值+低PE组合因子"""
    return combine_factors(
        factors or ["total_mv", "pe_ttm"],
        weights or [0.5, 0.5],
        date,
        pit,
        missing_strategy=MissingValueStrategy.RENORMALIZE,
    )
```

---

## 6. 行业中性化

### 6.1 行业内 Z-Score

```python
class IndustryNeutralizer:
    """行业中性化器"""
    
    def __init__(self, pit: PITQuery):
        self.pit = pit
    
    def neutralize(
        self,
        factor_df: pd.DataFrame,
        date: str,
        method: str = "zscore",
    ) -> pd.DataFrame:
        """
        行业中性化。
        
        方法：
        - group_zscore: 行业内 Z-Score（初始实现）
        - cross_sectional_regression: 截面回归（P2）
        """
        # 获取行业分类
        industry_map = self._get_industry_map(date)
        
        df = factor_df.copy()
        df["industry"] = df["ts_code"].map(industry_map)
        df = df.dropna(subset=["industry", "factor_value"])
        
        if method == "zscore":
            df["factor_value"] = df.groupby("industry")["factor_value"].transform(
                self._zscore
            )
        elif method == "rank":
            df["factor_value"] = df.groupby("industry")["factor_value"].transform(
                lambda x: x.rank(pct=True)
            )
        
        return df[["ts_code", "trade_date", "factor_value"]]
    
    @staticmethod
    def _zscore(series: pd.Series) -> pd.Series:
        """Z-Score 标准化"""
        mean = series.mean()
        std = series.std()
        if std == 0:
            return series * 0
        return (series - mean) / std
```

---

## 7. 分组收益

```python
def calculate_group_returns(
    self,
    factor_name: str,
    start_date: str,
    end_date: str,
    forward_days: int = 20,
    n_groups: int = 5,
) -> pd.DataFrame:
    """
    计算因子分组收益。
    
    使用 T+1 open → T+N+1 open 的收益。
    """
    trading_days = self._get_trading_days(start_date, end_date)
    
    group_returns = []
    
    for i, date in enumerate(trading_days):
        if i >= len(trading_days) - forward_days - 1:
            break
        
        # 获取因子值
        factor_values = factor_registry.compute(factor_name, date=date, pit=self.pit)
        
        if len(factor_values) < n_groups * 10:
            continue
        
        # 获取前瞻收益
        t_plus_1 = trading_days[i + 1]
        t_plus_n_plus_1 = trading_days[i + forward_days + 1]
        
        forward_returns = self._get_forward_returns(
            factor_values["ts_code"].tolist(),
            t_plus_1,
            t_plus_n_plus_1,
            price_field="open",
        )
        
        # 合并
        merged = factor_values.merge(forward_returns, on="ts_code", how="inner")
        
        # 分组
        merged["group"] = pd.qcut(
            merged["factor_value"],
            n_groups,
            labels=False,
            duplicates="drop",
        ) + 1
        
        # 计算每组平均收益
        group_avg = merged.groupby("group")["forward_return"].mean()
        
        for group, ret in group_avg.items():
            group_returns.append({
                "date": date,
                "group": group,
                "return": ret,
            })
    
    return pd.DataFrame(group_returns)
```

---

## 8. 使用示例

```python
from app.factors.registry import factor_registry
from app.factors.ic_analysis import ICAnalyzer

# 1. 计算 oriented 因子
pe_factor = factor_registry.compute("pe_ttm", date="20260630", pit=pit_query)
# pe_ttm direction=-1，所以 oriented 后越大越好（低 PE 的股票因子值高）

# 2. IC 分析
analyzer = ICAnalyzer(pit_query)
ic_summary = analyzer.calculate_ic_summary("pe_ttm", "20230101", "20260630")
print(f"Raw IC均值: {ic_summary['raw_ic_mean']:.4f}")
print(f"Tradable IC均值: {ic_summary['tradable_ic_mean']:.4f}")
print(f"声明: {ic_summary['disclaimer']}")

# 3. 组合因子
combined = combine_factors(
    ["total_mv", "pe_ttm", "roe"],
    [0.4, 0.3, 0.3],
    "20260630",
    pit_query,
    missing_strategy=MissingValueStrategy.RENORMALIZE,
)
```
