"""
领域模型定义

使用方式：
    from app.domain import (
        Instrument, MarketData, Bar, Tick, Signal, Order, Trade, Position,
        Account, Portfolio, RiskRule, RiskDecision, ExchangeInfo, Strategy,
        OrderDirection, OrderType, OrderStatus, RiskRuleType, SignalType, RiskAction,
        Exchange, Market, Frequency
    )
"""

from .models import (
    # 枚举类型
    Exchange,
    Market,
    OrderDirection,
    OrderType,
    OrderStatus,
    PositionSide,
    RiskRuleType,
    BrokerType,
    Frequency,
    SignalType,
    RiskAction,
    
    # 领域对象
    Instrument,
    MarketData,
    Bar,
    Tick,
    Signal,
    Order,
    Trade,
    Position,
    Account,
    Portfolio,
    RiskRule,
    RiskDecision,
    ExchangeInfo,
    StrategyContext,
    Strategy,
)


def __getattr__(name: str):
    """兼容旧代码从 app.domain 导入 Broker。"""
    if name == "Broker":
        from app.brokers.broker import Broker
        return Broker
    raise AttributeError(f"module 'app.domain' has no attribute {name!r}")
