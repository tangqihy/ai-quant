"""
股票状态管理 - 统一处理停牌、ST、退市、涨跌停
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from .base import MarketDataService
from .trading_calendar import TradingCalendar, get_trading_calendar

logger = logging.getLogger(__name__)


class StockStatus:
    """
    股票状态管理器
    
    职责：
    - 判断是否停牌
    - 判断是否ST
    - 判断是否退市
    - 判断是否涨跌停
    - 获取涨跌停价格
    """
    
    def __init__(self, market_data: MarketDataService):
        """
        初始化股票状态管理器
        
        Args:
            market_data: 市场数据服务
        """
        self._market_data = market_data
        self._cache = {}
    
    def is_suspended(self, symbol: str, date: str = None) -> bool:
        """
        判断是否停牌
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否停牌
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        date = self._normalize_date(date)
        cache_key = f"suspended_{symbol}_{date}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 获取最近的K线数据，如果没有数据则认为停牌
        try:
            bars = self._market_data.get_daily_bars(symbol, date, date)
            result = len(bars) == 0
        except Exception:
            result = True
        
        self._cache[cache_key] = result
        return result
    
    def is_st(self, symbol: str, date: str = None) -> bool:
        """
        判断是否ST股票
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否ST
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        date = self._normalize_date(date)
        cache_key = f"st_{symbol}_{date}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 通过股票名称判断是否ST
        try:
            info = self._market_data.get_stock_info(symbol)
            name = info.get('name', '')
            result = 'ST' in name or '*ST' in name
        except Exception:
            result = False
        
        self._cache[cache_key] = result
        return result
    
    def is_delisted(self, symbol: str, date: str = None) -> bool:
        """
        判断是否退市
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否退市
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        date = self._normalize_date(date)
        cache_key = f"delisted_{symbol}_{date}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 通过股票名称判断是否退市
        try:
            info = self._market_data.get_stock_info(symbol)
            name = info.get('name', '')
            result = '退' in name
        except Exception:
            result = False
        
        self._cache[cache_key] = result
        return result
    
    def is_limit_up(self, symbol: str, date: str = None) -> bool:
        """
        判断是否涨停
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否涨停
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        date = self._normalize_date(date)
        
        try:
            # 获取当日K线
            bars = self._market_data.get_daily_bars(symbol, date, date)
            
            if not bars:
                return False
            
            bar = bars[0]
            close = bar.get('close', 0)
            pre_close = bar.get('close', 0) - bar.get('change_amount', 0)
            
            if pre_close <= 0:
                return False
            
            # 计算涨跌幅
            change_pct = (close - pre_close) / pre_close * 100
            
            # ST股票涨跌停限制5%，其他限制10%
            limit_pct = 5 if self.is_st(symbol, date) else 10
            
            return change_pct >= limit_pct - 0.01  # 允许小误差
            
        except Exception:
            return False
    
    def is_limit_down(self, symbol: str, date: str = None) -> bool:
        """
        判断是否跌停
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否跌停
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        date = self._normalize_date(date)
        
        try:
            # 获取当日K线
            bars = self._market_data.get_daily_bars(symbol, date, date)
            
            if not bars:
                return False
            
            bar = bars[0]
            close = bar.get('close', 0)
            pre_close = bar.get('close', 0) - bar.get('change_amount', 0)
            
            if pre_close <= 0:
                return False
            
            # 计算涨跌幅
            change_pct = (close - pre_close) / pre_close * 100
            
            # ST股票涨跌停限制5%，其他限制10%
            limit_pct = 5 if self.is_st(symbol, date) else 10
            
            return change_pct <= -(limit_pct - 0.01)  # 允许小误差
            
        except Exception:
            return False
    
    def get_limit_price(
        self, 
        symbol: str, 
        date: str = None
    ) -> Tuple[float, float]:
        """
        获取涨跌停价格
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            Tuple[float, float]: (涨停价, 跌停价)
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        date = self._normalize_date(date)
        
        try:
            # 获取前一日收盘价
            trading_calendar = get_trading_calendar(self._market_data)
            prev_date = trading_calendar.get_prev_trading_day(date)
            
            bars = self._market_data.get_daily_bars(symbol, prev_date, prev_date)
            
            if not bars:
                return (0, 0)
            
            pre_close = bars[0].get('close', 0)
            
            if pre_close <= 0:
                return (0, 0)
            
            # ST股票涨跌停限制5%，其他限制10%
            limit_pct = 5 if self.is_st(symbol, date) else 10
            
            # 计算涨跌停价格（四舍五入到分）
            limit_up = round(pre_close * (1 + limit_pct / 100), 2)
            limit_down = round(pre_close * (1 - limit_pct / 100), 2)
            
            return (limit_up, limit_down)
            
        except Exception as e:
            logger.error(f"Failed to get limit price for {symbol}: {e}")
            return (0, 0)
    
    def can_buy(self, symbol: str, date: str = None) -> bool:
        """
        判断是否可以买入
        
        买入限制：
        - 停牌不能买
        - 涨停不能买
        - 退市不能买
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否可以买入
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        # 停牌不能买
        if self.is_suspended(symbol, date):
            return False
        
        # 涨停不能买
        if self.is_limit_up(symbol, date):
            return False
        
        # 退市不能买
        if self.is_delisted(symbol, date):
            return False
        
        return True
    
    def can_sell(self, symbol: str, date: str = None) -> bool:
        """
        判断是否可以卖出
        
        卖出限制：
        - 停牌不能卖
        - 跌停不能卖
        
        Args:
            symbol: 股票代码
            date: 日期，默认今天
            
        Returns:
            bool: 是否可以卖出
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        # 停牌不能卖
        if self.is_suspended(symbol, date):
            return False
        
        # 跌停不能卖
        if self.is_limit_down(symbol, date):
            return False
        
        return True
    
    def _normalize_date(self, date_str: str) -> str:
        """标准化日期格式为 YYYYMMDD"""
        if not date_str:
            return date_str
        return date_str.replace("-", "")


# 全局实例（需要在 market_data 初始化后设置）
_stock_status: Optional[StockStatus] = None


def get_stock_status(market_data: MarketDataService = None) -> StockStatus:
    """
    获取股票状态管理器
    
    Args:
        market_data: 市场数据服务，默认使用全局实例
        
    Returns:
        StockStatus: 股票状态管理器
    """
    global _stock_status
    
    if _stock_status is None:
        if market_data is None:
            from . import market_data as default_market_data
            market_data = default_market_data
        _stock_status = StockStatus(market_data)
    
    return _stock_status
