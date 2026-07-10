"""
Basic market factors.

All factors use ``@factor_registry.register`` with an appropriate *direction*
so that after orientation, "higher = better".

Factors:
- total_mv      (direction=-1)  小市值效应
- pe_ttm        (direction=-1)  低PE效应
- pb            (direction=-1)  低PB效应
- turnover_rate (direction=-1)  低换手率效应
- dv_ttm        (direction=1)   高股息效应
"""
from __future__ import annotations

import logging

import pandas as pd

from .registry import factor_registry

logger = logging.getLogger(__name__)


def _get_cross_section(date: str, pit, fields: list[str]) -> pd.DataFrame:
    """Fetch a cross-section snapshot and extract requested fields.

    ``pit`` is a :class:`~app.data.pit.PITQuery` instance whose
    ``get_cross_section`` merges daily, daily_basic, and financial data.

    The returned column names in the cross-section may be prefixed
    (e.g. ``basic__total_mv``).  We try the bare name first, then
    fall back to ``prefix__name`` variants.
    """
    df = pit.get_cross_section(date)
    if df.empty:
        return pd.DataFrame(columns=["ts_code"] + fields)

    result_cols = {"ts_code": df["ts_code"]}
    for f in fields:
        if f in df.columns:
            result_cols[f] = df[f]
        else:
            # try prefixed variants
            found = False
            for prefix in ("basic__", "daily__", "fina__"):
                col = f"{prefix}{f}"
                if col in df.columns:
                    result_cols[f] = df[col]
                    found = True
                    break
            if not found:
                result_cols[f] = pd.Series(dtype="float64")

    return pd.DataFrame(result_cols)


# ======================================================================
# Market Factors
# ======================================================================


@factor_registry.register(
    name="total_mv",
    description="总市值（万元）",
    category="market",
    direction=-1,  # 小市值效应: lower mv → higher oriented value
)
def compute_total_mv(date: str, pit, **kwargs) -> pd.DataFrame:
    """Total market value factor."""
    df = _get_cross_section(date, pit, ["total_mv"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["total_mv"],
    })


@factor_registry.register(
    name="pe_ttm",
    description="市盈率TTM",
    category="market",
    direction=-1,  # 低PE效应
)
def compute_pe_ttm(date: str, pit, **kwargs) -> pd.DataFrame:
    """PE TTM factor."""
    df = _get_cross_section(date, pit, ["pe_ttm"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["pe_ttm"],
    })


@factor_registry.register(
    name="pb",
    description="市净率",
    category="market",
    direction=-1,  # 低PB效应
)
def compute_pb(date: str, pit, **kwargs) -> pd.DataFrame:
    """PB (Price-to-Book) factor."""
    df = _get_cross_section(date, pit, ["pb"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["pb"],
    })


@factor_registry.register(
    name="turnover_rate",
    description="换手率",
    category="market",
    direction=-1,  # 低换手效应
)
def compute_turnover_rate(date: str, pit, **kwargs) -> pd.DataFrame:
    """Turnover rate factor."""
    df = _get_cross_section(date, pit, ["turnover_rate"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["turnover_rate"],
    })


@factor_registry.register(
    name="dv_ttm",
    description="股息率TTM",
    category="market",
    direction=1,  # 高股息效应
)
def compute_dv_ttm(date: str, pit, **kwargs) -> pd.DataFrame:
    """Dividend yield TTM factor."""
    df = _get_cross_section(date, pit, ["dv_ttm"])
    return pd.DataFrame({
        "ts_code": df["ts_code"],
        "trade_date": date,
        "factor_value": df["dv_ttm"],
    })
