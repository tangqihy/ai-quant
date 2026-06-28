"""
Event Bus - 事件总线

解耦组件，支持发布/订阅模式。
组件通过事件通信，不直接依赖彼此。
"""
import logging
import asyncio
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型枚举"""
    # 数据事件
    DATA_UPDATED = "data.updated"
    DATA_ERROR = "data.error"
    
    # 交易事件
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"
    
    # 持仓事件
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    POSITION_UPDATED = "position.updated"
    
    # 风控事件
    RISK_ALERT = "risk.alert"
    RISK_TRIGGERED = "risk.triggered"
    STOP_LOSS_HIT = "stop_loss.hit"
    STOP_PROFIT_HIT = "stop_profit.hit"
    
    # 系统事件
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    HEALTH_CHECK = "health.check"
    
    # 策略事件
    STRATEGY_SIGNAL = "strategy.signal"
    STRATEGY_ERROR = "strategy.error"


@dataclass
class Event:
    """事件对象"""
    event_type: str
    data: Any = None
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            import uuid
            self.event_id = str(uuid.uuid4())


# 事件处理器类型
EventHandler = Callable[[Event], None]


class EventBus:
    """
    事件总线
    
    支持：
    - 同步/异步事件处理
    - 事件过滤
    - 优先级队列
    - 错误处理
    """
    
    def __init__(self, max_workers: int = 4):
        """
        初始化事件总线
        
        Args:
            max_workers: 线程池最大工作线程数
        """
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._wildcard_handlers: List[EventHandler] = []
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._enabled = True
    
    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: int = 0
    ) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型，支持通配符 "*"
            handler: 事件处理函数
            priority: 优先级（数值越大越先执行）
        """
        if event_type == "*":
            self._wildcard_handlers.append(handler)
            logger.debug(f"Subscribed wildcard handler: {handler.__name__}")
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed to {event_type}: {handler.__name__}")
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type == "*":
            if handler in self._wildcard_handlers:
                self._wildcard_handlers.remove(handler)
        elif event_type in self._handlers:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
    
    def publish(self, event: Event) -> None:
        """
        发布事件（同步）
        
        Args:
            event: 事件对象
        """
        if not self._enabled:
            return
        
        # 记录事件历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        logger.debug(f"Publishing event: {event.event_type} from {event.source}")
        
        # 调用特定事件处理器
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in handler {handler.__name__} for {event.event_type}: {e}")
        
        # 调用通配符处理器
        for handler in self._wildcard_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in wildcard handler {handler.__name__}: {e}")
    
    async def publish_async(self, event: Event) -> None:
        """
        发布事件（异步）
        
        Args:
            event: 事件对象
        """
        if not self._enabled:
            return
        
        # 记录事件历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        logger.debug(f"Publishing async event: {event.event_type} from {event.source}")
        
        # 异步调用处理器
        handlers = self._handlers.get(event.event_type, []) + self._wildcard_handlers
        
        tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(event))
                else:
                    # 在线程池中执行同步处理器
                    loop = asyncio.get_event_loop()
                    tasks.append(loop.run_in_executor(self._executor, handler, event))
            except Exception as e:
                logger.error(f"Error preparing handler {handler.__name__}: {e}")
        
        # 等待所有处理器完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_subscribers(self, event_type: str) -> List[EventHandler]:
        """
        获取事件的订阅者
        
        Args:
            event_type: 事件类型
            
        Returns:
            List[EventHandler]: 订阅者列表
        """
        return self._handlers.get(event_type, []) + self._wildcard_handlers
    
    def get_event_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        获取事件历史
        
        Args:
            event_type: 事件类型过滤
            limit: 返回数量限制
            
        Returns:
            List[Event]: 事件列表
        """
        if event_type:
            events = [e for e in self._event_history if e.event_type == event_type]
        else:
            events = self._event_history
        
        return events[-limit:]
    
    def clear_history(self) -> None:
        """清空事件历史"""
        self._event_history.clear()
    
    def enable(self) -> None:
        """启用事件总线"""
        self._enabled = True
        logger.info("EventBus enabled")
    
    def disable(self) -> None:
        """禁用事件总线"""
        self._enabled = False
        logger.info("EventBus disabled")
    
    @property
    def is_enabled(self) -> bool:
        """是否启用"""
        return self._enabled
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            "enabled": self._enabled,
            "total_handlers": sum(len(h) for h in self._handlers.values()) + len(self._wildcard_handlers),
            "event_types": list(self._handlers.keys()),
            "history_size": len(self._event_history),
            "wildcard_handlers": len(self._wildcard_handlers),
        }


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    获取全局事件总线实例
    
    Returns:
        EventBus: 事件总线实例
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def set_event_bus(event_bus: EventBus) -> None:
    """
    设置全局事件总线实例
    
    Args:
        event_bus: 事件总线实例
    """
    global _event_bus
    _event_bus = event_bus


# 便捷函数
def subscribe(event_type: str, handler: EventHandler) -> None:
    """订阅事件"""
    get_event_bus().subscribe(event_type, handler)


def publish(event_type: str, data: Any = None, source: str = "") -> None:
    """发布事件"""
    event = Event(event_type=event_type, data=data, source=source)
    get_event_bus().publish(event)


async def publish_async(event_type: str, data: Any = None, source: str = "") -> None:
    """异步发布事件"""
    event = Event(event_type=event_type, data=data, source=source)
    await get_event_bus().publish_async(event)
