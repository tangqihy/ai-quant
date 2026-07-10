"""
Financial factors with Point-in-Time (PIT) correctness.

All factors query the PIT layer so that at date T we only see financial
data that was actually published on or before T (avoids look-ahead bias).

Factors:
- roe                (direction=1)   高ROE效应
- grossprofit_margin (direction=1)   高毛利率效应
- debt_to_assets     (direction=-1)  低资产负债率效应
- netprofit_yoy      (direction=1)   高净利润同比效应
"""
from __future__ import annotations

import logging

import pandas as pd

from .registry import factor_registry

logger = logging.getLogger(__name__)


@factor_registry.register(
    name="roe",
    description="净资产收益率 (ROE)",
    category="financial",
    direction=1,  # higher ROE → better
)
def compute_roe(date: str, pit, **kwargs) -> pd.DataFrame:
    """ROE factor (PIT-correct).

    Queries the ``fina_indicator`` interface via the PIT layer so only
    reports actually published by *date* are visible.
    """
    universe = pit.get_universe(date)
    if not universe:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    fina = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface="fina_indicator")
    if fina is None or fina.empty:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    roe_col = _find_column(fina, "roe")
    if roe_col is None:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    return pd.DataFrame({
        "ts_code": fina["ts_code"],
        "trade_date": date,
        "factor_value": fina[roe_col],
    })


@factor_registry.register(
    name="grossprofit_margin",
    description="销售毛利率",
    category="financial",
    direction=1,  # higher margin → better
)
def compute_grossprofit_margin(date: str, pit, **kwargs) -> pd.DataFrame:
    """Gross profit margin factor (PIT-correct)."""
    universe = pit.get_universe(date)
    if not universe:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    fina = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface="fina_indicator")
    if fina is None or fina.empty:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    col = _find_column(fina, "grossprofit_margin")
    if col is None:
        # fallback: try grossprofit_margin in income statement
        fina2 = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface="income")
        if fina2 is not None and not fina2.empty:
            col = _find_column(fina2, "grossprofit_margin")
            if col is not None:
                fina = fina2
        if col is None:
            return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    return pd.DataFrame({
        "ts_code": fina["ts_code"],
        "trade_date": date,
        "factor_value": fina[col],
    })


@factor_registry.register(
    name="debt_to_assets",
    description="资产负债率",
    category="financial",
    direction=-1,  # lower leverage → better
)
def compute_debt_to_assets(date: str, pit, **kwargs) -> pd.DataFrame:
    """Debt-to-assets ratio factor (PIT-correct)."""
    universe = pit.get_universe(date)
    if not universe:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    fina = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface="fina_indicator")
    if fina is None or fina.empty:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    col = _find_column(fina, "debt_to_assets")
    if col is None:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    return pd.DataFrame({
        "ts_code": fina["ts_code"],
        "trade_date": date,
        "factor_value": fina[col],
    })


@factor_registry.register(
    name="netprofit_yoy",
    description="净利润同比增长率",
    category="financial",
    direction=1,  # higher growth → better
)
def compute_netprofit_yoy(date: str, pit, **kwargs) -> pd.DataFrame:
    """Net profit year-over-year growth factor (PIT-correct)."""
    universe = pit.get_universe(date)
    if not universe:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    fina = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface="fina_indicator")
    if fina is None or fina.empty:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    col = _find_column(fina, "netprofit_yoy")
    if col is None:
        return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    return pd.DataFrame({
        "ts_code": fina["ts_code"],
        "trade_date": date,
        "factor_value": fina[col],
    })


# ======================================================================
# Helpers
# ======================================================================


def _find_column(df: pd.DataFrame, name: str) -> str | None:
    """Find *name* in *df* columns, trying bare name then prefixed variants."""
    if name in df.columns:
        return name
    for prefix in ("fina_indicator__", "fina__", "income__", "basic__"):
        col = f"{prefix}{name}"
        if col in df.columns:
            return col
    return None
