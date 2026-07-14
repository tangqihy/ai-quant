"""策略模块。

回测 API 当前使用 BaseStrategy 体系（generate_signals），Trading Core 策略
保留为后续模拟/实盘迁移入口。
"""

from typing import Dict, List, Optional

from .base import BaseStrategy
from .ma_cross import MACrossStrategy
from .rsi import RSIStrategy as BacktestRSIStrategy
from .strategy import (
    Strategy,
    MAStrategy,
    RSIStrategy,
    STRATEGY_REGISTRY,
    register_strategy,
    get_strategy as get_trading_strategy,
    list_strategies as list_trading_strategies,
)


_BACKTEST_STRATEGIES: Dict[str, BaseStrategy] = {
    "ma_cross": MACrossStrategy(),
    "rsi": BacktestRSIStrategy(),
}

_TRADING_STRATEGY_ALIAS = {
    "ma_cross": "MA",
    "rsi": "RSI",
}


def get(strategy_id: str) -> Optional[BaseStrategy]:
    """获取回测策略实例。"""
    return _BACKTEST_STRATEGIES.get(strategy_id)


def get_strategy(strategy_id: str) -> Optional[BaseStrategy]:
    """兼容旧调用名，返回支持 generate_signals 的回测策略。"""
    return get(strategy_id)


def get_trading_strategy_adapter(strategy_id: str, **kwargs) -> Optional[Strategy]:
    """
    将回测策略ID映射到 TradingCore Strategy，供模拟/实盘链路复用。
    """
    alias = _TRADING_STRATEGY_ALIAS.get(strategy_id, strategy_id)
    try:
        return get_trading_strategy(alias, **kwargs)
    except Exception:
        return None


def get_all() -> List[BaseStrategy]:
    """返回所有回测策略。"""
    return list(_BACKTEST_STRATEGIES.values())


def list_for_api() -> List[dict]:
    """返回前端可消费的策略元数据。"""
    return [
        {
            "id": strategy.strategy_id,
            "name": strategy.name,
            "description": strategy.description,
            "params": [param["name"] for param in strategy.param_schema],
            "param_schema": strategy.param_schema,
        }
        for strategy in get_all()
    ]


def list_strategies() -> List[dict]:
    """API 使用的回测策略列表。"""
    return list_for_api()


__all__ = [
    "BaseStrategy",
    "MACrossStrategy",
    "BacktestRSIStrategy",
    "Strategy",
    "MAStrategy",
    "RSIStrategy",
    "STRATEGY_REGISTRY",
    "register_strategy",
    "get_trading_strategy",
    "list_trading_strategies",
    "get",
    "get_strategy",
    "get_all",
    "list_for_api",
    "list_strategies",
    "get_trading_strategy_adapter",
]
