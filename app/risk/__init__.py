"""
风控模块

使用方式：
    from app.risk import RiskPersistence, get_risk_persistence, RiskEvent, RiskDecision
    
    # 获取持久化实例
    persistence = get_risk_persistence()
    
    # 保存风控事件
    event = RiskEvent(
        event_id='event1',
        rule_type=RiskRuleType.POSITION_LIMIT,
        symbol='600519',
        passed=True,
        reason='仓位限制检查通过'
    )
    persistence.save_event(event)
    
    # 保存风控决策
    decision = RiskDecision(
        decision_id='decision1',
        order_id='order1',
        symbol='600519',
        allowed=True,
        events=[event]
    )
    persistence.save_decision(decision)
    
    # 查询历史记录
    events = persistence.load_events(symbol='600519')
    decisions = persistence.load_decisions(order_id='order1')
"""

from .persistence import RiskEvent, RiskDecision, RiskPersistence, get_risk_persistence
