"""
FieldSpec definitions and INTERFACE_CONFIG for data normalization.

Based on docs/design/03-normalize-layer.md - provides explicit field-level
unit conversion specs so we never guess units from field names.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# FieldSpec
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldSpec:
    """Single-field unit/nullable contract.

    Parameters
    ----------
    name : str
        Column name as returned by Tushare.
    source_unit : str
        Unit in the raw Tushare data (e.g. "%", "千元", "手").
    canonical_unit : str
        Target unit inside the system (e.g. "ratio", "元", "股").
    multiplier : float
        ``canonical = source * multiplier``.
    nullable : bool
        Whether NULL/NaN is acceptable.
    description : str
        Human-readable description (Chinese, matching Tushare docs).
    """

    name: str
    source_unit: str
    canonical_unit: str
    multiplier: float
    nullable: bool
    description: str

    # ------------------------------------------------------------------
    def convert(self, value) -> Optional[float]:
        """Apply unit conversion.  Returns *None* for missing values."""
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        if pd.isna(value):
            return None
        return value * self.multiplier

    @property
    def needs_conversion(self) -> bool:
        return self.source_unit != self.canonical_unit


# ---------------------------------------------------------------------------
# Field-spec dictionaries per interface
# ---------------------------------------------------------------------------

# 日线行情
DAILY_FIELDS: dict[str, FieldSpec] = {
    "ts_code":    FieldSpec("ts_code",    "string",  "string",  1.0,    False, "股票代码"),
    "trade_date": FieldSpec("trade_date", "YYYYMMDD","YYYYMMDD",1.0,    False, "交易日期"),
    "open":       FieldSpec("open",       "元",      "元",      1.0,    False, "开盘价"),
    "high":       FieldSpec("high",       "元",      "元",      1.0,    False, "最高价"),
    "low":        FieldSpec("low",        "元",      "元",      1.0,    False, "最低价"),
    "close":      FieldSpec("close",      "元",      "元",      1.0,    False, "收盘价"),
    "pre_close":  FieldSpec("pre_close",  "元",      "元",      1.0,    False, "昨收价"),
    "change":     FieldSpec("change",     "元",      "元",      1.0,    False, "涨跌额"),
    "pct_chg":    FieldSpec("pct_chg",    "%",       "ratio",   0.01,   False, "涨跌幅"),
    "vol":        FieldSpec("vol",        "手",      "手",      1.0,    False, "成交量"),
    "amount":     FieldSpec("amount",     "千元",    "元",      1000.0, False, "成交额"),
}

# 每日指标
DAILY_BASIC_FIELDS: dict[str, FieldSpec] = {
    "ts_code":          FieldSpec("ts_code",          "string", "string", 1.0,      False, "股票代码"),
    "trade_date":       FieldSpec("trade_date",       "YYYYMMDD","YYYYMMDD",1.0,    False, "交易日期"),
    "close":            FieldSpec("close",            "元",     "元",     1.0,      False, "收盘价"),
    "turnover_rate":    FieldSpec("turnover_rate",    "%",      "ratio",  0.01,     False, "换手率"),
    "turnover_rate_f":  FieldSpec("turnover_rate_f",  "%",      "ratio",  0.01,     False, "换手率(自由流通)"),
    "volume_ratio":     FieldSpec("volume_ratio",     "ratio",  "ratio",  1.0,      True,  "量比"),
    "pe":               FieldSpec("pe",               "ratio",  "ratio",  1.0,      True,  "市盈率(总)"),
    "pe_ttm":           FieldSpec("pe_ttm",           "ratio",  "ratio",  1.0,      True,  "市盈率TTM"),
    "pb":               FieldSpec("pb",               "ratio",  "ratio",  1.0,      True,  "市净率"),
    "ps":               FieldSpec("ps",               "ratio",  "ratio",  1.0,      True,  "市销率"),
    "ps_ttm":           FieldSpec("ps_ttm",           "ratio",  "ratio",  1.0,      True,  "市销率TTM"),
    "dv_ratio":         FieldSpec("dv_ratio",         "%",      "ratio",  0.01,     True,  "股息率"),
    "dv_ttm":           FieldSpec("dv_ttm",           "%",      "ratio",  0.01,     True,  "股息率TTM"),
    "total_share":      FieldSpec("total_share",      "万股",   "股",     10000.0,  False, "总股本"),
    "float_share":      FieldSpec("float_share",      "万股",   "股",     10000.0,  False, "流通股本"),
    "free_share":       FieldSpec("free_share",       "万股",   "股",     10000.0,  False, "自由流通股本"),
    "total_mv":         FieldSpec("total_mv",         "万元",   "元",     10000.0,  False, "总市值"),
    "circ_mv":          FieldSpec("circ_mv",          "万元",   "元",     10000.0,  False, "流通市值"),
}

# 复权因子
ADJ_FACTOR_FIELDS: dict[str, FieldSpec] = {
    "ts_code":     FieldSpec("ts_code",     "string",  "string",  1.0,  False, "股票代码"),
    "trade_date":  FieldSpec("trade_date",  "YYYYMMDD","YYYYMMDD",1.0,  False, "交易日期"),
    "adj_factor":  FieldSpec("adj_factor",  "ratio",   "ratio",   1.0,  False, "复权因子"),
}

# 财务指标
FINA_INDICATOR_FIELDS: dict[str, FieldSpec] = {
    "ts_code":            FieldSpec("ts_code",            "string",  "string",  1.0,   False, "股票代码"),
    "ann_date":           FieldSpec("ann_date",           "YYYYMMDD","YYYYMMDD",1.0,   False, "公告日期"),
    "f_ann_date":         FieldSpec("f_ann_date",         "YYYYMMDD","YYYYMMDD",1.0,   True,  "实际公告日期"),
    "end_date":           FieldSpec("end_date",           "YYYYMMDD","YYYYMMDD",1.0,   False, "报告期"),
    "report_type":        FieldSpec("report_type",        "int",     "int",     1.0,   False, "报告类型"),
    "roe":                FieldSpec("roe",                "%",       "ratio",   0.01,  True,  "净资产收益率"),
    "roa":                FieldSpec("roa",                "%",       "ratio",   0.01,  True,  "总资产报酬率"),
    "grossprofit_margin": FieldSpec("grossprofit_margin", "%",       "ratio",   0.01,  True,  "毛利率"),
    "debt_to_assets":     FieldSpec("debt_to_assets",     "%",       "ratio",   0.01,  True,  "资产负债率"),
    "op_yoy":             FieldSpec("op_yoy",             "%",       "ratio",   0.01,  True,  "营收同比增速"),
    "netprofit_yoy":      FieldSpec("netprofit_yoy",      "%",       "ratio",   0.01,  True,  "归母净利润同比增速"),
}

# 指数成分权重
INDEX_WEIGHT_FIELDS: dict[str, FieldSpec] = {
    "index_code": FieldSpec("index_code", "string",     "string",     1.0, False, "指数代码"),
    "con_code":   FieldSpec("con_code",   "string",     "string",     1.0, False, "成分股代码"),
    "trade_date": FieldSpec("trade_date", "YYYYMMDD",   "YYYYMMDD",   1.0, False, "交易日期"),
    "weight":     FieldSpec("weight",     "%",          "%",          1.0, False, "权重"),
}


# ---------------------------------------------------------------------------
# INTERFACE_CONFIG – master registry
# ---------------------------------------------------------------------------

INTERFACE_CONFIG: dict[str, dict] = {
    "daily": {
        "fields": DAILY_FIELDS,
        "primary_key": ["ts_code", "trade_date"],
        "description": "日线行情",
    },
    "daily_basic": {
        "fields": DAILY_BASIC_FIELDS,
        "primary_key": ["ts_code", "trade_date"],
        "description": "每日指标",
    },
    "adj_factor": {
        "fields": ADJ_FACTOR_FIELDS,
        "primary_key": ["ts_code", "trade_date"],
        "description": "复权因子",
    },
    "fina_indicator": {
        "fields": FINA_INDICATOR_FIELDS,
        "primary_key": ["ts_code", "ann_date", "end_date", "report_type"],
        "description": "财务指标",
    },
    "income": {
        "fields": {},  # full field list omitted – handled by normalizer later
        "primary_key": ["ts_code", "ann_date", "end_date", "report_type"],
        "description": "利润表",
    },
    "balancesheet": {
        "fields": {},
        "primary_key": ["ts_code", "ann_date", "end_date", "report_type"],
        "description": "资产负债表",
    },
    "cashflow": {
        "fields": {},
        "primary_key": ["ts_code", "ann_date", "end_date", "report_type"],
        "description": "现金流量表",
    },
    "index_weight": {
        "fields": INDEX_WEIGHT_FIELDS,
        "primary_key": ["index_code", "con_code", "trade_date"],
        "description": "指数成分权重",
    },
    "trade_cal": {
        "fields": {},
        "primary_key": ["exchange_id", "cal_date"],
        "description": "交易日历",
    },
    "stock_basic": {
        "fields": {},
        "primary_key": ["ts_code"],
        "description": "股票列表",
    },
    "forecast": {
        "fields": {},
        "primary_key": ["ts_code", "ann_date", "end_date"],
        "description": "业绩预告",
    },
    "express": {
        "fields": {},
        "primary_key": ["ts_code", "ann_date", "end_date"],
        "description": "业绩快报",
    },
    "dividend": {
        "fields": {},
        "primary_key": ["ts_code", "ann_date", "end_date", "div_proc"],
        "description": "分红送股",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_field_specs(interface: str) -> dict[str, FieldSpec]:
    """Return FieldSpec dict for *interface*, or empty dict if unknown."""
    return INTERFACE_CONFIG.get(interface, {}).get("fields", {})


def get_primary_key(interface: str) -> list[str]:
    """Return primary-key column list for *interface*."""
    return INTERFACE_CONFIG.get(interface, {}).get("primary_key", [])


def apply_field_specs(df: pd.DataFrame, fields: dict[str, FieldSpec]) -> pd.DataFrame:
    """Apply unit conversions defined in *fields* to *df* (copy)."""
    result = df.copy()
    for col_name, spec in fields.items():
        if col_name not in result.columns:
            continue
        if spec.needs_conversion:
            result[col_name] = result[col_name].apply(spec.convert)
    return result
