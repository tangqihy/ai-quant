"""
信号评估与策略会话 API
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.response import ok, fail
from app.services.signal_service import evaluate_signal, scan_signal_timeline
from app.services.strategy_session_store import strategy_session_store
from app.strategies import list_strategies

router = APIRouter(prefix="/signals", tags=["信号监控"])


class SignalEvaluateRequest(BaseModel):
    symbol: str = Field(..., description="股票代码")
    strategy: str = Field("rsi", description="策略 ID")
    params: Optional[Dict[str, Any]] = Field(None, description="策略参数")
    period: str = Field("daily", description="K线周期 daily/5min/...")
    as_of: Optional[str] = Field(
        None,
        description="回放时点：YYYY-MM-DD 或 YYYY-MM-DD HH:mm；不传则为实时最新一根",
    )
    lookback_days: int = Field(120, ge=30, le=500, description="加载历史天数")


class SignalReplayRequest(BaseModel):
    symbol: str
    strategy: str = "rsi"
    params: Optional[Dict[str, Any]] = None
    period: str = "daily"
    as_of: Optional[str] = Field(None, description="截断终点（含），默认至今")
    lookback_days: int = Field(120, ge=30, le=500)
    warm_up: int = Field(30, ge=5, le=200, description="前 N 根预热，不进入步进列表")


class StrategySessionRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    symbol: str
    strategy: str
    params: Optional[Dict[str, Any]] = None
    period: str = "daily"
    position_pct: float = 5.0
    stop_loss_pct: float = 2.0
    stop_profit_pct: float = 4.0
    enabled: bool = True
    observe_factors: Optional[List[str]] = None
    exclusive_enable: bool = True


@router.get("/strategies")
async def signal_strategies():
    """信号页可用策略列表（与回测注册表一致）。"""
    return ok(data=list_strategies())


@router.post("/evaluate")
async def evaluate(req: SignalEvaluateRequest):
    result = evaluate_signal(
        symbol=req.symbol.strip(),
        strategy=req.strategy,
        params=req.params,
        period=req.period,
        as_of=req.as_of,
        lookback_days=req.lookback_days,
    )
    if "error" in result:
        return fail(error=result["error"])
    return ok(data=result)


@router.post("/replay")
async def replay_timeline(req: SignalReplayRequest):
    """
    历史回放时间轴：一次算出区间内每根 bar 的信号，供前端逐根步进。
    """
    result = scan_signal_timeline(
        symbol=req.symbol.strip(),
        strategy=req.strategy,
        params=req.params,
        period=req.period,
        as_of=req.as_of,
        lookback_days=req.lookback_days,
        warm_up=req.warm_up,
    )
    if "error" in result:
        return fail(error=result["error"])
    return ok(data=result, message=f"回放就绪，可步进 {result.get('step_total', 0)} 根")


@router.get("/evaluate")
async def evaluate_get(
    symbol: str = Query(..., description="股票代码"),
    strategy: str = Query("rsi"),
    bar_period: str = Query("daily", description="K线周期"),
    as_of: Optional[str] = Query(None, description="回放时点"),
    rsi_period: Optional[int] = Query(None, description="RSI 周期"),
    oversold: Optional[int] = Query(None),
    overbought: Optional[int] = Query(None),
    short_window: Optional[int] = Query(None),
    long_window: Optional[int] = Query(None),
):
    params: Dict[str, Any] = {}
    if rsi_period is not None:
        params["period"] = rsi_period
    if oversold is not None:
        params["oversold"] = oversold
    if overbought is not None:
        params["overbought"] = overbought
    if short_window is not None:
        params["short_window"] = short_window
    if long_window is not None:
        params["long_window"] = long_window
    result = evaluate_signal(
        symbol=symbol.strip(),
        strategy=strategy,
        params=params or None,
        period=bar_period,
        as_of=as_of,
    )
    if "error" in result:
        return fail(error=result["error"])
    return ok(data=result)


@router.get("/sessions")
async def list_sessions():
    return ok(data=strategy_session_store.list_sessions())


@router.get("/sessions/active")
async def get_active_session():
    session = strategy_session_store.get_active()
    return ok(data=session)


@router.post("/sessions")
async def upsert_session(req: StrategySessionRequest):
    session = strategy_session_store.upsert(req.model_dump())
    return ok(data=session, message="会话已保存")


@router.post("/sessions/{session_id}/enable")
async def enable_session(session_id: str, enabled: bool = Query(True)):
    session = strategy_session_store.set_enabled(session_id, enabled)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ok(data=session)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if not strategy_session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return ok(message="已删除")


@router.post("/sessions/{session_id}/evaluate")
async def evaluate_session(session_id: str):
    session = strategy_session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    result = evaluate_signal(
        symbol=session["symbol"],
        strategy=session["strategy"],
        params=session.get("params"),
        period=session.get("period") or "daily",
    )
    if "error" in result:
        return fail(error=result["error"])
    result["session_id"] = session_id
    result["session"] = session
    return ok(data=result)
