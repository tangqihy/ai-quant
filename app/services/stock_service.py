"""
股票数据服务 - 带缓存和重试
"""
import warnings
warnings.filterwarnings('ignore')

try:
    import akshare as ak
except ImportError:
    ak = None

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import time
import threading


class DataCache:
    """简单的内存缓存"""
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


def retry(func, retries=3, delay=1):
    """重试装饰器"""
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            if i == retries - 1:
                raise e
            time.sleep(delay * (i + 1))


class StockService:
    """股票数据服务类"""

    @staticmethod
    def get_stock_list(market: str = "沪深A股") -> List[Dict]:
        if ak is None:
            raise Exception("AkShare 未安装")

        cached = cache.get(f"stock_list_{market}", max_age=3600)
        if cached:
            return cached

        try:
            df = retry(lambda: ak.stock_info_a_code_name())
            stocks = [
                {"symbol": row.get("code", ""), "name": row.get("name", ""), "market": market}
                for _, row in df.iterrows()
            ]
            cache.set(f"stock_list_{market}", stocks)
            return stocks
        except Exception as e:
            raise Exception(f"获取股票列表失败: {str(e)}")

    @staticmethod
    def get_stock_history(
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq"
    ) -> List[Dict]:
        if ak is None:
            raise Exception("AkShare 未安装")

        cache_key = f"history_{symbol}_{start_date}_{end_date}_{adjust}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

        try:
            df = retry(lambda: ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_date, end_date=end_date, adjust=adjust
            ))

            klines = []
            for _, row in df.iterrows():
                klines.append({
                    "date": str(row.get("日期", "")),
                    "open": float(row.get("开盘", 0)),
                    "close": float(row.get("收盘", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "volume": float(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                    "amplitude": float(row.get("振幅", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "change_amount": float(row.get("涨跌额", 0)),
                    "turnover": float(row.get("换手率", 0))
                })
            cache.set(cache_key, klines)
            return klines
        except Exception as e:
            raise Exception(f"获取历史K线失败: {str(e)}")

    @staticmethod
    def get_realtime_quote(symbol: str) -> Dict:
        if ak is None:
            raise Exception("AkShare 未安装")

        # 复用批量行情的缓存
        cached = cache.get("realtime_all", max_age=60)
        if cached is None:
            try:
                df = retry(lambda: ak.stock_zh_a_spot_em(), retries=2, delay=2)
                cache.set("realtime_all", df)
                cached = df
            except Exception:
                return {"symbol": symbol, "name": "", "price": 0, "change_pct": 0,
                        "change_amount": 0, "open": 0, "high": 0, "low": 0,
                        "volume": 0, "amount": 0, "amplitude": 0, "turnover": 0,
                        "pe": None, "pb": None, "market_cap": None,
                        "circulating_cap": None, "timestamp": datetime.now().isoformat()}

        stock = cached[cached["代码"] == symbol]
        if stock.empty:
            raise ValueError(f"未找到股票: {symbol}")

        row = stock.iloc[0]
        return {
            "symbol": symbol,
            "name": row.get("名称", ""),
            "price": float(row.get("最新价", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "change_amount": float(row.get("涨跌额", 0)),
            "open": float(row.get("今开", 0)),
            "high": float(row.get("最高", 0)),
            "low": float(row.get("最低", 0)),
            "volume": float(row.get("成交量", 0)),
            "amount": float(row.get("成交额", 0)),
            "amplitude": float(row.get("振幅", 0)),
            "turnover": float(row.get("换手率", 0)),
            "pe": float(row.get("市盈率-动态", 0)) if pd.notna(row.get("市盈率-动态")) else None,
            "pb": float(row.get("市净率", 0)) if pd.notna(row.get("市净率")) else None,
            "market_cap": float(row.get("总市值", 0)) if pd.notna(row.get("总市值")) else None,
            "circulating_cap": float(row.get("流通市值", 0)) if pd.notna(row.get("流通市值")) else None,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def get_realtime_quotes(symbols: List[str]) -> List[Dict]:
        if ak is None:
            raise Exception("AkShare 未安装")

        cached = cache.get("realtime_all", max_age=60)
        if cached is None:
            try:
                df = retry(lambda: ak.stock_zh_a_spot_em(), retries=2, delay=2)
                cache.set("realtime_all", df)
                cached = df
            except Exception:
                # 降级：返回空行情，不阻塞页面
                return [{"symbol": s, "name": "", "price": 0, "change_pct": 0,
                         "change_amount": 0, "open": 0, "high": 0, "low": 0,
                         "volume": 0, "amount": 0, "turnover": 0} for s in symbols]

        stocks = cached[cached["代码"].isin(symbols)]
        results = []
        for _, row in stocks.iterrows():
            results.append({
                "symbol": row.get("代码", ""),
                "name": row.get("名称", ""),
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
                "change_amount": float(row.get("涨跌额", 0)),
                "open": float(row.get("今开", 0)),
                "high": float(row.get("最高", 0)),
                "low": float(row.get("最低", 0)),
                "volume": float(row.get("成交量", 0)),
                "amount": float(row.get("成交额", 0)),
                "turnover": float(row.get("换手率", 0)),
            })
        return results

    @staticmethod
    def get_stock_info(symbol: str) -> Dict:
        if ak is None:
            raise Exception("AkShare 未安装")

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
        except Exception as e:
            raise Exception(f"获取股票信息失败: {str(e)}")


stock_service = StockService()
