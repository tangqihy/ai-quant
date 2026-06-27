"""
数据源抽象层

使用方式：
    from app.providers import market_data, get_trading_calendar, get_adjustment_manager
    
    # 获取市场数据服务
    bars = market_data.get_daily_bars("600519", "20260101", "20260627")
    
    # 获取交易日历
    calendar = get_trading_calendar()
    is_trading = calendar.is_trading_day("20260626")
    
    # 获取复权管理器
    adjustment = get_adjustment_manager()
    adjusted_bars = adjustment.adjust_bars(bars, "600519", "qfq")
"""

from .base import DataProvider, MarketDataService
from .tushare_provider import TushareProvider, tushare_provider
from .trading_calendar import TradingCalendar, get_trading_calendar
from .adjustment_manager import AdjustmentManager, get_adjustment_manager


# 默认使用 Tushare 数据源
_default_provider = tushare_provider


def get_provider() -> DataProvider:
    """获取当前数据源"""
    return _default_provider


def set_provider(provider: DataProvider):
    """设置数据源"""
    global _default_provider
    _default_provider = provider


def get_market_data_service(provider: DataProvider = None) -> MarketDataService:
    """
    获取市场数据服务
    
    Args:
        provider: 数据源实现，默认使用 TushareProvider
        
    Returns:
        MarketDataService: 市场数据服务实例
    """
    if provider is None:
        provider = _default_provider
    return MarketDataService(provider)


# 便捷访问
market_data = get_market_data_service()
