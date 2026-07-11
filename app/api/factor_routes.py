"""
因子分析API路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.services.factor_service import (
    get_factor_ic,
    get_effective_factors,
    get_factor_by_name,
    get_factor_summary,
)

router = APIRouter(prefix="/factors", tags=["因子分析"])


@router.get("/ic")
async def factor_ic():
    """获取所有因子IC分析结果"""
    data = get_factor_ic()
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.get("/summary")
async def factor_summary():
    """获取因子概览统计"""
    data = get_factor_summary()
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.get("/effective")
async def effective_factors():
    """获取有效因子列表"""
    factors = get_effective_factors()
    return {"factors": factors, "count": len(factors)}


@router.get("/{factor_name}")
async def factor_detail(factor_name: str):
    """获取单个因子详情"""
    factor = get_factor_by_name(factor_name)
    if factor is None:
        raise HTTPException(status_code=404, detail=f"因子 {factor_name} 不存在")
    return factor


@router.get("/{factor_name}/distribution")
async def factor_distribution(factor_name: str):
    """获取因子分组收益分布（用于画图）"""
    factor = get_factor_by_name(factor_name)
    if factor is None:
        raise HTTPException(status_code=404, detail=f"因子 {factor_name} 不存在")

    return {
        "factor_name": factor["name"],
        "display_name": factor["display_name"],
        "group_returns": factor.get("group_returns", []),
        "group_labels": factor.get("group_labels", []),
        "icir": factor["icir"],
        "direction": factor["direction"],
    }
