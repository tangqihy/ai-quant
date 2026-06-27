"""
模拟交易持久化 - 将交易数据存储到SQLite

设计原则：
1. SQLite 当缓存，不是唯一事实来源
2. 支持数据重建
3. 使用事务保证一致性
"""
import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime
import logging

from ..domain import (
    Account, Portfolio, Position, Order, Trade,
    OrderDirection, OrderType, OrderStatus
)

logger = logging.getLogger(__name__)


class TradingPersistence:
    """
    交易持久化
    
    职责：
    - 存储账户信息
    - 存储订单信息
    - 存储成交信息
    - 存储持仓信息
    - 存储资金流水
    """
    
    def __init__(self, db_path: str = "data/trading.db"):
        """
        初始化持久化
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建账户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                initial_capital REAL,
                cash REAL,
                frozen REAL,
                total_value REAL,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 创建订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                account_id TEXT,
                portfolio_id TEXT,
                symbol TEXT,
                direction TEXT,
                price REAL,
                quantity INTEGER,
                order_type TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                filled_quantity INTEGER,
                filled_price REAL,
                commission REAL,
                slippage REAL,
                reject_reason TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        # 创建成交表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                order_id TEXT,
                account_id TEXT,
                portfolio_id TEXT,
                symbol TEXT,
                direction TEXT,
                price REAL,
                quantity INTEGER,
                commission REAL,
                slippage REAL,
                traded_at TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        ''')
        
        # 创建持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                portfolio_id TEXT,
                symbol TEXT,
                quantity INTEGER,
                available INTEGER,
                cost_price REAL,
                market_value REAL,
                unrealized_pnl REAL,
                realized_pnl REAL,
                updated_at TEXT,
                UNIQUE(account_id, portfolio_id, symbol)
            )
        ''')
        
        # 创建资金流水表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                amount REAL,
                type TEXT,
                description TEXT,
                created_at TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        # 创建账户快照表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                cash REAL,
                frozen REAL,
                total_value REAL,
                positions_json TEXT,
                created_at TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_account(self, account: Account):
        """
        保存账户
        
        Args:
            account: 账户对象
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO accounts 
            (account_id, initial_capital, cash, frozen, total_value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            account.account_id,
            account.initial_capital,
            account.cash,
            account.frozen,
            account.total_value,
            account.created_at.isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_account(self, account_id: str) -> Optional[Account]:
        """
        加载账户
        
        Args:
            account_id: 账户ID
            
        Returns:
            Optional[Account]: 账户对象
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM accounts WHERE account_id = ?', (account_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return Account(
                account_id=row[0],
                initial_capital=row[1],
                cash=row[2],
                frozen=row[3],
                total_value=row[4],
                created_at=datetime.fromisoformat(row[5])
            )
        
        return None
    
    def save_order(self, order: Order, account_id: str, portfolio_id: str):
        """
        保存订单
        
        Args:
            order: 订单对象
            account_id: 账户ID
            portfolio_id: 组合ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO orders 
            (order_id, account_id, portfolio_id, symbol, direction, price, quantity, 
             order_type, status, created_at, updated_at, filled_quantity, filled_price, 
             commission, slippage, reject_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order.order_id,
            account_id,
            portfolio_id,
            order.symbol,
            order.direction.value,
            order.price,
            order.quantity,
            order.order_type.value,
            order.status.value,
            order.created_at.isoformat(),
            order.updated_at.isoformat(),
            order.filled_quantity,
            order.filled_price,
            order.commission,
            order.slippage,
            order.reject_reason
        ))
        
        conn.commit()
        conn.close()
    
    def load_orders(
        self, 
        account_id: str, 
        portfolio_id: str = None,
        status: OrderStatus = None,
        limit: int = 100
    ) -> List[Order]:
        """
        加载订单
        
        Args:
            account_id: 账户ID
            portfolio_id: 组合ID
            status: 订单状态
            limit: 返回数量
            
        Returns:
            List[Order]: 订单列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM orders WHERE account_id = ?'
        params = [account_id]
        
        if portfolio_id:
            query += ' AND portfolio_id = ?'
            params.append(portfolio_id)
        
        if status:
            query += ' AND status = ?'
            params.append(status.value)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        orders = []
        for row in rows:
            order = Order(
                order_id=row[0],
                symbol=row[3],
                direction=OrderDirection(row[4]),
                price=row[5],
                quantity=row[6],
                order_type=OrderType(row[7]),
                status=OrderStatus(row[8]),
                created_at=datetime.fromisoformat(row[9]),
                updated_at=datetime.fromisoformat(row[10]),
                filled_quantity=row[11],
                filled_price=row[12],
                commission=row[13],
                slippage=row[14],
                reject_reason=row[15]
            )
            orders.append(order)
        
        return orders
    
    def save_trade(self, trade: Trade, account_id: str, portfolio_id: str):
        """
        保存成交
        
        Args:
            trade: 成交对象
            account_id: 账户ID
            portfolio_id: 组合ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades 
            (trade_id, order_id, account_id, portfolio_id, symbol, direction, 
             price, quantity, commission, slippage, traded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.trade_id,
            trade.order_id,
            account_id,
            portfolio_id,
            trade.symbol,
            trade.direction.value,
            trade.price,
            trade.quantity,
            trade.commission,
            trade.slippage,
            trade.traded_at.isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_trades(
        self, 
        account_id: str, 
        portfolio_id: str = None,
        symbol: str = None,
        limit: int = 100
    ) -> List[Trade]:
        """
        加载成交
        
        Args:
            account_id: 账户ID
            portfolio_id: 组合ID
            symbol: 股票代码
            limit: 返回数量
            
        Returns:
            List[Trade]: 成交列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM trades WHERE account_id = ?'
        params = [account_id]
        
        if portfolio_id:
            query += ' AND portfolio_id = ?'
            params.append(portfolio_id)
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        
        query += ' ORDER BY traded_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        trades = []
        for row in rows:
            trade = Trade(
                trade_id=row[0],
                order_id=row[1],
                symbol=row[4],
                direction=OrderDirection(row[5]),
                price=row[6],
                quantity=row[7],
                commission=row[8],
                slippage=row[9],
                traded_at=datetime.fromisoformat(row[10])
            )
            trades.append(trade)
        
        return trades
    
    def save_position(self, position: Position, account_id: str, portfolio_id: str):
        """
        保存持仓
        
        Args:
            position: 持仓对象
            account_id: 账户ID
            portfolio_id: 组合ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO positions 
            (account_id, portfolio_id, symbol, quantity, available, cost_price, 
             market_value, unrealized_pnl, realized_pnl, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            account_id,
            portfolio_id,
            position.symbol,
            position.quantity,
            position.available,
            position.cost_price,
            position.market_value,
            position.unrealized_pnl,
            position.realized_pnl,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_positions(
        self, 
        account_id: str, 
        portfolio_id: str = None
    ) -> Dict[str, Position]:
        """
        加载持仓
        
        Args:
            account_id: 账户ID
            portfolio_id: 组合ID
            
        Returns:
            Dict[str, Position]: 持仓字典 {symbol: position}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM positions WHERE account_id = ?'
        params = [account_id]
        
        if portfolio_id:
            query += ' AND portfolio_id = ?'
            params.append(portfolio_id)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        positions = {}
        for row in rows:
            position = Position(
                symbol=row[3],
                quantity=row[4],
                available=row[5],
                cost_price=row[6],
                market_value=row[7],
                unrealized_pnl=row[8],
                realized_pnl=row[9]
            )
            positions[position.symbol] = position
        
        return positions
    
    def save_cash_ledger(
        self, 
        account_id: str, 
        amount: float, 
        type: str, 
        description: str
    ):
        """
        保存资金流水
        
        Args:
            account_id: 账户ID
            amount: 金额
            type: 类型 (deposit/withdraw/freeze/unfreeze/commission)
            description: 描述
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO cash_ledger 
            (account_id, amount, type, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            account_id,
            amount,
            type,
            description,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_cash_ledger(
        self, 
        account_id: str, 
        limit: int = 100
    ) -> List[Dict]:
        """
        加载资金流水
        
        Args:
            account_id: 账户ID
            limit: 返回数量
            
        Returns:
            List[Dict]: 资金流水列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM cash_ledger 
            WHERE account_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (account_id, limit))
        
        rows = cursor.fetchall()
        
        conn.close()
        
        ledger = []
        for row in rows:
            ledger.append({
                'id': row[0],
                'account_id': row[1],
                'amount': row[2],
                'type': row[3],
                'description': row[4],
                'created_at': row[5]
            })
        
        return ledger
    
    def save_snapshot(self, account: Account, positions: Dict[str, Position]):
        """
        保存账户快照
        
        Args:
            account: 账户对象
            positions: 持仓字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 将持仓序列化为JSON
        positions_data = {}
        for symbol, pos in positions.items():
            positions_data[symbol] = {
                'quantity': pos.quantity,
                'available': pos.available,
                'cost_price': pos.cost_price,
                'market_value': pos.market_value,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl
            }
        
        positions_json = json.dumps(positions_data, ensure_ascii=False)
        
        cursor.execute('''
            INSERT INTO account_snapshots 
            (account_id, cash, frozen, total_value, positions_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            account.account_id,
            account.cash,
            account.frozen,
            account.total_value,
            positions_json,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_latest_snapshot(self, account_id: str) -> Optional[Dict]:
        """
        加载最新快照
        
        Args:
            account_id: 账户ID
            
        Returns:
            Optional[Dict]: 快照数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM account_snapshots 
            WHERE account_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (account_id,))
        
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return {
                'account_id': row[1],
                'cash': row[2],
                'frozen': row[3],
                'total_value': row[4],
                'positions': json.loads(row[5]),
                'created_at': row[6]
            }
        
        return None


# 全局实例
_trading_persistence: Optional[TradingPersistence] = None


def get_trading_persistence(db_path: str = "data/trading.db") -> TradingPersistence:
    """获取交易持久化实例"""
    global _trading_persistence
    
    if _trading_persistence is None:
        _trading_persistence = TradingPersistence(db_path)
    
    return _trading_persistence
