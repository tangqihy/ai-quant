"""
策略参数稳健性检验：邻域扫描 / Monte Carlo 扰动 + 多标的批跑。

复用 backtest_v2；同一标的只取一次 K 线，再对多组参数循环回测。
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.backtest_v2_service import run_backtest_v2
from app.services.signal_service import _coerce_params
from app.services.stock_service import stock_service
from app.strategies import get_strategy, list_strategies

def _schema_for(strategy_id: str) -> List[Dict[str, Any]]:
    meta = next((s for s in list_strategies() if s["id"] == strategy_id), None)
    if not meta:
        return []
    return list(meta.get("param_schema") or [])


def _param_bounds(
    spec: Dict[str, Any],
    baseline_val: float,
    perturbation_pct: float,
) -> Tuple[float, float]:
    base = float(baseline_val)
    pct = max(float(perturbation_pct), 0.0)
    lo = base * (1.0 - pct)
    hi = base * (1.0 + pct)
    if spec.get("min") is not None:
        lo = max(lo, float(spec["min"]))
    if spec.get("max") is not None:
        hi = min(hi, float(spec["max"]))
    if lo > hi:
        # ±pct 与 schema 无交集时退回 schema 全区间
        if spec.get("min") is not None and spec.get("max") is not None:
            lo, hi = float(spec["min"]), float(spec["max"])
        else:
            lo, hi = hi, lo
    return lo, hi


def _cast_param(spec: Dict[str, Any], value: float) -> Any:
    if spec.get("type") == "int":
        step = int(spec.get("step") or 1)
        v = int(round(value / step) * step) if step > 0 else int(round(value))
        if spec.get("min") is not None:
            v = max(v, int(spec["min"]))
        if spec.get("max") is not None:
            v = min(v, int(spec["max"]))
        return v
    return float(round(value, 6))


def _params_key(params: Dict[str, Any]) -> str:
    items = sorted((k, params[k]) for k in sorted(params.keys()))
    return repr(items)


def generate_neighborhood_variants(
    baseline: Dict[str, Any],
    schema: Sequence[Dict[str, Any]],
    perturbation_pct: float = 0.25,
    n_steps: int = 5,
) -> List[Dict[str, Any]]:
    """
    一次一参（OAT）邻域：固定其余参数，对每个参数在 [lo,hi] 上取 n_steps 点。
    首条始终为 baseline。
    """
    seen = {_params_key(baseline)}
    out: List[Dict[str, Any]] = [dict(baseline)]
    steps = max(int(n_steps), 2)

    for spec in schema:
        name = spec["name"]
        if name not in baseline:
            continue
        lo, hi = _param_bounds(spec, float(baseline[name]), perturbation_pct)
        if math.isclose(lo, hi, rel_tol=0, abs_tol=1e-9):
            continue
        for i in range(steps):
            raw = lo + (hi - lo) * i / (steps - 1)
            val = _cast_param(spec, raw)
            variant = dict(baseline)
            variant[name] = val
            key = _params_key(variant)
            if key in seen:
                continue
            seen.add(key)
            out.append(variant)
    return out


def generate_monte_carlo_variants(
    baseline: Dict[str, Any],
    schema: Sequence[Dict[str, Any]],
    perturbation_pct: float = 0.25,
    n_samples: int = 30,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """随机扰动：每组参数在邻域内均匀采样；首条为 baseline。"""
    rng = random.Random(int(seed))
    seen = {_params_key(baseline)}
    out: List[Dict[str, Any]] = [dict(baseline)]
    n = max(int(n_samples), 1)

    for _ in range(n):
        variant = dict(baseline)
        for spec in schema:
            name = spec["name"]
            if name not in baseline:
                continue
            lo, hi = _param_bounds(spec, float(baseline[name]), perturbation_pct)
            if math.isclose(lo, hi, rel_tol=0, abs_tol=1e-9):
                continue
            raw = rng.uniform(lo, hi)
            variant[name] = _cast_param(spec, raw)
        key = _params_key(variant)
        if key in seen:
            continue
        seen.add(key)
        out.append(variant)
    return out


def _percentile(sorted_vals: List[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _baseline_percentile(values: List[float], baseline: float) -> Optional[float]:
    """baseline 在样本中的经验分位（0–100）；越高表示 baseline 越靠右尾。"""
    if not values:
        return None
    below = sum(1 for v in values if v < baseline)
    equal = sum(1 for v in values if v == baseline)
    # mid-rank for ties
    return round((below + 0.5 * equal) / len(values) * 100.0, 2)


def _classify(stability_score: float, baseline_sharpe_pct: Optional[float]) -> str:
    """
    robust / moderate / sensitive
    - 平台区宽且 baseline 不在极端 → robust
    - baseline 分位过高（尖峰）或平台窄 → sensitive
    """
    tip_peak = baseline_sharpe_pct is not None and baseline_sharpe_pct >= 90
    if stability_score >= 0.8 and not tip_peak:
        return "robust"
    if stability_score >= 0.5 and not tip_peak:
        return "moderate"
    return "sensitive"


def _metric_distribution(runs: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    vals = [float(r[key]) for r in runs if r.get(key) is not None and "error" not in r]
    vals_sorted = sorted(vals)
    if not vals_sorted:
        return {"count": 0, "mean": None, "p5": None, "p50": None, "p95": None, "min": None, "max": None}
    mean = sum(vals_sorted) / len(vals_sorted)
    return {
        "count": len(vals_sorted),
        "mean": round(mean, 4),
        "p5": round(_percentile(vals_sorted, 5) or 0, 4),
        "p50": round(_percentile(vals_sorted, 50) or 0, 4),
        "p95": round(_percentile(vals_sorted, 95) or 0, 4),
        "min": round(vals_sorted[0], 4),
        "max": round(vals_sorted[-1], 4),
    }


def _summarize(
    runs: List[Dict[str, Any]],
    baseline_params: Dict[str, Any],
    plateau_threshold: float = 0.9,
) -> Dict[str, Any]:
    ok_runs = [r for r in runs if "error" not in r and r.get("success")]
    baseline_runs = [r for r in ok_runs if r.get("is_baseline")]
    baseline_metrics = None
    if baseline_runs:
        # 多标的时取 baseline 跨标的均值作为对照点
        b = baseline_runs
        baseline_metrics = {
            "total_return": round(sum(r["total_return"] for r in b) / len(b), 4),
            "sharpe": round(sum(r["sharpe"] for r in b) / len(b), 4),
            "max_drawdown": round(sum(r["max_drawdown"] for r in b) / len(b), 4),
            "win_rate": round(sum(r["win_rate"] for r in b) / len(b), 4),
            "n_symbols": len(b),
        }

    dist = {k: _metric_distribution(ok_runs, k) for k in ("total_return", "sharpe", "max_drawdown")}

    sharpes = [float(r["sharpe"]) for r in ok_runs if r.get("sharpe") is not None]
    best_sharpe = max(sharpes) if sharpes else None
    plateau_count = 0
    if best_sharpe is not None and best_sharpe > 0:
        thresh = best_sharpe * plateau_threshold
        plateau_count = sum(1 for s in sharpes if s >= thresh)
    elif best_sharpe is not None:
        # 全负时：接近最好（绝对值差距小）也算平台——用分位近似
        p50 = _percentile(sorted(sharpes), 50) or best_sharpe
        plateau_count = sum(1 for s in sharpes if s >= p50)
    stability_score = round(plateau_count / len(sharpes), 4) if sharpes else 0.0

    baseline_sharpe = baseline_metrics["sharpe"] if baseline_metrics else None
    baseline_sharpe_pct = (
        _baseline_percentile(sharpes, baseline_sharpe) if baseline_sharpe is not None else None
    )
    baseline_return = baseline_metrics["total_return"] if baseline_metrics else None
    returns = [float(r["total_return"]) for r in ok_runs if r.get("total_return") is not None]
    baseline_return_pct = (
        _baseline_percentile(returns, baseline_return) if baseline_return is not None else None
    )

    # 跨标的：baseline 各标的是否盈利 / 扰动中位是否为正
    by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    for r in ok_runs:
        by_symbol.setdefault(r["symbol"], []).append(r)

    symbol_rows = []
    profitable_baseline = 0
    stable_symbols = 0
    for sym, rows in by_symbol.items():
        b = next((x for x in rows if x.get("is_baseline")), None)
        rets = [float(x["total_return"]) for x in rows]
        med = _percentile(sorted(rets), 50)
        base_ret = float(b["total_return"]) if b else None
        if base_ret is not None and base_ret > 0:
            profitable_baseline += 1
        # 稳定：中位收益非负，且 baseline 相对中位跌幅不超过 50%（若 baseline>0）
        is_stable = med is not None and med >= 0
        if is_stable:
            stable_symbols += 1
        symbol_rows.append(
            {
                "symbol": sym,
                "baseline_return": round(base_ret, 4) if base_ret is not None else None,
                "baseline_sharpe": round(float(b["sharpe"]), 4) if b else None,
                "median_return": round(med, 4) if med is not None else None,
                "n_runs": len(rows),
                "stable": is_stable,
            }
        )

    n_sym = len(by_symbol) or 1
    cross_symbol_stability = round(stable_symbols / n_sym, 4)
    classification = _classify(stability_score, baseline_sharpe_pct)

    return {
        "baseline_params": baseline_params,
        "baseline_metrics": baseline_metrics,
        "distribution": dist,
        "stability_score": stability_score,
        "plateau_fraction": stability_score,
        "plateau_threshold": plateau_threshold,
        "baseline_sharpe_percentile": baseline_sharpe_pct,
        "baseline_return_percentile": baseline_return_pct,
        "classification": classification,
        "cross_symbol": {
            "n_symbols": len(by_symbol),
            "profitable_baseline_count": profitable_baseline,
            "stable_count": stable_symbols,
            "stability_ratio": cross_symbol_stability,
            "symbols": symbol_rows,
        },
        "n_ok": len(ok_runs),
        "n_failed": len(runs) - len(ok_runs),
    }


def run_robustness(
    symbols: List[str],
    strategy: str = "ma_cross",
    baseline_params: Optional[Dict[str, Any]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    initial_capital: float = 1_000_000,
    mode: str = "neighborhood",
    perturbation_pct: float = 0.25,
    n_steps: int = 5,
    n_samples: int = 30,
    seed: int = 42,
    max_runs: int = 200,
    plateau_threshold: float = 0.9,
) -> Dict[str, Any]:
    """
    多标的 × 参数扰动批跑。

    mode:
      - neighborhood: 一次一参邻域扫描
      - monte_carlo: 随机扰动采样
    """
    strategy_obj = get_strategy(strategy)
    if strategy_obj is None:
        return {"error": f"Unknown strategy: {strategy}"}

    cleaned = []
    for s in symbols or []:
        code = str(s or "").strip()
        if code and code not in cleaned:
            cleaned.append(code)
    if not cleaned:
        return {"error": "symbols 不能为空"}

    schema = _schema_for(strategy)
    baseline = _coerce_params(strategy, baseline_params)

    mode_l = (mode or "neighborhood").lower()
    if mode_l in ("monte_carlo", "mc", "random"):
        variants = generate_monte_carlo_variants(
            baseline, schema, perturbation_pct=perturbation_pct, n_samples=n_samples, seed=seed
        )
        mode_l = "monte_carlo"
    else:
        variants = generate_neighborhood_variants(
            baseline, schema, perturbation_pct=perturbation_pct, n_steps=n_steps
        )
        mode_l = "neighborhood"

    n_variants_full = len(variants)
    # 安全上限：优先保留 baseline（首条）+ 截断其余
    max_runs = max(int(max_runs), 1)
    if len(cleaned) * len(variants) > max_runs:
        max_variants = max(1, max_runs // len(cleaned))
        variants = variants[:max_variants]
    truncated = len(variants) < n_variants_full

    runs: List[Dict[str, Any]] = []
    baseline_key = _params_key(baseline)

    for symbol in cleaned:
        data = stock_service.get_stock_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
        if not data or len(data) < 50:
            runs.append(
                {
                    "symbol": symbol,
                    "params": baseline,
                    "is_baseline": True,
                    "success": False,
                    "error": "数据不足（需要至少50条K线）",
                }
            )
            continue

        for params in variants:
            is_base = _params_key(params) == baseline_key
            result = run_backtest_v2(
                symbol=symbol,
                data=data,
                strategy=strategy,
                initial_capital=initial_capital,
                **params,
            )
            if "error" in result:
                runs.append(
                    {
                        "symbol": symbol,
                        "params": params,
                        "is_baseline": is_base,
                        "success": False,
                        "error": result["error"],
                    }
                )
                continue
            runs.append(
                {
                    "symbol": symbol,
                    "params": params,
                    "is_baseline": is_base,
                    "success": True,
                    "total_return": result.get("total_return"),
                    "annual_return": result.get("annual_return"),
                    "max_drawdown": result.get("max_drawdown"),
                    "sharpe": result.get("sharpe"),
                    "win_rate": result.get("win_rate"),
                    "total_trades": result.get("total_trades"),
                    "final_value": result.get("final_value"),
                }
            )

    summary = _summarize(runs, baseline, plateau_threshold=plateau_threshold)

    return {
        "success": True,
        "mode": mode_l,
        "strategy": strategy,
        "symbols": cleaned,
        "perturbation_pct": perturbation_pct,
        "n_steps": n_steps if mode_l == "neighborhood" else None,
        "n_samples": n_samples if mode_l == "monte_carlo" else None,
        "seed": seed if mode_l == "monte_carlo" else None,
        "n_variants": len(variants),
        "n_runs": len(runs),
        "truncated": truncated,
        "start_date": start_date,
        "end_date": end_date,
        "summary": summary,
        "runs": runs,
    }
