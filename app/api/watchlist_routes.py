"""
自选数据 API 路由
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from app.models.watchlist import (
    WatchlistData, WatchlistGroup, WatchlistItem,
    CreateGroupRequest, AddStockRequest, UpdateStockRequest, RenameGroupRequest
)
from app.services.watchlist_store import (
    get_groups, create_group, update_group, delete_group,
    get_stocks, get_stock, add_stock, remove_stock,
    update_stock_groups, update_stock_note, get_all_data
)
from app.api.deps import require_auth

router = APIRouter(prefix="/watchlist", tags=["自选"], dependencies=[Depends(require_auth)])


@router.get("/data")
async def get_watchlist_data():
    """获取完整自选数据"""
    data = get_all_data()
    return {
        "success": True,
        "data": data
    }


# ==================== 分组管理 ====================

@router.get("/groups")
async def get_watchlist_groups():
    """获取所有分组"""
    groups = get_groups()
    return {
        "success": True,
        "data": groups
    }


@router.post("/groups")
async def create_watchlist_group(request: CreateGroupRequest):
    """创建分组"""
    group_id = str(uuid.uuid4())[:8]
    group = create_group(group_id, request.name, request.color)
    return {
        "success": True,
        "data": group
    }


@router.put("/groups/{group_id}")
async def update_watchlist_group(group_id: str, request: RenameGroupRequest):
    """更新分组"""
    success = update_group(group_id, name=request.name)
    if not success:
        raise HTTPException(status_code=404, detail="分组不存在")
    return {
        "success": True,
        "message": "分组更新成功"
    }


@router.delete("/groups/{group_id}")
async def delete_watchlist_group(group_id: str):
    """删除分组"""
    success = delete_group(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="分组不存在")
    return {
        "success": True,
        "message": "分组删除成功"
    }


# ==================== 股票管理 ====================

@router.get("/stocks")
async def get_watchlist_stocks():
    """获取所有自选股票"""
    stocks = get_stocks()
    return {
        "success": True,
        "data": stocks
    }



@router.post("/stocks")
async def add_watchlist_stock(request: AddStockRequest):
    """添加自选股票"""
    # 检查是否已存在
    existing = get_stock(request.symbol)
    if existing:
        # 更新分组
        update_stock_groups(request.symbol, request.group_ids)
        if request.note:
            update_stock_note(request.symbol, request.note)
        return {
            "success": True,
            "message": "股票已更新",
            "data": get_stock(request.symbol)
        }

    stock = add_stock(
        symbol=request.symbol,
        name=request.name,
        group_ids=request.group_ids,
        note=request.note
    )
    return {
        "success": True,
        "message": "添加成功",
        "data": stock
    }


@router.delete("/stocks/{symbol}")
async def remove_watchlist_stock(symbol: str):
    """移除自选股票"""
    success = remove_stock(symbol)
    if not success:
        raise HTTPException(status_code=404, detail="股票不在自选")
    return {
        "success": True,
        "message": "移除成功"
    }


@router.put("/stocks/{symbol}/groups")
async def update_stock_groups_api(symbol: str, request: UpdateStockRequest):
    """更新股票分组"""
    if request.group_ids is None:
        raise HTTPException(status_code=400, detail="group_ids 不能为空")
    success = update_stock_groups(symbol, request.group_ids)
    if not success:
        raise HTTPException(status_code=404, detail="股票不存在")
    return {
        "success": True,
        "message": "分组更新成功"
    }


@router.put("/stocks/{symbol}/note")
async def update_stock_note_api(symbol: str, request: UpdateStockRequest):
    """更新股票备注"""
    if request.note is None:
        raise HTTPException(status_code=400, detail="note 不能为空")
    success = update_stock_note(symbol, request.note)
    if not success:
        raise HTTPException(status_code=404, detail="股票不存在")
    return {
        "success": True,
        "message": "备注更新成功"
    }
