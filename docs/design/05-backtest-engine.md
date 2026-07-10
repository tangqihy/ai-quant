# 05 - 回测引擎技术方案

> 本文档定义向量化日频回测引擎的设计，包括 A 股交易规则模拟、信号生成、撮合逻辑和指标计算。
> 依赖文档：01-data-pipeline-architecture.md、04-pit-layer.md

---

## 1. 设计目标

1. **向量化计算**：不逐行循环，用 Pandas/NumPy 批量处理
2. **真实 A 股规则**：涨跌停、停牌、T+1、100股、费用
3. **信号延迟**：T 日收盘信号 → T+1 日成交
4. **成交量约束**：限制为当日成交额的百分比
5. **可复现性**：相同数据 + 相同参数 = 相同结果

---

## 2. A 股交易规则清单

### 2.1 涨跌停规则

| 市场 | 涨跌幅限制 | 说明 |
|------|-----------|------|
| 主板 | ±10% | 沪深主板 |
| 创业板 | ±20% | 2020-08-24 起 |
| 科创板 | ±20% | 2019-07-22 起 |
| 北交所 | ±30% | 2021-11-15 起 |
| ST 股票 | ±5% → ±10% | 2026-07-06 起改为 ±10% |
| 新股上市首日 | 不限（注册制）/ ±44%（核准制） | 需要特殊处理 |

**交易限制：**
- 一字涨停（开盘即涨停，全天未开板）：**不能买入**
- 一字跌停（开盘即跌停，全天未开板）：**不能卖出**
- 非一字涨停（盘中触及涨停但有开板）：可以买入，但成交概率低
- 非一字跌停：可以卖出，但成交概率低

### 2.2 停牌规则

- 停牌股票不能交易（买入或卖出）
- 停牌期间持仓不变，市值按停牌前价格计算
- 复牌后按正常规则交易

### 2.3 T+1 规则

- 今天买入的股票，今天不能卖出
- 今天卖出股票的资金，今天可以用于买入（资金 T+0 可用）
- 需要跟踪每笔持仓的买入日期

### 2.4 交易单位

- 最小交易单位：100 股（1 手）
- 买入数量必须是 100 的整数倍
- 卖出可以不是 100 的整数倍（如持有 150 股，可以卖出 150 股）
- 科创板最小交易单位：200 股（但超过 200 股后可以按 1 股递增）

### 2.5 费用模型

| 费用类型 | 费率 | 最低收费 | 说明 |
|----------|------|----------|------|
| 佣金 | 万 2.5 (0.025%) | 5 元 | 买卖双向收取 |
| 印花税 | 千 1 (0.1%) | 无 | 仅卖出时收取 |
| 过户费 | 十万分之一 (0.001%) | 无 | 买卖双向收取 |

```python
def calculate_commission(
    amount: float,
    direction: str,  # "buy" or "sell"
    commission_rate: float = 0.00025,
    commission_min: float = 5.0,
    stamp_tax_rate: float = 0.001,
    transfer_fee_rate: float = 0.00001,
) -> dict:
    """计算交易费用"""
    # 佣金
    commission = max(amount * commission_rate, commission_min)
    
    # 印花税（仅卖出）
    stamp_tax = amount * stamp_tax_rate if direction == "sell" else 0
    
    # 过户费
    transfer_fee = amount * transfer_fee_rate
    
    total = commission + stamp_tax + transfer_fee
    
    return {
        "commission": commission,
        "stamp_tax": stamp_tax,
        "transfer_fee": transfer_fee,
        "total": total,
    }
```

### 2.6 成交量约束

- 单笔订单的成交量不能超过当日成交量的一定比例（如 2%）
- 这是为了模拟大资金的冲击成本
- 小市值策略必须加这个约束，否则回测收益虚高

---

## 3. 信号生成

### 3.1 信号定义

```python
@dataclass
class Signal:
    """交易信号"""
    ts_code: str           # 股票代码
    signal_date: str       # 信号产生日期（T 日收盘后）
    direction: str         # "buy" or "sell"
    weight: float          # 目标权重（0~1），用于仓位分配
    reason: str            # 信号原因（用于分析）
    
    # 以下字段由引擎填写
    execute_date: str = "" # 执行日期（T+1）
    price: float = 0       # 成交价格
    quantity: int = 0      # 成交数量
    amount: float = 0      # 成交金额
    commission: float = 0  # 手续费
```

### 3.2 信号生成流程

```python
class Strategy(ABC):
    """策略基类"""
    
    @abstractmethod
    def generate_signals(
        self,
        date: str,
        cross_section: pd.DataFrame,  # 横截面数据
        universe: list[str],           # 可交易股票池
        positions: dict,               # 当前持仓
    ) -> list[Signal]:
        """
        生成交易信号。
        
        调用时机：T 日收盘后
        返回值：T+1 日要执行的信号列表
        
        Args:
            date: 当前日期（T 日）
            cross_section: 横截面数据，每行一只股票
            universe: 可交易股票池
            positions: 当前持仓 {ts_code: Position}
        
        Returns:
            信号列表
        """
        pass
```

### 3.3 信号延迟实现

```python
def generate_signals_on_date(self, date: str, ...) -> list[Signal]:
    """T 日收盘后生成信号"""
    signals = self.strategy.generate_signals(date, ...)
    
    # 设置执行日期为 T+1
    next_trading_day = self.calendar.get_next_trading_day(date)
    for signal in signals:
        signal.execute_date = next_trading_day
    
    return signals

def execute_signals_on_date(self, date: str, signals: list[Signal]):
    """T+1 日执行信号"""
    for signal in signals:
        if signal.execute_date != date:
            continue  # 不是今天要执行的信号
        
        self._execute_single_signal(signal, date)
```

---

## 4. 撮合逻辑

### 4.1 撮合流程

```python
def _execute_single_signal(self, signal: Signal, date: str):
    """执行单个信号"""
    
    # 1. 检查股票是否可交易
    if not self._is_tradable(signal.ts_code, date):
        signal.reject("停牌")
        return
    
    # 2. 获取当日行情
    bar = self._get_bar(signal.ts_code, date)
    if bar is None:
        signal.reject("无行情数据")
        return
    
    # 3. 检查涨跌停
    if signal.direction == "buy":
        if self._is_limit_up(signal.ts_code, date):
            signal.reject("一字涨停，不能买入")
            return
        # 非一字涨停：可以挂单，但成交概率低
        if self._is_touch_limit_up(signal.ts_code, date):
            signal.reject("触及涨停，成交概率低")
            return
    
    elif signal.direction == "sell":
        if self._is_limit_down(signal.ts_code, date):
            signal.reject("一字跌停，不能卖出")
            return
    
    # 4. 计算成交价格
    price = self._determine_price(signal, bar)
    
    # 5. 计算成交数量
    quantity = self._determine_quantity(signal, price, bar)
    
    # 6. 检查 T+1
    if signal.direction == "sell":
        if not self._can_sell(signal.ts_code, date):
            signal.reject("T+1 限制，今日买入的股票不能卖出")
            return
    
    # 7. 计算费用
    amount = price * quantity
    fees = calculate_commission(amount, signal.direction)
    
    # 8. 执行成交
    if signal.direction == "buy":
        self.account.freeze(amount + fees["total"])
        self.portfolio.buy(signal.ts_code, price, quantity, date)
    else:
        self.portfolio.sell(signal.ts_code, quantity)
        self.account.deposit(amount - fees["total"])
    
    # 9. 记录
    signal.price = price
    signal.quantity = quantity
    signal.amount = amount
    signal.commission = fees["total"]
```

### 4.2 成交价格确定

```python
def _determine_price(self, signal: Signal, bar: dict) -> float:
    """
    确定成交价格。
    
    规则：
    - 买入：使用开盘价（假设以开盘价成交）
    - 卖出：使用开盘价
    - 加滑点
    """
    base_price = bar["open"]
    
    if signal.direction == "buy":
        # 买入加滑点
        price = base_price * (1 + self.slippage_rate)
    else:
        # 卖出减滑点
        price = base_price * (1 - self.slippage_rate)
    
    # 确保价格在涨跌停范围内
    price = max(price, bar["low_limit"])  # 跌停价
    price = min(price, bar["high_limit"])  # 涨停价
    
    return round(price, 2)
```

### 4.3 成交数量确定

```python
def _determine_quantity(self, signal: Signal, price: float, bar: dict) -> int:
    """
    确定成交数量。
    
    考虑因素：
    1. 目标权重
    2. 可用资金
    3. 最小交易单位（100 股）
    4. 成交量约束
    """
    if signal.direction == "buy":
        # 1. 按目标权重计算目标金额
        target_amount = self.account.total_value * signal.weight
        
        # 2. 可用资金限制
        available_amount = min(target_amount, self.account.available_cash)
        
        # 3. 成交量约束
        volume_limit = bar["vol"] * 100 * self.volume_limit_pct  # vol 单位是手
        volume_limit_amount = volume_limit * price
        
        # 4. 取较小值
        actual_amount = min(available_amount, volume_limit_amount)
        
        # 5. 计算数量（向下取整到 100 股）
        quantity = int(actual_amount / price / 100) * 100
        
        # 6. 确保至少 100 股
        if quantity < 100:
            quantity = 0
        
        return quantity
    
    else:  # sell
        # 卖出：按目标权重计算
        position = self.portfolio.get_position(signal.ts_code)
        if position is None:
            return 0
        
        # 目标卖出数量
        target_quantity = int(position.quantity * signal.weight / 100) * 100
        
        # 可卖数量限制（T+1）
        available_quantity = position.available_quantity
        
        # 取较小值
        quantity = min(target_quantity, available_quantity)
        
        return quantity
```

---

## 5. 向量化实现

### 5.1 核心思想

不逐日逐股票循环，而是：
1. 预计算所有日期的信号
2. 按日期批量执行
3. 用 Pandas 向量化操作

### 5.2 信号矩阵

```python
def build_signal_matrix(
    self,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    构建信号矩阵。
    
    返回 DataFrame：
    - index: trade_date
    - columns: ts_code
    - values: weight (0=不操作, >0=买入权重, <0=卖出权重)
    """
    trading_days = self._get_trading_days(start_date, end_date)
    
    signals = []
    for date in trading_days:
        # 获取横截面数据
        cross_section = self.pit.get_cross_section(date)
        universe = self.pit.get_universe(date)
        
        # 调用策略
        day_signals = self.strategy.generate_signals(
            date, cross_section, universe, self.portfolio.positions
        )
        
        for signal in day_signals:
            signals.append({
                "signal_date": date,
                "execute_date": self.calendar.get_next_trading_day(date),
                "ts_code": signal.ts_code,
                "direction": signal.direction,
                "weight": signal.weight,
            })
    
    return pd.DataFrame(signals)
```

### 5.3 向量化撮合

```python
def execute_signals_vectorized(
    self,
    signals: pd.DataFrame,
    date: str,
    market_data: pd.DataFrame,
):
    """
    向量化执行当日信号。
    
    Args:
        signals: 当日要执行的信号
        date: 当前日期
        market_data: 当日行情数据
    """
    # 合并信号和行情
    merged = signals.merge(market_data, on="ts_code", how="left")
    
    # 买入信号
    buy_signals = merged[merged["direction"] == "buy"].copy()
    if len(buy_signals) > 0:
        # 计算买入价格（开盘价 + 滑点）
        buy_signals["price"] = buy_signals["open"] * (1 + self.slippage_rate)
        
        # 计算买入数量
        buy_signals["target_amount"] = self.account.total_value * buy_signals["weight"]
        buy_signals["quantity"] = (
            buy_signals["target_amount"] / buy_signals["price"] / 100
        ).astype(int) * 100
        
        # 成交量约束
        buy_signals["vol_limit"] = buy_signals["vol"] * 100 * self.volume_limit_pct
        buy_signals["quantity"] = buy_signals[["quantity", "vol_limit"]].min(axis=1).astype(int)
        
        # 批量执行
        for _, row in buy_signals.iterrows():
            if row["quantity"] >= 100:
                self._execute_buy(row["ts_code"], row["price"], row["quantity"])
    
    # 卖出信号
    sell_signals = merged[merged["direction"] == "sell"].copy()
    if len(sell_signals) > 0:
        sell_signals["price"] = sell_signals["open"] * (1 - self.slippage_rate)
        
        for _, row in sell_signals.iterrows():
            position = self.portfolio.get_position(row["ts_code"])
            if position and position.available_quantity > 0:
                quantity = min(
                    int(position.quantity * row["weight"] / 100) * 100,
                    position.available_quantity
                )
                if quantity > 0:
                    self._execute_sell(row["ts_code"], row["price"], quantity)
```

---

## 6. 账户管理

### 6.1 Account 类

```python
@dataclass
class Account:
    """账户"""
    initial_capital: float
    cash: float
    frozen: float  # 冻结资金（挂单未成交）
    
    @property
    def available_cash(self) -> float:
        """可用现金"""
        return self.cash - self.frozen
    
    @property
    def total_value(self) -> float:
        """总资产 = 现金 + 持仓市值"""
        return self.cash + self.portfolio.market_value
    
    def freeze(self, amount: float):
        """冻结资金"""
        if amount > self.available_cash:
            raise InsufficientBalanceError()
        self.frozen += amount
    
    def unfreeze(self, amount: float):
        """解冻资金"""
        self.frozen -= amount
    
    def deposit(self, amount: float):
        """入金"""
        self.cash += amount
    
    def withdraw(self, amount: float):
        """出金"""
        if amount > self.available_cash:
            raise InsufficientBalanceError()
        self.cash -= amount
```

### 6.2 Portfolio 类

```python
@dataclass
class Position:
    """持仓"""
    ts_code: str
    quantity: int          # 总数量
    available_quantity: int  # 可卖数量（T+1）
    cost_price: float      # 成本价
    buy_date: str          # 买入日期
    
    @property
    def market_value(self) -> float:
        """市值（需要当前价格）"""
        return self.quantity * self.current_price
    
    @property
    def unrealized_pnl(self) -> float:
        """浮动盈亏"""
        return (self.current_price - self.cost_price) * self.quantity


class Portfolio:
    """组合"""
    
    def __init__(self):
        self.positions: dict[str, Position] = {}
    
    def buy(self, ts_code: str, price: float, quantity: int, date: str):
        """买入"""
        if ts_code in self.positions:
            # 加仓
            pos = self.positions[ts_code]
            total_cost = pos.cost_price * pos.quantity + price * quantity
            pos.quantity += quantity
            pos.cost_price = total_cost / pos.quantity
        else:
            # 新建仓位
            self.positions[ts_code] = Position(
                ts_code=ts_code,
                quantity=quantity,
                available_quantity=0,  # T+1，今天买的今天不能卖
                cost_price=price,
                buy_date=date,
            )
    
    def sell(self, ts_code: str, quantity: int):
        """卖出"""
        pos = self.positions[ts_code]
        pos.quantity -= quantity
        pos.available_quantity -= quantity
        
        if pos.quantity <= 0:
            del self.positions[ts_code]
    
    def update_available(self):
        """更新可卖数量（每日开盘时调用）"""
        for pos in self.positions.values():
            pos.available_quantity = pos.quantity
    
    @property
    def market_value(self) -> float:
        """总市值"""
        return sum(pos.market_value for pos in self.positions.values())
```

---

## 7. 指标计算

### 7.1 核心指标

```python
class PerformanceMetrics:
    """绩效指标"""
    
    @staticmethod
    def calculate(equity_curve: pd.Series, benchmark: pd.Series = None) -> dict:
        """
        计算绩效指标。
        
        Args:
            equity_curve: 净值曲线（每日净值）
            benchmark: 基准净值曲线（可选）
        
        Returns:
            指标字典
        """
        returns = equity_curve.pct_change().dropna()
        
        metrics = {
            # 收益指标
            "total_return": (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1,
            "annual_return": (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (252 / len(equity_curve)) - 1,
            
            # 风险指标
            "annual_volatility": returns.std() * np.sqrt(252),
            "max_drawdown": PerformanceMetrics._max_drawdown(equity_curve),
            "max_drawdown_duration": PerformanceMetrics._max_drawdown_duration(equity_curve),
            
            # 风险调整收益
            "sharpe_ratio": PerformanceMetrics._sharpe(returns),
            "sortino_ratio": PerformanceMetrics._sortino(returns),
            "calmar_ratio": PerformanceMetrics._calmar(equity_curve, returns),
            
            # 交易统计
            "win_rate": PerformanceMetrics._win_rate(returns),
            "profit_loss_ratio": PerformanceMetrics._profit_loss_ratio(returns),
            "trade_count": PerformanceMetrics._trade_count(returns),
        }
        
        # 基准对比
        if benchmark is not None:
            metrics["excess_return"] = metrics["total_return"] - ((benchmark.iloc[-1] / benchmark.iloc[0]) - 1)
            metrics["information_ratio"] = PerformanceMetrics._information_ratio(returns, benchmark.pct_change().dropna())
            metrics["beta"] = PerformanceMetrics._beta(returns, benchmark.pct_change().dropna())
            metrics["alpha"] = metrics["annual_return"] - metrics["beta"] * ((benchmark.iloc[-1] / benchmark.iloc[0]) ** (252 / len(benchmark)) - 1)
        
        return metrics
    
    @staticmethod
    def _max_drawdown(equity_curve: pd.Series) -> float:
        """最大回撤"""
        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak
        return drawdown.min()
    
    @staticmethod
    def _sharpe(returns: pd.Series, risk_free_rate: float = 0.03) -> float:
        """夏普比率"""
        excess_returns = returns - risk_free_rate / 252
        return excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
    
    @staticmethod
    def _sortino(returns: pd.Series, risk_free_rate: float = 0.03) -> float:
        """索提诺比率"""
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252)
        return excess_returns.mean() * 252 / downside_std if downside_std > 0 else 0
```

### 7.2 月度收益分布

```python
def monthly_returns(equity_curve: pd.Series) -> pd.DataFrame:
    """计算月度收益"""
    monthly = equity_curve.resample("ME").last()
    returns = monthly.pct_change().dropna()
    
    # 转为年-月矩阵
    returns_df = pd.DataFrame({
        "year": returns.index.year,
        "month": returns.index.month,
        "return": returns.values,
    })
    
    pivot = returns_df.pivot(index="year", columns="month", values="return")
    pivot.columns = [f"{m}月" for m in pivot.columns]
    
    return pivot
```

---

## 8. 回测主循环

```python
class BacktestEngineV2:
    """向量化回测引擎"""
    
    def __init__(
        self,
        pit: PITQuery,
        initial_capital: float = 1000000,
        commission_rate: float = 0.00025,
        slippage_rate: float = 0.001,
        volume_limit_pct: float = 0.02,
    ):
        self.pit = pit
        self.account = Account(initial_capital)
        self.portfolio = Portfolio()
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.volume_limit_pct = volume_limit_pct
        
        # 记录
        self.equity_curve = []
        self.trade_log = []
        self.signal_log = []
    
    def run(self, strategy: Strategy, start_date: str, end_date: str) -> dict:
        """
        运行回测。
        
        Args:
            strategy: 策略实例
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            回测结果（指标 + 净值曲线 + 交易记录）
        """
        trading_days = self._get_trading_days(start_date, end_date)
        
        for date in trading_days:
            # 1. 更新可卖数量（T+1 解除）
            self.portfolio.update_available()
            
            # 2. 更新持仓市值
            self._update_market_value(date)
            
            # 3. 生成信号（T 日收盘后）
            if date != trading_days[-1]:  # 最后一天不生成信号
                cross_section = self.pit.get_cross_section(date)
                universe = self.pit.get_universe(date)
                signals = strategy.generate_signals(
                    date, cross_section, universe, self.portfolio.positions
                )
                
                # 设置执行日期
                next_day = self._get_next_trading_day(date)
                for signal in signals:
                    signal.execute_date = next_day
                
                self.signal_log.extend(signals)
            
            # 4. 执行信号（T+1 日开盘）
            today_signals = [s for s in self.signal_log if s.execute_date == date]
            if today_signals:
                market_data = self._get_market_data(date)
                self._execute_signals(today_signals, market_data)
            
            # 5. 记录净值
            self.equity_curve.append({
                "date": date,
                "equity": self.account.total_value,
                "cash": self.account.cash,
                "market_value": self.portfolio.market_value,
            })
        
        # 计算指标
        equity_series = pd.Series(
            [e["equity"] for e in self.equity_curve],
            index=[e["date"] for e in self.equity_curve],
        )
        
        metrics = PerformanceMetrics.calculate(equity_series)
        
        return {
            "metrics": metrics,
            "equity_curve": self.equity_curve,
            "trade_log": self.trade_log,
            "signal_log": self.signal_log,
        }
```

---

## 9. 使用示例

```python
from app.backtest.engine_v2 import BacktestEngineV2
from app.data.pit import PITQuery, PITDataManager
from app.data.duckdb_client import DuckDBClient

# 初始化
db = DuckDBClient()
pit = PITDataManager(db)
pit_query = PITQuery(pit)

engine = BacktestEngineV2(
    pit=pit_query,
    initial_capital=1000000,
    commission_rate=0.00025,
    slippage_rate=0.001,
    volume_limit_pct=0.02,
)

# 定义策略
class SmallCapValueStrategy(Strategy):
    def generate_signals(self, date, cross_section, universe, positions):
        # 小市值 + 低 PE 选股
        df = cross_section.copy()
        df = df[df["ts_code"].isin(universe)]
        df = df[df["pe_ttm"] > 0]  # 排除亏损股
        
        # 计算因子排名
        df["mv_rank"] = df["total_mv"].rank()  # 市值越小排名越前
        df["pe_rank"] = df["pe_ttm"].rank()     # PE 越低排名越前
        df["score"] = df["mv_rank"] + df["pe_rank"]
        
        # 选前 20 只
        selected = df.nsmallest(20, "score")
        
        signals = []
        for _, row in selected.iterrows():
            signals.append(Signal(
                ts_code=row["ts_code"],
                signal_date=date,
                direction="buy",
                weight=1.0 / 20,  # 等权重
                reason=f"小市值+低PE, score={row['score']:.0f}",
            ))
        
        return signals

# 运行回测
strategy = SmallCapValueStrategy()
result = engine.run(strategy, "20230101", "20260630")

# 输出结果
print(f"总收益: {result['metrics']['total_return']:.2%}")
print(f"年化收益: {result['metrics']['annual_return']:.2%}")
print(f"最大回撤: {result['metrics']['max_drawdown']:.2%}")
print(f"夏普比率: {result['metrics']['sharpe_ratio']:.2f}")
```
