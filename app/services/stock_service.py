"""
股票数据服务 - 本地缓存 + 腾讯数据源降级
"""
import warnings
warnings.filterwarnings('ignore')

try:
    import akshare as ak
except ImportError:
    ak = None

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import time
import threading
import json
import os

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
    def get_stock_list(market: str = "沪深A股") -> List[Dict]:
        cached = cache.get("stock_list", max_age=86400)
        if cached:
            return cached

        # 优先从本地文件加载
        local_file = os.path.join(DATA_DIR, "stock_list.json")
        if os.path.exists(local_file):
            with open(local_file, "r", encoding="utf-8") as f:
                stocks = json.load(f)
            result = [{"symbol": s["symbol"], "name": s["name"], "market": market} for s in stocks]
            cache.set("stock_list", result)
            return result

        # 降级到 AkShare
        if ak is None:
            return []
        try:
            df = retry(lambda: ak.stock_info_a_code_name())
            stocks = [{"symbol": row.get("code", ""), "name": row.get("name", ""), "market": market}
                      for _, row in df.iterrows()]
            cache.set("stock_list", stocks)
            return stocks
        except Exception:
            return []

    @staticmethod
    def get_stock_history(symbol: str, start_date: Optional[str] = None,
                          end_date: Optional[str] = None, adjust: str = "qfq") -> List[Dict]:
        if ak is None:
            return []

        cache_key = f"history_{symbol}_{start_date}_{end_date}_{adjust}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        # 先试东方财富
        try:
            df = retry(lambda: ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_date, end_date=end_date, adjust=adjust
            ), retries=1, delay=1)
            if df is not None and not df.empty:
                klines = [{"date": str(r.get("日期", "")), "open": float(r.get("开盘", 0)),
                           "close": float(r.get("收盘", 0)), "high": float(r.get("最高", 0)),
                           "low": float(r.get("最低", 0)), "volume": float(r.get("成交量", 0)),
                           "amount": float(r.get("成交额", 0)), "change_pct": float(r.get("涨跌幅", 0)),
                           "turnover": float(r.get("换手率", 0))} for _, r in df.iterrows()]
                cache.set(cache_key, klines)
                return klines
        except Exception:
            pass

        # 降级腾讯
        try:
            prefix = "sh" if symbol.startswith("6") else "sz"
            df = retry(lambda: ak.stock_zh_a_daily(
                symbol=f"{prefix}{symbol}", start_date=start_date,
                end_date=end_date, adjust=adjust if adjust else ""
            ))
            klines = [{"date": str(r.get("date", "")), "open": float(r.get("open", 0)),
                       "close": float(r.get("close", 0)), "high": float(r.get("high", 0)),
                       "low": float(r.get("low", 0)), "volume": float(r.get("volume", 0)),
                       "amount": float(r.get("amount", 0)), "change_pct": 0,
                       "turnover": round(float(r.get("turnover", 0)) * 100, 2)} for _, r in df.iterrows()]
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
