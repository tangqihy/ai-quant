"""
模拟交易数据模型
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Order(BaseModel):
    """订单模型"""
    id: str = Field(..., description="订单ID")
    symbol: str = Field(..., description="股票代码")
    action: Literal["BUY", "SELL"] = Field(..., description="买卖方向")
    order_type: Literal["LIMIT", "MARKET"] = Field(..., description="订单类型")
    price: Optional[float] = Field(None, description="委托价格（市价单可为空）")
    quantity: int = Field(..., description="委托数量")
    filled_quantity: int = Field(default=0, description="已成交数量")
    status: Literal["PENDING", "PARTIAL_FILLED", "FILLED", "CANCELLED", "REJECTED"] = Field(
        default="PENDING", description="订单状态"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    rejected_reason: Optional[str] = Field(None, description="拒绝原因")


class Trade(BaseModel):
    """成交记录模型"""
    id: str = Field(..., description="成交ID")
    order_id: str = Field(..., description="关联订单ID")
    symbol: str = Field(..., description="股票代码")
    action: Literal["BUY", "SELL"] = Field(..., description="买卖方向")
    price: float = Field(..., description="成交价格")
    quantity: int = Field(..., description="成交数量")
    commission: float = Field(..., description="佣金")
    stamp_tax: float = Field(default=0.0, description="印花税")
    transfer_fee: float = Field(default=0.0, description="过户费")
    total_fee: float = Field(..., description="总费用")
    timestamp: datetime = Field(default_factory=datetime.now, description="成交时间")


class Position(BaseModel):
    """持仓模型"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(default="", description="股票名称")
    quantity: int = Field(default=0, description="持仓数量")
    avg_cost: float = Field(default=0.0, description="平均成本")
    market_price: float = Field(default=0.0, description="当前市价")
    market_value: float = Field(default=0.0, description="市值")
    unrealized_pnl: float = Field(default=0.0, description="浮动盈亏")
    unrealized_pnl_pct: float = Field(default=0.0, description="浮动盈亏率(%)")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class Account(BaseModel):
    """账户模型"""
    user_id: str = Field(default="default", description="用户ID")
    initial_capital: float = Field(default=1000000.0, description="初始资金")
    cash: float = Field(default=1000000.0, description="可用资金")
    frozen_cash: float = Field(default=0.0, description="冻结资金")
    total_value: float = Field(default=1000000.0, description="总资产")
    positions_value: float = Field(default=0.0, description="持仓市值")
    realized_pnl: float = Field(default=0.0, description="已实现盈亏")
    total_commission: float = Field(default=0.0, description="累计佣金")
    total_stamp_tax: float = Field(default=0.0, description="累计印花税")
    total_transfer_fee: float = Field(default=0.0, description="累计过户费")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class OrderRequest(BaseModel):
    """下单请求"""
    symbol: str = Field(..., description="股票代码")
    action: Literal["BUY", "SELL"] = Field(..., description="买卖方向")
    order_type: Literal["LIMIT", "MARKET"] = Field(..., description="订单类型")
    price: Optional[float] = Field(None, description="委托价格")
    quantity: int = Field(..., gt=0, description="委托数量")


class OrderCancelRequest(BaseModel):
    """撤单请求"""
    order_id: str = Field(..., description="订单ID")
