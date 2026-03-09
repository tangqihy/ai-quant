"""
JoinQuant 聚宽数据服务 - 作为 AkShare 的备用/增强数据源
文档: https://www.joinquant.com/help/api/help#name:Stock
"""
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
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

    def get_realtime_quotes(self, symbols: List[str]) -> List[Dict]:
        """获取实时行情"""
        if not self._ensure_auth() or not symbols:
            return []

        try:
            jq_symbols = [self.normalize_symbol(s) for s in symbols]
            # 使用 get_current_data 获取实时数据
            data = jqdatasdk.get_current_data(jq_symbols)

            results = []
            for symbol in jq_symbols:
                if symbol in data:
                    d = data[symbol]
                    results.append({
                        "symbol": self.to_standard_symbol(symbol),
                        "name": d.name,
                        "price": float(d.current),
                        "open": float(d.open),
                        "high": float(d.high),
                        "low": float(d.low),
                        "volume": float(d.volume),
                        "amount": float(d.money) if hasattr(d, 'money') else 0,
                        "change_pct": float(d.pct_change) if hasattr(d, 'pct_change') else 0,
                        "change_amount": float(d.change) if hasattr(d, 'change') else 0,
                        "turnover": float(d.turnover_rate) if hasattr(d, 'turnover_rate') else 0,
                        "source": "joinquant"
                    })
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
            for date, row in df.iterrows():
                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "amount": float(row.get("money", 0)),
                    "change_pct": 0,  # 需要计算
                    "turnover": 0
                })
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
