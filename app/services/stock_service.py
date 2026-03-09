"""
股票数据服务 - 本地缓存 + 腾讯数据源降级 + K线本地库优先
"""
import warnings
warnings.filterwarnings('ignore')

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
import json
import os

from app.services.kline_store import get as kline_store_get, save as kline_store_save

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
        获取股票列表。支持内存分页，避免一次性加载全部数据到调用方。
        - 当 page 与 page_size 均为 None 时：返回 List[Dict]（保持原有接口）。
        - 当 page、page_size 均传入时：返回 {"data": List[Dict], "total": int}，仅包含当前页数据。
        - search：可选，按代码或名称过滤后再分页。
        """
        cached = cache.get("stock_list", max_age=86400)
        if cached is None:
            local_file = os.path.join(DATA_DIR, "stock_list.json")
            if os.path.exists(local_file):
                with open(local_file, "r", encoding="utf-8") as f:
                    stocks = json.load(f)
                cached = [{"symbol": s["symbol"], "name": s["name"], "market": market} for s in stocks]
            else:
                if ak is None:
                    cached = []
                else:
                    try:
                        df = retry(lambda: ak.stock_info_a_code_name())
                        cached = [
                            {"symbol": row.get("code", ""), "name": row.get("name", ""), "market": market}
                            for _, row in df.iterrows()
                        ]
                    except Exception:
                        cached = []
            cache.set("stock_list", cached)

        if search:
            cached = [s for s in cached if search in s.get("symbol", "") or search in s.get("name", "")]

        total = len(cached)
        if page is not None and page_size is not None:
            start = (page - 1) * page_size
            end = start + page_size
            return {"data": cached[start:end], "total": total}
        return cached

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

        # 2）本地无或未覆盖，从 API 拉取并增量更新
        cache_key = f"history_{symbol}_{start_date}_{end_date}_{adjust}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        if ak is None:
            return []

        try:
            df = retry(lambda: ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_date, end_date=end_date, adjust=adjust
            ), retries=1, delay=1)
            if df is not None and not df.empty:
                klines = StockService._normalize_klines_from_api(df, "em")
                kline_store_save(symbol, klines, adjust)
                cache.set(cache_key, klines)
                return klines
        except Exception:
            pass

        try:
            prefix = "sh" if symbol.startswith("6") else "sz"
            df = retry(lambda: ak.stock_zh_a_daily(
                symbol=f"{prefix}{symbol}", start_date=start_date,
                end_date=end_date, adjust=adjust if adjust else ""
            ))
            klines = StockService._normalize_klines_from_api(df, "daily")
            kline_store_save(symbol, klines, adjust)
            cache.set(cache_key, klines)
            return klines
        except Exception as e:
            raise Exception(f"获取历史K线失败: {str(e)}")

    @staticmethod
    def get_realtime_quotes(symbols: List[str]) -> List[Dict]:
        """并发获取实时行情（腾讯数据源）"""
        if ak is None:
            return []

        cache_key = f"quotes_{'_'.join(sorted(symbols[:5]))}"
        cached = cache.get(cache_key, max_age=120)
        if cached:
            return cached

        # 先试东方财富全量
        try:
            df = retry(lambda: ak.stock_zh_a_spot_em(), retries=1, delay=1)
            if df is not None and not df.empty:
                cache.set("realtime_all", df)
                stocks = df[df["代码"].isin(symbols)]
                results = [{"symbol": r.get("代码", ""), "name": r.get("名称", ""),
                            "price": float(r.get("最新价", 0)), "change_pct": float(r.get("涨跌幅", 0)),
                            "change_amount": float(r.get("涨跌额", 0)), "open": float(r.get("今开", 0)),
                            "high": float(r.get("最高", 0)), "low": float(r.get("最低", 0)),
                            "volume": float(r.get("成交量", 0)), "amount": float(r.get("成交额", 0)),
                            "turnover": float(r.get("换手率", 0))} for _, r in stocks.iterrows()]
                cache.set(cache_key, results)
                return results
        except Exception:
            pass

        # 降级：并发用腾讯数据源逐只获取
        stock_list = StockService.get_stock_list()
        name_map = {s["symbol"]: s["name"] for s in stock_list}

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_single_quote, s): s for s in symbols}
            for future in as_completed(futures):
                s = futures[future]
                try:
                    data = future.result()
                    if data:
                        data["name"] = name_map.get(s, "")
                        results.append(data)
                    else:
                        results.append({"symbol": s, "name": name_map.get(s, ""), "price": 0,
                                        "change_pct": 0, "change_amount": 0, "open": 0, "high": 0,
                                        "low": 0, "volume": 0, "amount": 0, "turnover": 0})
                except Exception:
                    results.append({"symbol": s, "name": name_map.get(s, ""), "price": 0,
                                    "change_pct": 0, "change_amount": 0, "open": 0, "high": 0,
                                    "low": 0, "volume": 0, "amount": 0, "turnover": 0})

        # 按原始顺序排序
        order = {s: i for i, s in enumerate(symbols)}
        results.sort(key=lambda x: order.get(x["symbol"], 999))
        cache.set(cache_key, results)
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
