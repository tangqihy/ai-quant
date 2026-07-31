"""
Stock Canvas API 路由

设计文档：docs/design/07-stock-canvas.md
注意：跨画布搜索使用 /canvas-search 独立路径，避免被 /canvas/{ts_code} 吞掉。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.response import ok
from app.models.canvas import (
    AddCardRequest,
    CanvasStatus,
    CardType,
    CreateCanvasRequest,
    EdgeType,
    LinkCardsRequest,
    UpdateCanvasRequest,
    UpdateCardRequest,
)
from app.services.canvas_service import (
    CanvasAlreadyExistsError,
    CanvasNotFoundError,
    CanvasService,
    CardNotFoundError,
    InvalidLinkError,
)
from app.services.canvas_store import CanvasStore

router = APIRouter(tags=["研究画布"])

_service = CanvasService(CanvasStore())


def _to_http(e: ValueError) -> HTTPException:
    if isinstance(e, CanvasAlreadyExistsError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, (CanvasNotFoundError, CardNotFoundError)):
        return HTTPException(status_code=404, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


# ==================== 画布 ====================

@router.get("/canvas")
async def list_canvases(status: Optional[str] = Query(None, description="按状态筛选")):
    """列出所有画布"""
    try:
        canvases = _service.list_canvases(status=status)
        return ok(data=[c.model_dump(mode="json") for c in canvases])
    except ValueError as e:
        raise _to_http(e)


@router.post("/canvas")
async def create_canvas(request: CreateCanvasRequest):
    """创建画布"""
    try:
        canvas = _service.create_canvas(request)
        return ok(data=canvas.model_dump(mode="json"), message="画布已创建")
    except ValueError as e:
        raise _to_http(e)


@router.get("/canvas/{ts_code}")
async def get_canvas_detail(ts_code: str):
    """画布详情（含所有卡片和关联）"""
    try:
        detail = _service.get_canvas_detail(ts_code)
        return ok(data=detail.model_dump(mode="json"))
    except ValueError as e:
        raise _to_http(e)


@router.patch("/canvas/{ts_code}")
async def update_canvas(ts_code: str, request: UpdateCanvasRequest):
    """更新画布状态/元数据"""
    try:
        canvas = _service.update_canvas(ts_code, request)
        return ok(data=canvas.model_dump(mode="json"))
    except ValueError as e:
        raise _to_http(e)


@router.delete("/canvas/{ts_code}")
async def delete_canvas(ts_code: str):
    """删除画布（级联删除卡片与关联）"""
    if not _service.store.delete_canvas(ts_code):
        raise HTTPException(status_code=404, detail=f"画布不存在: {ts_code}")
    return ok(message="画布已删除")


# ==================== 卡片 ====================

@router.post("/canvas/{ts_code}/cards")
async def add_card(ts_code: str, request: AddCardRequest):
    """向画布添加卡片"""
    try:
        card = _service.add_card(ts_code, request)
        return ok(data=card.model_dump(mode="json"), message="卡片已添加")
    except ValueError as e:
        raise _to_http(e)


@router.patch("/canvas/cards/{card_id}")
async def update_card(card_id: str, request: UpdateCardRequest):
    """更新卡片"""
    try:
        card = _service.update_card(card_id, request)
        return ok(data=card.model_dump(mode="json"))
    except ValueError as e:
        raise _to_http(e)


@router.delete("/canvas/cards/{card_id}")
async def delete_card(card_id: str):
    """删除卡片"""
    try:
        _service.delete_card(card_id)
        return ok(message="卡片已删除")
    except ValueError as e:
        raise _to_http(e)


# ==================== 关联 ====================

@router.post("/canvas/edges")
async def link_cards(request: LinkCardsRequest):
    """建立卡片关联"""
    try:
        edge = _service.link_cards(
            request.source_card_id, request.target_card_id,
            request.edge_type, label=request.label,
        )
        return ok(data=edge.model_dump(mode="json"), message="关联已建立")
    except ValueError as e:
        raise _to_http(e)


@router.delete("/canvas/edges/{edge_id}")
async def delete_edge(edge_id: str):
    """删除关联"""
    try:
        _service.delete_edge(edge_id)
        return ok(message="关联已删除")
    except ValueError as e:
        raise _to_http(e)


# ==================== 查询 ====================

@router.get("/canvas-search")
async def search_cards(
    keyword: str = Query(..., description="搜索关键字"),
    ts_code: Optional[str] = Query(None, description="限定画布"),
    card_type: Optional[str] = Query(None, description="限定卡片类型"),
):
    """跨画布搜索卡片"""
    try:
        ct = CardType(card_type) if card_type else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"非法卡片类型: {card_type}")
    cards = _service.search_cards(keyword, ts_code=ts_code, card_type=ct)
    return ok(data=[c.model_dump(mode="json") for c in cards])


@router.get("/canvas/{ts_code}/timeline")
async def get_timeline(ts_code: str):
    """画布时间线（从卡片日期字段派生）"""
    try:
        events = _service.get_timeline(ts_code)
        return ok(data=events)
    except ValueError as e:
        raise _to_http(e)


@router.get("/canvas/{ts_code}/decisions")
async def get_decisions(ts_code: str):
    """画布决策卡片（入场/出场计划、交易记录）"""
    try:
        cards = _service.get_decisions(ts_code)
        return ok(data=[c.model_dump(mode="json") for c in cards])
    except ValueError as e:
        raise _to_http(e)
