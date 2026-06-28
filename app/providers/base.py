"""
数据源抽象层 - 统一数据接口
所有模块（回测、模拟交易、风控、图表）统一访问这一层
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class DataProvider(ABC):
    """
    数据源抽象基类
    
    所有数据源都应实现此接口；当前主路径使用 Tushare。
    业务层不直接依赖具体数据源，而是通过此接口访问数据
    """
    
    @abstractmethod
    def get_stock_list(self, market: str = None) -> List[Dict]:
        """
        获取股票列表
        
        Args:
            market: 市场筛选（主板/创业板/科创板/北交所）
            
        Returns:
            List[Dict]: 股票列表，每项包含 symbol, name, ts_code, industry 等
        """
        pass
    
    @abstractmethod
    def get_daily_bars(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        adjust: str = "qfq"
    ) -> List[Dict]:
        """
        获取日线数据
        
        Args:
            symbol: 股票代码（如 600519）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            adjust: 复权类型 qfq(前复权)/hfq(后复权)/空(不复权)
            
        Returns:
            List[Dict]: K线数据，每项包含 date, open, high, low, close, volume, amount
        """
        pass
    
    @abstractmethod
    def get_minute_bars(
        self, 
        symbol: str, 
        freq: str = "5min",
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        获取分钟线数据
        
        Args:
            symbol: 股票代码
            freq: 频率（1min/5min/15min/30min/60min）
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[Dict]: 分钟线数据
        """
        pass
    
    @abstractmethod
    def get_latest_price(self, symbols: List[str]) -> List[Dict]:
        """
        获取最新价格（用于模拟交易/持仓估值）
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            List[Dict]: 最新价格，每项包含 symbol, price, change_pct 等
        """
        pass
    
    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> Dict:
        """
        获取实时行情（盘中监控）
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 实时行情数据
        """
        pass
    
    @abstractmethod
    def get_stock_info(self, symbol: str) -> Dict:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 股票信息（名称、行业、地区等）
        """
        pass
    
    @abstractmethod
    def get_trading_calendar(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[str]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            
        Returns:
            List[str]: 交易日列表（YYYYMMDD格式）
        """
        pass
    
    @abstractmethod
    def get_adj_factor(
        self, 
        symbol: str, 
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        获取复权因子
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[Dict]: 复权因子，每项包含 trade_date, adj_factor
        """
        pass
    
    @abstractmethod
    def is_trading_day(self, date: str) -> bool:
        """
        判断是否为交易日
        
        Args:
            date: 日期（YYYYMMDD）
            
        Returns:
            bool: 是否为交易日
        """
        pass
    
    @abstractmethod
    def get_next_trading_day(self, date: str) -> str:
        """
        获取下一个交易日
        
        Args:
            date: 日期（YYYYMMDD）
            
        Returns:
            str: 下一个交易日（YYYYMMDD）
        """
        pass


class MarketDataService:
    """
    市场数据服务 - 统一数据访问入口
    
    所有模块通过此类访问数据，不直接使用具体的数据源
    
    使用方式：
        market_data = MarketDataService(provider)
        bars = market_data.get_daily_bars("600519", "20260101", "20260627")
    """
    
    def __init__(self, provider: DataProvider):
        """
        初始化市场数据服务
        
        Args:
            provider: 数据源实现
        """
        self._provider = provider
        self._cache = {}
    
    @property
    def provider(self) -> DataProvider:
        """获取当前数据源"""
        return self._provider
    
    def get_stock_list(self, market: str = None) -> List[Dict]:
        """获取股票列表"""
        return self._provider.get_stock_list(market)
    
    def get_daily_bars(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        adjust: str = "qfq"
    ) -> List[Dict]:
        """
        获取日线数据
        
        自动处理：
        - 日期格式标准化
        - 复权处理
        """
        # 标准化日期格式
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        
        return self._provider.get_daily_bars(symbol, start_date, end_date, adjust)
    
    def get_minute_bars(
        self, 
        symbol: str, 
        freq: str = "5min",
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """获取分钟线数据"""
        return self._provider.get_minute_bars(symbol, freq, start_date, end_date)
    
    def get_latest_price(self, symbols: List[str]) -> List[Dict]:
        """获取最新价格"""
        return self._provider.get_latest_price(symbols)
    
    def get_realtime_quote(self, symbol: str) -> Dict:
        """获取实时行情"""
        return self._provider.get_realtime_quote(symbol)
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        return self._provider.get_stock_info(symbol)
    
    def get_trading_calendar(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[str]:
        """获取交易日历"""
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        
        return self._provider.get_trading_calendar(start_date, end_date)
    
    def get_adj_factor(
        self, 
        symbol: str, 
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """获取复权因子"""
        return self._provider.get_adj_factor(symbol, start_date, end_date)
    
    def is_trading_day(self, date: str) -> bool:
        """判断是否为交易日"""
        date = self._normalize_date(date)
        return self._provider.is_trading_day(date)
    
    def get_next_trading_day(self, date: str) -> str:
        """获取下一个交易日"""
        date = self._normalize_date(date)
        return self._provider.get_next_trading_day(date)
    
    def _normalize_date(self, date_str: str) -> str:
        """
        标准化日期格式为 YYYYMMDD
        
        支持输入：
        - YYYYMMDD
        - YYYY-MM-DD
        """
        if not date_str:
            return date_str
        return date_str.replace("-", "")
