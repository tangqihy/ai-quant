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
        fina = _fallback_financial(universe, date, pit, "fina_indicator")
        if fina.empty:
            return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    roe_col = _find_column(fina, "roe")
    if roe_col is None:
        roe_col = _find_column(fina, "q_roe")
    if roe_col is None:
        # fallback from income + balance sheet
        income = _fallback_financial(universe, date, pit, "income")
        balance = _fallback_financial(universe, date, pit, "balancesheet")
        net_col = _find_column(income, "n_income_attr_p") or _find_column(income, "n_income")
        eq_col = _find_column(balance, "total_hldr_eqy_exc_min_int") or _find_column(balance, "total_hldr_eqy_inc_min_int")
        if net_col and eq_col and not income.empty and not balance.empty:
            merged = income[["ts_code", net_col]].merge(balance[["ts_code", eq_col]], on="ts_code", how="inner")
            merged["factor_value"] = merged[net_col] / merged[eq_col].replace(0, pd.NA)
            return pd.DataFrame({
                "ts_code": merged["ts_code"],
                "trade_date": date,
                "factor_value": merged["factor_value"],
            })
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
        fina = _fallback_financial(universe, date, pit, "fina_indicator")
        if fina.empty:
            return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    col = _find_column(fina, "grossprofit_margin")
    if col is None:
        # fallback: try grossprofit_margin in income statement
        fina2 = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface="income")
        if fina2 is None or fina2.empty:
            fina2 = _fallback_financial(universe, date, pit, "income")
        if fina2 is not None and not fina2.empty:
            col = _find_column(fina2, "grossprofit_margin")
            if col is None:
                revenue_col = _find_column(fina2, "revenue")
                cost_col = _find_column(fina2, "oper_cost")
                if revenue_col and cost_col:
                    tmp = fina2[["ts_code", revenue_col, cost_col]].copy()
                    tmp["factor_value"] = (tmp[revenue_col] - tmp[cost_col]) / tmp[revenue_col].replace(0, pd.NA)
                    return pd.DataFrame(
                        {"ts_code": tmp["ts_code"], "trade_date": date, "factor_value": tmp["factor_value"]}
                    )
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
        fina = _fallback_financial(universe, date, pit, "fina_indicator")
        if fina.empty:
            fina = _fallback_financial(universe, date, pit, "balancesheet")
            if fina.empty:
                return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    col = _find_column(fina, "debt_to_assets")
    if col is None:
        liab_col = _find_column(fina, "total_liab")
        asset_col = _find_column(fina, "total_assets")
        if liab_col and asset_col:
            tmp = fina[["ts_code", liab_col, asset_col]].copy()
            tmp["factor_value"] = tmp[liab_col] / tmp[asset_col].replace(0, pd.NA)
            return pd.DataFrame({"ts_code": tmp["ts_code"], "trade_date": date, "factor_value": tmp["factor_value"]})
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
        fina = _fallback_financial(universe, date, pit, "fina_indicator")
        if fina.empty:
            return pd.DataFrame(columns=["ts_code", "trade_date", "factor_value"])

    col = _find_column(fina, "netprofit_yoy")
    if col is None:
        col = _find_column(fina, "dt_netprofit_yoy")
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


def _fallback_financial(universe: list[str], date: str, pit, interface: str) -> pd.DataFrame:
    """
    Fall back to PITQuery cross section when direct PIT batch is unavailable.
    """
    try:
        data = pit.pit.get_financial_pit_batch(universe, date, report_type=1, interface=interface)
        if data is not None and not data.empty:
            return data
    except Exception:
        pass
    try:
        cs = pit.get_cross_section(date, ts_codes=universe)
        return cs if cs is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()
