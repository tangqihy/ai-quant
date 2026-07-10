"""
DownloadScheduler – orchestrates daily incremental and periodic financial
data collection with watermark validation and retry.

Based on docs/design/02-data-collector.md §4 and §5.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .collector import BatchManifest, TushareCollector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DownloadScheduler
# ---------------------------------------------------------------------------

class DownloadScheduler:
    """High-level scheduler that drives :class:`TushareCollector`.

    Parameters
    ----------
    collector : TushareCollector
        An initialised collector instance.
    raw_dir : str | Path
        Must match ``collector.raw_dir``.  Used for watermark look-ups.
    """

    # Default interfaces for daily incremental download
    DAILY_INTERFACES: list[str] = ["daily", "adj_factor", "daily_basic"]

    # Financial interfaces
    FINANCIAL_INTERFACES: list[str] = [
        "income", "balancesheet", "cashflow", "fina_indicator",
    ]

    def __init__(self, collector: TushareCollector, raw_dir: str | Path = "data/raw") -> None:
        self.collector = collector
        self.raw_dir = Path(raw_dir)

    # ------------------------------------------------------------------
    # Daily incremental
    # ------------------------------------------------------------------

    def run_daily(self, date: Optional[str] = None, max_retries: int = 3) -> list[BatchManifest]:
        """Download daily market data for *date* (default: latest trading day).

        Steps per interface:
        1. Skip if already downloaded (manifest exists & validated).
        2. Download via collector.
        3. Watermark-validate; retry on failure.

        Returns manifests for all interfaces processed.
        """
        if date is None:
            date = self._get_latest_trading_day()

        manifests: list[BatchManifest] = []

        for interface in self.DAILY_INTERFACES:
            if self._is_downloaded(interface, {"trade_date": date}):
                logger.info("Already downloaded %s for %s – skipping", interface, date)
                continue

            manifest = self.collector.download_with_retry(
                interface=interface,
                params={"trade_date": date},
                max_retries=max_retries,
            )

            # Watermark validation (read back and check quality)
            if manifest.status == "success" and manifest.row_count > 0:
                data_path = self.collector.get_latest_batch(interface, {"trade_date": date})
                if data_path is not None:
                    if not self._validate_watermark(interface, date, manifest, data_path):
                        logger.warning(
                            "Watermark failed for %s %s – retrying once",
                            interface, date,
                        )
                        manifest = self.collector.download_with_retry(
                            interface=interface,
                            params={"trade_date": date},
                            max_retries=1,
                        )

            manifests.append(manifest)

        return manifests

    # ------------------------------------------------------------------
    # Financial data
    # ------------------------------------------------------------------

    def run_financial(self, lookback_periods: int = 4) -> list[BatchManifest]:
        """Download financial data for the last *lookback_periods* report periods.

        This automatically captures late corrections because each run
        re-downloads recent periods (append-only: duplicates are separate
        batches that can be deduplicated in the normalise layer).
        """
        periods = self._get_recent_periods(lookback_periods)
        manifests: list[BatchManifest] = []

        for period in periods:
            for interface in self.FINANCIAL_INTERFACES:
                try:
                    m = self.collector.download_with_retry(
                        interface=interface,
                        params={"period": period},
                    )
                    manifests.append(m)
                except Exception as exc:
                    logger.error("Financial download failed %s %s: %s", interface, period, exc)

        return manifests

    # ------------------------------------------------------------------
    # Full download (first-time bootstrap)
    # ------------------------------------------------------------------

    def run_full(
        self,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> list[BatchManifest]:
        """Download daily data for every trading day in [start_date, end_date].

        Intended for initial back-fill only.  For ongoing use, prefer
        :meth:`run_daily`.
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        manifests: list[BatchManifest] = []
        current = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")

        while current <= end:
            date_str = current.strftime("%Y%m%d")
            try:
                batch = self.run_daily(date=date_str)
                manifests.extend(batch)
            except Exception as exc:
                logger.error("Full download failed for %s: %s", date_str, exc)
            current += timedelta(days=1)

        return manifests

    # ------------------------------------------------------------------
    # Watermark validation
    # ------------------------------------------------------------------

    def _validate_watermark(
        self,
        interface: str,
        date: str,
        manifest: BatchManifest,
        data_path: Path,
    ) -> bool:
        """Validate downloaded data quality.

        Returns ``True`` if all checks pass.  Logs details on failure.
        """
        if manifest.status != "success":
            logger.warning("Manifest status is %s", manifest.status)
            return False

        try:
            df = pd.read_parquet(data_path)
        except Exception as exc:
            logger.error("Cannot read parquet %s: %s", data_path, exc)
            return False

        checks: dict[str, bool] = {}

        if interface == "daily":
            rolling_median = self._get_rolling_median("daily")
            checks = {
                "row_count_ok": len(df) >= rolling_median * 0.9 if rolling_median > 0 else len(df) > 0,
                "trade_date_unique": df["trade_date"].nunique() == 1 if "trade_date" in df.columns else False,
                "ts_code_no_dup": df["ts_code"].is_unique if "ts_code" in df.columns else False,
                "close_not_null_pct": (df["close"].notna().mean() > 0.95) if "close" in df.columns else False,
                "max_date_match": (df["trade_date"].max() == date) if "trade_date" in df.columns else False,
            }

        elif interface == "adj_factor":
            rolling_median = self._get_rolling_median("adj_factor")
            checks = {
                "row_count_ok": len(df) >= rolling_median * 0.9 if rolling_median > 0 else len(df) > 0,
                "adj_factor_positive": (df["adj_factor"] > 0).all() if "adj_factor" in df.columns else False,
            }

        elif interface == "daily_basic":
            checks = {
                "row_count_ok": len(df) > 0,
                "ts_code_not_null": df["ts_code"].notna().all() if "ts_code" in df.columns else False,
            }

        elif interface in self.FINANCIAL_INTERFACES:
            checks = {
                "row_count_ok": len(df) > 0,
                "ts_code_not_null": df["ts_code"].notna().all() if "ts_code" in df.columns else False,
                "end_date_not_null": df["end_date"].notna().all() if "end_date" in df.columns else False,
            }

        else:
            # Unknown interface – basic sanity
            checks = {"row_count_ok": len(df) > 0}

        # Log individual check results
        all_pass = True
        for name, passed in checks.items():
            if not passed:
                logger.warning("Watermark check FAILED: %s / %s / %s", interface, date, name)
                all_pass = False

        if all_pass:
            logger.info("Watermark OK for %s %s (%d rows)", interface, date, len(df))

        return all_pass

    # ------------------------------------------------------------------
    # Rolling median helper
    # ------------------------------------------------------------------

    def _get_rolling_median(self, interface: str, window: int = 20) -> float:
        """Compute rolling median of row counts from recent successful manifests."""
        manifests = self.collector.list_batches(interface, status_filter="success")
        # Sort by completed_at descending, take *window* most recent
        manifests.sort(key=lambda m: m.completed_at, reverse=True)
        row_counts = [m.row_count for m in manifests[:window] if m.row_count > 0]
        return float(np.median(row_counts)) if row_counts else 0.0

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    def _is_downloaded(self, interface: str, params: dict) -> bool:
        """Check whether a successful batch with matching *params* already exists."""
        return self.collector.get_latest_batch(interface, params) is not None

    # ------------------------------------------------------------------
    # Trading calendar helpers
    # ------------------------------------------------------------------

    def _get_latest_trading_day(self) -> str:
        """Derive the most recent trading day.

        Uses a simple heuristic: if after 17:30 CST use today (weekday),
        otherwise yesterday.  Falls back to collector's trade_cal API.
        """
        now = datetime.now()
        # If it's a weekday and after 17:30, today is likely the answer
        if now.weekday() < 5 and now.hour >= 17 and now.minute >= 30:
            candidate = now.strftime("%Y%m%d")
        else:
            # Go back to find last weekday
            candidate_dt = now - timedelta(days=1)
            while candidate_dt.weekday() >= 5:  # skip weekends
                candidate_dt -= timedelta(days=1)
            candidate = candidate_dt.strftime("%Y%m%d")

        # Verify against trade_cal if possible
        try:
            pro = self.collector.pro
            df: pd.DataFrame = pro.query(
                "trade_cal",
                exchange="SSE",
                start_date=(now - timedelta(days=10)).strftime("%Y%m%d"),
                end_date=now.strftime("%Y%m%d"),
            )
            if df is not None and len(df) > 0:
                open_days = df[df["is_open"] == 1]["cal_date"].tolist()
                if open_days:
                    return sorted(open_days, reverse=True)[0]
        except Exception:
            pass

        return candidate

    # ------------------------------------------------------------------
    # Financial period helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_recent_periods(n: int) -> list[str]:
        """Return the *n* most recent report-period strings (YYYYMMDD).

        Report periods are 03-31, 06-30, 09-30, 12-31 each year.
        """
        today = datetime.now()
        periods: list[str] = []

        for year in range(today.year - 1, today.year + 1):
            for month_day in [("03", "31"), ("06", "30"), ("09", "30"), ("12", "31")]:
                period = f"{year}{month_day[0]}{month_day[1]}"
                if period <= today.strftime("%Y%m%d"):
                    periods.append(period)

        return sorted(periods, reverse=True)[:n]
