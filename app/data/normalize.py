"""
Normalize layer – transforms raw Tushare data into canonical, versioned Parquet.

Based on docs/design/03-normalize-layer.md:
- FieldSpec unit conversion (multiplier)
- YYYYMMDD string → DATE
- Dedup by primary key
- Versioned storage: data/normalized/versions/{interface}/ingest_date=…/batch_id=…/
- Latest view:      data/normalized/latest/{interface}/trade_year=…/trade_month=…/
- Monthly compaction
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .collector import BatchManifest
from .schemas import (
    INTERFACE_CONFIG,
    FieldSpec,
    apply_field_specs,
    get_field_specs,
    get_primary_key,
)

logger = logging.getLogger(__name__)


class DataNormalizer:
    """Transforms raw-layer batches into normalized, versioned Parquet files.

    Parameters
    ----------
    raw_dir : str | Path
        Root of the raw layer (default ``data/raw``).
    normalized_dir : str | Path
        Root of the normalized layer (default ``data/normalized``).
    """

    def __init__(
        self,
        raw_dir: str | Path = "data/raw",
        normalized_dir: str | Path = "data/normalized",
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.normalized_dir = Path(normalized_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize_interface(self, interface: str) -> int:
        """Normalize all *new* raw batches for *interface*.

        Returns the number of batches that were newly normalized.
        """
        raw_interface_dir = self.raw_dir / interface
        if not raw_interface_dir.exists():
            logger.warning("Raw directory missing for %s", interface)
            return 0

        fields = get_field_specs(interface)
        count = 0

        for manifest_path in sorted(raw_interface_dir.rglob("manifest.json")):
            manifest = self._read_manifest(manifest_path)
            if manifest is None or manifest.status != "success":
                continue
            if manifest.row_count == 0:
                continue

            batch_dir = manifest_path.parent
            ingest_date = manifest.requested_at[:10].replace("-", "")
            target_dir = (
                self.normalized_dir
                / "versions"
                / interface
                / f"ingest_date={ingest_date}"
                / f"batch_id={manifest.batch_id}"
            )

            # Skip already-normalized batches
            if (target_dir / "data.parquet").exists():
                continue

            data_path = batch_dir / "data.parquet"
            if not data_path.exists():
                continue

            try:
                df = pd.read_parquet(data_path)
                df = self._normalize_df(df, fields, interface)
                target_dir.mkdir(parents=True, exist_ok=True)
                df.to_parquet(target_dir / "data.parquet", index=False)
                count += 1
                logger.info(
                    "Normalized %s batch %s (%d rows)",
                    interface,
                    manifest.batch_id,
                    len(df),
                )
            except Exception:
                logger.exception(
                    "Failed to normalize %s batch %s",
                    interface,
                    manifest.batch_id,
                )

        # Rebuild the latest view after new data arrives
        if count > 0:
            self.generate_latest_view(interface)

        return count

    def normalize_all(self) -> dict[str, int]:
        """Normalize every interface defined in INTERFACE_CONFIG.

        Returns {interface: batch_count}.
        """
        results: dict[str, int] = {}
        for interface in INTERFACE_CONFIG:
            results[interface] = self.normalize_interface(interface)
        return results

    def generate_latest_view(self, interface: str) -> None:
        """Rebuild the ``latest/`` view for *interface*.

        Reads every version under ``versions/{interface}``, deduplicates by
        primary key (keeping the row with the highest ``ingested_at``), and
        writes hive-partitioned parquet by ``trade_year`` / ``trade_month``.
        """
        versions_dir = self.normalized_dir / "versions" / interface
        latest_dir = self.normalized_dir / "latest" / interface

        if not versions_dir.exists():
            logger.warning("No versions directory for %s", interface)
            return

        # Collect all versioned data
        all_dfs: list[pd.DataFrame] = []
        for parquet_path in versions_dir.rglob("data.parquet"):
            try:
                all_dfs.append(pd.read_parquet(parquet_path))
            except Exception:
                logger.exception("Failed to read %s", parquet_path)

        if not all_dfs:
            logger.info("No data in versions for %s", interface)
            return

        merged = pd.concat(all_dfs, ignore_index=True)

        # Dedup by primary key, keeping the latest ingested version
        pk = get_primary_key(interface)
        if pk:
            # ingested_at is a tiebreaker; if present, sort by it
            if "ingested_at" in merged.columns:
                merged = merged.sort_values("ingested_at", ascending=False)
            merged = merged.drop_duplicates(subset=pk, keep="first")

        # Partition by trade_year / trade_month
        if "trade_date" in merged.columns and pd.api.types.is_datetime64_any_dtype(
            merged["trade_date"]
        ):
            merged["trade_year"] = merged["trade_date"].dt.year.astype(str)
            merged["trade_month"] = merged["trade_date"].dt.strftime("%m")
        elif "trade_date" in merged.columns:
            # still string YYYYMMDD – derive partitions from string
            td = merged["trade_date"].astype(str).str.replace("-", "")
            merged["trade_year"] = td.str[:4]
            merged["trade_month"] = td.str[4:6]
        else:
            # No trade_date: write a single flat parquet
            latest_dir.mkdir(parents=True, exist_ok=True)
            merged.to_parquet(latest_dir / "data.parquet", index=False)
            logger.info("Latest view for %s: %d rows (flat)", interface, len(merged))
            return

        # Remove stale latest view
        import shutil

        if latest_dir.exists():
            shutil.rmtree(latest_dir)

        merged.to_parquet(latest_dir, partition_cols=["trade_year", "trade_month"], index=False)
        logger.info(
            "Latest view for %s: %d rows partitioned by trade_year/trade_month",
            interface,
            len(merged),
        )

    def compact_monthly(self, interface: str, year: int, month: int) -> None:
        """Merge all Parquet shards for a month into a single file.

        This improves DuckDB read performance when there are many small files.
        """
        latest_dir = self.normalized_dir / "latest" / interface
        month_dir = latest_dir / f"trade_year={year}" / f"trade_month={month:02d}"

        if not month_dir.exists():
            logger.warning("Month directory does not exist: %s", month_dir)
            return

        parquet_files = sorted(month_dir.glob("*.parquet"))
        if len(parquet_files) <= 1:
            return  # nothing to compact

        dfs = [pd.read_parquet(f) for f in parquet_files]
        merged = pd.concat(dfs, ignore_index=True)

        pk = get_primary_key(interface)
        if pk:
            merged = merged.drop_duplicates(subset=pk, keep="last")

        # Write compacted file
        compact_path = month_dir / "data.parquet"
        merged.to_parquet(compact_path, index=False)

        # Remove shards (but not the file we just wrote)
        for f in parquet_files:
            if f != compact_path:
                f.unlink()

        logger.info(
            "Compacted %s %d-%02d: %d files → 1 file (%d rows)",
            interface,
            year,
            month,
            len(parquet_files),
            len(merged),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_df(
        df: pd.DataFrame,
        fields: dict[str, FieldSpec],
        interface: str,
    ) -> pd.DataFrame:
        """Apply FieldSpec conversion and date-type coercion."""
        # 1. Unit conversion
        if fields:
            df = apply_field_specs(df, fields)

        # 2. Date conversion: YYYYMMDD string → datetime64 (DATE)
        df = _convert_date_columns(df)

        return df

    @staticmethod
    def _read_manifest(path: Path) -> Optional[BatchManifest]:
        try:
            with open(path, encoding="utf-8") as fh:
                return BatchManifest.from_json(fh.read())
        except Exception:
            return None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

# Columns that should be treated as date columns
_DATE_SUFFIXES = ("date", "_date")


def _convert_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any column whose name contains 'date' from YYYYMMDD string
    to pandas datetime64 (DATE type in Parquet).

    Handles both plain strings and already-numeric representations.
    """
    result = df.copy()
    for col in result.columns:
        if any(col.endswith(suffix) or col == suffix for suffix in ("date",)):
            if result[col].dtype == object:
                # String column – parse YYYYMMDD or YYYY-MM-DD
                result[col] = pd.to_datetime(
                    result[col].str.replace("-", ""),
                    format="%Y%m%d",
                    errors="coerce",
                )
            elif pd.api.types.is_integer_dtype(result[col]):
                result[col] = pd.to_datetime(
                    result[col].astype(str), format="%Y%m%d", errors="coerce"
                )
    return result
