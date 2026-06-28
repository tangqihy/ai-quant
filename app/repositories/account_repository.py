"""
账户 Repository - 账户数据访问
"""
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import SQLiteRepository
from ..domain import Account


class AccountRepository(SQLiteRepository):
    """
    账户 Repository
    
    负责账户数据的持久化
    """
    
    def __init__(self, db_path: str = "app/data/accounts.db"):
        super().__init__(db_path, "accounts")
    
    def _get_entity_id(self, entity: Account) -> str:
        """获取实体ID"""
        return entity.account_id
    
    def _serialize(self, entity: Account) -> str:
        """序列化实体"""
        return json.dumps({
            "account_id": entity.account_id,
            "initial_capital": entity.initial_capital,
            "cash": entity.cash,
            "frozen": entity.frozen,
            "total_value": entity.total_value,
            "created_at": entity.created_at.isoformat(),
        })
    
    def _deserialize(self, data: str) -> Account:
        """反序列化实体"""
        obj = json.loads(data)
        
        return Account(
            account_id=obj["account_id"],
            initial_capital=obj["initial_capital"],
            cash=obj["cash"],
            frozen=obj["frozen"],
            total_value=obj["total_value"],
            created_at=datetime.fromisoformat(obj["created_at"]),
        )
