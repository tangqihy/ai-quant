"""
JoinQuant 聚宽数据服务 - 作为 AkShare 的备用/增强数据源
文档: https://www.joinquant.com/help/api/help#name:Stock

注意: 免费账号有以下限制:
- 只能获取 2024-11-30 至 2025-12-07 的数据
- 无法使用 get_current_tick (需要付费)
- 可以使用 get_price 获取日/分钟级数据
"""
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

# JoinQuant SDK
jqdatasdk = None
try:
    import jqdatasdk as jqd
    jqdatasdk = jqd
except ImportError:
    logger.warning("jqdatasdk not installed, JoinQuant data source unavailable")


class JoinQuantService:
    """JoinQuant 数据服务"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if JoinQuantService._initialized:
            return
        self.username = os.getenv("JQ_USERNAME", "")
        self.password = os.getenv("JQ_PASSWORD", "")
        self._auth = False
        JoinQuantService._initialized = True

    def _ensure_auth(self) -> bool:
        """确保已登录"""
        if not jqdatasdk:
            return False
        if self._auth:
            return True
        if not self.username or not self.password:
            logger.warning("JQ_USERNAME or JQ_PASSWORD not set")
            return False
        try:
            jqdatasdk.auth(self.username, self.password)
            self._auth = True
            logger.info("JoinQuant auth success")
            return True
        except Exception as e:
            logger.error(f"JoinQuant auth failed: {e}")
            return False

    def normalize_symbol(self, symbol: str) -> str:
        """将股票代码转换为 JoinQuant 格式"""
        # JoinQuant 格式: 000001.XSHE (深市) / 600000.XSHG (沪市)
        if ".XSHE" in symbol or ".XSHG" in symbol:
            return symbol
        if symbol.startswith("6"):
            return f"{symbol}.XSHG"
        return f"{symbol}.XSHE"

    def to_standard_symbol(self, jq_symbol: str) -> str:
        """将 JoinQuant 格式转换为标准代码"""
        return jq_symbol.split(".")[0]

    def _get_valid_date_range(self) -> tuple:
        """获取账号允许的有效日期范围"""
        # 免费账号限制: 2024-11-30 至 2025-12-07
        # 使用固定日期确保在有效范围内
        end_date = "2025-03-10"
        start_date = "2025-03-05"
        return start_date, end_date

    def get_realtime_quotes(self, symbols: List[str]) -> List[Dict]:
        """获取实时行情 - 使用 get_price 获取最新分钟数据"""
        if not self._ensure_auth() or not symbols:
            return []

        try:
            jq_symbols = [self.normalize_symbol(s) for s in symbols]
            # 使用固定日期（账号限制只能获取到2025年的数据）
            today = "2025-03-10"

            results = []
            for jq_symbol in jq_symbols:
                try:
                    # 获取当日分钟数据，取最后一根作为最新价格
                    df = jqdatasdk.get_price(
                        jq_symbol,
                        start_date=f"{today} 09:30:00",
                        end_date=f"{today} 15:00:00",
                        frequency='1m',
                        fields=['open', 'high', 'low', 'close', 'volume'],
                        skip_paused=True
                    )

                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        prev_close = df.iloc[0]['close'] if len(df) > 1 else latest['close']
                        change = latest['close'] - prev_close
                        change_pct = (change / prev_close * 100) if prev_close else 0

                        results.append({
                            "symbol": self.to_standard_symbol(jq_symbol),
                            "name": "",  # 需要单独获取
                            "price": float(latest['close']),
                            "open": float(latest['open']),
                            "high": float(latest['high']),
                            "low": float(latest['low']),
                            "volume": float(latest['volume']),
                            "amount": 0,
                            "change_pct": round(change_pct, 2),
                            "change_amount": round(change, 2),
                            "turnover": 0,
                            "source": "joinquant"
                        })
                except Exception as e:
                    logger.warning(f"JoinQuant get price for {jq_symbol} failed: {e}")
                    continue

            return results
        except Exception as e:
            logger.error(f"JoinQuant get_realtime_quotes failed: {e}")
            return []

    def get_stock_history(self, symbol: str, start_date: str, end_date: str,
                          adjust: str = "qfq") -> List[Dict]:
        """获取历史K线"""
        if not self._ensure_auth():
            return []

        try:
            jq_symbol = self.normalize_symbol(symbol)
            # 转换复权类型
            jq_adjust = "post" if adjust == "qfq" else ("pre" if adjust == "hfq" else None)

            # 确保日期在有效范围内
            valid_start, valid_end = self._get_valid_date_range()
            if start_date < valid_start:
                start_date = valid_start
            if end_date > valid_end:
                end_date = valid_end

            df = jqdatasdk.get_price(
                jq_symbol,
                start_date=start_date,
                end_date=end_date,
                frequency="daily",
                fields=["open", "high", "low", "close", "volume", "money"],
                skip_paused=True,
                fq=jq_adjust
            )

            if df is None or df.empty:
                return []

            results = []
            prev_close = None
            for date, row in df.iterrows():
                close = float(row["close"])
                change_pct = 0
                if prev_close:
                    change_pct = round((close - prev_close) / prev_close * 100, 2)

                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": close,
                    "volume": float(row["volume"]),
                    "amount": float(row.get("money", 0)),
                    "change_pct": change_pct,
                    "turnover": 0
                })
                prev_close = close

            return results
        except Exception as e:
            logger.error(f"JoinQuant get_stock_history failed: {e}")
            return []

    def get_all_stocks(self) -> List[Dict]:
        """获取所有股票列表"""
        if not self._ensure_auth():
            return []

        try:
            # 获取所有股票
            stocks = jqdatasdk.get_all_securities(types=['stock'], date=datetime.now())
            results = []
            for code, row in stocks.iterrows():
                results.append({
                    "symbol": self.to_standard_symbol(code),
                    "name": row["display_name"],
                    "market": "沪深A股"
                })
            return results
        except Exception as e:
            logger.error(f"JoinQuant get_all_stocks failed: {e}")
            return []


# 全局实例
jq_service = JoinQuantService()
