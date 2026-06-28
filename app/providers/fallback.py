"""
数据源降级管理器

支持主备数据源切换，自动降级，健康检查。
"""
import logging
from typing import List, Dict, Optional, Any
from app.providers.base import DataProvider
from app.core.config import settings
from app.core.exceptions import DataSourceError

logger = logging.getLogger(__name__)


class FallbackDataProvider(DataProvider):
    """
    降级数据源管理器
    
    支持主备数据源切换，主数据源失败时自动降级到备数据源。
    """
    
    def __init__(
        self,
        primary: DataProvider,
        fallback: Optional[DataProvider] = None,
        fallback_on_error: bool = True,
    ):
        """
        初始化降级数据源
        
        Args:
            primary: 主数据源
            fallback: 备数据源（可选）
            fallback_on_error: 主数据源失败时是否降级
        """
        self._primary = primary
        self._fallback = fallback
        self._fallback_on_error = fallback_on_error
        self._primary_healthy = True
        self._fallback_healthy = True if fallback else False
    
    @property
    def primary(self) -> DataProvider:
        """获取主数据源"""
        return self._primary
    
    @property
    def fallback(self) -> Optional[DataProvider]:
        """获取备数据源"""
        return self._fallback
    
    @property
    def is_primary_healthy(self) -> bool:
        """主数据源是否健康"""
        return self._primary_healthy
    
    @property
    def is_fallback_healthy(self) -> bool:
        """备数据源是否健康"""
        return self._fallback_healthy
    
    def _execute_with_fallback(self, method_name: str, *args, **kwargs) -> Any:
        """
        执行数据源方法，支持降级
        
        Args:
            method_name: 方法名
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            数据源返回结果
            
        Raises:
            DataSourceError: 所有数据源都失败时抛出
        """
        # 尝试主数据源
        if self._primary_healthy:
            try:
                method = getattr(self._primary, method_name)
                result = method(*args, **kwargs)
                self._primary_healthy = True
                return result
            except Exception as e:
                logger.warning(f"Primary data source failed for {method_name}: {e}")
                self._primary_healthy = False
                
                # 如果不降级，直接抛出异常
                if not self._fallback_on_error:
                    raise DataSourceError(f"主数据源失败: {e}")
        
        # 尝试备数据源
        if self._fallback and self._fallback_healthy:
            try:
                method = getattr(self._fallback, method_name)
                result = method(*args, **kwargs)
                self._fallback_healthy = True
                logger.info(f"Fallback data source succeeded for {method_name}")
                return result
            except Exception as e:
                logger.warning(f"Fallback data source failed for {method_name}: {e}")
                self._fallback_healthy = False
        
        # 所有数据源都失败
        raise DataSourceError(f"所有数据源都失败，方法: {method_name}")
    
    def get_stock_list(self, market: str = None) -> List[Dict]:
        """获取股票列表"""
        return self._execute_with_fallback("get_stock_list", market)
    
    def get_daily_bars(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        adjust: str = "qfq"
    ) -> List[Dict]:
        """获取日线数据"""
        return self._execute_with_fallback("get_daily_bars", symbol, start_date, end_date, adjust)
    
    def get_minute_bars(
        self, 
        symbol: str, 
        freq: str = "5min",
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """获取分钟线数据"""
        return self._execute_with_fallback("get_minute_bars", symbol, freq, start_date, end_date)
    
    def get_latest_price(self, symbols: List[str]) -> List[Dict]:
        """获取最新价格"""
        return self._execute_with_fallback("get_latest_price", symbols)
    
    def get_realtime_quote(self, symbol: str) -> Dict:
        """获取实时行情"""
        return self._execute_with_fallback("get_realtime_quote", symbol)
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        return self._execute_with_fallback("get_stock_info", symbol)
    
    def get_trading_calendar(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[str]:
        """获取交易日历"""
        return self._execute_with_fallback("get_trading_calendar", start_date, end_date)
    
    def get_adj_factor(
        self, 
        symbol: str, 
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """获取复权因子"""
        return self._execute_with_fallback("get_adj_factor", symbol, start_date, end_date)
    
    def is_trading_day(self, date: str) -> bool:
        """判断是否为交易日"""
        return self._execute_with_fallback("is_trading_day", date)
    
    def get_next_trading_day(self, date: str) -> str:
        """获取下一个交易日"""
        return self._execute_with_fallback("get_next_trading_day", date)
    
    def health_check(self) -> Dict[str, bool]:
        """
        健康检查
        
        Returns:
            Dict[str, bool]: 各数据源健康状态
        """
        result = {
            "primary": self._primary_healthy,
            "fallback": self._fallback_healthy,
        }
        
        # 测试主数据源
        try:
            self._primary.get_stock_list()
            self._primary_healthy = True
        except Exception:
            self._primary_healthy = False
        
        # 测试备数据源
        if self._fallback:
            try:
                self._fallback.get_stock_list()
                self._fallback_healthy = True
            except Exception:
                self._fallback_healthy = False
        
        return result


def create_fallback_provider() -> FallbackDataProvider:
    """
    创建降级数据源
    
    根据配置创建主备数据源组合。
    """
    from app.providers.tushare_provider import TushareProvider
    
    # 创建主数据源
    primary = TushareProvider()
    
    # 创建备数据源（如果配置了）
    fallback = None
    if settings.data_source_fallback == "jqdata":
        try:
            from app.services.jq_data_service import JoinQuantService
            fallback = JoinQuantService()
        except Exception as e:
            logger.warning(f"Failed to create fallback data source: {e}")
    
    return FallbackDataProvider(
        primary=primary,
        fallback=fallback,
        fallback_on_error=True,
    )
