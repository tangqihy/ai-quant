"""
撮合器 - 负责订单撮合

设计原则：
1. Broker 只负责撮合，不负责风控和持仓管理
2. 支持三种实现：BacktestBroker、PaperBroker、LiveBroker
3. 三种 Broker 可以复用大量逻辑，只是数据来源不同
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import logging

from ..domain import (
    Order, Trade, Position, MarketData, ExchangeInfo,
    OrderDirection, OrderType, OrderStatus
)

logger = logging.getLogger(__name__)


class Broker(ABC):
    """
    撮合器基类
    
    职责：
    - 提交订单
    - 撤销订单
    - 撮合订单
    - 计算成交价、滑点、手续费
    - 处理T+1、涨跌停、停牌
    """
    
    def __init__(self, exchange: ExchangeInfo):
        """
        初始化撮合器
        
        Args:
            exchange: 交易所信息
        """
        self._exchange = exchange
        self._pending_orders: Dict[str, Order] = {}  # 待撮合订单
        self._completed_orders: Dict[str, Order] = {}  # 已完成订单
    
    @property
    def exchange(self) -> ExchangeInfo:
        """获取交易所信息"""
        return self._exchange
    
    def submit_order(self, order: Order) -> bool:
        """
        提交订单
        
        Args:
            order: 订单
            
        Returns:
            bool: 是否成功
        """
        # 验证订单
        if not self._validate_order(order):
            return False
        
        # 更新订单状态
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now()
        
        # 添加到待撮合队列
        self._pending_orders[order.order_id] = order
        
        logger.info(f"Order submitted: {order.order_id}")
        return True
    
    def cancel_order(self, order_id: str) -> bool:
        """
        撤销订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 是否成功
        """
        if order_id not in self._pending_orders:
            logger.warning(f"Order {order_id} not found in pending orders")
            return False
        
        order = self._pending_orders[order_id]
        
        if not order.is_active:
            logger.warning(f"Order {order_id} is not active")
            return False
        
        order.cancel()
        
        # 移动到已完成队列
        self._completed_orders[order_id] = order
        del self._pending_orders[order_id]
        
        logger.info(f"Order cancelled: {order_id}")
        return True
    
    def match(self, bar: MarketData) -> List[Trade]:
        """
        撮合订单
        
        Args:
            bar: 当前K线数据
            
        Returns:
            List[Trade]: 成交列表
        """
        trades = []
        
        # 遍历待撮合订单
        orders_to_remove = []
        for order_id, order in self._pending_orders.items():
            # 检查是否可以撮合
            if not self._can_match(order, bar):
                continue
            
            # 执行撮合
            trade = self._execute_match(order, bar)
            if trade:
                trades.append(trade)
                
                # 订单完成
                if order.is_filled:
                    orders_to_remove.append(order_id)
        
        # 移除已完成订单
        for order_id in orders_to_remove:
            self._completed_orders[order_id] = self._pending_orders[order_id]
            del self._pending_orders[order_id]
        
        return trades
    
    def get_pending_orders(self) -> List[Order]:
        """获取待撮合订单"""
        return list(self._pending_orders.values())
    
    def get_completed_orders(self) -> List[Order]:
        """获取已完成订单"""
        return list(self._completed_orders.values())
    
    def _validate_order(self, order: Order) -> bool:
        """
        验证订单
        
        Args:
            order: 订单
            
        Returns:
            bool: 是否有效
        """
        # 检查订单类型
        if order.order_type == OrderType.LIMIT and order.price <= 0:
            logger.warning(f"Invalid limit order price: {order.price}")
            order.reject("Invalid price")
            return False
        
        # 检查数量
        if order.quantity <= 0:
            logger.warning(f"Invalid order quantity: {order.quantity}")
            order.reject("Invalid quantity")
            return False
        
        # 检查数量是否是100的整数倍
        if order.quantity % self._exchange.lot_size != 0:
            logger.warning(f"Order quantity must be multiple of {self._exchange.lot_size}")
            order.reject(f"Quantity must be multiple of {self._exchange.lot_size}")
            return False
        
        return True
    
    def _can_match(self, order: Order, bar: MarketData) -> bool:
        """
        检查是否可以撮合
        
        Args:
            order: 订单
            bar: 当前K线数据
            
        Returns:
            bool: 是否可以撮合
        """
        # 限价单检查价格
        if order.order_type == OrderType.LIMIT:
            if order.direction == OrderDirection.BUY:
                # 买单：盘中最低价或收盘价触及委托价
                return min(bar.low, bar.close) <= order.price
            else:
                # 卖单：盘中最高价或收盘价触及委托价
                return max(bar.high, bar.close) >= order.price
        
        # 市价单总是可以撮合
        return True
    
    def _execute_match(self, order: Order, bar: MarketData) -> Optional[Trade]:
        """
        执行撮合
        
        Args:
            order: 订单
            bar: 当前K线数据
            
        Returns:
            Optional[Trade]: 成交记录
        """
        # 记录成交前的数量
        fill_quantity = order.remaining_quantity
        
        # 计算成交价格
        fill_price = self._calculate_fill_price(order, bar)
        
        # 计算滑点
        slippage = self._calculate_slippage(order, fill_price)
        
        # 计算手续费
        commission = self._exchange.calculate_commission(
            fill_price * fill_quantity,
            order.direction
        )
        
        # 执行成交
        try:
            order.fill(fill_price, fill_quantity, commission, slippage)
        except ValueError as e:
            logger.error(f"Failed to fill order: {e}")
            return None
        
        # 创建成交记录
        trade = Trade(
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            price=fill_price,
            quantity=fill_quantity,
            commission=commission,
            slippage=slippage,
            traded_at=bar.datetime
        )
        
        logger.info(f"Trade executed: {trade.symbol} {trade.direction.value} {trade.quantity} @ {trade.price}")
        return trade
    
    def _calculate_fill_price(self, order: Order, bar: MarketData) -> float:
        """
        计算成交价格
        
        Args:
            order: 订单
            bar: 当前K线数据
            
        Returns:
            float: 成交价格
        """
        if order.order_type == OrderType.MARKET:
            # 市价单：使用当前收盘价
            return bar.close
        else:
            # 限价单：使用委托价
            return order.price
    
    def _calculate_slippage(self, order: Order, fill_price: float) -> float:
        """
        计算滑点
        
        Args:
            order: 订单
            fill_price: 成交价格
            
        Returns:
            float: 滑点金额
        """
        # 滑点 = 成交价与委托价的差额
        if order.direction == OrderDirection.BUY:
            slippage = (fill_price - order.price) * order.remaining_quantity
        else:
            slippage = (order.price - fill_price) * order.remaining_quantity
        
        return max(0, slippage)


class BacktestBroker(Broker):
    """
    回测撮合器
    
    使用历史数据进行撮合
    """
    
    def __init__(self, exchange: ExchangeInfo):
        super().__init__(exchange)
        self._current_date: Optional[str] = None
    
    def set_current_date(self, date: str):
        """设置当前日期（回测用）"""
        self._current_date = date


class PaperBroker(Broker):
    """
    模拟撮合器
    
    使用实时数据进行撮合
    """
    
    def __init__(self, exchange: ExchangeInfo):
        super().__init__(exchange)
        self._connected = True

    @property
    def connected(self) -> bool:
        return self._connected

    def set_connected(self, connected: bool) -> None:
        self._connected = connected

    def match_quote(self, price: float, symbol: str = "", when: Optional[datetime] = None) -> List[Trade]:
        """
        使用实时行情快照触发撮合，便于模拟交易复用 Broker 逻辑。
        """
        bar = MarketData(
            symbol=symbol or "",
            datetime=when or datetime.now(),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=0,
            amount=0,
        )
        return self.match(bar)


class LiveBroker(Broker):
    """
    实盘撮合器
    
    对接券商API进行撮合
    """
    
    def __init__(self, exchange: ExchangeInfo):
        super().__init__(exchange)
        self._connected = False
    
    def connect(self) -> bool:
        """连接券商。

        实盘交易尚未接入具体券商 SDK，调用方不能把该 Broker 当作可用实盘通道。
        """
        raise NotImplementedError("LiveBroker 尚未接入券商 API")
    
    def disconnect(self):
        """断开连接"""
        self._connected = False
