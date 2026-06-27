"""
交易日历管理 - 统一处理交易日、节假日、开盘时间
"""
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from .base import MarketDataService

logger = logging.getLogger(__name__)


class TradingCalendar:
    """
    交易日历管理器
    
    职责：
    - 判断是否交易日
    - 判断是否开盘
    - 处理节假日
    - 处理提前收盘
    - 获取下一个/上一个交易日
    """
    
    def __init__(self, market_data: MarketDataService):
        """
        初始化交易日历管理器
        
        Args:
            market_data: 市场数据服务
        """
        self._market_data = market_data
        self._cache = {}
    
    def is_trading_day(self, date: str) -> bool:
        """
        判断是否为交易日
        
        Args:
            date: 日期（YYYYMMDD 或 YYYY-MM-DD）
            
        Returns:
            bool: 是否为交易日
        """
        date = self._normalize_date(date)
        
        # 检查缓存
        if date in self._cache:
            return self._cache[date]
        
        result = self._market_data.is_trading_day(date)
        self._cache[date] = result
        
        return result
    
    def is_market_open(self, dt: datetime = None) -> bool:
        """
        判断当前是否开盘
        
        开盘时间：
        - 上午：9:30 - 11:30
        - 下午：13:00 - 15:00
        
        Args:
            dt: 时间，默认当前时间
            
        Returns:
            bool: 是否开盘
        """
        if dt is None:
            dt = datetime.now()
        
        # 判断是否交易日
        date_str = dt.strftime('%Y%m%d')
        if not self.is_trading_day(date_str):
            return False
        
        # 判断是否在交易时间内
        hour = dt.hour
        minute = dt.minute
        time_val = hour * 100 + minute
        
        # 上午：9:30 - 11:30
        if 930 <= time_val <= 1130:
            return True
        
        # 下午：13:00 - 15:00
        if 1300 <= time_val <= 1500:
            return True
        
        return False
    
    def get_next_trading_day(self, date: str) -> str:
        """
        获取下一个交易日
        
        Args:
            date: 日期（YYYYMMDD 或 YYYY-MM-DD）
            
        Returns:
            str: 下一个交易日（YYYYMMDD）
        """
        date = self._normalize_date(date)
        return self._market_data.get_next_trading_day(date)
    
    def get_prev_trading_day(self, date: str) -> str:
        """
        获取上一个交易日
        
        Args:
            date: 日期（YYYYMMDD 或 YYYY-MM-DD）
            
        Returns:
            str: 上一个交易日（YYYYMMDD）
        """
        date = self._normalize_date(date)
        
        # 向前查找
        current = datetime.strptime(date, '%Y%m%d')
        for i in range(10):  # 最多查找10天
            prev_day = current - timedelta(days=i + 1)
            prev_date = prev_day.strftime('%Y%m%d')
            if self.is_trading_day(prev_date):
                return prev_date
        
        return date
    
    def get_trading_days(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[str]:
        """
        获取区间内的所有交易日
        
        Args:
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            
        Returns:
            List[str]: 交易日列表（YYYYMMDD格式）
        """
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        
        return self._market_data.get_trading_calendar(start_date, end_date)
    
    def count_trading_days(
        self, 
        start_date: str, 
        end_date: str
    ) -> int:
        """
        计算区间内的交易日数量
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            int: 交易日数量
        """
        trading_days = self.get_trading_days(start_date, end_date)
        return len(trading_days)
    
    def get_last_trading_day_of_month(self, year: int, month: int) -> str:
        """
        获取某月最后一个交易日
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            str: 最后一个交易日（YYYYMMDD）
        """
        # 获取月末日期
        if month == 12:
            end_date = f"{year + 1}0101"
        else:
            end_date = f"{year}{month + 1:02d}01"
        
        end_dt = datetime.strptime(end_date, '%Y%m%d') - timedelta(days=1)
        end_date = end_dt.strftime('%Y%m%d')
        
        # 向前查找交易日
        for i in range(10):
            check_date = end_dt - timedelta(days=i)
            check_date_str = check_date.strftime('%Y%m%d')
            if self.is_trading_day(check_date_str):
                return check_date_str
        
        return end_date
    
    def get_first_trading_day_of_month(self, year: int, month: int) -> str:
        """
        获取某月第一个交易日
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            str: 第一个交易日（YYYYMMDD）
        """
        start_date = f"{year}{month:02d}01"
        return self.get_next_trading_day(start_date)
    
    def _normalize_date(self, date_str: str) -> str:
        """标准化日期格式为 YYYYMMDD"""
        if not date_str:
            return date_str
        return date_str.replace("-", "")


# 全局实例（需要在 market_data 初始化后设置）
_trading_calendar: Optional[TradingCalendar] = None


def get_trading_calendar(market_data: MarketDataService = None) -> TradingCalendar:
    """
    获取交易日历管理器
    
    Args:
        market_data: 市场数据服务，默认使用全局实例
        
    Returns:
        TradingCalendar: 交易日历管理器
    """
    global _trading_calendar
    
    if _trading_calendar is None:
        if market_data is None:
            from . import market_data as default_market_data
            market_data = default_market_data
        _trading_calendar = TradingCalendar(market_data)
    
    return _trading_calendar
