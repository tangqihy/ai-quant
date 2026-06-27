"""
交易管理模块

使用方式：
    from app.trading import TradingManager, get_trading_persistence
    
    # 创建交易管理器
    trading = TradingManager()
    
    # 创建账户
    account = trading.create_trading_account('account1', 1000000)
    
    # 创建组合
    portfolio = trading.create_portfolio('account1', 'MA_strategy')
    
    # 处理成交
    trading.process_order_fill('account1', 'portfolio_MA_strategy', trade)
    
    # 获取账户摘要
    summary = trading.get_account_summary('account1')
    
    # 持久化
    persistence = get_trading_persistence()
    persistence.save_account(account)
    persistence.save_order(order, 'account1', 'portfolio_MA_strategy')
"""

from .account import AccountManager, PortfolioManager, TradingManager
from .persistence import TradingPersistence, get_trading_persistence
