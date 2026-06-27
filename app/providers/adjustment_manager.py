"""
复权管理 - 统一处理前复权、后复权、不复权
"""
from typing import List, Dict, Optional, Tuple
import logging

from .base import MarketDataService

logger = logging.getLogger(__name__)


class AdjustmentManager:
    """
    复权管理器
    
    职责：
    - 统一复权处理
    - 前复权计算
    - 后复权计算
    - 不复权处理
    - 复权因子缓存
    """
    
    def __init__(self, market_data: MarketDataService):
        """
        初始化复权管理器
        
        Args:
            market_data: 市场数据服务
        """
        self._market_data = market_data
        self._adj_factor_cache = {}
    
    def adjust_price(
        self, 
        price: float, 
        adj_factor: float, 
        latest_adj_factor: float, 
        method: str = "qfq"
    ) -> float:
        """
        复权价格计算
        
        Args:
            price: 原始价格
            adj_factor: 当日复权因子
            latest_adj_factor: 最新复权因子
            method: 复权方法 qfq(前复权)/hfq(后复权)/空(不复权)
            
        Returns:
            float: 复权后的价格
        """
        if method == "":
            return price
        
        if method == "qfq":
            # 前复权 = 原始价格 * (当日复权因子 / 最新复权因子)
            factor = adj_factor / latest_adj_factor if latest_adj_factor else 1.0
        elif method == "hfq":
            # 后复权 = 原始价格 * (最新复权因子 / 当日复权因子)
            factor = latest_adj_factor / adj_factor if adj_factor else 1.0
        else:
            return price
        
        return round(price * factor, 2)
    
    def adjust_bars(
        self, 
        bars: List[Dict], 
        symbol: str, 
        method: str = "qfq"
    ) -> List[Dict]:
        """
        对K线数据进行复权处理
        
        Args:
            bars: K线数据列表
            symbol: 股票代码
            method: 复权方法 qfq(前复权)/hfq(后复权)/空(不复权)
            
        Returns:
            List[Dict]: 复权后的K线数据
        """
        if method == "" or not bars:
            return bars
        
        # 获取复权因子
        adj_factors = self._get_adj_factors(symbol, bars)
        
        if not adj_factors:
            logger.warning(f"No adj_factor data for {symbol}, returning original bars")
            return bars
        
        # 获取最新复权因子
        latest_adj = max(adj_factors.values()) if adj_factors else 1.0
        
        # 复权处理
        adjusted_bars = []
        for bar in bars:
            date = bar.get('date', '').replace('-', '')
            adj_factor = adj_factors.get(date, 1.0)
            
            adjusted_bar = bar.copy()
            adjusted_bar['open'] = self.adjust_price(bar['open'], adj_factor, latest_adj, method)
            adjusted_bar['high'] = self.adjust_price(bar['high'], adj_factor, latest_adj, method)
            adjusted_bar['low'] = self.adjust_price(bar['low'], adj_factor, latest_adj, method)
            adjusted_bar['close'] = self.adjust_price(bar['close'], adj_factor, latest_adj, method)
            
            adjusted_bars.append(adjusted_bar)
        
        return adjusted_bars
    
    def get_adj_factor(
        self, 
        symbol: str, 
        date: str
    ) -> float:
        """
        获取指定日期的复权因子
        
        Args:
            symbol: 股票代码
            date: 日期（YYYYMMDD）
            
        Returns:
            float: 复权因子
        """
        date = date.replace('-', '')
        
        # 检查缓存
        cache_key = f"{symbol}_{date}"
        if cache_key in self._adj_factor_cache:
            return self._adj_factor_cache[cache_key]
        
        # 从数据源获取
        adj_data = self._market_data.get_adj_factor(symbol, date, date)
        
        if adj_data:
            adj_factor = adj_data[0].get('adj_factor', 1.0)
            self._adj_factor_cache[cache_key] = adj_factor
            return adj_factor
        
        return 1.0
    
    def _get_adj_factors(
        self, 
        symbol: str, 
        bars: List[Dict]
    ) -> Dict[str, float]:
        """
        获取K线数据对应的复权因子
        
        Args:
            symbol: 股票代码
            bars: K线数据列表
            
        Returns:
            Dict[str, float]: 日期到复权因子的映射
        """
        if not bars:
            return {}
        
        # 获取日期范围
        dates = [bar.get('date', '').replace('-', '') for bar in bars]
        dates = [d for d in dates if d]
        
        if not dates:
            return {}
        
        start_date = min(dates)
        end_date = max(dates)
        
        # 检查缓存
        cache_key = f"{symbol}_{start_date}_{end_date}"
        if cache_key in self._adj_factor_cache:
            return self._adj_factor_cache[cache_key]
        
        # 从数据源获取
        adj_data = self._market_data.get_adj_factor(symbol, start_date, end_date)
        
        result = {}
        for item in adj_data:
            trade_date = item.get('trade_date', '')
            adj_factor = item.get('adj_factor', 1.0)
            result[trade_date] = adj_factor
        
        # 更新缓存
        self._adj_factor_cache[cache_key] = result
        
        return result


# 全局实例（需要在 market_data 初始化后设置）
_adjustment_manager: Optional[AdjustmentManager] = None


def get_adjustment_manager(market_data: MarketDataService = None) -> AdjustmentManager:
    """
    获取复权管理器
    
    Args:
        market_data: 市场数据服务，默认使用全局实例
        
    Returns:
        AdjustmentManager: 复权管理器
    """
    global _adjustment_manager
    
    if _adjustment_manager is None:
        if market_data is None:
            from . import market_data as default_market_data
            market_data = default_market_data
        _adjustment_manager = AdjustmentManager(market_data)
    
    return _adjustment_manager
