"""
股票数据服务 - 本地缓存 + 腾讯数据源降级 + K线本地库优先
"""
import warnings
import logging
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:
    ak = None

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import time
import threading
import os

from app.services.kline_store import get as kline_store_get, save as kline_store_save
from app.services.stock_list_store import (
    ensure_initialized as stock_list_ensure_initialized,
    get_page as stock_list_get_page,
    get_all as stock_list_get_all,
    get_symbol_name_map as stock_list_get_symbol_name_map,
)
from app.services.jq_data_service import jq_service

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


def retry(func, retries=2, delay=1):
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            if i == retries - 1:
                raise e
            time.sleep(delay)


def _fetch_single_quote(symbol: str) -> Dict:
    """用腾讯数据源获取单只股票最新数据"""
    try:
        prefix = "sh" if symbol.startswith("6") else "sz"
        ts = f"{prefix}{symbol}"
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
        df = ak.stock_zh_a_daily(symbol=ts, start_date=start, end_date=end, adjust="")
        if df.empty:
            return None
        row = df.iloc[-1]
        prev_close = df.iloc[-2]["close"] if len(df) > 1 else row["open"]
        change = row["close"] - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "symbol": symbol,
            "price": float(row["close"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "volume": float(row["volume"]),
            "amount": float(row["amount"]),
            "change_pct": round(change_pct, 2),
            "change_amount": round(change, 2),
            "turnover": round(float(row.get("turnover", 0)) * 100, 2),
        }
    except Exception:
        return None


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
        获取股票列表。优先从本地 SQLite 分页/搜索，避免重复拉取 AkShare。
        - 首次启动或数据过期时自动从 AkShare 拉取并写入本地（每日最多刷新一次）。
        - 当 page 与 page_size 均为 None 时：返回 List[Dict]（保持原有接口）。
        - 当 page、page_size 均传入时：返回 {"data": List[Dict], "total": int}，数据库层分页与搜索。
        """
        def _fetch_from_ak() -> List[Dict]:
            if ak is None:
                return []
            try:
                logger.info("stock_list: fetching full list from AkShare (local empty or stale)")
                df = retry(lambda: ak.stock_info_a_code_name())
                return [
                    {"symbol": row.get("code", ""), "name": row.get("name", ""), "market": market}
                    for _, row in df.iterrows()
                ]
            except Exception:
                return []

        # 分页/搜索请求：仅当缓存未命中时检查并可能拉取 AkShare，避免每次翻页都访问 DB 的 is_stale
        if page is not None and page_size is not None:
            if cache.get(STOCK_LIST_INIT_CACHE_KEY, max_age=STOCK_LIST_INIT_CACHE_TTL) is None:
                stock_list_ensure_initialized(_fetch_from_ak)
                cache.set(STOCK_LIST_INIT_CACHE_KEY, True)
            data, total = stock_list_get_page(page=page, page_size=page_size, search=search, market=market)
            logger.debug("stock_list: served from SQLite page=%s page_size=%s total=%s", page, page_size, total)
            return {"data": data, "total": total}
        stock_list_ensure_initialized(_fetch_from_ak)
        return stock_list_get_all(market=market)

    @staticmethod
    def _normalize_klines_from_api(df, source: str) -> List[Dict]:
        """将 API 返回的 DataFrame 统一为 K 线字典列表"""
        if df is None or df.empty:
            return []
        if source == "em":
            return [
                {"date": str(r.get("日期", "")), "open": float(r.get("开盘", 0)), "close": float(r.get("收盘", 0)),
                 "high": float(r.get("最高", 0)), "low": float(r.get("最低", 0)), "volume": float(r.get("成交量", 0)),
                 "amount": float(r.get("成交额", 0)), "change_pct": float(r.get("涨跌幅", 0)),
                 "turnover": float(r.get("换手率", 0))}
                for _, r in df.iterrows()
            ]
        return [
            {"date": str(r.get("date", "")), "open": float(r.get("open", 0)), "close": float(r.get("close", 0)),
             "high": float(r.get("high", 0)), "low": float(r.get("low", 0)), "volume": float(r.get("volume", 0)),
             "amount": float(r.get("amount", 0)), "change_pct": 0,
             "turnover": round(float(r.get("turnover", 0)) * 100, 2)}
            for _, r in df.iterrows()
        ]

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

        # 2）本地无或未覆盖，从 JoinQuant 拉取（只用 JoinQuant 做回测）
        cache_key = f"history_{symbol}_{start_date}_{end_date}_{adjust}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        # 只用 JoinQuant（历史数据稳定，适合回测）
        try:
            klines = jq_service.get_stock_history(symbol, start_date, end_date, adjust)
            if klines:
                kline_store_save(symbol, klines, adjust)
                cache.set(cache_key, klines)
                return klines
        except Exception as e:
            logger.warning(f"JoinQuant history failed: {e}")
            raise Exception(f"获取历史K线失败: {str(e)}")

    @staticmethod
    def get_realtime_quotes(symbols: List[str]) -> List[Dict]:
        """获取实时行情 - 不显示实时行情，返回空数据占位"""
        if not symbols:
            return []

        # 不获取实时行情，只返回占位数据
        name_map = stock_list_get_symbol_name_map()
        results = []
        for s in symbols:
            results.append({
                "symbol": s,
                "name": name_map.get(s, ""),
                "price": 0,
                "change_pct": 0,
                "change_amount": 0,
                "open": 0,
                "high": 0,
                "low": 0,
                "volume": 0,
                "amount": 0,
                "turnover": 0
            })
        return results

    @staticmethod
    def get_realtime_quote(symbol: str) -> Dict:
        quotes = StockService.get_realtime_quotes([symbol])
        if quotes:
            q = quotes[0]
            q["timestamp"] = datetime.now().isoformat()
            return q
        return {"symbol": symbol, "name": "", "price": 0, "timestamp": datetime.now().isoformat()}

    @staticmethod
    def get_stock_info(symbol: str) -> Dict:
        if ak is None:
            return {"symbol": symbol}
        cache_key = f"info_{symbol}"
        cached = cache.get(cache_key, max_age=3600)
        if cached:
            return cached
        try:
            df = retry(lambda: ak.stock_individual_info_em(symbol=symbol))
            info = {"symbol": symbol}
            for _, row in df.iterrows():
                info[row.get("item", "")] = row.get("value", "")
            cache.set(cache_key, info)
            return info
        except Exception:
            return {"symbol": symbol}


stock_service = StockService()
