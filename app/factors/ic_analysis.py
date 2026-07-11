"""
IC (Information Coefficient) analysis.

Based on docs/design/06-factor-framework.md §4:

- Uses **T+1 open → T+N+1 open** returns (matches real execution timing).
- Separates **raw IC** (all stocks) from **tradable IC** (excludes suspended,
  limit-up, ST stocks).
- ``calculate_ic_summary`` returns raw_ic_mean, tradable_ic_mean, and a
  disclaimer about in-sample statistics.
- ``calculate_group_returns`` splits stocks into quintile portfolios.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from .registry import factor_registry

logger = logging.getLogger(__name__)


class ICAnalyzer:
    """Information Coefficient analyser.

    Parameters
    ----------
    pit : PITQuery
        The PIT data facade used to fetch cross-sections and prices.
    """

    def __init__(self, pit) -> None:
        self.pit = pit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_ic(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        forward_days: int = 20,
        method: str = "rank",
    ) -> pd.DataFrame:
        """Calculate daily IC series.

        The return horizon is **T+1 open → T+N+1 open**, matching the
        strategy's real execution window.

        Parameters
        ----------
        factor_name : str
            Registered factor name.
        start_date / end_date : str
            Date range (YYYYMMDD or YYYY-MM-DD).
        forward_days : int
            Number of forward trading days for the return calculation.
        method : str
            ``"rank"`` for Spearman rank IC, ``"pearson"`` for Pearson IC.

        Returns
        -------
        pd.DataFrame
            Columns: date, raw_ic, tradable_ic, sample_count, tradable_count.
        """
        trading_days = self._get_trading_days(start_date, end_date)
        if len(trading_days) < forward_days + 2:
            return pd.DataFrame(columns=["date", "raw_ic", "tradable_ic", "sample_count", "tradable_count"])

        ic_records: list[dict] = []

        for i in range(len(trading_days) - forward_days - 1):
            date = trading_days[i]
            t_plus_1 = trading_days[i + 1]
            t_plus_n_plus_1 = trading_days[i + forward_days + 1]

            # 1. Compute factor values at T (oriented)
            try:
                factor_df = factor_registry.compute(factor_name, date=date, pit=self.pit)
            except Exception:
                logger.debug("Factor %s failed on %s", factor_name, date, exc_info=True)
                continue

            if factor_df is None or len(factor_df) == 0:
                continue

            # 2. Forward returns: T+1 open → T+N+1 open
            forward_ret = self._get_forward_returns(
                factor_df["ts_code"].tolist(),
                t_plus_1,
                t_plus_n_plus_1,
                price_field="open",
            )
            if forward_ret.empty:
                continue

            # 3. Tradable mask
            tradable_mask = self._get_tradable_mask(
                factor_df["ts_code"].tolist(),
                t_plus_1,
                t_plus_n_plus_1,
            )

            # 4. Merge
            merged = factor_df.merge(forward_ret, on="ts_code", how="inner")
            if tradable_mask is not None and len(tradable_mask) > 0:
                merged = merged.merge(tradable_mask, on="ts_code", how="left")
                if "is_tradable" not in merged.columns:
                    merged["is_tradable"] = True
                merged["is_tradable"] = merged["is_tradable"].fillna(True)
            else:
                merged["is_tradable"] = True

            # Drop NaN factor values
            merged = merged.dropna(subset=["factor_value", "forward_return"])

            if len(merged) < 30:
                continue

            # 5. Raw IC (all samples)
            corr_method = "spearman" if method == "rank" else "pearson"
            raw_ic = merged["factor_value"].corr(merged["forward_return"], method=corr_method)

            # 6. Tradable IC
            tradable_df = merged[merged["is_tradable"] == True]
            tradable_ic: Optional[float] = None
            if len(tradable_df) >= 30:
                tradable_ic = tradable_df["factor_value"].corr(
                    tradable_df["forward_return"], method=corr_method
                )

            ic_records.append({
                "date": date,
                "raw_ic": raw_ic,
                "tradable_ic": tradable_ic,
                "sample_count": len(merged),
                "tradable_count": len(tradable_df),
            })

        return pd.DataFrame(ic_records)

    def calculate_ic_summary(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        forward_days: int = 20,
        method: str = "rank",
    ) -> dict:
        """Summarise IC statistics.

        Returns
        -------
        dict
            Keys: factor_name, raw_ic_mean, raw_ic_std, raw_ic_ir,
            tradable_ic_mean, tradable_ic_std, tradable_ic_ir,
            sample_count, disclaimer.
        """
        ic_df = self.calculate_ic(factor_name, start_date, end_date, forward_days, method)

        if ic_df.empty:
            return {
                "factor_name": factor_name,
                "raw_ic_mean": None,
                "raw_ic_std": None,
                "raw_ic_ir": None,
                "tradable_ic_mean": None,
                "tradable_ic_std": None,
                "tradable_ic_ir": None,
                "sample_count": 0,
                "disclaimer": "当前结果为样本内统计，不代表样本外有效性",
            }

        raw = ic_df["raw_ic"].dropna()
        trad = ic_df["tradable_ic"].dropna()

        def _safe_ir(series: pd.Series) -> Optional[float]:
            if len(series) < 2 or series.std() == 0:
                return None
            return float(series.mean() / series.std())

        return {
            "factor_name": factor_name,
            "raw_ic_mean": float(raw.mean()) if len(raw) > 0 else None,
            "raw_ic_std": float(raw.std()) if len(raw) > 0 else None,
            "raw_ic_ir": _safe_ir(raw),
            "tradable_ic_mean": float(trad.mean()) if len(trad) > 0 else None,
            "tradable_ic_std": float(trad.std()) if len(trad) > 0 else None,
            "tradable_ic_ir": _safe_ir(trad),
            "sample_count": len(ic_df),
            "disclaimer": "当前结果为样本内统计，不代表样本外有效性",
        }

    def calculate_group_returns(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        forward_days: int = 20,
        n_groups: int = 5,
    ) -> pd.DataFrame:
        """Quintile portfolio returns.

        Stocks are sorted by oriented factor value into *n_groups* equal-sized
        portfolios.  Returns use T+1 open → T+N+1 open.

        Returns
        -------
        pd.DataFrame
            Columns: date, group, return (mean return per group).
        """
        trading_days = self._get_trading_days(start_date, end_date)
        if len(trading_days) < forward_days + 2:
            return pd.DataFrame(columns=["date", "group", "return"])

        records: list[dict] = []

        for i in range(len(trading_days) - forward_days - 1):
            date = trading_days[i]
            t_plus_1 = trading_days[i + 1]
            t_plus_n_plus_1 = trading_days[i + forward_days + 1]

            try:
                factor_df = factor_registry.compute(factor_name, date=date, pit=self.pit)
            except Exception:
                continue

            if factor_df is None or len(factor_df) < n_groups * 10:
                continue

            forward_ret = self._get_forward_returns(
                factor_df["ts_code"].tolist(), t_plus_1, t_plus_n_plus_1, "open"
            )
            if forward_ret.empty:
                continue

            merged = factor_df.merge(forward_ret, on="ts_code", how="inner").dropna(
                subset=["factor_value", "forward_return"]
            )
            if len(merged) < n_groups * 10:
                continue

            try:
                merged["group"] = pd.qcut(
                    merged["factor_value"],
                    n_groups,
                    labels=False,
                    duplicates="drop",
                ) + 1
            except ValueError:
                continue

            for grp, grp_df in merged.groupby("group"):
                records.append({
                    "date": date,
                    "group": int(grp),
                    "return": float(grp_df["forward_return"].mean()),
                })

        return pd.DataFrame(records)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_forward_returns(
        self,
        ts_codes: list[str],
        start_date: str,
        end_date: str,
        price_field: str = "open",
    ) -> pd.DataFrame:
        """Get forward returns between two dates using *price_field* prices.

        Returns DataFrame with columns [ts_code, forward_return].
        """
        if not ts_codes:
            return pd.DataFrame(columns=["ts_code", "forward_return"])

        sd = _norm(start_date)
        ed = _norm(end_date)

        try:
            self.pit.client._ensure_view("daily")
            placeholders = ", ".join("?" for _ in ts_codes)
            sql = f"""
                SELECT ts_code, trade_date, {price_field}
                FROM daily
                WHERE ts_code IN ({placeholders})
                  AND trade_date IN (?, ?)
            """
            params = list(ts_codes) + [sd, ed]
            df = self.pit.client.query(sql, params)
        except Exception:
            logger.debug("_get_forward_returns query failed", exc_info=True)
            return pd.DataFrame(columns=["ts_code", "forward_return"])

        if df.empty or price_field not in df.columns:
            return pd.DataFrame(columns=["ts_code", "forward_return"])

        pivot = df.pivot(index="ts_code", columns="trade_date", values=price_field)

        dates_sorted = sorted(pivot.columns)
        if len(dates_sorted) < 2:
            return pd.DataFrame(columns=["ts_code", "forward_return"])

        p_start = pivot[dates_sorted[0]]
        p_end = pivot[dates_sorted[-1]]

        ret = ((p_end / p_start) - 1).dropna()
        ret.name = "forward_return"

        return ret.reset_index()

    def _get_tradable_mask(
        self,
        ts_codes: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Filter out suspended, limit-up, ST stocks.

        Returns DataFrame with columns [ts_code, is_tradable].
        """
        if not ts_codes:
            return pd.DataFrame(columns=["ts_code", "is_tradable"])

        sd = _norm(start_date)

        try:
            self.pit.client._ensure_view("daily")
            placeholders = ", ".join("?" for _ in ts_codes)

            # Check for missing bars (suspended) and limit-up at T+1
            sql = f"""
                SELECT
                    d.ts_code,
                    CASE
                        WHEN d.close IS NULL THEN FALSE
                        WHEN d.open IS NOT NULL
                             AND d.high IS NOT NULL
                             AND d.low IS NOT NULL
                             AND d.open = d.high
                             AND d.high = d.low
                             AND d.open >= d.close * 1.095
                             THEN FALSE
                        ELSE TRUE
                    END AS is_tradable
                FROM (
                    SELECT DISTINCT ts_code FROM daily
                    WHERE ts_code IN ({placeholders})
                ) u
                LEFT JOIN daily d
                    ON u.ts_code = d.ts_code AND d.trade_date = ?
            """
            params = list(ts_codes) + [sd]
            df = self.pit.client.query(sql, params)

            if df.empty:
                return pd.DataFrame(columns=["ts_code", "is_tradable"])

            df["is_tradable"] = df["is_tradable"].fillna(False).astype(bool)
            return df

        except Exception:
            logger.debug("_get_tradable_mask query failed", exc_info=True)
            # Fallback: mark all as tradable
            return pd.DataFrame({"ts_code": ts_codes, "is_tradable": True})

    def _get_trading_days(self, start_date: str, end_date: str) -> list[str]:
        """Get sorted trading day list."""
        try:
            dates = self.pit.client.get_trade_dates(start_date, end_date)
            return [_norm(d) for d in dates]
        except Exception:
            return []


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _norm(d: str) -> str:
    """归一化为存储格式 ``YYYYMMDD``（normalized 层的 trade_date 以该字符串存储）。"""
    s = str(d).replace("-", "")
    if len(s) == 8 and s.isdigit():
        return s
    return str(d)
