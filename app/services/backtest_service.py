"""
回测引擎服务
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import random


class BacktestEngine:
    """简单回测引擎"""
    
    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0  # 持仓股数
        self.holdings = []  # 持仓记录
        self.trades = []  # 交易记录
        self.daily_values = []  # 每日资产净值
        
    def run(
        self,
        symbol: str,
        data: List[Dict],
        strategy: str = "ma_cross",
        short_window: int = 5,
        long_window: int = 20
    ) -> Dict:
        """运行回测"""
        if not data:
            return {"error": "No data provided"}
            
        # 转换为DataFrame
        df = pd.DataFrame(data)
        df = df.sort_values('date')
        
        # 计算技术指标
        if strategy == "ma_cross":
            df['ma_short'] = df['close'].rolling(window=short_window).mean()
            df['ma_long'] = df['close'].rolling(window=long_window).mean()
            
        # 初始化
        self.capital = self.initial_capital
        self.position = 0
        self.trades = []
        self.daily_values = []
        
        # 交易信号
        in_position = False
        
        for i, row in df.iterrows():
            date = row.get('date', '')
            close = row.get('close', 0)
            
            # 简单的MA交叉策略
            if strategy == "ma_cross":
                if not in_position and row['ma_short'] > row['ma_long']:
                    # 买入信号
                    shares = int(self.capital * 0.95 / close)
                    if shares > 0:
                        cost = shares * close
                        self.capital -= cost
                        self.position = shares
                        self.trades.append({
                            "date": date,
                            "action": "BUY",
                            "price": close,
                            "shares": shares,
                            "cost": cost
                        })
                        in_position = True
                elif in_position and row['ma_short'] < row['ma_long']:
                    # 卖出信号
                    proceeds = self.position * close
                    self.capital += proceeds
                    self.trades.append({
                        "date": date,
                        "action": "SELL",
                        "price": close,
                        "shares": self.position,
                        "proceeds": proceeds
                    })
                    in_position = False
                    self.position = 0
            
            # 记录每日净值
            position_value = self.position * close
            total_value = self.capital + position_value
            self.daily_values.append({
                "date": date,
                "value": total_value,
                "capital": self.capital,
                "position_value": position_value
            })
            
        # 最终平仓
        if self.position > 0:
            last_price = df.iloc[-1]['close']
            proceeds = self.position * last_price
            self.capital += proceeds
            self.trades.append({
                "date": df.iloc[-1]['date'],
                "action": "SELL",
                "price": last_price,
                "shares": self.position,
                "proceeds": proceeds
            })
            self.position = 0
            
        # 计算绩效指标
        final_value = self.capital
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 计算年化收益率
        if len(self.daily_values) > 0:
            start_date = self.daily_values[0]['date']
            end_date = self.daily_values[-1]['date']
            # 支持多种日期格式
            for fmt in ('%Y%m%d', '%Y-%m-%d'):
                try:
                    d_start = datetime.strptime(start_date, fmt)
                    d_end = datetime.strptime(end_date, fmt)
                    break
                except ValueError:
                    continue
            else:
                d_start = datetime.strptime(start_date[:10], '%Y-%m-%d')
                d_end = datetime.strptime(end_date[:10], '%Y-%m-%d')
            days = (d_end - d_start).days
            years = max(days / 365, 0.01)
            annual_return = ((1 + total_return/100) ** (1/years) - 1) * 100
        else:
            annual_return = 0
            
        # 计算最大回撤
        max_value = self.initial_capital
        max_drawdown = 0
        for dv in self.daily_values:
            if dv['value'] > max_value:
                max_value = dv['value']
            drawdown = (max_value - dv['value']) / max_value * 100
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
            "trades": self.trades[-20:],  # 最近20笔
            "daily_values": self.daily_values[-100:],  # 最近100天
            "win_rate": self._calculate_win_rate()
        }
        
    def _calculate_win_rate(self) -> float:
        """计算胜率"""
        if not self.trades:
            return 0
        # 简单计算：盈利交易/总交易
        wins = 0
        for i in range(0, len(self.trades)-1, 2):
            if i+1 < len(self.trades):
                buy = self.trades[i]
                sell = self.trades[i+1]
                if sell.get('proceeds', 0) > buy.get('cost', 0):
                    wins += 1
        return round(wins / max(len(self.trades)//2, 1) * 100, 2)


# 全局回测引擎实例
backtest_engine = BacktestEngine()


def run_backtest(
    symbol: str,
    data: List[Dict],
    strategy: str = "ma_cross",
    short_window: int = 5,
    long_window: int = 20,
    initial_capital: float = 1000000
) -> Dict:
    """运行回测的入口函数"""
    engine = BacktestEngine(initial_capital)
    return engine.run(symbol, data, strategy, short_window, long_window)
