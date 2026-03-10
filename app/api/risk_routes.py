"""
风控 API 路由
"""
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.models.risk import RiskRule, RiskAlert, StopLossConfig, BlacklistItem
from app.services.risk_service import risk_service

router = APIRouter(prefix="/risk", tags=["风控"])


# ==================== 规则管理 ====================

@router.get("/rules")
async def get_risk_rules():
    """获取风控规则列表"""
    rules = risk_service.get_rules()
    return {
        "success": True,
        "data": [r.model_dump() for r in rules]
    }


class UpdateRuleRequest(BaseModel):
    enabled: bool
    params: Optional[dict] = None


@router.put("/rules/{rule_id}")
async def update_risk_rule(rule_id: str, request: UpdateRuleRequest):
    """更新风控规则"""
    rule = risk_service.update_rule(rule_id, request.enabled, request.params)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {
        "success": True,
        "data": rule.model_dump()
    }


# ==================== 止损止盈 ====================

class StopLossRequest(BaseModel):
    symbol: str
    position_id: str
    stop_loss_pct: float
    stop_profit_pct: Optional[float] = None
    trailing_stop: bool = False
    trailing_stop_pct: Optional[float] = None


@router.post("/stop-loss")
async def set_stop_loss(request: StopLossRequest):
    """设置止损止盈"""
    config = risk_service.set_stop_loss(
        symbol=request.symbol,
        position_id=request.position_id,
        stop_loss_pct=request.stop_loss_pct,
        stop_profit_pct=request.stop_profit_pct,
        trailing_stop=request.trailing_stop,
        trailing_stop_pct=request.trailing_stop_pct
    )
    return {
        "success": True,
        "data": config.model_dump()
    }


@router.get("/stop-loss/{symbol}")
async def get_stop_loss(symbol: str):
    """获取止损止盈配置"""
    config = risk_service.get_stop_loss_config(symbol)
    if not config:
        raise HTTPException(status_code=404, detail="未设置止损止盈")
    return {
        "success": True,
        "data": config.model_dump()
    }


@router.delete("/stop-loss/{symbol}")
async def remove_stop_loss(symbol: str):
    """移除止损止盈"""
    success = risk_service.remove_stop_loss(symbol)
    if not success:
        raise HTTPException(status_code=404, detail="未设置止损止盈")
    return {
        "success": True,
        "message": "止损止盈已移除"
    }


# ==================== 黑名单 ====================

class BlacklistRequest(BaseModel):
    symbol: str
    reason: str
    description: str = ""
    expires_in_hours: Optional[int] = None


@router.post("/blacklist")
async def add_to_blacklist(request: BlacklistRequest):
    """添加到黑名单"""
    item = risk_service.add_to_blacklist(
        symbol=request.symbol,
        reason=request.reason,
        description=request.description,
        expires_in_hours=request.expires_in_hours
    )
    return {
        "success": True,
        "data": item.model_dump()
    }


@router.get("/blacklist")
async def get_blacklist():
    """获取黑名单"""
    items = risk_service.get_blacklist()
    return {
        "success": True,
        "data": [i.model_dump() for i in items]
    }


@router.delete("/blacklist/{symbol}")
async def remove_from_blacklist(symbol: str):
    """从黑名单移除"""
    success = risk_service.remove_from_blacklist(symbol)
    if not success:
        raise HTTPException(status_code=404, detail="股票不在黑名单")
    return {
        "success": True,
        "message": "已从黑名单移除"
    }


# ==================== 告警 ====================

@router.get("/alerts")
async def get_alerts(
    acknowledged: Optional[bool] = Query(None, description="是否已确认"),
    limit: int = Query(100, description="返回数量")
):
    """获取风控告警"""
    alerts = risk_service.get_alerts(acknowledged, limit)
    return {
        "success": True,
        "data": [a.model_dump() for a in alerts]
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """确认告警"""
    success = risk_service.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="告警不存在")
    return {
        "success": True,
        "message": "告警已确认"
    }


@router.delete("/alerts")
async def clear_alerts():
    """清空告警"""
    risk_service.clear_alerts()
    return {
        "success": True,
        "message": "告警已清空"
    }


# ==================== 检查 ====================

class CheckRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    price: float
    account_value: float


@router.post("/check")
async def check_risk(request: CheckRequest):
    """风控检查（测试用）"""
    from app.services.simulation_service import simulation_service

    # 获取当前持仓
    positions = {p.symbol: p for p in simulation_service.get_positions()}

    result = risk_service.check_order(
        symbol=request.symbol,
        action=request.action,
        quantity=request.quantity,
        price=request.price,
        account_value=request.account_value,
        positions=positions
    )
    return {
        "success": True,
        "data": result.model_dump()
    }
