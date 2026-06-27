"""
策略 API - 固定的策略接口

设计原则：
1. Strategy API 现在就固定，以后不用改
2. 所有策略都应继承 Strategy 基类
3. 策略上下文提供统一的接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable
from datetime import datetime
import logging

from ..domain import (
    MarketData, Order, Trade, Position, Account, Portfolio,
    OrderDirection, OrderType, Frequency, StrategyContext
)

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """
    策略基类
    
    所有策略都应继承此类，实现以下方法：
    - initialize(): 初始化
    - on_bar(): K线更新
    - on_tick(): Tick更新
    - on_order(): 订单更新
    - on_trade(): 成交更新
    - on_finish(): 策略结束
    """
    
    def __init__(self, strategy_id: str = None):
        """
        初始化策略
        
        Args:
            strategy_id: 策略ID，默认自动生成
        """
        self.strategy_id = strategy_id or str(self.__class__.__name__)
        self.context = StrategyContext(self.strategy_id)
        self._is_initialized = False
        self._is_running = False
    
    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._is_initialized
    
    @property
    def is_running(self) -> bool:
        """是否运行中"""
        return self._is_running
    
    def initialize(self):
        """
        初始化策略
        
        在策略开始运行前调用，用于：
        - 订阅行情
        - 初始化参数
        - 加载历史数据
        """
        pass
    
    def on_bar(self, bar: MarketData):
        """
        K线更新
        
        每次收到新的K线数据时调用
        
        Args:
            bar: K线数据
        """
        pass
    
    def on_tick(self, tick: MarketData):
        """
        Tick更新
        
        每次收到新的Tick数据时调用
        
        Args:
            tick: Tick数据
        """
        pass
    
    def on_order(self, order: Order):
        """
        订单更新
        
        订单状态变化时调用
        
        Args:
            order: 订单信息
        """
        pass
    
    def on_trade(self, trade: Trade):
        """
        成交更新
        
        订单成交时调用
        
        Args:
            trade: 成交信息
        """
        pass
    
    def on_finish(self):
        """
        策略结束
        
        策略停止时调用，用于：
        - 清理资源
        - 保存状态
        - 输出统计
        """
        pass
    
    def start(self):
        """启动策略"""
        if self._is_initialized:
            logger.warning(f"Strategy {self.strategy_id} already initialized")
            return
        
        logger.info(f"Starting strategy: {self.strategy_id}")
        self.initialize()
        self._is_initialized = True
        self._is_running = True
    
    def stop(self):
        """停止策略"""
        if not self._is_running:
            logger.warning(f"Strategy {self.strategy_id} is not running")
            return
        
        logger.info(f"Stopping strategy: {self.strategy_id}")
        self.on_finish()
        self._is_running = False
    
    def handle_bar(self, bar: MarketData):
        """
        处理K线更新
        
        Args:
            bar: K线数据
        """
        if not self._is_running:
            return
        
        self.on_bar(bar)
    
    def handle_tick(self, tick: MarketData):
        """
        处理Tick更新
        
        Args:
            tick: Tick数据
        """
        if not self._is_running:
            return
        
        self.on_tick(tick)
    
    def handle_order(self, order: Order):
        """
        处理订单更新
        
        Args:
            order: 订单信息
        """
        self.on_order(order)
    
    def handle_trade(self, trade: Trade):
        """
        处理成交更新
        
        Args:
            trade: 成交信息
        """
        self.on_trade(trade)


class MAStrategy(Strategy):
    """
    MA交叉策略示例
    
    短期均线上穿长期均线 -> 买入
    短期均线下穿长期均线 -> 卖出
    """
    
    def __init__(self, strategy_id: str = None, short_window: int = 5, long_window: int = 20):
        super().__init__(strategy_id)
        self.short_window = short_window
        self.long_window = long_window
        self.prices: List[float] = []
        self.position: Optional[Position] = None
    
    def initialize(self):
        """初始化"""
        # 订阅行情
        self.context.subscribe(["600519"], Frequency.DAILY)
        
        logger.info(f"MA Strategy initialized: short={self.short_window}, long={self.long_window}")
    
    def on_bar(self, bar: MarketData):
        """K线更新"""
        # 记录价格
        self.prices.append(bar.close)
        
        # 保持价格列表长度
        if len(self.prices) > self.long_window:
            self.prices = self.prices[-self.long_window:]
        
        # 检查是否有足够的数据
        if len(self.prices) < self.long_window:
            return
        
        # 计算MA
        short_ma = sum(self.prices[-self.short_window:]) / self.short_window
        long_ma = sum(self.prices[-self.long_window:]) / self.long_window
        
        # 金叉买入
        if short_ma > long_ma and self.position is None:
            order = self.context.order(
                bar.symbol,
                OrderDirection.BUY,
                100,
                bar.close,
                OrderType.LIMIT
            )
            logger.info(f"Buy signal: {bar.symbol} @ {bar.close}")
        
        # 死叉卖出
        elif short_ma < long_ma and self.position is not None:
            order = self.context.order(
                bar.symbol,
                OrderDirection.SELL,
                self.position.quantity,
                bar.close,
                OrderType.LIMIT
            )
            logger.info(f"Sell signal: {bar.symbol} @ {bar.close}")
    
    def on_order(self, order: Order):
        """订单更新"""
        logger.info(f"Order update: {order.order_id} - {order.status.value}")
    
    def on_trade(self, trade: Trade):
        """成交更新"""
        logger.info(f"Trade executed: {trade.symbol} {trade.direction.value} {trade.quantity} @ {trade.price}")
        
        # 更新持仓
        if trade.direction == OrderDirection.BUY:
            self.position = Position(
                symbol=trade.symbol,
                quantity=trade.quantity,
                available=trade.quantity,
                cost_price=trade.price
            )
        else:
            self.position = None
    
    def on_finish(self):
        """策略结束"""
        logger.info(f"Strategy finished: {self.strategy_id}")
        if self.position:
            logger.info(f"Final position: {self.position.symbol} {self.position.quantity}")


class RSIStrategy(Strategy):
    """
    RSI策略示例
    
    RSI < 30 -> 超卖，买入
    RSI > 70 -> 超买，卖出
    """
    
    def __init__(self, strategy_id: str = None, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(strategy_id)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.prices: List[float] = []
        self.position: Optional[Position] = None
    
    def initialize(self):
        """初始化"""
        self.context.subscribe(["600519"], Frequency.DAILY)
        logger.info(f"RSI Strategy initialized: period={self.period}, oversold={self.oversold}, overbought={self.overbought}")
    
    def on_bar(self, bar: MarketData):
        """K线更新"""
        # 记录价格
        self.prices.append(bar.close)
        
        # 保持价格列表长度
        if len(self.prices) > self.period + 1:
            self.prices = self.prices[-(self.period + 1):]
        
        # 检查是否有足够的数据
        if len(self.prices) < self.period + 1:
            return
        
        # 计算RSI
        rsi = self._calculate_rsi()
        
        # 超卖买入
        if rsi < self.oversold and self.position is None:
            order = self.context.order(
                bar.symbol,
                OrderDirection.BUY,
                100,
                bar.close,
                OrderType.LIMIT
            )
            logger.info(f"Buy signal (RSI={rsi:.2f}): {bar.symbol} @ {bar.close}")
        
        # 超买卖出
        elif rsi > self.overbought and self.position is not None:
            order = self.context.order(
                bar.symbol,
                OrderDirection.SELL,
                self.position.quantity,
                bar.close,
                OrderType.LIMIT
            )
            logger.info(f"Sell signal (RSI={rsi:.2f}): {bar.symbol} @ {bar.close}")
    
    def _calculate_rsi(self) -> float:
        """计算RSI"""
        gains = []
        losses = []
        
        for i in range(1, len(self.prices)):
            change = self.prices[i] - self.prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-self.period:]) / self.period
        avg_loss = sum(losses[-self.period:]) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def on_order(self, order: Order):
        """订单更新"""
        logger.info(f"Order update: {order.order_id} - {order.status.value}")
    
    def on_trade(self, trade: Trade):
        """成交更新"""
        logger.info(f"Trade executed: {trade.symbol} {trade.direction.value} {trade.quantity} @ {trade.price}")
        
        # 更新持仓
        if trade.direction == OrderDirection.BUY:
            self.position = Position(
                symbol=trade.symbol,
                quantity=trade.quantity,
                available=trade.quantity,
                cost_price=trade.price
            )
        else:
            self.position = None
    
    def on_finish(self):
        """策略结束"""
        logger.info(f"Strategy finished: {self.strategy_id}")
        if self.position:
            logger.info(f"Final position: {self.position.symbol} {self.position.quantity}")


# 策略注册表
STRATEGY_REGISTRY: Dict[str, type] = {
    "MA": MAStrategy,
    "RSI": RSIStrategy,
}


def register_strategy(name: str, strategy_class: type):
    """注册策略"""
    STRATEGY_REGISTRY[name] = strategy_class


def get_strategy(name: str, **kwargs) -> Strategy:
    """获取策略实例"""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}")
    
    return STRATEGY_REGISTRY[name](**kwargs)


def list_strategies() -> List[str]:
    """列出所有策略"""
    return list(STRATEGY_REGISTRY.keys())
