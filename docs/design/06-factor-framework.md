# 06 - 因子框架技术方案

> 本文档定义因子计算框架的设计，包括因子注册、计算、标准化、行业中性化和 IC 分析。
> 依赖文档：01-data-pipeline-architecture.md、04-pit-layer.md

---

## 1. 设计目标

1. **注册机制**：装饰器注册，统一接口
2. **可组合**：基础因子组合成复合因子
3. **行业中性化**：按申万行业分组标准化
4. **IC 分析**：评估因子有效性
5. **可复现**：相同数据 + 相同参数 = 相同因子值

---

## 2. 因子分类

### 2.1 按数据来源分类

| 类别 | 数据来源 | 示例 |
|------|----------|------|
| 行情因子 | daily, daily_basic | 市值、换手率、波动率 |
| 财务因子 | fina_indicator, income | ROE、毛利率、营收增速 |
| 动量因子 | daily（历史行情） | 5日收益率、相对强弱 |
| 事件因子 | forecast, dividend | 业绩预告、分红 |

### 2.2 按计算方式分类

| 类别 | 计算方式 | 示例 |
|------|----------|------|
| 截面因子 | 同一时间点，跨股票计算 | 市值排名、PE 百分位 |
| 时序因子 | 同一股票，跨时间计算 | 动量、波动率、均线 |
| 混合因子 | 两者结合 | 行业中性化后的因子 |

---

## 3. 因子注册机制

### 3.1 注册器

```python
# app/factors/registry.py

from typing import Callable, Optional
from dataclasses import dataclass

@dataclass
class FactorMeta:
    """因子元数据"""
    name: str                    # 因子名称
    description: str             # 因子描述
    category: str                # 因子类别（market/financial/momentum/event）
    direction: int               # 方向（1=越大越好，-1=越小越好）
    compute_fn: Callable         # 计算函数
    dependencies: list[str]      # 依赖的其他因子
    params: dict                 # 默认参数

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
    
    def get(self, name: str) -> Optional[FactorMeta]:
        """获取因子元数据"""
        return self._factors.get(name)
    
    def list_factors(self) -> list[str]:
        """列出所有已注册的因子"""
        return list(self._factors.keys())
    
    def compute(self, name: str, **kwargs) -> pd.DataFrame:
        """计算单个因子"""
        meta = self._factors.get(name)
        if meta is None:
            raise ValueError(f"因子 {name} 未注册")
        
        # 合并默认参数
        params = {**meta.params, **kwargs}
        
        return meta.compute_fn(**params)
    
    def compute_batch(
        self,
        factor_names: list[str],
        **kwargs,
    ) -> pd.DataFrame:
        """
        批量计算多个因子。
        
        返回 DataFrame：
        - index: (ts_code, trade_date)
        - columns: 因子名称
        """
        results = []
        
        for name in factor_names:
            factor_df = self.compute(name, **kwargs)
            factor_df = factor_df.rename(columns={"factor_value": name})
            results.append(factor_df)
        
        # 合并所有因子
        if not results:
            return pd.DataFrame()
        
        merged = results[0]
        for df in results[1:]:
            merged = merged.merge(df, on=["ts_code", "trade_date"], how="outer")
        
        return merged

# 全局注册表
factor_registry = FactorRegistry()
```

### 3.2 使用示例

```python
from app.factors.registry import factor_registry

@factor_registry.register(
    name="pe_ttm",
    description="市盈率TTM",
    category="market",
    direction=-1,  # PE 越低越好
)
def compute_pe_ttm(
    date: str,
    pit: PITQuery,
    **kwargs,
) -> pd.DataFrame:
    """计算 PE TTM 因子"""
    cross_section = pit.get_cross_section(date, fields=["ts_code", "pe_ttm"])
    
    return pd.DataFrame({
        "ts_code": cross_section["ts_code"],
        "trade_date": date,
        "factor_value": cross_section["pe_ttm"],
    })
```

---

## 4. 基础因子实现

### 4.1 行情因子

```python
# app/factors/base_factors.py

@factor_registry.register(
    name="total_mv",
    description="总市值（万元）",
    category="market",
    direction=-1,  # 小市值效应
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
    name="circ_mv",
    description="流通市值（万元）",
    category="market",
    direction=-1,
)
def compute_circ_mv(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """流通市值因子"""
    df = pit.get_cross_section(date, fields=["ts_code", "circ_mv"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["circ_mv"],
    })


@factor_registry.register(
    name="pb",
    description="市净率",
    category="market",
    direction=-1,  # 低 PB 效应
)
def compute_pb(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """市净率因子"""
    df = pit.get_cross_section(date, fields=["ts_code", "pb"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["pb"],
    })


@factor_registry.register(
    name="turnover_rate",
    description="换手率",
    category="market",
    direction=-1,  # 低换手效应
)
def compute_turnover_rate(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """换手率因子"""
    df = pit.get_cross_section(date, fields=["ts_code", "turnover_rate"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["turnover_rate"],
    })


@factor_registry.register(
    name="dv_ttm",
    description="股息率TTM",
    category="market",
    direction=1,  # 高股息效应
)
def compute_dv_ttm(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """股息率因子"""
    df = pit.get_cross_section(date, fields=["ts_code", "dv_ttm"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["dv_ttm"],
    })
```

### 4.2 财务因子

```python
# app/factors/financial_factors.py

@factor_registry.register(
    name="roe",
    description="净资产收益率",
    category="financial",
    direction=1,  # ROE 越高越好
)
def compute_roe(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """ROE 因子（PIT）"""
    # 获取可交易股票池
    universe = pit.get_universe(date)
    
    # 批量获取 PIT 财务数据
    financial = pit.pit.get_financial_pit_batch(
        universe, date,
        fields=["ts_code", "roe"],
    )
    
    return pd.DataFrame({
        "ts_code": financial["ts_code"],
        "trade_date": date,
        "factor_value": financial["roe"],
    })


@factor_registry.register(
    name="grossprofit_margin",
    description="毛利率",
    category="financial",
    direction=1,
)
def compute_grossprofit_margin(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """毛利率因子（PIT）"""
    universe = pit.get_universe(date)
    financial = pit.pit.get_financial_pit_batch(
        universe, date,
        fields=["ts_code", "grossprofit_margin"],
    )
    
    return pd.DataFrame({
        "ts_code": financial["ts_code"],
        "trade_date": date,
        "factor_value": financial["grossprofit_margin"],
    })


@factor_registry.register(
    name="debt_to_assets",
    description="资产负债率",
    category="financial",
    direction=-1,  # 低杠杆更好
)
def compute_debt_to_assets(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """资产负债率因子（PIT）"""
    universe = pit.get_universe(date)
    financial = pit.pit.get_financial_pit_batch(
        universe, date,
        fields=["ts_code", "debt_to_assets"],
    )
    
    return pd.DataFrame({
        "ts_code": financial["ts_code"],
        "trade_date": date,
        "factor_value": financial["debt_to_assets"],
    })


@factor_registry.register(
    name="netprofit_yoy",
    description="归母净利润同比增速",
    category="financial",
    direction=1,  # 高增速更好
)
def compute_netprofit_yoy(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """净利润增速因子（PIT）"""
    universe = pit.get_universe(date)
    financial = pit.pit.get_financial_pit_batch(
        universe, date,
        fields=["ts_code", "netprofit_yoy"],
    )
    
    return pd.DataFrame({
        "ts_code": financial["ts_code"],
        "trade_date": date,
        "factor_value": financial["netprofit_yoy"],
    })


@factor_registry.register(
    name="op_yoy",
    description="营收同比增速",
    category="financial",
    direction=1,
)
def compute_op_yoy(date: str, pit: PITQuery, **kwargs) -> pd.DataFrame:
    """营收增速因子（PIT）"""
    universe = pit.get_universe(date)
    financial = pit.pit.get_financial_pit_batch(
        universe, date,
        fields=["ts_code", "op_yoy"],
    )
    
    return pd.DataFrame({
        "ts_code": financial["ts_code"],
        "trade_date": date,
        "factor_value": financial["op_yoy"],
    })
```

### 4.3 动量因子

```python
# app/factors/momentum_factors.py

@factor_registry.register(
    name="momentum_5d",
    description="5日动量（5日收益率）",
    category="momentum",
    direction=1,
    params={"window": 5},
)
def compute_momentum(
    date: str,
    pit: PITQuery,
    window: int = 5,
    **kwargs,
) -> pd.DataFrame:
    """
    N 日动量因子。
    
    计算方式：当日收盘价 / N日前收盘价 - 1
    """
    # 获取最近 N+1 个交易日的行情
    trading_days = pit.pit.db.query(f"""
        SELECT DISTINCT trade_date FROM daily
        WHERE trade_date <= '{date}'
        ORDER BY trade_date DESC
        LIMIT {window + 1}
    """)["trade_date"].tolist()
    
    if len(trading_days) < window + 1:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])
    
    start_date = trading_days[-1]
    end_date = trading_days[0]
    
    # 获取行情数据
    prices = pit.pit.db.query(f"""
        SELECT ts_code, trade_date, close
        FROM daily
        WHERE trade_date IN ('{start_date}', '{end_date}')
    """)
    
    # 计算收益率
    pivot = prices.pivot(index="ts_code", columns="trade_date", values="close")
    momentum = (pivot[end_date] / pivot[start_date]) - 1
    
    return pd.DataFrame({
        "ts_code": momentum.index,
        "trade_date": date,
        "factor_value": momentum.values,
    })


@factor_registry.register(
    name="volatility_20d",
    description="20日波动率",
    category="momentum",
    direction=-1,  # 低波动更好
    params={"window": 20},
)
def compute_volatility(
    date: str,
    pit: PITQuery,
    window: int = 20,
    **kwargs,
) -> pd.DataFrame:
    """
    N 日波动率因子。
    
    计算方式：最近 N 日日收益率的标准差
    """
    # 获取最近 N 个交易日的行情
    prices = pit.pit.db.query(f"""
        SELECT ts_code, trade_date, pct_chg
        FROM daily
        WHERE trade_date <= '{date}'
          AND trade_date > (
              SELECT MIN(trade_date) FROM (
                  SELECT trade_date FROM daily
                  WHERE trade_date <= '{date}'
                  ORDER BY trade_date DESC
                  LIMIT {window}
              )
          )
    """)
    
    # 计算波动率
    volatility = prices.groupby("ts_code")["pct_chg"].std()
    
    return pd.DataFrame({
        "ts_code": volatility.index,
        "trade_date": date,
        "factor_value": volatility.values,
    })
```

---

## 5. 因子标准化

### 5.1 标准化方法

```python
# app/factors/neutralize.py

class FactorNormalizer:
    """因子标准化器"""
    
    @staticmethod
    def zscore(factor_values: pd.Series) -> pd.Series:
        """
        Z-Score 标准化。
        
        公式：(x - mean) / std
        
        优点：保留异常值信息
        缺点：受极端值影响
        """
        mean = factor_values.mean()
        std = factor_values.std()
        if std == 0:
            return factor_values * 0
        return (factor_values - mean) / std
    
    @staticmethod
    def rank(factor_values: pd.Series) -> pd.Series:
        """
        排名标准化。
        
        将因子值转换为 0~1 的排名百分位。
        
        优点：不受极端值影响
        缺点：丢失因子值的绝对信息
        """
        return factor_values.rank(pct=True)
    
    @staticmethod
    def minmax(factor_values: pd.Series) -> pd.Series:
        """
        Min-Max 标准化。
        
        公式：(x - min) / (max - min)
        
        优点：结果在 0~1 之间
        缺点：受极端值影响大
        """
        min_val = factor_values.min()
        max_val = factor_values.max()
        if max_val == min_val:
            return factor_values * 0
        return (factor_values - min_val) / (max_val - min_val)
    
    @staticmethod
    def winsorize(factor_values: pd.Series, limits: tuple = (0.01, 0.99)) -> pd.Series:
        """
        缩尾处理。
        
        将极端值限制在指定百分位范围内。
        """
        lower = factor_values.quantile(limits[0])
        upper = factor_values.quantile(limits[1])
        return factor_values.clip(lower, upper)
```

### 5.2 行业中性化

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
        
        流程：
        1. 获取每只股票的申万行业分类
        2. 按行业分组
        3. 在每个行业内做标准化
        4. 合并结果
        
        这样做的好处：
        - 消除行业间的系统性差异
        - 因子值在不同行业间可比
        - 避免因子过度暴露于某个行业
        """
        # 1. 获取行业分类
        industry_map = self._get_industry_map(date)
        
        # 2. 合并行业信息
        df = factor_df.copy()
        df["industry"] = df["ts_code"].map(industry_map)
        
        # 3. 排除无行业分类的股票
        df = df.dropna(subset=["industry", "factor_value"])
        
        # 4. 按行业分组标准化
        normalizer = FactorNormalizer()
        
        if method == "zscore":
            df["factor_value"] = df.groupby("industry")["factor_value"].transform(
                normalizer.zscore
            )
        elif method == "rank":
            df["factor_value"] = df.groupby("industry")["factor_value"].transform(
                normalizer.rank
            )
        elif method == "minmax":
            df["factor_value"] = df.groupby("industry")["factor_value"].transform(
                normalizer.minmax
            )
        
        return df[["ts_code", "trade_date", "factor_value"]]
    
    def _get_industry_map(self, date: str) -> dict[str, str]:
        """获取股票-行业映射"""
        result = self.pit.pit.db.query("""
            SELECT stock_code as ts_code, index_code as industry
            FROM index_member_all
        """)
        return dict(zip(result["ts_code"], result["industry"]))
```

---

## 6. IC 分析

### 6.1 IC 计算

```python
# app/factors/ic_analysis.py

class ICAnalyzer:
    """因子 IC 分析器"""
    
    def __init__(self, pit: PITQuery):
        self.pit = pit
    
    def calculate_ic(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        forward_days: int = 20,
        method: str = "rank",  # "rank" = Rank IC, "normal" = Normal IC
    ) -> pd.DataFrame:
        """
        计算因子的 IC（Information Coefficient）。
        
        IC = corr(factor_value, forward_return)
        
        Args:
            factor_name: 因子名称
            start_date: 开始日期
            end_date: 结束日期
            forward_days: 前瞻收益天数
            method: "rank" 计算 Rank IC（Spearman），"normal" 计算 Pearson IC
        
        Returns:
            DataFrame with columns: [date, ic, rank_ic]
        """
        trading_days = self._get_trading_days(start_date, end_date)
        
        ic_series = []
        
        for i, date in enumerate(trading_days):
            # 跳过最后 forward_days 天（无法计算前瞻收益）
            if i >= len(trading_days) - forward_days:
                break
            
            # 1. 获取当日因子值
            factor_values = factor_registry.compute(factor_name, date=date, pit=self.pit)
            
            if len(factor_values) == 0:
                continue
            
            # 2. 获取前瞻收益
            future_date = trading_days[i + forward_days]
            forward_returns = self._get_forward_returns(
                factor_values["ts_code"].tolist(),
                date,
                future_date,
            )
            
            # 3. 合并
            merged = factor_values.merge(
                forward_returns, on="ts_code", how="inner"
            )
            
            if len(merged) < 30:  # 样本太少
                continue
            
            # 4. 计算 IC
            if method == "rank":
                ic = merged["factor_value"].corr(merged["forward_return"], method="spearman")
            else:
                ic = merged["factor_value"].corr(merged["forward_return"])
            
            ic_series.append({
                "date": date,
                "ic": ic,
                "sample_count": len(merged),
            })
        
        return pd.DataFrame(ic_series)
    
    def _get_forward_returns(
        self,
        ts_codes: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """计算前瞻收益"""
        codes_str = ", ".join(f"'{c}'" for c in ts_codes)
        
        result = self.pit.pit.db.query(f"""
            SELECT 
                a.ts_code,
                (b.close / a.close - 1) as forward_return
            FROM daily a
            JOIN daily b ON a.ts_code = b.ts_code
            WHERE a.ts_code IN ({codes_str})
              AND a.trade_date = '{start_date}'
              AND b.trade_date = '{end_date}'
        """)
        
        return result
    
    def calculate_ic_summary(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        forward_days: int = 20,
    ) -> dict:
        """
        计算因子 IC 的汇总统计。
        
        返回：
        - ic_mean: IC 均值
        - ic_std: IC 标准差
        - ic_ir: IC 信息比率（IC均值/IC标准差）
        - ic_positive_ratio: IC 为正的比例
        - ic_abs_gt_002: |IC| > 0.02 的比例
        """
        ic_df = self.calculate_ic(factor_name, start_date, end_date, forward_days)
        
        if len(ic_df) == 0:
            return {}
        
        ic_values = ic_df["ic"]
        
        return {
            "factor_name": factor_name,
            "ic_mean": ic_values.mean(),
            "ic_std": ic_values.std(),
            "ic_ir": ic_values.mean() / ic_values.std() if ic_values.std() > 0 else 0,
            "ic_positive_ratio": (ic_values > 0).mean(),
            "ic_abs_gt_002": (ic_values.abs() > 0.02).mean(),
            "ic_abs_gt_005": (ic_values.abs() > 0.05).mean(),
            "sample_count": len(ic_df),
        }
    
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
        
        将股票按因子值分为 N 组，计算每组的平均前瞻收益。
        
        用途：
        - 验证因子的单调性（因子值越高，收益越高/低）
        - 评估因子的经济意义
        """
        trading_days = self._get_trading_days(start_date, end_date)
        
        group_returns = []
        
        for i, date in enumerate(trading_days):
            if i >= len(trading_days) - forward_days:
                break
            
            # 获取因子值
            factor_values = factor_registry.compute(factor_name, date=date, pit=self.pit)
            
            if len(factor_values) < n_groups * 10:  # 每组至少 10 只
                continue
            
            # 获取前瞻收益
            future_date = trading_days[i + forward_days]
            forward_returns = self._get_forward_returns(
                factor_values["ts_code"].tolist(),
                date,
                future_date,
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

### 6.2 因子有效性判断标准

```python
FACTOR_QUALITY_THRESHOLDS = {
    "ic_mean_abs": 0.02,        # |IC均值| > 0.02
    "ic_ir_abs": 0.5,           # |ICIR| > 0.5
    "ic_positive_ratio": 0.55,  # IC为正的比例 > 55%
    "monotonicity": 0.8,        # 分组收益单调性 > 80%
}

def evaluate_factor(
    factor_name: str,
    ic_summary: dict,
    group_returns: pd.DataFrame,
) -> dict:
    """评估因子有效性"""
    
    # IC 指标
    ic_pass = (
        abs(ic_summary.get("ic_mean", 0)) >= FACTOR_QUALITY_THRESHOLDS["ic_mean_abs"]
        and abs(ic_summary.get("ic_ir", 0)) >= FACTOR_QUALITY_THRESHOLDS["ic_ir_abs"]
        and ic_summary.get("ic_positive_ratio", 0) >= FACTOR_QUALITY_THRESHOLDS["ic_positive_ratio"]
    )
    
    # 分组收益单调性
    if len(group_returns) > 0:
        avg_by_group = group_returns.groupby("group")["return"].mean()
        is_monotonic = (
            avg_by_group.is_monotonic_increasing
            or avg_by_group.is_monotonic_decreasing
        )
    else:
        is_monotonic = False
    
    return {
        "factor_name": factor_name,
        "ic_pass": ic_pass,
        "is_monotonic": is_monotonic,
        "overall_pass": ic_pass and is_monotonic,
        "ic_summary": ic_summary,
    }
```

---

## 7. 复合因子

### 7.1 因子组合

```python
def combine_factors(
    factor_names: list[str],
    weights: list[float],
    date: str,
    pit: PITQuery,
    neutralize: bool = True,
    standardize: str = "zscore",
) -> pd.DataFrame:
    """
    组合多个因子。
    
    Args:
        factor_names: 因子名称列表
        weights: 权重列表（与因子名称一一对应）
        date: 日期
        pit: PIT 查询
        neutralize: 是否行业中性化
        standardize: 标准化方法
    
    Returns:
        组合因子值
    """
    normalizer = FactorNormalizer()
    neutralizer = IndustryNeutralizer(pit)
    
    combined = None
    
    for name, weight in zip(factor_names, weights):
        # 计算因子
        factor_df = factor_registry.compute(name, date=date, pit=pit)
        
        # 标准化
        factor_df["factor_value"] = normalizer.winsorize(factor_df["factor_value"])
        
        if neutralize:
            factor_df = neutralizer.neutralize(factor_df, date, method=standardize)
        else:
            if standardize == "zscore":
                factor_df["factor_value"] = normalizer.zscore(factor_df["factor_value"])
            elif standardize == "rank":
                factor_df["factor_value"] = normalizer.rank(factor_df["factor_value"])
        
        # 加权
        factor_df["factor_value"] = factor_df["factor_value"] * weight
        
        # 合并
        if combined is None:
            combined = factor_df.rename(columns={"factor_value": name})
        else:
            combined = combined.merge(
                factor_df.rename(columns={"factor_value": name}),
                on=["ts_code", "trade_date"],
                how="outer",
            )
    
    # 求和
    factor_cols = [name for name in factor_names if name in combined.columns]
    combined["factor_value"] = combined[factor_cols].sum(axis=1)
    
    return combined[["ts_code", "trade_date", "factor_value"]]
```

### 7.2 预定义组合因子

```python
@factor_registry.register(
    name="small_cap_value",
    description="小市值+低PE组合",
    category="composite",
    direction=-1,
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
        neutralize=True,
        standardize="rank",
    )
```

---

## 8. 因子计算流程

```python
class FactorEngine:
    """因子计算引擎"""
    
    def __init__(self, pit: PITQuery):
        self.pit = pit
        self.registry = factor_registry
    
    def compute_factor_panel(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        """
        计算因子的面板数据。
        
        返回 DataFrame：
        - index: (ts_code, trade_date)
        - columns: factor_value
        
        用于批量回测和 IC 分析。
        """
        trading_days = self._get_trading_days(start_date, end_date)
        
        results = []
        for date in trading_days:
            factor_df = self.registry.compute(factor_name, date=date, pit=self.pit, **kwargs)
            results.append(factor_df)
        
        return pd.concat(results, ignore_index=True)
    
    def compute_multi_factor_panel(
        self,
        factor_names: list[str],
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        """
        计算多个因子的面板数据。
        
        返回 DataFrame：
        - index: (ts_code, trade_date)
        - columns: 各因子名称
        """
        trading_days = self._get_trading_days(start_date, end_date)
        
        results = []
        for date in trading_days:
            factor_df = self.registry.compute_batch(factor_names, date=date, pit=self.pit, **kwargs)
            results.append(factor_df)
        
        return pd.concat(results, ignore_index=True)
```

---

## 9. 使用示例

```python
from app.factors.registry import factor_registry
from app.factors.ic_analysis import ICAnalyzer
from app.factors.neutralize import IndustryNeutralizer

# 1. 计算单个因子
pe_factor = factor_registry.compute("pe_ttm", date="20260630", pit=pit_query)

# 2. IC 分析
analyzer = ICAnalyzer(pit_query)
ic_summary = analyzer.calculate_ic_summary("pe_ttm", "20230101", "20260630", forward_days=20)
print(f"IC均值: {ic_summary['ic_mean']:.4f}")
print(f"ICIR: {ic_summary['ic_ir']:.4f}")

# 3. 分组收益
group_returns = analyzer.calculate_group_returns("pe_ttm", "20230101", "20260630")
print(group_returns.groupby("group")["return"].mean())

# 4. 组合因子
combined = combine_factors(
    ["total_mv", "pe_ttm", "roe"],
    [0.4, 0.3, 0.3],
    "20260630",
    pit_query,
    neutralize=True,
)
```
