"""
订单 Repository - 订单数据访问
"""
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import SQLiteRepository
from ..domain import Order, OrderStatus, OrderDirection, OrderType


class OrderRepository(SQLiteRepository):
    """
    订单 Repository
    
    负责订单数据的持久化
    """
    
    def __init__(self, db_path: str = "app/data/orders.db"):
        super().__init__(db_path, "orders")
    
    def find_by_status(self, status: OrderStatus) -> List[Order]:
        """根据状态查找订单"""
        return self.find_all({"status": status.value})
    
    def find_by_symbol(self, symbol: str) -> List[Order]:
        """根据股票代码查找订单"""
        return self.find_all({"symbol": symbol})
    
    def find_active_orders(self) -> List[Order]:
        """查找活跃订单"""
        active_statuses = [
            OrderStatus.PENDING.value,
            OrderStatus.SUBMITTED.value,
            OrderStatus.ACCEPTED.value,
            OrderStatus.PARTIAL.value
        ]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            placeholders = ",".join(["?" for _ in active_statuses])
            cursor.execute(
                f"SELECT data FROM {self._table_name} WHERE json_extract(data, '$.status') IN ({placeholders})",
                active_statuses
            )
            rows = cursor.fetchall()
            return [self._deserialize(row[0]) for row in rows]
        finally:
            conn.close()
    
    def _get_entity_id(self, entity: Order) -> str:
        """获取实体ID"""
        return entity.order_id
    
    def _serialize(self, entity: Order) -> str:
        """序列化实体"""
        return json.dumps({
            "order_id": entity.order_id,
            "symbol": entity.symbol,
            "direction": entity.direction.value,
            "price": entity.price,
            "quantity": entity.quantity,
            "order_type": entity.order_type.value,
            "status": entity.status.value,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
            "filled_quantity": entity.filled_quantity,
            "filled_price": entity.filled_price,
            "commission": entity.commission,
            "slippage": entity.slippage,
            "reject_reason": entity.reject_reason,
        })
    
    def _deserialize(self, data: str) -> Order:
        """反序列化实体"""
        obj = json.loads(data)
        
        return Order(
            order_id=obj["order_id"],
            symbol=obj["symbol"],
            direction=OrderDirection(obj["direction"]),
            price=obj["price"],
            quantity=obj["quantity"],
            order_type=OrderType(obj["order_type"]),
            status=OrderStatus(obj["status"]),
            created_at=datetime.fromisoformat(obj["created_at"]),
            updated_at=datetime.fromisoformat(obj["updated_at"]),
            filled_quantity=obj["filled_quantity"],
            filled_price=obj["filled_price"],
            commission=obj["commission"],
            slippage=obj["slippage"],
            reject_reason=obj["reject_reason"],
        )
