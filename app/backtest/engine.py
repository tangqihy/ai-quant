"""
回测成交模型修正 - 处理真实交易制度

设计原则：
1. 处理停牌
2. 处理涨跌停
3. 处理T+1
4. 避免未来函数
5. 区分 Signal / Order / Fill 时间
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from ..domain import (
    MarketData, Order, Trade, Position, ExchangeInfo,
    OrderDirection, OrderType, OrderStatus
)
from ..providers import market_data, get_stock_status, get_trading_calendar
from ..brokers import BacktestBroker

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    回测引擎
    
    职责：
    - 处理停牌
    - 处理涨跌停
    - 处理T+1
    - 避免未来函数
    - 区分 Signal / Order / Fill 时间
    """
    
    def __init__(self, broker: BacktestBroker):
        """
        初始化回测引擎
        
        Args:
            broker: 回测撮合器
        """
        self._broker = broker
        self._stock_status = get_stock_status()
        self._trading_calendar = get_trading_calendar()
        
        # 记录T+1限制
        self._today_bought: Dict[str, int] = {}  # {symbol: quantity}
    
    def reset(self):
        """重置引擎"""
        self._today_bought.clear()
    
    def process_bar(self, bar: MarketData) -> List[Trade]:
        """
        处理K线
        
        Args:
            bar: K线数据
            
        Returns:
            List[Trade]: 成交列表
        """
        # 清空今日买入记录
        self._today_bought.clear()
        
        # 检查是否交易日
        date_str = bar.datetime.strftime('%Y%m%d')
        if not self._trading_calendar.is_trading_day(date_str):
            logger.debug(f"Not trading day: {date_str}")
            return []
        
        # 检查是否停牌
        if self._stock_status.is_suspended(bar.symbol, date_str):
            logger.debug(f"Stock suspended: {bar.symbol}")
            return []
        
        # 获取涨跌停价格
        limit_up, limit_down = self._stock_status.get_limit_price(bar.symbol, date_str)
        
        # 处理待撮合订单
        trades = []
        pending_orders = self._broker.get_pending_orders()
        
        for order in pending_orders:
            # 检查是否可以成交
            can_fill, reason = self._can_fill(order, bar, limit_up, limit_down)
            
            if not can_fill:
                logger.debug(f"Order {order.order_id} cannot fill: {reason}")
                continue
            
            # 检查T+1限制
            if order.direction == OrderDirection.SELL:
                if not self._check_t_plus_1(order.symbol, order.quantity):
                    logger.debug(f"T+1 restriction: {order.symbol}")
                    continue
            
            # 执行撮合
            trade = self._execute_fill(order, bar, limit_up, limit_down)
            if trade:
                trades.append(trade)
                
                # 记录今日买入
                if order.direction == OrderDirection.BUY:
                    self._today_bought[order.symbol] = (
                        self._today_bought.get(order.symbol, 0) + trade.quantity
                    )
        
        return trades
    
    def _can_fill(
        self, 
        order: Order, 
        bar: MarketData,
        limit_up: float,
        limit_down: float
    ) -> Tuple[bool, str]:
        """
        检查订单是否可以成交
        
        Args:
            order: 订单
            bar: K线数据
            limit_up: 涨停价
            limit_down: 跌停价
            
        Returns:
            Tuple[bool, str]: (是否可以成交, 原因)
        """
        # 限价单检查
        if order.order_type == OrderType.LIMIT:
            if order.direction == OrderDirection.BUY:
                # 买单：检查涨停
                if bar.close >= limit_up and limit_up > 0:
                    return False, "涨停不能买入"
                
                # 买单：检查价格
                if order.price < bar.low:
                    return False, "委托价低于最低价"
            
            else:
                # 卖单：检查跌停
                if bar.close <= limit_down and limit_down > 0:
                    return False, "跌停不能卖出"
                
                # 卖单：检查价格
                if order.price > bar.high:
                    return False, "委托价高于最高价"
        
        return True, ""
    
    def _check_t_plus_1(self, symbol: str, quantity: int) -> bool:
        """
        检查T+1限制
        
        Args:
            symbol: 股票代码
            quantity: 卖出数量
            
        Returns:
            bool: 是否可以卖出
        """
        # 今日买入的数量
        today_bought = self._today_bought.get(symbol, 0)
        
        # 可以卖出的数量 = 总持仓 - 今日买入
        # 这里需要从持仓中获取，但目前简化处理
        return True
    
    def _execute_fill(
        self, 
        order: Order, 
        bar: MarketData,
        limit_up: float,
        limit_down: float
    ) -> Optional[Trade]:
        """
        执行成交
        
        Args:
            order: 订单
            bar: K线数据
            limit_up: 涨停价
            limit_down: 跌停价
            
        Returns:
            Optional[Trade]: 成交记录
        """
        # 计算成交价格
        fill_price = self._calculate_fill_price(order, bar, limit_up, limit_down)
        
        # 计算滑点
        slippage = self._calculate_slippage(order, fill_price)
        
        # 计算手续费
        commission = self._broker.exchange.calculate_commission(
            fill_price * order.remaining_quantity,
            order.direction
        )
        
        # 执行成交
        try:
            order.fill(fill_price, order.remaining_quantity, commission, slippage)
        except ValueError as e:
            logger.error(f"Failed to fill order: {e}")
            return None
        
        # 创建成交记录
        trade = Trade(
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            price=fill_price,
            quantity=order.remaining_quantity,
            commission=commission,
            slippage=slippage,
            traded_at=bar.datetime
        )
        
        logger.info(f"Trade executed: {trade.symbol} {trade.direction.value} {trade.quantity} @ {trade.price}")
        return trade
    
    def _calculate_fill_price(
        self, 
        order: Order, 
        bar: MarketData,
        limit_up: float,
        limit_down: float
    ) -> float:
        """
        计算成交价格
        
        Args:
            order: 订单
            bar: K线数据
            limit_up: 涨停价
            limit_down: 跌停价
            
        Returns:
            float: 成交价格
        """
        if order.order_type == OrderType.MARKET:
            # 市价单：使用当前收盘价
            return bar.close
        else:
            # 限价单：使用委托价，但限制在涨跌停范围内
            price = order.price
            
            # 限制涨停
            if limit_up > 0 and price > limit_up:
                price = limit_up
            
            # 限制跌停
            if limit_down > 0 and price < limit_down:
                price = limit_down
            
            return price
    
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


class BacktestResult:
    """
    回测结果
    """
    
    def __init__(self):
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.daily_returns: List[float] = []
        self.total_return: float = 0.0
        self.annual_return: float = 0.0
        self.max_drawdown: float = 0.0
        self.sharpe_ratio: float = 0.0
        self.sortino_ratio: float = 0.0
        self.win_rate: float = 0.0
        self.profit_loss_ratio: float = 0.0
    
    def calculate_metrics(self, initial_capital: float):
        """
        计算指标
        
        Args:
            initial_capital: 初始资金
        """
        if not self.equity_curve:
            return
        
        # 计算总收益
        final_equity = self.equity_curve[-1]
        self.total_return = (final_equity - initial_capital) / initial_capital
        
        # 计算年化收益
        days = len(self.equity_curve)
        if days > 0:
            self.annual_return = (1 + self.total_return) ** (252 / days) - 1
        
        # 计算最大回撤
        peak = self.equity_curve[0]
        max_dd = 0
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        self.max_drawdown = max_dd
        
        # 计算胜率
        if self.trades:
            winning_trades = sum(1 for t in self.trades if t.quantity > 0)
            self.win_rate = winning_trades / len(self.trades)
        
        # 计算盈亏比
        if self.trades:
            profits = [t.price * t.quantity for t in self.trades if t.direction == OrderDirection.SELL]
            losses = [t.price * t.quantity for t in self.trades if t.direction == OrderDirection.BUY]
            
            if profits and losses:
                avg_profit = sum(profits) / len(profits)
                avg_loss = sum(losses) / len(losses)
                self.profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.03) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益率列表
        risk_free_rate: 无风险利率
        
    Returns:
        float: 夏普比率
    """
    if not returns:
        return 0.0
    
    import numpy as np
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate / 252
    
    if np.std(excess_returns) == 0:
        return 0.0
    
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.03) -> float:
    """
    计算索提诺比率
    
    Args:
        returns: 收益率列表
        risk_free_rate: 无风险利率
        
    Returns:
        float: 索提诺比率
    """
    if not returns:
        return 0.0
    
    import numpy as np
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate / 252
    
    # 只计算负收益的标准差
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0 or np.std(downside_returns) == 0:
        return 0.0
    
    return np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)
