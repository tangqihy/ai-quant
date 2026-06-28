"""
成交 Repository - 成交数据访问
"""
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import SQLiteRepository
from ..domain import Trade, OrderDirection


class TradeRepository(SQLiteRepository):
    """
    成交 Repository
    
    负责成交数据的持久化
    """
    
    def __init__(self, db_path: str = "app/data/trades.db"):
        super().__init__(db_path, "trades")
    
    def find_by_order_id(self, order_id: str) -> List[Trade]:
        """根据订单ID查找成交"""
        return self.find_all({"order_id": order_id})
    
    def find_by_symbol(self, symbol: str) -> List[Trade]:
        """根据股票代码查找成交"""
        return self.find_all({"symbol": symbol})
    
    def find_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Trade]:
        """根据日期范围查找成交"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"SELECT data FROM {self._table_name} WHERE json_extract(data, '$.traded_at') BETWEEN ? AND ?",
                (start_date.isoformat(), end_date.isoformat())
            )
            rows = cursor.fetchall()
            return [self._deserialize(row[0]) for row in rows]
        finally:
            conn.close()
    
    def _get_entity_id(self, entity: Trade) -> str:
        """获取实体ID"""
        return entity.trade_id
    
    def _serialize(self, entity: Trade) -> str:
        """序列化实体"""
        return json.dumps({
            "trade_id": entity.trade_id,
            "order_id": entity.order_id,
            "symbol": entity.symbol,
            "direction": entity.direction.value,
            "price": entity.price,
            "quantity": entity.quantity,
            "commission": entity.commission,
            "slippage": entity.slippage,
            "traded_at": entity.traded_at.isoformat(),
        })
    
    def _deserialize(self, data: str) -> Trade:
        """反序列化实体"""
        obj = json.loads(data)
        
        return Trade(
            trade_id=obj["trade_id"],
            order_id=obj["order_id"],
            symbol=obj["symbol"],
            direction=OrderDirection(obj["direction"]),
            price=obj["price"],
            quantity=obj["quantity"],
            commission=obj["commission"],
            slippage=obj["slippage"],
            traded_at=datetime.fromisoformat(obj["traded_at"]),
        )
