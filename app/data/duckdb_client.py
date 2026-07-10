"""
DuckDB client for the normalized data layer.

Registers hive-partitioned Parquet views so every interface is queryable with
plain SQL.  Also exposes convenience helpers for the most common queries used
by the PIT layer and the backtest engine.

Based on docs/design/03-normalize-layer.md and docs/design/04-pit-layer.md.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from .schemas import INTERFACE_CONFIG

logger = logging.getLogger(__name__)


class DuckDBClient:
    """Thin wrapper around a DuckDB in-process connection with auto-registered
    views over the ``normalized/latest/`` Parquet directory.

    Parameters
    ----------
    normalized_dir : str | Path
        Root of the normalized layer (default ``data/normalized``).
    database : str | None
        Path to a DuckDB database file for persistence.  ``None`` (default)
        uses an in-memory database.
    """

    def __init__(
        self,
        normalized_dir: str | Path = "data/normalized",
        database: str | None = None,
    ) -> None:
        self.normalized_dir = Path(normalized_dir)
        self._con = duckdb.connect(database=database or ":memory:")
        self._registered_views: set[str] = set()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Underlying DuckDB connection (for advanced use)."""
        return self._con

    def close(self) -> None:
        """Close the underlying connection."""
        self._con.close()
        self._registered_views.clear()

    def __enter__(self) -> DuckDBClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # View registration
    # ------------------------------------------------------------------

    def register_interface_view(self, interface: str, view_name: str | None = None) -> str:
        """Create (or replace) a DuckDB view over the latest Parquet data for
        *interface*.

        Parameters
        ----------
        interface : str
            Interface name (e.g. ``"daily"``, ``"fina_indicator"``).
        view_name : str | None
            SQL view name.  Defaults to *interface* itself.

        Returns
        -------
        str
            The view name that was registered.
        """
        view_name = view_name or interface
        latest_dir = self.normalized_dir / "latest" / interface

        if not latest_dir.exists():
            logger.warning("Latest directory missing for %s – view will be empty", interface)
            # Create an empty view so downstream SQL doesn't break
            self._con.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS SELECT NULL WHERE FALSE"
            )
        else:
            # Use glob pattern to pick up all parquet under hive partitions
            glob_pattern = str(latest_dir / "**" / "*.parquet")
            self._con.execute(f"""
                CREATE OR REPLACE VIEW {view_name} AS
                SELECT *
                FROM read_parquet(
                    '{glob_pattern}',
                    hive_partitioning = true,
                    union_by_name = true
                )
            """)

        self._registered_views.add(view_name)
        logger.info("Registered view '%s' → %s", view_name, latest_dir)
        return view_name

    def register_all_views(self) -> None:
        """Register views for every interface in INTERFACE_CONFIG."""
        for interface in INTERFACE_CONFIG:
            self.register_interface_view(interface)

    def register_versions_view(
        self, interface: str, view_name: str | None = None
    ) -> str:
        """Create a view over *all* versioned data (not just latest).

        Useful for PIT queries that need access to ``ingested_at``.
        """
        view_name = view_name or f"{interface}_versions"
        versions_dir = self.normalized_dir / "versions" / interface

        if not versions_dir.exists():
            self._con.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS SELECT NULL WHERE FALSE"
            )
        else:
            glob_pattern = str(versions_dir / "**" / "*.parquet")
            self._con.execute(f"""
                CREATE OR REPLACE VIEW {view_name} AS
                SELECT *
                FROM read_parquet(
                    '{glob_pattern}',
                    hive_partitioning = true,
                    union_by_name = true
                )
            """)

        self._registered_views.add(view_name)
        return view_name

    # ------------------------------------------------------------------
    # SQL query interface
    # ------------------------------------------------------------------

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        """Execute a SQL query and return a pandas DataFrame.

        Parameters
        ----------
        sql : str
            SQL query text.  May reference any registered view.
        params : list | None
            Optional positional parameters for parameterised queries.

        Returns
        -------
        pd.DataFrame
        """
        if params:
            result = self._con.execute(sql, params)
        else:
            result = self._con.execute(sql)
        return result.fetchdf()

    def execute(self, sql: str, params: list | None = None) -> None:
        """Execute a statement without returning results (DDL, INSERT, etc.)."""
        if params:
            self._con.execute(sql, params)
        else:
            self._con.execute(sql)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_latest_daily(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Fetch daily bars for *ts_code* from the ``daily`` view.

        Parameters
        ----------
        ts_code : str
            Stock code, e.g. ``"600519.SH"``.
        start_date / end_date : str | None
            Date range in ``YYYYMMDD`` format (inclusive).
        limit : int | None
            Maximum rows to return.
        """
        self._ensure_view("daily")

        where = ["ts_code = ?", "trade_date IS NOT NULL"]
        params: list = [ts_code]

        if start_date:
            where.append("trade_date >= ?")
            params.append(_parse_date(start_date))
        if end_date:
            where.append("trade_date <= ?")
            params.append(_parse_date(end_date))

        sql = f"""
            SELECT *
            FROM daily
            WHERE {" AND ".join(where)}
            ORDER BY trade_date
        """
        if limit:
            sql += f"\nLIMIT {int(limit)}"

        return self.query(sql, params)

    def get_latest_daily_basic(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Fetch daily-basic indicators for *ts_code*."""
        self._ensure_view("daily_basic")

        where = ["ts_code = ?", "trade_date IS NOT NULL"]
        params: list = [ts_code]

        if start_date:
            where.append("trade_date >= ?")
            params.append(_parse_date(start_date))
        if end_date:
            where.append("trade_date <= ?")
            params.append(_parse_date(end_date))

        sql = f"""
            SELECT *
            FROM daily_basic
            WHERE {" AND ".join(where)}
            ORDER BY trade_date
        """
        return self.query(sql, params)

    def get_financial_pit(
        self,
        ts_code: str,
        as_of_date: str,
        report_type: int = 1,
        interface: str = "fina_indicator",
    ) -> Optional[pd.DataFrame]:
        """PIT query: get the most recent financial data visible as of *as_of_date*.

        Uses **versions** view (which includes ``ingested_at``) to apply the
        full PIT version-selection logic:

        1. ``published_at <= as_of_date``  (visibility)
        2. Max ``end_date``                (latest report period)
        3. Max ``published_at``            (latest announcement)
        4. Max ``ingested_at``             (latest ingestion – tiebreaker)
        """
        view = f"{interface}_versions"
        self._ensure_versions_view(interface, view)

        # published_at is derived from ann_date; we coalesce f_ann_date/ann_date
        sql = f"""
            SELECT *
            FROM {view}
            WHERE ts_code = ?
              AND report_type = ?
              AND COALESCE(
                  CASE WHEN f_ann_date IS NOT NULL THEN f_ann_date END,
                  ann_date
              ) <= ?
            ORDER BY
                end_date DESC,
                COALESCE(
                    CASE WHEN f_ann_date IS NOT NULL THEN f_ann_date END,
                    ann_date
                ) DESC,
                CASE WHEN f_ann_date IS NOT NULL THEN 0 ELSE 1 END ASC,
                ingested_at DESC
            LIMIT 1
        """
        result = self.query(sql, [ts_code, report_type, _parse_date(as_of_date)])
        return result if len(result) > 0 else None

    def get_financial_pit_batch(
        self,
        ts_codes: list[str],
        as_of_date: str,
        report_type: int = 1,
        interface: str = "fina_indicator",
    ) -> pd.DataFrame:
        """PIT query for a batch of stocks at a single *as_of_date*.

        Returns one row per ts_code (latest version per PIT rules).
        """
        view = f"{interface}_versions"
        self._ensure_versions_view(interface, view)

        if not ts_codes:
            return pd.DataFrame()

        placeholders = ", ".join("?" for _ in ts_codes)
        params = list(ts_codes) + [report_type, _parse_date(as_of_date)]

        sql = f"""
            SELECT *
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY ts_code
                        ORDER BY
                            end_date DESC,
                            COALESCE(
                                CASE WHEN f_ann_date IS NOT NULL THEN f_ann_date END,
                                ann_date
                            ) DESC,
                            CASE WHEN f_ann_date IS NOT NULL THEN 0 ELSE 1 END ASC,
                            ingested_at DESC
                    ) AS _rn
                FROM {view}
                WHERE ts_code IN ({placeholders})
                  AND report_type = ?
                  AND COALESCE(
                      CASE WHEN f_ann_date IS NOT NULL THEN f_ann_date END,
                      ann_date
                  ) <= ?
            )
            WHERE _rn = 1
        """
        result = self.query(sql, params)
        if "_rn" in result.columns:
            result = result.drop(columns=["_rn"])
        return result

    def get_index_members_pit(
        self,
        index_code: str,
        as_of_date: str,
    ) -> list[str]:
        """PIT query: get index constituent codes as of *as_of_date*.

        Uses **trade_date** as the effective date for index weight data
        (index_weight has ``trade_date`` which represents the date the
        weight snapshot was taken).
        """
        self._ensure_view("index_weight")

        sql = """
            SELECT DISTINCT con_code
            FROM index_weight
            WHERE index_code = ?
              AND trade_date <= ?
            ORDER BY con_code
        """
        result = self.query(sql, [index_code, _parse_date(as_of_date)])
        return result["con_code"].tolist()

    def get_st_stocks_pit(self, as_of_date: str) -> list[str]:
        """PIT query: get ST-marked stocks as of *as_of_date*.

        ST status is determined by stock name containing 'ST'.
        This is a placeholder – a proper implementation would use
        an instrument_status table with effective_date.
        """
        self._ensure_view("stock_basic")

        sql = """
            SELECT ts_code
            FROM stock_basic
            WHERE name LIKE '%ST%'
        """
        result = self.query(sql)
        return result["ts_code"].tolist()

    def get_trade_dates(
        self,
        start_date: str,
        end_date: str,
        exchange: str = "SSE",
    ) -> list[str]:
        """Return all trade dates in the given range from trade_cal."""
        self._ensure_view("trade_cal")

        sql = """
            SELECT cal_date
            FROM trade_cal
            WHERE exchange_id = ?
              AND is_open = 1
              AND cal_date >= ?
              AND cal_date <= ?
            ORDER BY cal_date
        """
        result = self.query(sql, [exchange, _parse_date(start_date), _parse_date(end_date)])
        return result["cal_date"].tolist()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_view(self, interface: str) -> None:
        """Register a view if it hasn't been registered yet."""
        if interface not in self._registered_views:
            self.register_interface_view(interface)

    def _ensure_versions_view(self, interface: str, view_name: str) -> None:
        """Register a versions view if it hasn't been registered yet."""
        if view_name not in self._registered_views:
            self.register_versions_view(interface, view_name)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_date(date_str: str) -> str:
    """Normalise a date string to ``YYYY-MM-DD`` for DuckDB DATE comparison.

    DuckDB can parse both ``YYYYMMDD`` and ``YYYY-MM-DD``, but the latter
    is more explicit and avoids ambiguity.
    """
    s = date_str.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return date_str
