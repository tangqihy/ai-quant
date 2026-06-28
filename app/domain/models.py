"""
领域模型定义 - 量化交易系统核心领域对象

设计原则：
1. 领域驱动：定义稳定的领域对象，而不是到处传 dict/DataFrame
2. 职责单一：每个领域对象只负责自己的业务逻辑
3. 不可变性：核心领域对象尽量使用不可变设计
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


# ============================================================
# 枚举类型
# ============================================================

class Exchange(Enum):
    """交易所"""
    SH = "SH"  # 上海证券交易所
    SZ = "SZ"  # 深圳证券交易所
    BJ = "BJ"  # 北京证券交易所


class Market(Enum):
    """市场"""
    MAIN = "MAIN"      # 主板
    GEM = "GEM"        # 创业板
    STAR = "STAR"      # 科创板
    BSE = "BSE"        # 北交所


class OrderDirection(Enum):
    """订单方向"""
    BUY = "buy"    # 买入
    SELL = "sell"  # 卖出


class OrderType(Enum):
    """订单类型"""
    LIMIT = "limit"    # 限价单
    MARKET = "market"  # 市价单


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"        # 待提交
    SUBMITTED = "submitted"    # 已提交
    ACCEPTED = "accepted"      # 已接受
    PARTIAL = "partial"        # 部分成交
    FILLED = "filled"          # 全部成交
    CANCELLED = "cancelled"    # 已撤销
    REJECTED = "rejected"      # 已拒绝


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"    # 多头
    SHORT = "short"  # 空头（期货用）


class RiskRuleType(Enum):
    """风控规则类型"""
    POSITION_LIMIT = "position_limit"      # 仓位限制
    STOP_LOSS = "stop_loss"                # 止损
    TAKE_PROFIT = "take_profit"            # 止盈
    BLACKLIST = "blacklist"                # 黑名单
    ORDER_AMOUNT = "order_amount"          # 订单金额限制
    DAILY_TRADES = "daily_trades"          # 每日交易次数限制


class BrokerType(Enum):
    """撮合器类型"""
    BACKTEST = "backtest"  # 回测撮合器
    PAPER = "paper"        # 模拟撮合器
    LIVE = "live"          # 实盘撮合器


class Frequency(Enum):
    """数据频率"""
    TICK = "tick"      # Tick
    MIN_1 = "1min"     # 1分钟
    MIN_5 = "5min"     # 5分钟
    MIN_15 = "15min"   # 15分钟
    MIN_30 = "30min"   # 30分钟
    MIN_60 = "60min"   # 60分钟
    DAILY = "1d"       # 日线
    WEEKLY = "1w"      # 周线
    MONTHLY = "1m"     # 月线


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"        # 买入信号
    SELL = "sell"      # 卖出信号
    HOLD = "hold"      # 持有
    CLOSE = "close"    # 平仓


class RiskAction(Enum):
    """风控动作"""
    PASS = "pass"          # 通过
    REJECT = "reject"      # 拒绝
    MODIFY = "modify"      # 修改（如减少数量）
    WARN = "warn"          # 警告


# ============================================================
# 领域对象
# ============================================================

@dataclass
class Instrument:
    """
    股票/合约
    
    表示一个可交易的金融工具
    """
    symbol: str           # 股票代码 (600519)
    name: str             # 股票名称 (贵州茅台)
    exchange: Exchange    # 交易所
    market: Market        # 市场
    industry: str = ""    # 行业
    list_date: str = ""   # 上市日期
    delist_date: str = "" # 退市日期
    status: str = "active"  # 状态 (active/suspended/delisted)
    
    @property
    def ts_code(self) -> str:
        """Tushare格式代码 (600519.SH)"""
        return f"{self.symbol}.{self.exchange.value}"
    
    @property
    def is_st(self) -> bool:
        """是否ST"""
        return "ST" in self.name or "*ST" in self.name
    
    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return self.status == "active"
    
    def get_price_limit(self) -> float:
        """获取涨跌停限制"""
        if self.is_st:
            return 0.05  # ST股票5%
        elif self.market == Market.STAR or self.market == Market.GEM:
            return 0.20  # 科创板/创业板20%
        else:
            return 0.10  # 主板10%


@dataclass
class MarketData:
    """
    行情数据
    
    表示某个时间点的行情信息（基类）
    """
    symbol: str           # 股票代码
    datetime: datetime    # 时间
    open: float           # 开盘价
    high: float           # 最高价
    low: float            # 最低价
    close: float          # 收盘价
    volume: float         # 成交量
    amount: float         # 成交额
    change_pct: float = 0.0    # 涨跌幅
    turnover: float = 0.0      # 换手率
    adj_factor: float = 1.0    # 复权因子
    
    @property
    def typical_price(self) -> float:
        """典型价格 (最高+最低+收盘)/3"""
        return (self.high + self.low + self.close) / 3
    
    @property
    def vwap(self) -> float:
        """成交量加权平均价"""
        if self.volume > 0:
            return self.amount / self.volume
        return self.close
    
    def adjust(self, adj_factor: float, latest_adj_factor: float, method: str = "qfq") -> 'MarketData':
        """复权处理"""
        if method == "":
            return self
        
        if method == "qfq":
            factor = adj_factor / latest_adj_factor if latest_adj_factor else 1.0
        elif method == "hfq":
            factor = latest_adj_factor / adj_factor if adj_factor else 1.0
        else:
            return self
        
        return MarketData(
            symbol=self.symbol,
            datetime=self.datetime,
            open=round(self.open * factor, 2),
            high=round(self.high * factor, 2),
            low=round(self.low * factor, 2),
            close=round(self.close * factor, 2),
            volume=self.volume,
            amount=self.amount,
            change_pct=self.change_pct,
            turnover=self.turnover,
            adj_factor=adj_factor
        )


@dataclass
class Bar(MarketData):
    """
    K线数据
    
    继承 MarketData，表示一根K线
    """
    frequency: Frequency = Frequency.DAILY  # 频率
    is_complete: bool = True  # 是否已完成（盘中可能为False）
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], frequency: Frequency = Frequency.DAILY) -> 'Bar':
        """从字典创建"""
        return cls(
            symbol=data.get("symbol", ""),
            datetime=data.get("datetime", datetime.now()),
            open=data.get("open", 0.0),
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            close=data.get("close", 0.0),
            volume=data.get("volume", 0.0),
            amount=data.get("amount", 0.0),
            change_pct=data.get("change_pct", 0.0),
            turnover=data.get("turnover", 0.0),
            adj_factor=data.get("adj_factor", 1.0),
            frequency=frequency,
        )


@dataclass
class Tick:
    """
    Tick数据
    
    表示逐笔报价数据（盘口）
    """
    symbol: str           # 股票代码
    datetime: datetime    # 时间
    price: float          # 最新价
    volume: float         # 成交量
    amount: float         # 成交额
    bid_price: float = 0.0    # 买一价
    bid_volume: float = 0.0   # 买一量
    ask_price: float = 0.0    # 卖一价
    ask_volume: float = 0.0   # 卖一量
    open: float = 0.0         # 开盘价
    high: float = 0.0         # 最高价
    low: float = 0.0          # 最低价
    pre_close: float = 0.0    # 昨收价
    change_pct: float = 0.0   # 涨跌幅
    
    @property
    def spread(self) -> float:
        """买卖价差"""
        if self.bid_price > 0 and self.ask_price > 0:
            return self.ask_price - self.bid_price
        return 0.0
    
    @property
    def mid_price(self) -> float:
        """中间价"""
        if self.bid_price > 0 and self.ask_price > 0:
            return (self.bid_price + self.ask_price) / 2
        return self.price
    
    def to_bar(self) -> MarketData:
        """转换为K线数据"""
        return MarketData(
            symbol=self.symbol,
            datetime=self.datetime,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.price,
            volume=self.volume,
            amount=self.amount,
            change_pct=self.change_pct,
        )


@dataclass
class Signal:
    """
    策略信号
    
    表示策略产生的交易信号
    """
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""           # 策略ID
    symbol: str = ""                # 股票代码
    signal_type: SignalType = SignalType.HOLD  # 信号类型
    price: float = 0.0             # 建议价格
    quantity: int = 0              # 建议数量
    reason: str = ""               # 信号原因
    confidence: float = 1.0        # 置信度 (0-1)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_buy(self) -> bool:
        """是否买入信号"""
        return self.signal_type == SignalType.BUY
    
    @property
    def is_sell(self) -> bool:
        """是否卖出信号"""
        return self.signal_type == SignalType.SELL
    
    def to_order(
        self,
        order_type: OrderType = OrderType.LIMIT,
        account_id: str = ""
    ) -> Order:
        """转换为订单"""
        if self.signal_type == SignalType.HOLD:
            raise ValueError("Cannot create order from HOLD signal")
        
        direction = OrderDirection.BUY if self.is_buy else OrderDirection.SELL
        
        return Order(
            symbol=self.symbol,
            direction=direction,
            price=self.price,
            quantity=self.quantity,
            order_type=order_type,
        )


@dataclass
class RiskDecision:
    """
    风控决策
    
    表示风控系统的决策结果
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""              # 关联的订单ID
    symbol: str = ""                # 股票代码
    action: RiskAction = RiskAction.PASS  # 决策动作
    reason: str = ""                # 决策原因
    original_quantity: int = 0      # 原始数量
    modified_quantity: int = 0      # 修改后的数量（如果action=MODIFY）
    rule_id: str = ""               # 触发的规则ID
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_pass(self) -> bool:
        """是否通过"""
        return self.action == RiskAction.PASS
    
    @property
    def is_reject(self) -> bool:
        """是否拒绝"""
        return self.action == RiskAction.REJECT
    
    @property
    def is_modify(self) -> bool:
        """是否修改"""
        return self.action == RiskAction.MODIFY


@dataclass
class Order:
    """
    订单
    
    表示一个交易订单
    """
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    direction: OrderDirection = OrderDirection.BUY
    price: float = 0.0
    quantity: int = 0
    order_type: OrderType = OrderType.LIMIT
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    reject_reason: str = ""
    
    @property
    def is_filled(self) -> bool:
        """是否全部成交"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_cancelled(self) -> bool:
        """是否已撤销"""
        return self.status == OrderStatus.CANCELLED
    
    @property
    def is_rejected(self) -> bool:
        """是否已拒绝"""
        return self.status == OrderStatus.REJECTED
    
    @property
    def is_active(self) -> bool:
        """是否活跃（待提交/已提交/已接受/部分成交）"""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIAL
        ]
    
    @property
    def remaining_quantity(self) -> int:
        """剩余数量"""
        return self.quantity - self.filled_quantity
    
    @property
    def total_cost(self) -> float:
        """总成本（含手续费和滑点）"""
        return self.filled_price * self.filled_quantity + self.commission + self.slippage
    
    def fill(self, price: float, quantity: int, commission: float = 0.0, slippage: float = 0.0):
        """成交"""
        # 更新成交信息
        total_filled = self.filled_quantity + quantity
        if total_filled > self.quantity:
            raise ValueError(f"Filled quantity {total_filled} exceeds order quantity {self.quantity}")
        
        # 计算成交均价
        if self.filled_quantity == 0:
            self.filled_price = price
        else:
            self.filled_price = (
                self.filled_price * self.filled_quantity + price * quantity
            ) / total_filled
        
        self.filled_quantity = total_filled
        self.commission += commission
        self.slippage += slippage
        self.updated_at = datetime.now()
        
        # 更新状态
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIAL
    
    def cancel(self):
        """撤销"""
        if not self.is_active:
            raise ValueError(f"Cannot cancel order in status {self.status}")
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.now()
    
    def reject(self, reason: str):
        """拒绝"""
        self.status = OrderStatus.REJECTED
        self.reject_reason = reason
        self.updated_at = datetime.now()


@dataclass
class Trade:
    """
    成交
    
    表示一次实际成交
    """
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    direction: OrderDirection = OrderDirection.BUY
    price: float = 0.0
    quantity: int = 0
    commission: float = 0.0
    slippage: float = 0.0
    traded_at: datetime = field(default_factory=datetime.now)
    
    @property
    def amount(self) -> float:
        """成交金额"""
        return self.price * self.quantity
    
    @property
    def net_amount(self) -> float:
        """净成交金额（扣除手续费）"""
        return self.amount - self.commission


@dataclass
class Position:
    """
    持仓
    
    表示某个股票的持仓
    """
    symbol: str = ""
    quantity: int = 0        # 持仓数量
    available: int = 0       # 可用数量（T+1后）
    cost_price: float = 0.0  # 成本价
    market_value: float = 0.0  # 市值
    unrealized_pnl: float = 0.0  # 浮动盈亏
    realized_pnl: float = 0.0    # 已实现盈亏
    
    @property
    def avg_cost(self) -> float:
        """平均成本"""
        if self.quantity > 0:
            return self.cost_price
        return 0.0
    
    @property
    def pnl_ratio(self) -> float:
        """盈亏比例"""
        if self.cost_price > 0 and self.quantity > 0:
            current_price = self.market_value / self.quantity
            return (current_price - self.cost_price) / self.cost_price
        return 0.0
    
    def update_market_value(self, current_price: float):
        """更新市值"""
        self.market_value = current_price * self.quantity
        if self.quantity > 0:
            self.unrealized_pnl = (current_price - self.cost_price) * self.quantity
    
    def buy(self, price: float, quantity: int):
        """买入"""
        # 计算新的成本价
        total_cost = self.cost_price * self.quantity + price * quantity
        self.quantity += quantity
        self.available += quantity  # T+1后可用
        self.cost_price = total_cost / self.quantity if self.quantity > 0 else 0
    
    def sell(self, price: float, quantity: int) -> float:
        """
        卖出
        
        Returns:
            float: 已实现盈亏
        """
        if quantity > self.available:
            raise ValueError(f"Sell quantity {quantity} exceeds available {self.available}")
        
        # 计算已实现盈亏
        pnl = (price - self.cost_price) * quantity
        self.realized_pnl += pnl
        
        # 更新持仓
        self.quantity -= quantity
        self.available -= quantity
        
        # 清空持仓
        if self.quantity <= 0:
            self.quantity = 0
            self.available = 0
            self.cost_price = 0
            self.market_value = 0
            self.unrealized_pnl = 0
        
        return pnl


@dataclass
class Account:
    """
    账户
    
    表示一个交易账户，负责现金管理
    """
    account_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    initial_capital: float = 1000000.0  # 初始资金
    cash: float = 1000000.0            # 可用资金
    frozen: float = 0.0                # 冻结资金
    total_value: float = 1000000.0     # 总资产
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def available_cash(self) -> float:
        """可用资金"""
        return self.cash
    
    @property
    def total_cash(self) -> float:
        """总现金（可用+冻结）"""
        return self.cash + self.frozen
    
    def deposit(self, amount: float):
        """入金"""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.cash += amount
        self._update_total_value()
    
    def withdraw(self, amount: float):
        """出金"""
        if amount <= 0:
            raise ValueError("Withdraw amount must be positive")
        if amount > self.cash:
            raise ValueError(f"Withdraw amount {amount} exceeds available cash {self.cash}")
        self.cash -= amount
        self._update_total_value()
    
    def freeze(self, amount: float):
        """冻结资金"""
        if amount > self.cash:
            raise ValueError(f"Freeze amount {amount} exceeds available cash {self.cash}")
        self.cash -= amount
        self.frozen += amount
    
    def unfreeze(self, amount: float):
        """解冻资金"""
        if amount > self.frozen:
            raise ValueError(f"Unfreeze amount {amount} exceeds frozen {self.frozen}")
        self.frozen -= amount
        self.cash += amount
    
    def _update_total_value(self, positions_value: float = 0):
        """更新总资产"""
        self.total_value = self.cash + self.frozen + positions_value


@dataclass
class Portfolio:
    """
    组合
    
    表示一个投资组合，负责持仓管理
    """
    portfolio_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    strategy_id: str = ""
    positions: Dict[str, Position] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def total_positions(self) -> int:
        """持仓数量"""
        return len(self.positions)
    
    @property
    def total_market_value(self) -> float:
        """总市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_unrealized_pnl(self) -> float:
        """总浮动盈亏"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    @property
    def total_realized_pnl(self) -> float:
        """总已实现盈亏"""
        return sum(pos.realized_pnl for pos in self.positions.values())
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(symbol)
    
    def add_position(self, position: Position):
        """添加持仓"""
        self.positions[position.symbol] = position
    
    def remove_position(self, symbol: str):
        """移除持仓"""
        if symbol in self.positions:
            del self.positions[symbol]
    
    def update_market_value(self, prices: Dict[str, float]):
        """更新市值"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_market_value(prices[symbol])


@dataclass
class RiskRule:
    """
    风控规则
    
    表示一个风控规则
    """
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_type: RiskRuleType = RiskRuleType.POSITION_LIMIT
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""
    
    def check(self, context: Dict[str, Any]) -> bool:
        """
        检查风控规则
        
        Args:
            context: 上下文信息
            
        Returns:
            bool: 是否通过
        """
        if not self.enabled:
            return True
        
        if self.rule_type == RiskRuleType.POSITION_LIMIT:
            return self._check_position_limit(context)
        elif self.rule_type == RiskRuleType.STOP_LOSS:
            return self._check_stop_loss(context)
        elif self.rule_type == RiskRuleType.TAKE_PROFIT:
            return self._check_take_profit(context)
        elif self.rule_type == RiskRuleType.BLACKLIST:
            return self._check_blacklist(context)
        elif self.rule_type == RiskRuleType.ORDER_AMOUNT:
            return self._check_order_amount(context)
        elif self.rule_type == RiskRuleType.DAILY_TRADES:
            return self._check_daily_trades(context)
        
        return True
    
    def _check_position_limit(self, context: Dict[str, Any]) -> bool:
        """检查仓位限制"""
        position_ratio = context.get("position_ratio", 0)
        max_ratio = self.params.get("max_ratio", 0.5)
        return position_ratio <= max_ratio
    
    def _check_stop_loss(self, context: Dict[str, Any]) -> bool:
        """检查止损"""
        pnl_ratio = context.get("pnl_ratio", 0)
        stop_loss = self.params.get("stop_loss", -0.1)
        return pnl_ratio >= stop_loss
    
    def _check_take_profit(self, context: Dict[str, Any]) -> bool:
        """检查止盈"""
        pnl_ratio = context.get("pnl_ratio", 0)
        take_profit = self.params.get("take_profit", 0.2)
        return pnl_ratio <= take_profit
    
    def _check_blacklist(self, context: Dict[str, Any]) -> bool:
        """检查黑名单"""
        symbol = context.get("symbol", "")
        blacklist = self.params.get("blacklist", [])
        return symbol not in blacklist
    
    def _check_order_amount(self, context: Dict[str, Any]) -> bool:
        """检查订单金额"""
        order_amount = context.get("order_amount", 0)
        max_amount = self.params.get("max_amount", 100000)
        return order_amount <= max_amount
    
    def _check_daily_trades(self, context: Dict[str, Any]) -> bool:
        """检查每日交易次数"""
        daily_trades = context.get("daily_trades", 0)
        max_trades = self.params.get("max_trades", 10)
        return daily_trades < max_trades


@dataclass
class ExchangeInfo:
    """
    交易所信息
    
    表示交易所的规则和信息
    """
    name: str = ""
    exchange: Exchange = Exchange.SH
    tick_size: float = 0.01      # 最小变动价位
    lot_size: int = 100          # 最小交易单位
    t_plus: int = 1              # T+N (T+1)
    price_limit: float = 0.10    # 涨跌停限制 (10%)
    commission_rate: float = 0.0003  # 佣金率
    stamp_tax_rate: float = 0.001    # 印花税率（卖出时收取）
    min_commission: float = 5.0      # 最低佣金
    
    def calculate_commission(self, amount: float, direction: OrderDirection) -> float:
        """
        计算手续费
        
        Args:
            amount: 成交金额
            direction: 订单方向
            
        Returns:
            float: 手续费
        """
        # 佣金
        commission = max(amount * self.commission_rate, self.min_commission)
        
        # 印花税（卖出时收取）
        if direction == OrderDirection.SELL:
            commission += amount * self.stamp_tax_rate
        
        return round(commission, 2)
    
    def round_price(self, price: float) -> float:
        """价格取整到最小变动价位"""
        return round(round(price / self.tick_size) * self.tick_size, 2)
    
    def round_quantity(self, quantity: int) -> int:
        """数量取整到最小交易单位"""
        return (quantity // self.lot_size) * self.lot_size


# ============================================================
# 策略上下文
# ============================================================

class StrategyContext:
    """
    策略上下文
    
    提供给策略的接口
    """
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self._subscribed_symbols: List[str] = []
        self._pending_orders: List[Order] = []
    
    def subscribe(self, symbols: List[str], frequency: Frequency = Frequency.DAILY):
        """订阅行情"""
        self._subscribed_symbols.extend(symbols)
    
    def order(
        self, 
        symbol: str, 
        direction: OrderDirection, 
        quantity: int, 
        price: float = None, 
        order_type: OrderType = OrderType.LIMIT
    ) -> Order:
        """下单"""
        order = Order(
            symbol=symbol,
            direction=direction,
            price=price or 0,
            quantity=quantity,
            order_type=order_type
        )
        self._pending_orders.append(order)
        return order
    
    def cancel(self, order_id: str) -> bool:
        """撤单"""
        for order in self._pending_orders:
            if order.order_id == order_id and order.is_active:
                order.cancel()
                return True
        return False
    
    def get_pending_orders(self) -> List[Order]:
        """获取待处理订单"""
        return [o for o in self._pending_orders if o.is_active]


# ============================================================
# 策略基类
# ============================================================

class Strategy:
    """
    策略基类
    
    所有策略都应继承此类
    
    生命周期：
    1. initialize() - 初始化参数
    2. on_start() - 策略启动
    3. on_bar(bar) - K线到达
    4. on_tick(tick) - Tick到达
    5. on_order(order) - 订单状态变化
    6. on_trade(trade) - 成交回报
    7. on_finish() - 策略结束
    """
    
    def __init__(self, strategy_id: str = None):
        self.strategy_id = strategy_id or str(uuid.uuid4())
        self.context = StrategyContext(self.strategy_id)
        self._is_running = False
    
    @property
    def is_running(self) -> bool:
        """策略是否运行中"""
        return self._is_running
    
    def initialize(self):
        """初始化，加载参数、历史数据"""
        pass
    
    def on_start(self):
        """策略启动"""
        self._is_running = True
    
    def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        K线更新
        
        Args:
            bar: K线数据
            
        Returns:
            Optional[Signal]: 交易信号（如果有）
        """
        return None
    
    def on_tick(self, tick: Tick) -> Optional[Signal]:
        """
        Tick更新
        
        Args:
            tick: Tick数据
            
        Returns:
            Optional[Signal]: 交易信号（如果有）
        """
        return None
    
    def on_order(self, order: Order):
        """订单状态变化"""
        pass
    
    def on_trade(self, trade: Trade):
        """成交回报"""
        pass
    
    def on_finish(self):
        """策略结束"""
        self._is_running = False
