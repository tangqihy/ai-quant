"""
因子分析API路由
"""
from pathlib import Path
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.services.factor_service import (
    get_factor_ic,
    get_effective_factors,
    get_factor_by_name,
    get_factor_summary,
)
from app.api.deps import require_auth

router = APIRouter(prefix="/factors", tags=["因子分析"], dependencies=[Depends(require_auth)])


@router.get("/ic")
async def factor_ic():
    """获取所有因子IC分析结果"""
    return get_factor_ic()


@router.get("/summary")
async def factor_summary():
    """获取因子概览统计"""
    return get_factor_summary()


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


@router.post("/refresh")
async def refresh_factor_ic(
    start: Optional[str] = Query(None, description="起始日期 YYYYMMDD"),
    end: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    forward_days: int = Query(10, ge=1, le=60),
    skip_download: bool = Query(True),
):
    """
    触发因子 IC 刷新（同步执行，通常建议在夜间使用）。
    """
    cmd = ["python", "scripts/run_factor_ic.py", "--forward-days", str(forward_days)]
    if start:
        cmd += ["--start", start]
    if end:
        cmd += ["--end", end]
    if skip_download:
        cmd.append("--skip-download")

    repo_root = Path(__file__).resolve().parents[2]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60 * 60,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="刷新超时，请缩短区间或改用离线脚本")

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "因子刷新失败"
        raise HTTPException(status_code=500, detail=detail)

    return {
        "success": True,
        "message": "因子IC刷新完成",
        "output": (completed.stdout or "").splitlines()[-20:],
    }
