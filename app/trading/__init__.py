"""
交易管理模块

使用方式：
    from app.trading import TradingManager
    
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
"""

from .account import AccountManager, PortfolioManager, TradingManager
