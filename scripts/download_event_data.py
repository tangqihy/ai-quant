#!/usr/bin/env python3
"""
Download Tushare event data (forecast, express, dividend, repurchase, share_float)
for the full market from 2025-07-10 to 2026-07-10, then normalize.

Usage:
    cd /root/.openclaw/workspace/ai-quant
    python scripts/download_event_data.py
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.collector import TushareCollector
from app.data.normalize import DataNormalizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("event_download")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INTERFACES = ["forecast", "express", "dividend", "repurchase", "share_float"]
START_DATE = "20250710"
END_DATE = "20260710"
RAW_DIR = "data/raw"


def get_token() -> str:
    """Read Tushare token from .env or environment."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TUSHARE_TOKEN="):
                    return line.split("=", 1)[1]
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise RuntimeError("No TUSHARE_TOKEN found in .env or environment")
    return token


def get_trade_dates(collector: TushareCollector, start: str, end: str) -> list[str]:
    """Fetch trade calendar between start and end dates."""
    df = collector.pro.query(
        "trade_cal",
        exchange="SSE",
        start_date=start,
        end_date=end,
        fields="cal_date,is_open",
    )
    if df is None or len(df) == 0:
        raise RuntimeError("Failed to fetch trade calendar")
    open_days = df[df["is_open"] == 1]["cal_date"].sort_values().tolist()
    logger.info("Found %d trade dates from %s to %s", len(open_days), start, end)
    return open_days


def download_event_batch(
    collector: TushareCollector,
    interface: str,
    dates: list[str],
) -> dict:
    """Download event data for each date in dates list.

    Uses ann_date parameter for each interface.
    Returns summary dict.
    """
    success_count = 0
    fail_count = 0
    total_rows = 0

    for i, date in enumerate(dates):
        try:
            # For event interfaces, ann_date is the common filter
            params = {"ann_date": date}

            manifest = collector.download_with_retry(
                interface=interface,
                params=params,
                max_retries=2,
            )

            if manifest.status == "success":
                success_count += 1
                total_rows += manifest.row_count
            else:
                fail_count += 1
                logger.warning(
                    "Non-success status for %s %s: %s",
                    interface, date, manifest.status,
                )

            # Progress logging every 50 dates
            if (i + 1) % 50 == 0 or (i + 1) == len(dates):
                logger.info(
                    "[%s] Progress: %d/%d dates, %d rows so far",
                    interface, i + 1, len(dates), total_rows,
                )

        except Exception as exc:
            fail_count += 1
            logger.error("Failed %s %s: %s", interface, date, exc)
            # Continue with next date rather than aborting entirely
            continue

    summary = {
        "interface": interface,
        "dates_processed": len(dates),
        "success": success_count,
        "failed": fail_count,
        "total_rows": total_rows,
    }
    logger.info(
        "Done %s: %d success, %d failed, %d total rows",
        interface, success_count, fail_count, total_rows,
    )
    return summary


def main():
    token = get_token()
    collector = TushareCollector(token=token, raw_dir=RAW_DIR)
    normalizer = DataNormalizer(raw_dir=RAW_DIR)

    # 1. Get trade dates
    logger.info("=" * 60)
    logger.info("Starting event data download: %s → %s", START_DATE, END_DATE)
    logger.info("=" * 60)

    trade_dates = get_trade_dates(collector, START_DATE, END_DATE)
    logger.info("Will iterate through %d trade dates", len(trade_dates))

    # 2. Download each interface
    summaries = []
    for interface in INTERFACES:
        logger.info("-" * 60)
        logger.info("Downloading: %s", interface)
        logger.info("-" * 60)
        summary = download_event_batch(collector, interface, trade_dates)
        summaries.append(summary)

    # 3. Print summary
    logger.info("=" * 60)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("=" * 60)
    for s in summaries:
        logger.info(
            "  %-15s | %d dates | %d success | %d failed | %d rows",
            s["interface"], s["dates_processed"],
            s["success"], s["failed"], s["total_rows"],
        )

    # 4. Normalize all downloaded data
    logger.info("=" * 60)
    logger.info("NORMALIZING DATA")
    logger.info("=" * 60)
    for interface in INTERFACES:
        try:
            count = normalizer.normalize_interface(interface)
            logger.info("Normalized %s: %d new batches", interface, count)
        except Exception as exc:
            logger.error("Normalization failed for %s: %s", interface, exc)

    # 5. Final summary
    logger.info("=" * 60)
    logger.info("ALL DONE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
