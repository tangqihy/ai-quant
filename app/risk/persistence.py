"""
风控事件记录 - 记录风控决策和事件

设计原则：
1. 记录所有风控决策
2. 支持审计和排查
3. 便于历史分析
"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
import logging

from ..domain import RiskRuleType

logger = logging.getLogger(__name__)


class RiskEvent:
    """
    风控事件
    
    记录风控检查的结果
    """
    
    def __init__(
        self,
        event_id: str,
        rule_type: RiskRuleType,
        symbol: str,
        passed: bool,
        reason: str,
        params: Dict = None,
        created_at: datetime = None
    ):
        self.event_id = event_id
        self.rule_type = rule_type
        self.symbol = symbol
        self.passed = passed
        self.reason = reason
        self.params = params or {}
        self.created_at = created_at or datetime.now()


class RiskDecision:
    """
    风控决策
    
    记录订单的风控决策
    """
    
    def __init__(
        self,
        decision_id: str,
        order_id: str,
        symbol: str,
        allowed: bool,
        events: List[RiskEvent] = None,
        reject_reason: str = "",
        created_at: datetime = None
    ):
        self.decision_id = decision_id
        self.order_id = order_id
        self.symbol = symbol
        self.allowed = allowed
        self.events = events or []
        self.reject_reason = reject_reason
        self.created_at = created_at or datetime.now()


class RiskPersistence:
    """
    风控持久化
    
    职责：
    - 存储风控事件
    - 存储风控决策
    - 查询历史记录
    """
    
    def __init__(self, db_path: str = "data/risk.db"):
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
        
        # 创建风控事件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_events (
                event_id TEXT PRIMARY KEY,
                rule_type TEXT,
                symbol TEXT,
                passed BOOLEAN,
                reason TEXT,
                params_json TEXT,
                created_at TEXT
            )
        ''')
        
        # 创建风控决策表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_decisions (
                decision_id TEXT PRIMARY KEY,
                order_id TEXT,
                symbol TEXT,
                allowed BOOLEAN,
                reject_reason TEXT,
                events_json TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_event(self, event: RiskEvent):
        """
        保存风控事件
        
        Args:
            event: 风控事件
        """
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO risk_events 
            (event_id, rule_type, symbol, passed, reason, params_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.event_id,
            event.rule_type.value,
            event.symbol,
            event.passed,
            event.reason,
            json.dumps(event.params, ensure_ascii=False),
            event.created_at.isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def save_decision(self, decision: RiskDecision):
        """
        保存风控决策
        
        Args:
            decision: 风控决策
        """
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 序列化事件
        events_data = []
        for event in decision.events:
            events_data.append({
                'event_id': event.event_id,
                'rule_type': event.rule_type.value,
                'symbol': event.symbol,
                'passed': event.passed,
                'reason': event.reason,
                'params': event.params,
                'created_at': event.created_at.isoformat()
            })
        
        cursor.execute('''
            INSERT INTO risk_decisions 
            (decision_id, order_id, symbol, allowed, reject_reason, events_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            decision.decision_id,
            decision.order_id,
            decision.symbol,
            decision.allowed,
            decision.reject_reason,
            json.dumps(events_data, ensure_ascii=False),
            decision.created_at.isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def load_events(
        self,
        symbol: str = None,
        rule_type: RiskRuleType = None,
        passed: bool = None,
        limit: int = 100
    ) -> List[RiskEvent]:
        """
        加载风控事件
        
        Args:
            symbol: 股票代码
            rule_type: 规则类型
            passed: 是否通过
            limit: 返回数量
            
        Returns:
            List[RiskEvent]: 风控事件列表
        """
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM risk_events WHERE 1=1'
        params = []
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        
        if rule_type:
            query += ' AND rule_type = ?'
            params.append(rule_type.value)
        
        if passed is not None:
            query += ' AND passed = ?'
            params.append(passed)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        events = []
        for row in rows:
            event = RiskEvent(
                event_id=row[0],
                rule_type=RiskRuleType(row[1]),
                symbol=row[2],
                passed=bool(row[3]),
                reason=row[4],
                params=json.loads(row[5]) if row[5] else {},
                created_at=datetime.fromisoformat(row[6])
            )
            events.append(event)
        
        return events
    
    def load_decisions(
        self,
        order_id: str = None,
        symbol: str = None,
        allowed: bool = None,
        limit: int = 100
    ) -> List[RiskDecision]:
        """
        加载风控决策
        
        Args:
            order_id: 订单ID
            symbol: 股票代码
            allowed: 是否允许
            limit: 返回数量
            
        Returns:
            List[RiskDecision]: 风控决策列表
        """
        import json
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM risk_decisions WHERE 1=1'
        params = []
        
        if order_id:
            query += ' AND order_id = ?'
            params.append(order_id)
        
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        
        if allowed is not None:
            query += ' AND allowed = ?'
            params.append(allowed)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        decisions = []
        for row in rows:
            # 反序列化事件
            events_data = json.loads(row[5]) if row[5] else []
            events = []
            for event_data in events_data:
                event = RiskEvent(
                    event_id=event_data['event_id'],
                    rule_type=RiskRuleType(event_data['rule_type']),
                    symbol=event_data['symbol'],
                    passed=event_data['passed'],
                    reason=event_data['reason'],
                    params=event_data.get('params', {}),
                    created_at=datetime.fromisoformat(event_data['created_at'])
                )
                events.append(event)
            
            decision = RiskDecision(
                decision_id=row[0],
                order_id=row[1],
                symbol=row[2],
                allowed=bool(row[3]),
                events=events,
                reject_reason=row[4],
                created_at=datetime.fromisoformat(row[6])
            )
            decisions.append(decision)
        
        return decisions


# 全局实例
_risk_persistence: Optional[RiskPersistence] = None


def get_risk_persistence(db_path: str = "data/risk.db") -> RiskPersistence:
    """获取风控持久化实例"""
    global _risk_persistence
    
    if _risk_persistence is None:
        _risk_persistence = RiskPersistence(db_path)
    
    return _risk_persistence
