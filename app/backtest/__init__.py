"""
回测模块

使用方式：
    from app.backtest import BacktestEngine, BacktestResult, calculate_sharpe_ratio, calculate_sortino_ratio
    from app.brokers import BacktestBroker
    from app.domain import ExchangeInfo, Exchange
    
    # 创建撮合器
    exchange = ExchangeInfo(name='上交所', exchange=Exchange.SH)
    broker = BacktestBroker(exchange)
    
    # 创建回测引擎
    engine = BacktestEngine(broker)
    
    # 处理K线
    trades = engine.process_bar(bar)
    
    # 计算指标
    result = BacktestResult()
    result.calculate_metrics(initial_capital=1000000)
    
    sharpe = calculate_sharpe_ratio(returns)
    sortino = calculate_sortino_ratio(returns)
"""

from .engine import (
    BacktestEngine,
    BacktestResult,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)
