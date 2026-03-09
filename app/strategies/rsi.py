"""
RSI 策略 - 超卖买入、超买卖出
"""
from typing import Dict, List, Any
import pandas as pd
from app.strategies.base import BaseStrategy


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """计算 RSI 指标"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


class RSIStrategy(BaseStrategy):
    """RSI 超卖超买策略：RSI < 超卖线买入，RSI > 超买线卖出"""

    @property
    def strategy_id(self) -> str:
        return "rsi"

    @property
    def name(self) -> str:
        return "RSI策略"

    @property
    def description(self) -> str:
        return "RSI 超卖时买入、超买时卖出"

    @property
    def param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "period", "type": "int", "default": 14, "description": "RSI 周期"},
            {"name": "oversold", "type": "int", "default": 30, "description": "超卖线，低于此值买入"},
            {"name": "overbought", "type": "int", "default": 70, "description": "超买线，高于此值卖出"},
        ]

    def generate_signals(
        self,
        df: pd.DataFrame,
        **params: Any,
    ) -> pd.DataFrame:
        period = int(params.get("period", 14))
        oversold = int(params.get("oversold", 30))
        overbought = int(params.get("overbought", 70))
        df = df.copy()
        df["rsi"] = _calc_rsi(df["close"], period=period)
        # 从超卖区上穿超卖线：买入
        df["buy_signal"] = (df["rsi"].shift(1) < oversold) & (df["rsi"] >= oversold)
        # 从超买区下穿超买线：卖出
        df["sell_signal"] = (df["rsi"].shift(1) > overbought) & (df["rsi"] <= overbought)
        return df
