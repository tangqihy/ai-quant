"""
策略注册表 - 统一注册、按 id 获取，供回测引擎与 API 使用
"""
from typing import Dict, List, Optional
from app.strategies.base import BaseStrategy
from app.strategies.ma_cross import MACrossStrategy
from app.strategies.rsi import RSIStrategy

# 策略注册表：id -> 策略实例
_registry: Dict[str, BaseStrategy] = {}


def register(strategy: BaseStrategy) -> None:
    """注册一个策略"""
    _registry[strategy.strategy_id] = strategy


def get(strategy_id: str) -> Optional[BaseStrategy]:
    """按 id 获取策略"""
    return _registry.get(strategy_id)


def get_all() -> List[BaseStrategy]:
    """返回所有已注册策略"""
    return list(_registry.values())


def list_for_api() -> List[dict]:
    """返回供 API 使用的策略列表（id, name, params, description）"""
    result = []
    for s in get_all():
        params = [p["name"] for p in s.param_schema]
        result.append({
            "id": s.strategy_id,
            "name": s.name,
            "params": params,
            "param_schema": s.param_schema,
            "description": s.description,
        })
    return result


# 注册内置策略
register(MACrossStrategy())
register(RSIStrategy())
