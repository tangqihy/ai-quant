"""
Point-in-Time (PIT) data manager.

Based on docs/design/04-pit-layer.md:
- ``published_at`` is the core PIT condition for financial data.
- Announcements without a precise time default to the next trade date.
- Version selection: published_at <= as_of → max published_at → max ingested_at.
- State data (ST, delisting, index composition) uses ``effective_date``.

Provides :class:`PITDataManager` for low-level PIT queries and
:class:`PITQuery` as the high-level facade used by the backtest engine.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .duckdb_client import DuckDBClient

logger = logging.getLogger(__name__)

# Interfaces that carry financial-report semantics (need PIT version selection)
FINANCIAL_INTERFACES = frozenset({
    "fina_indicator",
    "income",
    "balancesheet",
    "cashflow",
    "forecast",
    "express",
})


# ======================================================================
# PITDataManager
# ======================================================================

class PITDataManager:
    """Low-level PIT data operations.

    Parameters
    ----------
    client : DuckDBClient
        An already-configured client with views registered.
    trade_dates : list[str] | None
        Sorted list of trade dates (``YYYY-MM-DD``) used to resolve
        "next trade date" for announcements without a precise time.
        If ``None``, a simple calendar heuristic (skip weekends) is used.
    """

    def __init__(
        self,
        client: DuckDBClient,
        trade_dates: list[str] | None = None,
    ) -> None:
        self.client = client
        self._trade_dates = trade_dates or []
        self._trade_dates_set = set(self._trade_dates)

    # ------------------------------------------------------------------
    # Published-at resolution
    # ------------------------------------------------------------------

    def resolve_published_at(self, ann_date: str) -> str:
        """Map an announcement *date* to a conservative ``published_at``.

        Rule (from design doc §2.2):
        - Without a precise time the data is only available on the **next
          trade date** after *ann_date*.

        Parameters
        ----------
        ann_date : str
            ``YYYYMMDD`` or ``YYYY-MM-DD``.

        Returns
        -------
        str
            ``YYYY-MM-DD`` of the next trade date.
        """
        normalised = _normalise_date(ann_date)
        return self._next_trade_date(normalised)

    # ------------------------------------------------------------------
    # Financial PIT queries
    # ------------------------------------------------------------------

    def get_financial_pit(
        self,
        ts_code: str,
        as_of_date: str,
        report_type: int = 1,
        interface: str = "fina_indicator",
    ) -> Optional[pd.DataFrame]:
        """PIT financial query for a single stock.

        Version selection order (§3.2):
        1. ``published_at <= as_of_date``   (visibility filter)
        2. ``end_date DESC``                (latest report period)
        3. ``published_at DESC``            (latest announcement for same period)
        4. ``ingested_at DESC``             (tiebreaker)

        Where ``published_at`` is derived as:
        ``COALESCE(f_ann_date, ann_date)`` mapped to next trade date.
        """
        return self.client.get_financial_pit(
            ts_code=ts_code,
            as_of_date=as_of_date,
            report_type=report_type,
            interface=interface,
        )

    def get_financial_pit_batch(
        self,
        ts_codes: list[str],
        as_of_date: str,
        report_type: int = 1,
        interface: str = "fina_indicator",
    ) -> pd.DataFrame:
        """PIT financial query for a batch of stocks at one *as_of_date*.

        Returns one row per ``ts_code``.
        """
        return self.client.get_financial_pit_batch(
            ts_codes=ts_codes,
            as_of_date=as_of_date,
            report_type=report_type,
            interface=interface,
        )

    def get_financial_pit_cross_section(
        self,
        ts_codes: list[str],
        as_of_date: str,
        report_type: int = 1,
    ) -> pd.DataFrame:
        """PIT cross-section across *all* financial interfaces.

        Merges fina_indicator + income + balancesheet + cashflow + …
        into a single wide DataFrame keyed by (ts_code, end_date).
        """
        frames: list[pd.DataFrame] = []
        for iface in sorted(FINANCIAL_INTERFACES):
            try:
                df = self.get_financial_pit_batch(
                    ts_codes, as_of_date, report_type, interface=iface
                )
                if df is not None and len(df) > 0:
                    # Prefix columns to avoid clashes (except join keys)
                    join_keys = {"ts_code", "end_date", "ann_date", "report_type"}
                    rename_map = {
                        c: f"{iface}__{c}" for c in df.columns if c not in join_keys
                    }
                    df = df.rename(columns=rename_map)
                    frames.append(df)
            except Exception:
                logger.debug("Skipping interface %s (not available)", iface)

        if not frames:
            return pd.DataFrame()

        merged = frames[0]
        for extra in frames[1:]:
            merged = merged.merge(extra, on=["ts_code", "end_date"], how="outer")

        return merged

    # ------------------------------------------------------------------
    # Index-members PIT
    # ------------------------------------------------------------------

    def get_index_members_pit(
        self,
        index_code: str,
        as_of_date: str,
    ) -> list[str]:
        """Get index constituent stock codes visible as of *as_of_date*.

        Uses ``trade_date`` as the effective date (§4.2).
        """
        return self.client.get_index_members_pit(index_code, as_of_date)

    # ------------------------------------------------------------------
    # State-data PIT helpers (ST / delisting / universe)
    # ------------------------------------------------------------------

    def get_st_stocks_pit(self, as_of_date: str) -> list[str]:
        """ST stocks visible as of *as_of_date* (uses effective_date)."""
        return self.client.get_st_stocks_pit(as_of_date)

    def get_universe(
        self,
        as_of_date: str,
        exclude_st: bool = True,
        exclude_delisted: bool = True,
    ) -> list[str]:
        """Get the tradeable stock universe as of *as_of_date*.

        Filters:
        - Listed on or before *as_of_date*
        - Not delisted before *as_of_date*
        - Optionally excludes ST stocks
        """
        client = self.client
        client._ensure_view("stock_basic")

        # Check available columns and types
        try:
            cols_df = client.query("DESCRIBE stock_basic")
            available_cols = set(cols_df["column_name"].tolist())
            # 检查 list_date 列类型
            list_date_row = cols_df[cols_df["column_name"] == "list_date"]
            list_date_type = str(list_date_row["column_type"].iloc[0]) if len(list_date_row) > 0 else ""
        except Exception:
            available_cols = set()
            list_date_type = ""

        as_of_yyyymmdd = _normalise_date(as_of_date).replace("-", "")
        as_of_fmt = f"{as_of_yyyymmdd[:4]}-{as_of_yyyymmdd[4:6]}-{as_of_yyyymmdd[6:8]}"

        is_timestamp = "TIMESTAMP" in list_date_type.upper()
        date_op = "?::TIMESTAMP" if is_timestamp else "?"
        date_val = as_of_fmt if is_timestamp else as_of_yyyymmdd

        where = [
            "list_date IS NOT NULL",
            f"list_date <= {date_op}",
        ]
        params: list = [date_val]

        if exclude_delisted and "delist_date" in available_cols:
            where.append(f"(delist_date IS NULL OR delist_date > {date_op})")
            params.append(date_val)

        sql = f"""
            SELECT ts_code
            FROM stock_basic
            WHERE {" AND ".join(where)}
            ORDER BY ts_code
        """
        result = client.query(sql, params)
        universe = result["ts_code"].tolist()

        if exclude_st:
            st_set = set(self.get_st_stocks_pit(as_of_date))
            universe = [c for c in universe if c not in st_set]

        return universe

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_trade_date(self, date_str: str) -> str:
        """Return the next trade date on or after *date_str*.

        If a trade calendar is available, use it; otherwise skip weekends.
        """
        if self._trade_dates:
            for td in self._trade_dates:
                if td >= date_str:
                    return td
            # All trade dates exhausted – return date_str as-is
            return date_str

        # Fallback: skip weekends
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt += timedelta(days=1)
        while dt.weekday() >= 5:  # Saturday=5, Sunday=6
            dt += timedelta(days=1)
        return dt.strftime("%Y-%m-%d")


# ======================================================================
# PITQuery – high-level facade for the backtest engine
# ======================================================================

class PITQuery:
    """High-level PIT interface consumed by the backtest engine.

    Wraps :class:`PITDataManager` and :class:`DuckDBClient` to provide
    ``get_universe()`` and ``get_cross_section()``.

    Parameters
    ----------
    client : DuckDBClient
        Configured DuckDB client.
    trade_dates : list[str] | None
        Sorted trade dates for next-trade-date resolution.
    """

    def __init__(
        self,
        client: DuckDBClient,
        trade_dates: list[str] | None = None,
    ) -> None:
        self.client = client
        self.pit = PITDataManager(client, trade_dates)

    # ------------------------------------------------------------------
    # Universe
    # ------------------------------------------------------------------

    def get_universe(
        self,
        as_of_date: str,
        index_code: str | None = None,
        exclude_st: bool = True,
        exclude_delisted: bool = True,
    ) -> list[str]:
        """Get tradeable stock codes as of *as_of_date*.

        If *index_code* is given, intersect with index constituents.
        """
        universe = set(
            self.pit.get_universe(
                as_of_date, exclude_st=exclude_st, exclude_delisted=exclude_delisted
            )
        )

        if index_code:
            members = set(self.pit.get_index_members_pit(index_code, as_of_date))
            universe = universe & members

        return sorted(universe)

    # ------------------------------------------------------------------
    # Cross-section
    # ------------------------------------------------------------------

    def get_cross_section(
        self,
        as_of_date: str,
        ts_codes: list[str] | None = None,
        index_code: str | None = None,
    ) -> pd.DataFrame:
        """Build a cross-sectional snapshot for *as_of_date*.

        Combines:
        - Latest daily bars (close, volume, etc.)
        - Latest daily_basic (PE, PB, market cap, etc.)
        - PIT financial indicators (ROE, ROA, etc.)

        Parameters
        ----------
        as_of_date : str
            Date (``YYYYMMDD`` or ``YYYY-MM-DD``).
        ts_codes : list[str] | None
            Restrict to these stocks.  If ``None``, use *index_code* or
            full universe.
        index_code : str | None
            Restrict to index constituents.

        Returns
        -------
        pd.DataFrame
            One row per stock, columns from all merged sources.
        """
        # Resolve stock list
        if ts_codes is None:
            ts_codes = self.get_universe(as_of_date, index_code=index_code)

        if not ts_codes:
            return pd.DataFrame()

        client = self.client
        normalised_as_of = _normalise_date(as_of_date)

        # 检查 trade_date 列类型
        def _date_param(date_str: str) -> tuple[str, str]:
            """返回 (SQL参数占位符, 参数值)，自动适配 TIMESTAMP_NS 或字符串列。"""
            try:
                desc = client.query("DESCRIBE daily")
                row = desc[desc["column_name"] == "trade_date"]
                col_type = str(row["column_type"].iloc[0]) if len(row) > 0 else ""
            except Exception:
                col_type = ""
            if "TIMESTAMP" in col_type.upper():
                fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str
                return "?::TIMESTAMP", fmt
            return "?", date_str

        date_op, date_val = _date_param(normalised_as_of)

        # --- daily bars (latest on or before as_of) ----------------------
        client._ensure_view("daily")
        placeholders = ", ".join("?" for _ in ts_codes)
        daily = pd.DataFrame()
        try:
            daily_sql = f"""
                SELECT *
                FROM daily
                WHERE ts_code IN ({placeholders})
                  AND trade_date <= {date_op}
                ORDER BY ts_code, trade_date DESC
            """
            params = list(ts_codes) + [date_val]
            daily_all = client.query(daily_sql, params)
            # Dedup: keep latest trade_date per ts_code
            if len(daily_all) > 0 and "ts_code" in daily_all.columns:
                daily = daily_all.groupby("ts_code", as_index=False).first()
        except Exception:
            logger.debug("daily view not available for cross-section")

        # --- daily_basic -------------------------------------------------
        client._ensure_view("daily_basic")
        basic = pd.DataFrame()
        try:
            basic_sql = f"""
                SELECT *
                FROM daily_basic
                WHERE ts_code IN ({placeholders})
                  AND trade_date <= {date_op}
                ORDER BY ts_code, trade_date DESC
            """
            basic_all = client.query(basic_sql, params)
            if len(basic_all) > 0 and "ts_code" in basic_all.columns:
                basic = basic_all.groupby("ts_code", as_index=False).first()
        except Exception:
            logger.debug("daily_basic view not available for cross-section")

        # --- PIT financial indicators ------------------------------------
        fina = pd.DataFrame()
        try:
            fina = self.pit.get_financial_pit_batch(
                ts_codes, as_of_date, report_type=1, interface="fina_indicator"
            )
        except Exception:
            logger.debug("fina_indicator not available for cross-section")

        # --- Merge -------------------------------------------------------
        merged = pd.DataFrame({"ts_code": ts_codes})

        if len(daily) > 0:
            # Avoid column collision: prefix daily columns except join key
            daily_cols = [c for c in daily.columns if c != "ts_code"]
            daily_renamed = daily.rename(
                columns={c: f"daily__{c}" for c in daily_cols}
            )
            merged = merged.merge(daily_renamed, on="ts_code", how="left")

        if len(basic) > 0:
            basic_cols = [c for c in basic.columns if c != "ts_code"]
            basic_renamed = basic.rename(
                columns={c: f"basic__{c}" for c in basic_cols}
            )
            merged = merged.merge(basic_renamed, on="ts_code", how="left")

        if len(fina) > 0:
            fina_cols = [
                c for c in fina.columns if c not in ("ts_code", "end_date")
            ]
            fina_renamed = fina.rename(
                columns={c: f"fina__{c}" for c in fina_cols}
            )
            merged = merged.merge(fina_renamed, on="ts_code", how="left")

        return merged


# ======================================================================
# Module helpers
# ======================================================================

def _normalise_date(date_str: str) -> str:
    """``YYYYMMDD`` → ``YYYY-MM-DD``."""
    s = date_str.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return date_str
