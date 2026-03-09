"""
回测引擎服务 - 向量化计算 + 滑点/手续费
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import random


class BacktestEngine:
    """简单回测引擎（Pandas 向量化 + 滑点/手续费）"""

    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0
        self.holdings = []
        self.trades = []
        self.daily_values = []

    def run(
        self,
        symbol: str,
        data: List[Dict],
        strategy: str = "ma_cross",
        short_window: int = 5,
        long_window: int = 20,
        slippage_bps: int = 5,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
    ) -> Dict:
        """
        运行回测。使用 Pandas 向量化计算信号，再按日应用交易与滑点/手续费。
        slippage_bps: 滑点（基点），买入价=close*(1+slippage_bps/10000)，卖出价=close*(1-slippage_bps/10000)
        commission_rate: 佣金率（按成交金额）
        min_commission: 最低佣金（元）
        """
        if not data:
            return {"error": "No data provided"}

        df = pd.DataFrame(data)
        df = df.sort_values("date").reset_index(drop=True)

        # 向量化计算技术指标
        if strategy == "ma_cross":
            df["ma_short"] = df["close"].rolling(window=short_window).mean()
            df["ma_long"] = df["close"].rolling(window=long_window).mean()
            # 向量化信号：金叉买入、死叉卖出
            df["buy_signal"] = (df["ma_short"] > df["ma_long"]) & (df["ma_short"].shift(1) <= df["ma_long"].shift(1))
            df["sell_signal"] = (df["ma_short"] < df["ma_long"]) & (df["ma_short"].shift(1) >= df["ma_long"].shift(1))
        else:
            df["buy_signal"] = False
            df["sell_signal"] = False

        # 滑点：买入价上浮、卖出价下浮（单位：bps）
        df["buy_price"] = df["close"] * (1 + slippage_bps / 10000.0)
        df["sell_price"] = df["close"] * (1 - slippage_bps / 10000.0)
        df["buy_price"] = df["buy_price"].fillna(df["close"])
        df["sell_price"] = df["sell_price"].fillna(df["close"])

        self.capital = self.initial_capital
        self.position = 0
        self.trades = []
        self.daily_values = []
        in_position = False

        # 按行应用交易逻辑（状态依赖持仓），使用预计算的向量化价格与信号
        for i in range(len(df)):
            row = df.iloc[i]
            date = row.get("date", "")
            close = row["close"]
            buy_price = row["buy_price"]
            sell_price = row["sell_price"]

            if strategy == "ma_cross":
                if not in_position and row["buy_signal"]:
                    shares = int(self.capital * 0.95 / buy_price)
                    if shares > 0:
                        amount = shares * buy_price
                        commission = max(amount * commission_rate, min_commission)
                        self.capital -= amount + commission
                        self.position = shares
                        self.trades.append({
                            "date": date,
                            "action": "BUY",
                            "price": round(buy_price, 2),
                            "shares": shares,
                            "cost": round(amount + commission, 2),
                        })
                        in_position = True
                elif in_position and row["sell_signal"]:
                    proceeds = self.position * sell_price
                    commission = max(proceeds * commission_rate, min_commission)
                    self.capital += proceeds - commission
                    self.trades.append({
                        "date": date,
                        "action": "SELL",
                        "price": round(sell_price, 2),
                        "shares": self.position,
                        "proceeds": round(proceeds - commission, 2),
                    })
                    in_position = False
                    self.position = 0

            position_value = self.position * close
            total_value = self.capital + position_value
            self.daily_values.append({
                "date": date,
                "value": total_value,
                "capital": self.capital,
                "position_value": position_value,
            })

        # 最终平仓
        if self.position > 0:
            last_row = df.iloc[-1]
            sell_price = last_row["sell_price"]
            proceeds = self.position * sell_price
            commission = max(proceeds * commission_rate, min_commission)
            self.capital += proceeds - commission
            self.trades.append({
                "date": last_row["date"],
                "action": "SELL",
                "price": round(sell_price, 2),
                "shares": self.position,
                "proceeds": round(proceeds - commission, 2),
            })
            self.position = 0

        final_value = self.capital
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100

        if len(self.daily_values) > 0:
            start_date = self.daily_values[0]["date"]
            end_date = self.daily_values[-1]["date"]
            s = start_date.replace("-", "")[:8]
            e = end_date.replace("-", "")[:8]
            try:
                d_start = datetime.strptime(s, "%Y%m%d")
                d_end = datetime.strptime(e, "%Y%m%d")
            except ValueError:
                d_start = datetime.strptime(start_date[:10], "%Y-%m-%d")
                d_end = datetime.strptime(end_date[:10], "%Y-%m-%d")
            days = (d_end - d_start).days
            years = max(days / 365, 0.01)
            annual_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100
        else:
            annual_return = 0

        max_value = self.initial_capital
        max_drawdown = 0
        for dv in self.daily_values:
            if dv["value"] > max_value:
                max_value = dv["value"]
            drawdown = (max_value - dv["value"]) / max_value * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "success": True,
            "symbol": symbol,
            "strategy": strategy,
            "initial_capital": self.initial_capital,
            "final_value": round(final_value, 2),
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "total_trades": len(self.trades),
            "trades": self.trades[-20:],
            "daily_values": self.daily_values[-100:],
            "win_rate": self._calculate_win_rate(),
        }

    def _calculate_win_rate(self) -> float:
        """计算胜率（盈利笔数 / 总卖出笔数）"""
        if not self.trades:
            return 0
        wins = 0
        for i in range(0, len(self.trades) - 1, 2):
            if i + 1 < len(self.trades):
                buy = self.trades[i]
                sell = self.trades[i + 1]
                if sell.get("proceeds", 0) > buy.get("cost", 0):
                    wins += 1
        return round(wins / max(len(self.trades) // 2, 1) * 100, 2)


# 全局回测引擎实例
backtest_engine = BacktestEngine()


def run_backtest(
    symbol: str,
    data: List[Dict],
    strategy: str = "ma_cross",
    short_window: int = 5,
    long_window: int = 20,
    initial_capital: float = 1000000,
    slippage_bps: int = 5,
    commission_rate: float = 0.0003,
    min_commission: float = 5.0,
) -> Dict:
    """运行回测的入口函数（含滑点与手续费默认参数）"""
    engine = BacktestEngine(initial_capital)
    return engine.run(
        symbol, data, strategy, short_window, long_window,
        slippage_bps=slippage_bps,
        commission_rate=commission_rate,
        min_commission=min_commission,
    )
