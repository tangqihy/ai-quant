"""
数据源抽象层

使用方式：
    from app.providers import get_market_data_service, tushare_provider
    
    # 获取市场数据服务
    market_data = get_market_data_service()
    
    # 使用统一接口获取数据
    bars = market_data.get_daily_bars("600519", "20260101", "20260627")
    stocks = market_data.get_stock_list()
"""

from .base import DataProvider, MarketDataService
from .tushare_provider import TushareProvider, tushare_provider


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
