"""
Event Bus 集成 - 将关键事件接入事件总线

设计原则：
1. 只接关键事件，避免所有业务都事件化
2. 主要用于审计、日志、WebSocket、AI Agent
3. 事件处理器应该是轻量级的，不阻塞主业务流程
"""
import logging
from typing import Dict, Any

from ..core.event_bus import EventBus, Event, EventType, get_event_bus
from ..domain import Order, Trade, Position, RiskDecision

logger = logging.getLogger(__name__)


class TradingEventPublisher:
    """
    交易事件发布器
    
    负责将交易相关的事件发布到 Event Bus
    """
    
    def __init__(self, event_bus: EventBus = None):
        self._event_bus = event_bus or get_event_bus()
    
    def publish_order_submitted(self, order: Order):
        """发布订单提交事件"""
        event = Event(
            event_type=EventType.ORDER_SUBMITTED,
            data={
                "order_id": order.order_id,
                "symbol": order.symbol,
                "direction": order.direction.value,
                "price": order.price,
                "quantity": order.quantity,
                "order_type": order.order_type.value,
            },
            source="trading"
        )
        self._event_bus.publish(event)
        logger.debug(f"Published ORDER_SUBMITTED: {order.order_id}")
    
    def publish_order_filled(self, order: Order, trade: Trade):
        """发布订单成交事件"""
        event = Event(
            event_type=EventType.ORDER_FILLED,
            data={
                "order_id": order.order_id,
                "trade_id": trade.trade_id,
                "symbol": order.symbol,
                "direction": order.direction.value,
                "price": trade.price,
                "quantity": trade.quantity,
                "commission": trade.commission,
            },
            source="trading"
        )
        self._event_bus.publish(event)
        logger.debug(f"Published ORDER_FILLED: {order.order_id}")
    
    def publish_order_cancelled(self, order: Order):
        """发布订单撤销事件"""
        event = Event(
            event_type=EventType.ORDER_CANCELLED,
            data={
                "order_id": order.order_id,
                "symbol": order.symbol,
                "direction": order.direction.value,
                "quantity": order.quantity,
            },
            source="trading"
        )
        self._event_bus.publish(event)
        logger.debug(f"Published ORDER_CANCELLED: {order.order_id}")
    
    def publish_order_rejected(self, order: Order, reason: str):
        """发布订单拒绝事件"""
        event = Event(
            event_type=EventType.ORDER_REJECTED,
            data={
                "order_id": order.order_id,
                "symbol": order.symbol,
                "direction": order.direction.value,
                "quantity": order.quantity,
                "reason": reason,
            },
            source="trading"
        )
        self._event_bus.publish(event)
        logger.debug(f"Published ORDER_REJECTED: {order.order_id}")
    
    def publish_position_changed(self, position: Position, change_type: str):
        """发布持仓变化事件"""
        event = Event(
            event_type=EventType.POSITION_CHANGED,
            data={
                "symbol": position.symbol,
                "quantity": position.quantity,
                "available": position.available,
                "cost_price": position.cost_price,
                "market_value": position.market_value,
                "unrealized_pnl": position.unrealized_pnl,
                "change_type": change_type,  # "buy", "sell", "update"
            },
            source="trading"
        )
        self._event_bus.publish(event)
        logger.debug(f"Published POSITION_CHANGED: {position.symbol}")
    
    def publish_risk_rejected(self, decision: RiskDecision):
        """发布风控拒绝事件"""
        event = Event(
            event_type=EventType.RISK_REJECTED,
            data={
                "decision_id": decision.decision_id,
                "order_id": decision.order_id,
                "symbol": decision.symbol,
                "action": decision.action.value,
                "reason": decision.reason,
                "rule_id": decision.rule_id,
            },
            source="risk"
        )
        self._event_bus.publish(event)
        logger.debug(f"Published RISK_REJECTED: {decision.order_id}")


class TradingEventHandler:
    """
    交易事件处理器
    
    处理交易相关的事件，用于审计、日志等
    """
    
    def __init__(self, event_bus: EventBus = None):
        self._event_bus = event_bus or get_event_bus()
        self._register_handlers()
    
    def _register_handlers(self):
        """注册事件处理器"""
        self._event_bus.subscribe(EventType.ORDER_SUBMITTED, self._on_order_submitted)
        self._event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        self._event_bus.subscribe(EventType.ORDER_CANCELLED, self._on_order_cancelled)
        self._event_bus.subscribe(EventType.ORDER_REJECTED, self._on_order_rejected)
        self._event_bus.subscribe(EventType.POSITION_CHANGED, self._on_position_changed)
        self._event_bus.subscribe(EventType.RISK_REJECTED, self._on_risk_rejected)
    
    def _on_order_submitted(self, event: Event):
        """处理订单提交事件"""
        data = event.data
        logger.info(f"[AUDIT] Order submitted: {data['order_id']} {data['symbol']} {data['direction']} {data['quantity']} @ {data['price']}")
    
    def _on_order_filled(self, event: Event):
        """处理订单成交事件"""
        data = event.data
        logger.info(f"[AUDIT] Order filled: {data['order_id']} {data['symbol']} {data['direction']} {data['quantity']} @ {data['price']}")
    
    def _on_order_cancelled(self, event: Event):
        """处理订单撤销事件"""
        data = event.data
        logger.info(f"[AUDIT] Order cancelled: {data['order_id']} {data['symbol']}")
    
    def _on_order_rejected(self, event: Event):
        """处理订单拒绝事件"""
        data = event.data
        logger.warning(f"[AUDIT] Order rejected: {data['order_id']} {data['symbol']} reason: {data['reason']}")
    
    def _on_position_changed(self, event: Event):
        """处理持仓变化事件"""
        data = event.data
        logger.info(f"[AUDIT] Position changed: {data['symbol']} qty={data['quantity']} type={data['change_type']}")
    
    def _on_risk_rejected(self, event: Event):
        """处理风控拒绝事件"""
        data = event.data
        logger.warning(f"[AUDIT] Risk rejected: {data['order_id']} {data['symbol']} reason: {data['reason']}")


# 全局实例
_trading_event_publisher: TradingEventPublisher = None
_trading_event_handler: TradingEventHandler = None


def get_trading_event_publisher() -> TradingEventPublisher:
    """获取交易事件发布器"""
    global _trading_event_publisher
    if _trading_event_publisher is None:
        _trading_event_publisher = TradingEventPublisher()
    return _trading_event_publisher


def get_trading_event_handler() -> TradingEventHandler:
    """获取交易事件处理器"""
    global _trading_event_handler
    if _trading_event_handler is None:
        _trading_event_handler = TradingEventHandler()
    return _trading_event_handler


def init_trading_events():
    """初始化交易事件系统"""
    get_trading_event_publisher()
    get_trading_event_handler()
    logger.info("Trading event system initialized")
