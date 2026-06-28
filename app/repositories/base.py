"""
Repository 基类 - 数据访问层抽象

设计原则：
1. Repository 负责数据持久化
2. Service 不直接操作数据库，通过 Repository 访问
3. 支持多种存储后端（SQLite、PostgreSQL、Redis 等）
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime


class Repository(ABC):
    """
    Repository 基类
    
    所有 Repository 都应继承此类
    """
    
    @abstractmethod
    def save(self, entity: Any) -> bool:
        """
        保存实体
        
        Args:
            entity: 实体对象
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[Any]:
        """
        根据ID查找实体
        
        Args:
            entity_id: 实体ID
            
        Returns:
            Optional[Any]: 实体对象，不存在返回 None
        """
        pass
    
    @abstractmethod
    def find_all(self, filters: Dict[str, Any] = None) -> List[Any]:
        """
        查找所有实体
        
        Args:
            filters: 过滤条件
            
        Returns:
            List[Any]: 实体列表
        """
        pass
    
    @abstractmethod
    def update(self, entity: Any) -> bool:
        """
        更新实体
        
        Args:
            entity: 实体对象
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        删除实体
        
        Args:
            entity_id: 实体ID
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def exists(self, entity_id: str) -> bool:
        """
        检查实体是否存在
        
        Args:
            entity_id: 实体ID
            
        Returns:
            bool: 是否存在
        """
        pass
    
    @abstractmethod
    def count(self, filters: Dict[str, Any] = None) -> int:
        """
        统计实体数量
        
        Args:
            filters: 过滤条件
            
        Returns:
            int: 数量
        """
        pass


class SQLiteRepository(Repository):
    """
    SQLite Repository 基类
    
    提供 SQLite 通用实现
    """
    
    def __init__(self, db_path: str, table_name: str):
        """
        初始化 SQLite Repository
        
        Args:
            db_path: 数据库路径
            table_name: 表名
        """
        self._db_path = db_path
        self._table_name = table_name
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        # 创建表（如果不存在）
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _get_connection(self):
        """获取数据库连接"""
        import sqlite3
        return sqlite3.connect(self._db_path)
    
    def save(self, entity: Any) -> bool:
        """保存实体"""
        import json
        
        entity_id = self._get_entity_id(entity)
        data = self._serialize(entity)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"INSERT OR REPLACE INTO {self._table_name} (id, data, updated_at) VALUES (?, ?, ?)",
                (entity_id, data, datetime.now().isoformat())
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save entity: {e}")
            return False
        finally:
            conn.close()
    
    def find_by_id(self, entity_id: str) -> Optional[Any]:
        """根据ID查找实体"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"SELECT data FROM {self._table_name} WHERE id = ?",
                (entity_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._deserialize(row[0])
            return None
        finally:
            conn.close()
    
    def find_all(self, filters: Dict[str, Any] = None) -> List[Any]:
        """查找所有实体"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if filters:
                # 简单的过滤实现
                conditions = " AND ".join([f"{k} = ?" for k in filters.keys()])
                values = list(filters.values())
                cursor.execute(
                    f"SELECT data FROM {self._table_name} WHERE {conditions}",
                    values
                )
            else:
                cursor.execute(f"SELECT data FROM {self._table_name}")
            
            rows = cursor.fetchall()
            return [self._deserialize(row[0]) for row in rows]
        finally:
            conn.close()
    
    def update(self, entity: Any) -> bool:
        """更新实体"""
        return self.save(entity)
    
    def delete(self, entity_id: str) -> bool:
        """删除实体"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"DELETE FROM {self._table_name} WHERE id = ?",
                (entity_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            return False
        finally:
            conn.close()
    
    def exists(self, entity_id: str) -> bool:
        """检查实体是否存在"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM {self._table_name} WHERE id = ?",
                (entity_id,)
            )
            count = cursor.fetchone()[0]
            return count > 0
        finally:
            conn.close()
    
    def count(self, filters: Dict[str, Any] = None) -> int:
        """统计实体数量"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if filters:
                conditions = " AND ".join([f"{k} = ?" for k in filters.keys()])
                values = list(filters.values())
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self._table_name} WHERE {conditions}",
                    values
                )
            else:
                cursor.execute(f"SELECT COUNT(*) FROM {self._table_name}")
            
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    @abstractmethod
    def _get_entity_id(self, entity: Any) -> str:
        """获取实体ID"""
        pass
    
    @abstractmethod
    def _serialize(self, entity: Any) -> str:
        """序列化实体"""
        pass
    
    @abstractmethod
    def _deserialize(self, data: str) -> Any:
        """反序列化实体"""
        pass


# 导入 logging
import logging
logger = logging.getLogger(__name__)
