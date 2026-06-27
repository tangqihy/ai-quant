"""
账户与组合管理 - 分离账户和组合的职责

设计原则：
1. Account 负责现金管理
2. Portfolio 负责组合管理
3. Position 负责单只股票
4. 一个账户管理多个组合
5. 一个组合支持多个策略
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

from ..domain import (
    Account, Portfolio, Position, Trade, Order,
    OrderDirection
)

logger = logging.getLogger(__name__)


class AccountManager:
    """
    账户管理器
    
    职责：
    - 管理账户资金
    - 处理入金/出金
    - 冻结/解冻资金
    - 计算总资产
    """
    
    def __init__(self):
        self._accounts: Dict[str, Account] = {}
    
    def create_account(
        self, 
        account_id: str = None, 
        initial_capital: float = 1000000.0
    ) -> Account:
        """
        创建账户
        
        Args:
            account_id: 账户ID，默认自动生成
            initial_capital: 初始资金
            
        Returns:
            Account: 账户对象
        """
        account = Account(
            account_id=account_id or f"account_{len(self._accounts) + 1}",
            initial_capital=initial_capital,
            cash=initial_capital,
            total_value=initial_capital
        )
        
        self._accounts[account.account_id] = account
        logger.info(f"Account created: {account.account_id} with capital {initial_capital}")
        
        return account
    
    def get_account(self, account_id: str) -> Optional[Account]:
        """获取账户"""
        return self._accounts.get(account_id)
    
    def deposit(self, account_id: str, amount: float):
        """
        入金
        
        Args:
            account_id: 账户ID
            amount: 入金金额
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        account.deposit(amount)
        logger.info(f"Deposit {amount} to account {account_id}")
    
    def withdraw(self, account_id: str, amount: float):
        """
        出金
        
        Args:
            account_id: 账户ID
            amount: 出金金额
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        account.withdraw(amount)
        logger.info(f"Withdraw {amount} from account {account_id}")
    
    def freeze(self, account_id: str, amount: float):
        """
        冻结资金
        
        Args:
            account_id: 账户ID
            amount: 冻结金额
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        account.freeze(amount)
        logger.info(f"Freeze {amount} in account {account_id}")
    
    def unfreeze(self, account_id: str, amount: float):
        """
        解冻资金
        
        Args:
            account_id: 账户ID
            amount: 解冻金额
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        account.unfreeze(amount)
        logger.info(f"Unfreeze {amount} in account {account_id}")
    
    def update_total_value(self, account_id: str, positions_value: float):
        """
        更新总资产
        
        Args:
            account_id: 账户ID
            positions_value: 持仓市值
        """
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        account._update_total_value(positions_value)
    
    def list_accounts(self) -> List[Account]:
        """列出所有账户"""
        return list(self._accounts.values())


class PortfolioManager:
    """
    组合管理器
    
    职责：
    - 管理投资组合
    - 处理持仓
    - 计算盈亏
    """
    
    def __init__(self):
        self._portfolios: Dict[str, Portfolio] = {}
    
    def create_portfolio(
        self, 
        account_id: str, 
        strategy_id: str,
        portfolio_id: str = None
    ) -> Portfolio:
        """
        创建组合
        
        Args:
            account_id: 账户ID
            strategy_id: 策略ID
            portfolio_id: 组合ID，默认自动生成
            
        Returns:
            Portfolio: 组合对象
        """
        portfolio = Portfolio(
            portfolio_id=portfolio_id or f"portfolio_{strategy_id}",
            account_id=account_id,
            strategy_id=strategy_id
        )
        
        self._portfolios[portfolio.portfolio_id] = portfolio
        logger.info(f"Portfolio created: {portfolio.portfolio_id} for strategy {strategy_id}")
        
        return portfolio
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """获取组合"""
        return self._portfolios.get(portfolio_id)
    
    def get_portfolios_by_account(self, account_id: str) -> List[Portfolio]:
        """获取账户下的所有组合"""
        return [p for p in self._portfolios.values() if p.account_id == account_id]
    
    def get_portfolios_by_strategy(self, strategy_id: str) -> List[Portfolio]:
        """获取策略的所有组合"""
        return [p for p in self._portfolios.values() if p.strategy_id == strategy_id]
    
    def process_trade(self, portfolio_id: str, trade: Trade):
        """
        处理成交
        
        Args:
            portfolio_id: 组合ID
            trade: 成交信息
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio not found: {portfolio_id}")
        
        symbol = trade.symbol
        
        if trade.direction == OrderDirection.BUY:
            # 买入
            if symbol not in portfolio.positions:
                portfolio.positions[symbol] = Position(symbol=symbol)
            
            position = portfolio.positions[symbol]
            position.buy(trade.price, trade.quantity)
            
            logger.info(f"Buy {trade.quantity} {symbol} @ {trade.price}")
        
        else:
            # 卖出
            if symbol not in portfolio.positions:
                raise ValueError(f"No position for {symbol}")
            
            position = portfolio.positions[symbol]
            pnl = position.sell(trade.price, trade.quantity)
            
            # 清空持仓
            if position.quantity <= 0:
                del portfolio.positions[symbol]
            
            logger.info(f"Sell {trade.quantity} {symbol} @ {trade.price}, PnL: {pnl}")
    
    def update_market_value(self, portfolio_id: str, prices: Dict[str, float]):
        """
        更新市值
        
        Args:
            portfolio_id: 组合ID
            prices: 价格字典 {symbol: price}
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio not found: {portfolio_id}")
        
        portfolio.update_market_value(prices)
    
    def get_position(self, portfolio_id: str, symbol: str) -> Optional[Position]:
        """
        获取持仓
        
        Args:
            portfolio_id: 组合ID
            symbol: 股票代码
            
        Returns:
            Optional[Position]: 持仓对象
        """
        portfolio = self.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        
        return portfolio.get_position(symbol)
    
    def list_portfolios(self) -> List[Portfolio]:
        """列出所有组合"""
        return list(self._portfolios.values())


class TradingManager:
    """
    交易管理器
    
    整合账户和组合管理
    """
    
    def __init__(self):
        self.account_manager = AccountManager()
        self.portfolio_manager = PortfolioManager()
    
    def create_trading_account(
        self, 
        account_id: str = None,
        initial_capital: float = 1000000.0
    ) -> Account:
        """创建交易账户"""
        return self.account_manager.create_account(account_id, initial_capital)
    
    def create_portfolio(
        self, 
        account_id: str, 
        strategy_id: str,
        portfolio_id: str = None
    ) -> Portfolio:
        """创建投资组合"""
        # 验证账户存在
        account = self.account_manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        return self.portfolio_manager.create_portfolio(account_id, strategy_id, portfolio_id)
    
    def process_order_fill(
        self, 
        account_id: str,
        portfolio_id: str,
        trade: Trade
    ):
        """
        处理订单成交
        
        Args:
            account_id: 账户ID
            portfolio_id: 组合ID
            trade: 成交信息
        """
        account = self.account_manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        # 计算成交金额
        amount = trade.price * trade.quantity
        
        if trade.direction == OrderDirection.BUY:
            # 买入：扣减现金
            account.cash -= amount + trade.commission
        else:
            # 卖出：增加现金
            account.cash += amount - trade.commission
        
        # 更新持仓
        self.portfolio_manager.process_trade(portfolio_id, trade)
        
        # 更新总资产
        portfolio = self.portfolio_manager.get_portfolio(portfolio_id)
        if portfolio:
            self.account_manager.update_total_value(account_id, portfolio.total_market_value)
    
    def get_account_summary(self, account_id: str) -> Dict:
        """
        获取账户摘要
        
        Args:
            account_id: 账户ID
            
        Returns:
            Dict: 账户摘要
        """
        account = self.account_manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        
        portfolios = self.portfolio_manager.get_portfolios_by_account(account_id)
        
        return {
            'account_id': account.account_id,
            'initial_capital': account.initial_capital,
            'cash': account.cash,
            'frozen': account.frozen,
            'total_value': account.total_value,
            'positions_value': sum(p.total_market_value for p in portfolios),
            'unrealized_pnl': sum(p.total_unrealized_pnl for p in portfolios),
            'realized_pnl': sum(p.total_realized_pnl for p in portfolios),
            'portfolios_count': len(portfolios)
        }
