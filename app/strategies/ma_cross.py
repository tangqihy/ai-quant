"""
MA 均线交叉策略 - 短期均线上穿长期均线买入，下穿卖出
"""
from typing import Dict, List, Any
import pandas as pd
from app.strategies.base import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """双均线金叉/死叉策略"""

    @property
    def strategy_id(self) -> str:
        return "ma_cross"

    @property
    def name(self) -> str:
        return "MA交叉策略"

    @property
    def description(self) -> str:
        return "短期均线上穿长期均线买入，下穿卖出"

    @property
    def param_schema(self) -> List[Dict[str, Any]]:
        return [
            {"name": "short_window", "type": "int", "default": 5, "description": "短期均线周期"},
            {"name": "long_window", "type": "int", "default": 20, "description": "长期均线周期"},
        ]

    def generate_signals(
        self,
        df: pd.DataFrame,
        **params: Any,
    ) -> pd.DataFrame:
        short_window = int(params.get("short_window", 5))
        long_window = int(params.get("long_window", 20))
        df = df.copy()
        df["ma_short"] = df["close"].rolling(window=short_window).mean()
        df["ma_long"] = df["close"].rolling(window=long_window).mean()
        # 金叉：短期上穿长期
        df["buy_signal"] = (df["ma_short"] > df["ma_long"]) & (
            df["ma_short"].shift(1) <= df["ma_long"].shift(1)
        )
        # 死叉：短期下穿长期
        df["sell_signal"] = (df["ma_short"] < df["ma_long"]) & (
            df["ma_short"].shift(1) >= df["ma_long"].shift(1)
        )
        return df
