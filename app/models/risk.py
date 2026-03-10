"""
风控数据模型
"""
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class RiskRule(BaseModel):
    """风控规则"""
    id: str = Field(..., description="规则ID")
    name: str = Field(..., description="规则名称")
    rule_type: Literal["POSITION_LIMIT", "STOP_LOSS", "STOP_PROFIT", "BLACKLIST", "TRADE_LIMIT"] = Field(
        ..., description="规则类型"
    )
    enabled: bool = Field(default=True, description="是否启用")
    params: dict = Field(default_factory=dict, description="规则参数")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class RiskAlert(BaseModel):
    """风控告警"""
    id: str = Field(..., description="告警ID")
    rule_id: str = Field(..., description="触发规则ID")
    rule_name: str = Field(..., description="规则名称")
    alert_type: Literal["WARNING", "ERROR", "BLOCK"] = Field(..., description="告警级别")
    symbol: Optional[str] = Field(None, description="涉及股票")
    message: str = Field(..., description="告警信息")
    details: dict = Field(default_factory=dict, description="详细信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    acknowledged: bool = Field(default=False, description="是否已确认")


class StopLossConfig(BaseModel):
    """止损配置"""
    symbol: str = Field(..., description="股票代码")
    position_id: str = Field(..., description="持仓ID")
    stop_loss_price: float = Field(..., description="止损价格")
    stop_loss_pct: float = Field(..., description="止损百分比")
    stop_profit_price: Optional[float] = Field(None, description="止盈价格")
    stop_profit_pct: Optional[float] = Field(None, description="止盈百分比")
    trailing_stop: bool = Field(default=False, description="是否移动止损")
    trailing_stop_pct: Optional[float] = Field(None, description="移动止损百分比")
    highest_price: Optional[float] = Field(None, description="最高价（用于移动止损）")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class BlacklistItem(BaseModel):
    """黑名单项"""
    symbol: str = Field(..., description="股票代码")
    reason: Literal["ST", "DELISTING", "SUSPENDED", "LIMIT_UP", "LIMIT_DOWN", "MANUAL"] = Field(
        ..., description="黑名单原因"
    )
    description: str = Field(default="", description="描述")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class RiskCheckResult(BaseModel):
    """风控检查结果"""
    passed: bool = Field(..., description="是否通过")
    blocked: bool = Field(default=False, description="是否被阻止")
    alerts: List[RiskAlert] = Field(default_factory=list, description="告警列表")
    message: Optional[str] = Field(None, description="提示信息")
