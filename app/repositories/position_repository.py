"""
持仓 Repository - 持仓数据访问
"""
import json
from typing import List, Optional, Dict, Any

from .base import SQLiteRepository
from ..domain import Position


class PositionRepository(SQLiteRepository):
    """
    持仓 Repository
    
    负责持仓数据的持久化
    """
    
    def __init__(self, db_path: str = "app/data/positions.db"):
        super().__init__(db_path, "positions")
    
    def find_by_portfolio_id(self, portfolio_id: str) -> List[Position]:
        """根据组合ID查找持仓"""
        return self.find_all({"portfolio_id": portfolio_id})
    
    def find_by_symbol(self, symbol: str) -> List[Position]:
        """根据股票代码查找持仓"""
        return self.find_all({"symbol": symbol})
    
    def find_by_portfolio_and_symbol(self, portfolio_id: str, symbol: str) -> Optional[Position]:
        """根据组合ID和股票代码查找持仓"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"SELECT data FROM {self._table_name} WHERE json_extract(data, '$.portfolio_id') = ? AND json_extract(data, '$.symbol') = ?",
                (portfolio_id, symbol)
            )
            row = cursor.fetchone()
            
            if row:
                return self._deserialize(row[0])
            return None
        finally:
            conn.close()
    
    def _get_entity_id(self, entity: Position) -> str:
        """获取实体ID"""
        # 使用 portfolio_id + symbol 作为复合ID
        return f"{entity.portfolio_id}_{entity.symbol}"
    
    def _serialize(self, entity: Position) -> str:
        """序列化实体"""
        return json.dumps({
            "portfolio_id": entity.portfolio_id,
            "symbol": entity.symbol,
            "quantity": entity.quantity,
            "available": entity.available,
            "cost_price": entity.cost_price,
            "market_value": entity.market_value,
            "unrealized_pnl": entity.unrealized_pnl,
            "realized_pnl": entity.realized_pnl,
        })
    
    def _deserialize(self, data: str) -> Position:
        """反序列化实体"""
        obj = json.loads(data)
        
        position = Position(
            symbol=obj["symbol"],
            quantity=obj["quantity"],
            available=obj["available"],
            cost_price=obj["cost_price"],
            market_value=obj["market_value"],
            unrealized_pnl=obj["unrealized_pnl"],
            realized_pnl=obj["realized_pnl"],
        )
        position.portfolio_id = obj["portfolio_id"]
        
        return position
