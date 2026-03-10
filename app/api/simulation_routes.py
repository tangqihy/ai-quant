"""
模拟交易 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.models.simulation import OrderRequest, Order, Trade, Position, Account
from app.services.simulation_service import simulation_service

router = APIRouter(prefix="/simulation", tags=["模拟交易"])


@router.post("/reset")
async def reset_account(initial_capital: float = 1000000.0):
    """重置模拟账户"""
    simulation_service.reset_account(initial_capital)
    return {
        "success": True,
        "message": f"账户已重置，初始资金: {initial_capital:,.2f}"
    }


@router.get("/account")
async def get_account() -> dict:
    """获取账户信息"""
    account = simulation_service.get_account()
    return {
        "success": True,
        "data": account.model_dump()
    }


@router.post("/orders")
async def create_order(request: OrderRequest):
    """创建订单（下单）"""
    order = simulation_service.create_order(
        symbol=request.symbol,
        action=request.action,
        order_type=request.order_type,
        price=request.price,
        quantity=request.quantity
    )
    return {
        "success": order.status != "REJECTED",
        "data": order.model_dump(),
        "message": order.rejected_reason if order.status == "REJECTED" else None
    }


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """撤销订单"""
    success = simulation_service.cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=400, detail="撤单失败，订单不存在或已成交")
    return {
        "success": True,
        "message": "撤单成功"
    }


@router.get("/orders")
async def get_orders(
    status: Optional[str] = Query(None, description="订单状态筛选")
):
    """获取订单列表"""
    orders = simulation_service.get_orders(status)
    return {
        "success": True,
        "data": [o.model_dump() for o in orders],
        "total": len(orders)
    }


@router.get("/trades")
async def get_trades():
    """获取成交记录"""
    trades = simulation_service.get_trades()
    return {
        "success": True,
        "data": [t.model_dump() for t in trades],
        "total": len(trades)
    }


@router.get("/positions")
async def get_positions():
    """获取持仓列表"""
    positions = simulation_service.get_positions()
    return {
        "success": True,
        "data": [p.model_dump() for p in positions],
        "total": len(positions)
    }


@router.post("/match")
async def match_orders():
    """触发订单撮合（测试用）"""
    trades = simulation_service.match_orders()
    return {
        "success": True,
        "message": f"撮合完成，成交 {len(trades)} 笔",
        "data": [t.model_dump() for t in trades]
    }
