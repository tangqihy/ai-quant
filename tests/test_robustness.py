"""稳健性邻域 / Monte Carlo 生成与汇总单测（不依赖外网行情）。"""
from app.services.robustness_service import (
    generate_monte_carlo_variants,
    generate_neighborhood_variants,
    _summarize,
    _params_key,
)


SCHEMA = [
    {
        "name": "short_window",
        "type": "int",
        "default": 5,
        "min": 2,
        "max": 30,
        "step": 1,
    },
    {
        "name": "long_window",
        "type": "int",
        "default": 20,
        "min": 5,
        "max": 120,
        "step": 1,
    },
]


def test_neighborhood_includes_baseline_and_varies_one_at_a_time():
    baseline = {"short_window": 5, "long_window": 20}
    variants = generate_neighborhood_variants(
        baseline, SCHEMA, perturbation_pct=0.4, n_steps=5
    )
    assert variants[0] == baseline
    assert len(variants) > 1
    # 除 baseline 外，每次只改一个键（相对 baseline）
    for v in variants[1:]:
        diffs = [k for k in baseline if v[k] != baseline[k]]
        assert len(diffs) == 1


def test_monte_carlo_deterministic_with_seed():
    baseline = {"short_window": 5, "long_window": 20}
    a = generate_monte_carlo_variants(
        baseline, SCHEMA, perturbation_pct=0.3, n_samples=10, seed=7
    )
    b = generate_monte_carlo_variants(
        baseline, SCHEMA, perturbation_pct=0.3, n_samples=10, seed=7
    )
    assert [_params_key(x) for x in a] == [_params_key(x) for x in b]
    assert a[0] == baseline


def test_summarize_classification_and_cross_symbol():
    baseline = {"short_window": 5, "long_window": 20}
    runs = []
    for sym in ("AAA", "BBB"):
        runs.append(
            {
                "symbol": sym,
                "params": baseline,
                "is_baseline": True,
                "success": True,
                "total_return": 8.0,
                "sharpe": 1.0,
                "max_drawdown": 5.0,
                "win_rate": 50.0,
                "total_trades": 4,
            }
        )
        for i, sh in enumerate([0.9, 1.05, 0.95, 1.1]):
            runs.append(
                {
                    "symbol": sym,
                    "params": {"short_window": 4 + i, "long_window": 20},
                    "is_baseline": False,
                    "success": True,
                    "total_return": 6.0 + i,
                    "sharpe": sh,
                    "max_drawdown": 6.0,
                    "win_rate": 45.0,
                    "total_trades": 3,
                }
            )
    summary = _summarize(runs, baseline, plateau_threshold=0.9)
    assert summary["baseline_metrics"] is not None
    assert summary["cross_symbol"]["n_symbols"] == 2
    assert summary["classification"] in ("robust", "moderate", "sensitive")
    assert "distribution" in summary
    assert summary["distribution"]["sharpe"]["count"] > 0
