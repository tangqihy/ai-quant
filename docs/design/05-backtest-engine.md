# 05 - 回测引擎技术方案（最终版）

> 本文档定义回测引擎的设计，采用混合架构：向量化因子计算 + 状态化撮合。
> 依赖文档：01-data-pipeline-architecture.md、04-pit-layer.md

---

## 1. 核心原则

1. **混合架构：** 因子向量化 + 撮合状态化
2. **领域分离：** Signal → OrderIntent → Order → Trade
3. **完整账本：** submit→freeze→fill→settle
4. **可复现性：** BacktestRunManifest 记录所有配置

---

## 2. 混合架构

### 2.1 向量化 vs 状态化

| 层 | 计算方式 | 说明 |
|----|----------|------|
| 因子计算 | 向量化 | 批量处理，不逐行循环 |
| 信号生成 | 向量化 | 基于因子值批量生成信号 |
| 订单撮合 | 状态化 | T+1、资金冻结、部分成交需要状态机 |
| 账户管理 | 状态化 | 持仓 lot、可卖数量需要状态 |
| 指标汇总 | 向量化 | 净值曲线、收益分布批量计算 |

### 2.2 主循环

```python
class BacktestEngine:
    """混合架构回测引擎"""
    
    def run(self, strategy, start_date, end_date) -> BacktestResult:
        """回测主循环"""
        # 初始化 RunManifest
        manifest = self._create_manifest(strategy, start_date, end_date)
        
        trading_days = self._get_trading_days(start_date, end_date)
        
        for date in trading_days:
            # 1. 更新持仓状态（T+1 解除）
            self.portfolio.update_sellable(date)
            
            # 2. 向量化：生成信号
            signals = self._generate_signals_vectorized(strategy, date)
            
            # 3. 状态化：执行交易
            self._execute_trades_stateful(signals, date)
            
            # 4. 记录净值
            self._record_equity(date)
        
        # 5. 向量化：计算指标
        metrics = self._calculate_metrics_vectorized()
        
        return BacktestResult(manifest=manifest, metrics=metrics, ...)
```

---

## 3. 领域模型：Signal / Order / Trade

### 3.1 Signal（策略信号）

```python
@dataclass
class Signal:
    """
    策略信号：策略希望做什么。
    
    不包含执行结果（价格、数量、手续费）。
    """
    ts_code: str           # 股票代码
    signal_date: str       # 信号产生日期（T 日收盘后）
    direction: str         # "buy" or "sell"
    weight: float          # 目标权重（0~1）
    reason: str            # 信号原因
```

### 3.2 OrderIntent（订单意向）

```python
@dataclass
class OrderIntent:
    """
    订单意向：从 Signal 转换为可执行的订单。
    
    包含执行约束（价格、数量）。
    """
    ts_code: str
    direction: str
    target_quantity: int   # 目标数量
    price_limit: Optional[float]  # 限价（None = 市价）
    execute_date: str      # 执行日期（T+1）
    source_signal: Signal  # 来源信号
```

### 3.3 Order（委托）

```python
@dataclass
class Order:
    """
    委托：提交给撮合引擎的订单。
    
    有状态机：pending → submitted → filled / cancelled / rejected
    """
    order_id: str
    ts_code: str
    direction: str
    price: float           # 委托价格
    quantity: int          # 委托数量
    order_type: str        # "limit" / "market"
    status: str            # "pending" / "submitted" / "filled" / "cancelled" / "rejected"
    
    # 资金状态
    frozen_amount: float   # 冻结金额
    frozen_quantity: int   # 冻结数量（卖出时）
    
    # 时间
    created_at: str
    submitted_at: Optional[str]
    filled_at: Optional[str]
    
    # 来源
    source_intent: OrderIntent
    
    def fill(self, price: float, quantity: int, commission: float):
        """成交"""
        self.status = "filled"
        self.filled_at = datetime.now().isoformat()
        # 创建 Trade
        ...
    
    def cancel(self, reason: str):
        """撤单"""
        self.status = "cancelled"
        # 解冻资金
        ...
    
    def reject(self, reason: str):
        """拒单"""
        self.status = "rejected"
        # 解冻资金
        ...
```

### 3.4 Trade（成交）

```python
@dataclass
class Trade:
    """
    成交：最终成交了什么。
    """
    trade_id: str
    order_id: str
    ts_code: str
    direction: str
    price: float           # 成交价格
    quantity: int          # 成交数量
    amount: float          # 成交金额
    commission: float      # 手续费
    
    # 时间
    trade_date: str
    
    # 来源
    source_order: Order
```

### 3.5 流程图

```
Signal (策略希望做什么)
    │
    ▼
OrderIntent (转换为可执行意向)
    │
    ▼
Order (提交给撮合引擎)
    │
    ├── fill → Trade (成交)
    ├── cancel → 解冻资金
    └── reject → 解冻资金
```

---

## 4. A 股交易规则

### 4.1 涨跌停规则

| 市场 | 涨跌幅限制 |
|------|-----------|
| 主板 | ±10% |
| 创业板 | ±20% |
| 科创板 | ±20% |
| 北交所 | ±30% |
| ST 股票 | ±5%（2026-07-06 起改为 ±10%）|

### 4.2 撮合模式

```python
class MatchingMode(Enum):
    """撮合模式"""
    STRICT = "strict"       # 一字涨停不可买，一字跌停不可卖
    SIMPLE = "simple"       # 只根据开盘价是否封板判断

def is_tradable(
    ts_code: str,
    date: str,
    direction: str,
    mode: MatchingMode,
) -> tuple[bool, str]:
    """判断是否可交易"""
    bar = get_bar(ts_code, date)
    
    if bar is None:
        return False, "无行情数据"
    
    if is_suspended(ts_code, date):
        return False, "停牌"
    
    if direction == "buy":
        if mode == MatchingMode.STRICT:
            # 一字涨停：开盘价 = 最高价 = 最低价 = 涨停价
            if bar["open"] == bar["high"] == bar["low"] == get_limit_up(ts_code, date):
                return False, "一字涨停"
        elif mode == MatchingMode.SIMPLE:
            # 开盘价封板
            if bar["open"] == get_limit_up(ts_code, date):
                return False, "开盘涨停"
    
    elif direction == "sell":
        if mode == MatchingMode.STRICT:
            if bar["open"] == bar["high"] == bar["low"] == get_limit_down(ts_code, date):
                return False, "一字跌停"
        elif mode == MatchingMode.SIMPLE:
            if bar["open"] == get_limit_down(ts_code, date):
                return False, "开盘跌停"
    
    return True, "可交易"
```

### 4.3 成交量约束

```python
def calculate_max_quantity(
    ts_code: str,
    date: str,
    participation_rate: float = 0.02,
) -> int:
    """
    计算最大可成交量。
    
    基于数量约束（不是金额约束）。
    """
    bar = get_bar(ts_code, date)
    
    # Tushare vol 单位是手，需要转换为股
    day_volume_shares = bar["vol"] * 100
    
    max_quantity = int(day_volume_shares * participation_rate)
    
    # 向下取整到 100 股
    return (max_quantity // 100) * 100
```

---

## 5. 订单生命周期

### 5.1 完整账本

```python
class OrderLedger:
    """订单账本"""
    
    def submit(self, intent: OrderIntent) -> Order:
        """
        提交订单。
        
        流程：
        1. 验证可交易性
        2. 计算委托价格和数量
        3. 冻结资金（买入）或冻结持仓（卖出）
        4. 创建 Order
        """
        # 验证可交易性
        tradable, reason = is_tradable(
            intent.ts_code, intent.execute_date, intent.direction, self.matching_mode
        )
        if not tradable:
            return self._reject(intent, reason)
        
        # 计算委托价格
        price = self._determine_price(intent)
        
        # 计算委托数量
        quantity = self._determine_quantity(intent, price)
        
        if quantity == 0:
            return self._reject(intent, "数量不足")
        
        # 冻结资金
        if intent.direction == "buy":
            amount = price * quantity
            commission = calculate_commission(amount, "buy")
            self.account.freeze(amount + commission["total"])
        else:
            self.portfolio.freeze(intent.ts_code, quantity)
        
        # 创建 Order
        order = Order(
            order_id=str(uuid.uuid4()),
            ts_code=intent.ts_code,
            direction=intent.direction,
            price=price,
            quantity=quantity,
            order_type="limit",
            status="submitted",
            frozen_amount=price * quantity if intent.direction == "buy" else 0,
            frozen_quantity=quantity if intent.direction == "sell" else 0,
            created_at=datetime.now().isoformat(),
            submitted_at=datetime.now().isoformat(),
            source_intent=intent,
        )
        
        return order
    
    def fill(self, order: Order, fill_price: float, fill_quantity: int) -> Trade:
        """
        成交流程。
        
        流程：
        1. 计算成交金额和手续费
        2. 解冻资金，扣除实际支出
        3. 更新持仓
        4. 创建 Trade
        """
        amount = fill_price * fill_quantity
        commission = calculate_commission(amount, order.direction)
        
        if order.direction == "buy":
            # 解冻，扣除实际支出
            self.account.unfreeze(order.frozen_amount)
            self.account.withdraw(amount + commission["total"])
            self.portfolio.buy(order.ts_code, fill_price, fill_quantity, order.execute_date)
        else:
            # 解冻持仓，收到资金
            self.portfolio.unfreeze(order.ts_code, order.frozen_quantity)
            self.portfolio.sell(order.ts_code, fill_quantity)
            self.account.deposit(amount - commission["total"])
        
        # 更新 Order 状态
        order.fill(fill_price, fill_quantity, commission["total"])
        
        # 创建 Trade
        trade = Trade(
            trade_id=str(uuid.uuid4()),
            order_id=order.order_id,
            ts_code=order.ts_code,
            direction=order.direction,
            price=fill_price,
            quantity=fill_quantity,
            amount=amount,
            commission=commission["total"],
            trade_date=order.execute_date,
            source_order=order,
        )
        
        return trade
    
    def cancel(self, order: Order, reason: str):
        """
        撤单流程。
        
        流程：
        1. 解冻资金或持仓
        2. 更新 Order 状态
        """
        if order.direction == "buy":
            self.account.unfreeze(order.frozen_amount)
        else:
            self.portfolio.unfreeze(order.ts_code, order.frozen_quantity)
        
        order.cancel(reason)
```

### 5.2 T+1 Lot 追踪

```python
@dataclass
class PositionLot:
    """持仓 Lot"""
    ts_code: str
    acquired_date: str     # 买入日期
    quantity: int          # 总数量
    remaining_quantity: int  # 剩余数量
    cost_price: float      # 成本价

class Portfolio:
    """组合"""
    
    def __init__(self):
        self.lots: dict[str, list[PositionLot]] = {}  # ts_code -> lots
    
    def buy(self, ts_code: str, price: float, quantity: int, date: str):
        """买入"""
        lot = PositionLot(
            ts_code=ts_code,
            acquired_date=date,
            quantity=quantity,
            remaining_quantity=quantity,  # T+1，今天买的今天不能卖
            cost_price=price,
        )
        
        if ts_code not in self.lots:
            self.lots[ts_code] = []
        self.lots[ts_code].append(lot)
    
    def sell(self, ts_code: str, quantity: int):
        """卖出"""
        lots = self.lots[ts_code]
        remaining = quantity
        
        for lot in lots:
            if lot.remaining_quantity <= 0:
                continue
            
            sell_qty = min(remaining, lot.remaining_quantity)
            lot.remaining_quantity -= sell_qty
            remaining -= sell_qty
            
            if remaining <= 0:
                break
        
        # 清理空 lot
        self.lots[ts_code] = [l for l in lots if l.remaining_quantity > 0]
    
    def update_sellable(self, date: str):
        """更新可卖数量（T+1 解除）"""
        for ts_code, lots in self.lots.items():
            for lot in lots:
                if lot.acquired_date < date:
                    # T+1 解除，全部可卖
                    pass  # remaining_quantity 已经等于 quantity
    
    def get_sellable_quantity(self, ts_code: str) -> int:
        """获取可卖数量"""
        if ts_code not in self.lots:
            return 0
        return sum(lot.remaining_quantity for lot in self.lots[ts_code])
    
    def get_total_quantity(self, ts_code: str) -> int:
        """获取总数量"""
        if ts_code not in self.lots:
            return 0
        return sum(lot.quantity for lot in self.lots[ts_code])
    
    def freeze(self, ts_code: str, quantity: int):
        """冻结持仓（卖出时）"""
        remaining = quantity
        for lot in self.lots[ts_code]:
            freeze_qty = min(remaining, lot.remaining_quantity)
            lot.remaining_quantity -= freeze_qty
            remaining -= freeze_qty
            if remaining <= 0:
                break
    
    def unfreeze(self, ts_code: str, quantity: int):
        """解冻持仓（撤单时）"""
        remaining = quantity
        for lot in reversed(self.lots[ts_code]):
            unfreeze_qty = min(remaining, lot.quantity - lot.remaining_quantity)
            lot.remaining_quantity += unfreeze_qty
            remaining -= unfreeze_qty
            if remaining <= 0:
                break
```

---

## 6. BacktestRunManifest

```python
@dataclass
class BacktestRunManifest:
    """回测运行清单"""
    run_id: str                    # UUID
    strategy_name: str             # 策略名称
    strategy_version: str          # 策略版本
    parameters: dict               # 策略参数
    
    start_date: str                # 回测开始日期
    end_date: str                  # 回测结束日期
    
    universe_definition: str       # 股票池定义（如 "000300.SH"）
    dataset_version: str           # 数据集版本
    data_cutoff: str               # 数据截止日期
    
    adjustment_mode: str           # 复权模式（"qfq" / "hfq"）
    broker_model: str              # 撮合模式（"strict" / "simple"）
    fee_model: dict                # 费用模型参数
    
    code_commit: str               # 代码提交 hash
    created_at: str                # 创建时间
    
    # 结果
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
```

---

## 7. 使用示例

```python
from app.backtest.engine import BacktestEngine
from app.backtest.manifest import BacktestRunManifest

# 初始化
engine = BacktestEngine(
    pit=pit_query,
    adjustment=AdjustmentManager(anchor_date="20260630"),
    matching_mode=MatchingMode.STRICT,
    fee_model={"commission_rate": 0.00025, "stamp_tax_rate": 0.001},
)

# 运行回测
result = engine.run(
    strategy=SmallCapValueStrategy(),
    start_date="20230101",
    end_date="20260630",
)

# 保存 RunManifest
result.manifest.save("results/run_manifest.json")

# 输出指标
print(f"总收益: {result.metrics['total_return']:.2%}")
print(f"最大回撤: {result.metrics['max_drawdown']:.2%}")
print(f"夏普比率: {result.metrics['sharpe_ratio']:.2f}")
```
