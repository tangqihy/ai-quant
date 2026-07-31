"""
稳健性检验 API：参数邻域扫描 / Monte Carlo + 多标的批跑。
"""
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ok, fail
from app.services.robustness_service import run_robustness

router = APIRouter(prefix="/backtest", tags=["稳健性检验"])


class RobustnessRequest(BaseModel):
    symbols: List[str] = Field(..., min_length=1, description="研究标的池")
    strategy: str = Field("ma_cross", description="策略 ID")
    baseline_params: Optional[Dict[str, Any]] = Field(
        None, description="基准参数；缺省用策略 param_schema 默认值"
    )
    start_date: Optional[str] = Field(None, description="YYYYMMDD")
    end_date: Optional[str] = Field(None, description="YYYYMMDD")
    initial_capital: float = Field(1_000_000, gt=0)
    mode: Literal["neighborhood", "monte_carlo"] = Field(
        "neighborhood",
        description="neighborhood=一次一参邻域扫描；monte_carlo=随机扰动",
    )
    perturbation_pct: float = Field(
        0.25, ge=0.05, le=1.0, description="相对 baseline 的扰动幅度（如 0.25=±25%）"
    )
    n_steps: int = Field(5, ge=2, le=21, description="邻域模式：每参数采样点数")
    n_samples: int = Field(30, ge=5, le=200, description="Monte Carlo 采样组数（不含 baseline）")
    seed: int = Field(42, description="Monte Carlo 随机种子")
    max_runs: int = Field(200, ge=1, le=500, description="总回测次数上限（标的×参数组）")
    plateau_threshold: float = Field(
        0.9, ge=0.5, le=1.0, description="平台区：Sharpe ≥ best×threshold 的比例"
    )


@router.post("/robustness")
async def robustness_check(req: RobustnessRequest):
    """
    对 baseline 参数做邻域/随机扰动，在多标的上批跑 backtest_v2，
    返回收益分布、baseline 分位、跨标的稳定性与 robust/moderate/sensitive 分类。
    """
    result = run_robustness(
        symbols=req.symbols,
        strategy=req.strategy,
        baseline_params=req.baseline_params,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        mode=req.mode,
        perturbation_pct=req.perturbation_pct,
        n_steps=req.n_steps,
        n_samples=req.n_samples,
        seed=req.seed,
        max_runs=req.max_runs,
        plateau_threshold=req.plateau_threshold,
    )
    if "error" in result:
        return fail(error=result["error"])
    return ok(data=result, message="稳健性检验完成")
