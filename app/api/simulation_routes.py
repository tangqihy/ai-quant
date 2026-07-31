"""
模拟交易 API 路由
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.models.simulation import OrderRequest, Order, Trade, Position, Account
from app.services.simulation_service import simulation_service
from app.services.signal_service import evaluate_signal
from app.services.risk_service import risk_service
from app.services.stock_service import stock_service
from app.core.response import ok, fail

router = APIRouter(prefix="/simulation", tags=["模拟交易"])


class ExecuteSignalRequest(BaseModel):
    symbol: str
    strategy: str = "rsi"
    params: Optional[Dict[str, Any]] = None
    period: str = "daily"
    as_of: Optional[str] = Field(None, description="回放时点；盘后联调时按该时点评估信号")
    position_pct: float = Field(5.0, ge=0.1, le=100, description="买入仓位占权益比例%")
    order_type: str = "MARKET"
    force: bool = Field(False, description="忽略时段限制强制下单")
    stop_loss_pct: Optional[float] = Field(2.0, description="买入后设置止损%")
    stop_profit_pct: Optional[float] = Field(4.0, description="买入后设置止盈%")


@router.post("/reset")
async def reset_account(initial_capital: float = 1000000.0):
    """重置模拟账户"""
    simulation_service.reset_account(initial_capital)
    return ok(message=f"账户已重置，初始资金: {initial_capital:,.2f}")


@router.get("/account")
async def get_account() -> dict:
    """获取账户信息"""
    account = simulation_service.get_account()
    return ok(data=account.model_dump())


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
    if order.status == "REJECTED":
        return fail(error="订单被拒绝", message=order.rejected_reason)
    return ok(data=order.model_dump())


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """撤销订单"""
    success = simulation_service.cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=400, detail="撤单失败，订单不存在或已成交")
    return ok(message="撤单成功")


@router.get("/orders")
async def get_orders(
    status: Optional[str] = Query(None, description="订单状态筛选")
):
    """获取订单列表"""
    orders = simulation_service.get_orders(status)
    return ok(data=[o.model_dump() for o in orders])


@router.get("/trades")
async def get_trades():
    """获取成交记录"""
    trades = simulation_service.get_trades()
    return ok(data=[t.model_dump() for t in trades])


@router.get("/positions")
async def get_positions():
    """获取持仓列表"""
    positions = simulation_service.get_positions()
    return ok(data=[p.model_dump() for p in positions])


@router.post("/match")
async def match_orders():
    """触发订单撮合（测试用）"""
    trades = simulation_service.match_orders()
    return ok(data=[t.model_dump() for t in trades], message=f"撮合完成，成交 {len(trades)} 笔")


@router.post("/execute-signal")
async def execute_signal(req: ExecuteSignalRequest):
    """
    根据策略信号一键模拟下单（半自动 Paper）：
    BUY/SELL 且（在允许时段或 force）时创建市价/限价单并立即撮合。
    """
    signal = evaluate_signal(
        symbol=req.symbol.strip(),
        strategy=req.strategy,
        params=req.params,
        period=req.period,
        as_of=req.as_of,
    )
    if "error" in signal:
        return fail(error=signal["error"])

    action = signal.get("action")
    if action not in ("BUY", "SELL"):
        return ok(
            data={"signal": signal, "order": None, "trades": []},
            message="当前无买卖信号，未下单",
        )
    if not signal.get("in_trading_window") and not req.force:
        return {
            "success": False,
            "error": "OUT_OF_WINDOW",
            "message": signal.get("window_reason") or "不在允许下单时段",
            "data": {"signal": signal},
        }

    account = simulation_service.get_account()
    price = float(signal.get("suggested_price") or signal.get("quote_price") or 0)
    if price <= 0:
        return {
            "success": False,
            "error": "NO_PRICE",
            "message": "无法获取有效价格",
            "data": {"signal": signal},
        }

    positions = {p.symbol: p for p in simulation_service.get_positions()}
    if action == "BUY":
        budget = account.total_value * (req.position_pct / 100.0)
        qty = int(budget / price / 100) * 100
        if qty < 100:
            return {
                "success": False,
                "error": "QTY_TOO_SMALL",
                "message": "按仓位计算不足 100 股",
                "data": {"signal": signal},
            }
    else:
        pos = positions.get(req.symbol.strip())
        qty = int(pos.quantity) if pos else 0
        if qty < 100:
            return {
                "success": False,
                "error": "NO_POSITION",
                "message": "无持仓可卖",
                "data": {"signal": signal},
            }

    order_type = req.order_type if req.order_type in ("MARKET", "LIMIT") else "MARKET"
    order = simulation_service.create_order(
        symbol=req.symbol.strip(),
        action=action,
        order_type=order_type,
        price=None if order_type == "MARKET" else price,
        quantity=qty,
    )
    if order.status == "REJECTED":
        return {
            "success": False,
            "error": "订单被拒绝",
            "message": order.rejected_reason,
            "data": {"signal": signal, "order": order.model_dump()},
        }

    trades = simulation_service.match_orders()
    related = [t.model_dump() for t in trades if t.order_id == order.id]

    stop_config = None
    if action == "BUY" and req.stop_loss_pct is not None:
        try:
            cfg = risk_service.set_stop_loss(
                symbol=req.symbol.strip(),
                position_id=req.symbol.strip(),
                stop_loss_pct=req.stop_loss_pct,
                stop_profit_pct=req.stop_profit_pct,
            )
            stop_config = cfg.model_dump()
        except Exception:
            stop_config = None

    return ok(
        data={
            "signal": signal,
            "order": order.model_dump(),
            "trades": related,
            "stop_loss": stop_config,
        },
        message=f"已按信号{action} {qty}股",
    )


@router.post("/check-stops")
async def check_stops():
    """
    扫描模拟持仓止损/止盈：触发则自动市价平仓。
    """
    positions = simulation_service.get_positions()
    alerts = []
    orders = []
    trades_out = []

    for pos in positions:
        if pos.quantity <= 0:
            continue
        try:
            quote = stock_service.get_realtime_quote(pos.symbol)
            price = float(quote.get("price") or pos.market_price or 0)
        except Exception:
            price = float(pos.market_price or 0)
        if price <= 0:
            continue

        config = risk_service.get_stop_loss_config(pos.symbol)
        if config is None and pos.avg_cost > 0:
            try:
                risk_service.set_stop_loss(
                    symbol=pos.symbol,
                    position_id=pos.symbol,
                    stop_loss_pct=2.0,
                    stop_profit_pct=4.0,
                )
            except Exception:
                continue

        alert = risk_service.check_stop_loss(pos.symbol, price)
        if alert is None:
            continue

        alerts.append(alert.model_dump())
        order = simulation_service.create_order(
            symbol=pos.symbol,
            action="SELL",
            order_type="MARKET",
            price=None,
            quantity=pos.quantity,
        )
        orders.append(order.model_dump())
        if order.status != "REJECTED":
            matched = simulation_service.match_orders()
            trades_out.extend([t.model_dump() for t in matched if t.order_id == order.id])
            risk_service.remove_stop_loss(pos.symbol)

    return ok(
        data={"alerts": alerts, "orders": orders, "trades": trades_out},
        message=f"止损扫描完成，触发 {len(alerts)} 笔",
    )
