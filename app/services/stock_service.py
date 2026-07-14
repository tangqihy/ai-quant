"""
股票数据服务 - Tushare + 本地缓存 + K线本地库优先
"""
import logging

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import time
import threading
import os

logger = logging.getLogger(__name__)

from app.services.kline_store import get as kline_store_get, save as kline_store_save
from app.services.stock_list_store import (
    ensure_initialized as stock_list_ensure_initialized,
    get_page as stock_list_get_page,
    get_all as stock_list_get_all,
    get_symbol_name_map as stock_list_get_symbol_name_map,
)
from app.services.tushare_service import tushare_service

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


class DataCache:
    """内存缓存"""
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key: str, max_age: int = 300):
        with self._lock:
            if key in self._cache:
                data, ts = self._cache[key]
                if time.time() - ts < max_age:
                    return data
        return None

    def set(self, key: str, data):
        with self._lock:
            self._cache[key] = (data, time.time())


# 股票列表「已初始化」检查缓存：60 秒内不重复调 ensure_initialized，避免每次翻页都走 is_stale()/get_last_updated
STOCK_LIST_INIT_CACHE_KEY = "stock_list_initialized"
STOCK_LIST_INIT_CACHE_TTL = 60

cache = DataCache()


class StockService:
    """股票数据服务"""

    @staticmethod
    def get_stock_list(
        market: str = "沪深A股",
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Union[List[Dict], Dict]:
        """
        获取股票列表。优先从本地 SQLite 分页/搜索，避免重复拉取 Tushare。
        - 首次启动或数据过期时自动从 Tushare 拉取并写入本地（每日最多刷新一次）。
        - 当 page 与 page_size 均为 None 时：返回 List[Dict]（保持原有接口）。
        - 当 page、page_size 均传入时：返回 {"data": List[Dict], "total": int}，数据库层分页与搜索。
        """
        def _fetch_from_tushare() -> List[Dict]:
            """从 Tushare 获取股票列表"""
            try:
                logger.info("stock_list: fetching full list from Tushare (local empty or stale)")
                data = tushare_service.get_stock_list()
                return [
                    {"symbol": item.get("symbol", ""), "name": item.get("name", ""), "market": market}
                    for item in data
                ]
            except Exception as e:
                logger.warning(f"Tushare stock_list failed: {e}")
                return []

        # 分页/搜索请求：仅当缓存未命中时检查并可能拉取 Tushare，避免每次翻页都访问 DB 的 is_stale
        if page is not None and page_size is not None:
            if cache.get(STOCK_LIST_INIT_CACHE_KEY, max_age=STOCK_LIST_INIT_CACHE_TTL) is None:
                stock_list_ensure_initialized(_fetch_from_tushare)
                cache.set(STOCK_LIST_INIT_CACHE_KEY, True)
            data, total = stock_list_get_page(page=page, page_size=page_size, search=search, market=market)
            logger.debug("stock_list: served from SQLite page=%s page_size=%s total=%s", page, page_size, total)
            return {"data": data, "total": total}
        stock_list_ensure_initialized(_fetch_from_tushare)
        return stock_list_get_all(market=market)

    @staticmethod
    def get_stock_history(symbol: str, start_date: Optional[str] = None,
                          end_date: Optional[str] = None, adjust: str = "qfq") -> List[Dict]:
        """获取历史 K 线。优先从本地 SQLite 读取；缺失或未覆盖时从 API 拉取并增量写入。"""
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        # 1）优先查本地数据库
        local = kline_store_get(symbol=symbol, start_date=start_date, end_date=end_date, adjust=adjust)
        if local:
            first_date = local[0]["date"]
            last_date = local[-1]["date"]
            if (not start_date or first_date <= start_date) and (not end_date or last_date >= end_date):
                cache_key = f"history_{symbol}_{start_date}_{end_date}_{adjust}"
                cache.set(cache_key, local, max_age=600)
                return local

        # 2）本地无或未覆盖，从 Tushare 拉取
        cache_key = f"history_{symbol}_{start_date}_{end_date}_{adjust}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        # 使用 Tushare 获取历史数据（免费、稳定、无日期限制）
        try:
            klines = tushare_service.get_stock_history(symbol, start_date, end_date, adjust)
            if klines:
                kline_store_save(symbol, klines, adjust)
                cache.set(cache_key, klines)
                return klines
        except Exception as e:
            logger.warning(f"Tushare history failed: {e}")
            raise Exception(f"获取历史K线失败: {str(e)}")

    @staticmethod
    def get_realtime_quotes(symbols: List[str]) -> List[Dict]:
        """获取实时行情 - 使用 Tushare 最新日线数据"""
        if not symbols:
            return []

        try:
            # 使用 tushare 获取最新行情
            results = tushare_service.get_realtime_quotes(symbols)
            
            # 填充股票名称
            name_map = stock_list_get_symbol_name_map()
            for item in results:
                if not item.get('name'):
                    item['name'] = name_map.get(item['symbol'], '')
                item['is_delayed'] = True
                item['delay_note'] = '当前为日线近似行情，非逐笔实时'

            result_map = {item.get("symbol"): item for item in results}
            return [
                result_map.get(symbol) or StockService._empty_quote(symbol, name_map.get(symbol, ""))
                for symbol in symbols
            ]
        except Exception as e:
            logger.warning(f"Tushare realtime quotes failed: {e}")
            
            # Tushare 不可用时返回占位数据，保持响应结构稳定。
            name_map = stock_list_get_symbol_name_map()
            return [StockService._empty_quote(s, name_map.get(s, "")) for s in symbols]

    @staticmethod
    def get_realtime_quote(symbol: str) -> Dict:
        quotes = StockService.get_realtime_quotes([symbol])
        if quotes:
            q = quotes[0]
            q["timestamp"] = datetime.now().isoformat()
            return q
        return {"symbol": symbol, "name": "", "price": 0, "timestamp": datetime.now().isoformat()}

    @staticmethod
    def _empty_quote(symbol: str, name: str = "") -> Dict:
        """构造无行情时的稳定占位响应。"""
        return {
            "symbol": symbol,
            "name": name,
            "price": 0,
            "change_pct": 0,
            "change_amount": 0,
            "open": 0,
            "high": 0,
            "low": 0,
            "volume": 0,
            "amount": 0,
            "turnover": 0,
            "is_delayed": True,
            "delay_note": "当前为日线近似行情，非逐笔实时",
        }

    @staticmethod
    def get_stock_info(symbol: str) -> Dict:
        cache_key = f"info_{symbol}"
        cached = cache.get(cache_key, max_age=3600)
        if cached:
            return cached
        
        try:
            info = tushare_service.get_stock_info(symbol)
            cache.set(cache_key, info)
            return info
        except Exception as e:
            logger.warning(f"Tushare stock info failed: {e}")
            return {"symbol": symbol}


stock_service = StockService()
