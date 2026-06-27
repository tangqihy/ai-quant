"""
策略模块

使用方式：
    from app.strategies import Strategy, MAStrategy, RSIStrategy
    
    # 创建策略
    strategy = MAStrategy(short_window=5, long_window=20)
    
    # 启动策略
    strategy.start()
    
    # 处理K线
    strategy.handle_bar(bar)
    
    # 停止策略
    strategy.stop()
"""

from .strategy import (
    Strategy,
    MAStrategy,
    RSIStrategy,
    STRATEGY_REGISTRY,
    register_strategy,
    get_strategy,
    list_strategies,
)
