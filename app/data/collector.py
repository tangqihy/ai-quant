"""
Tushare data collector with append-only Parquet storage and BatchManifest.

Based on docs/design/02-data-collector.md.

Key design choices:
- Append-only: raw layer never overwrites old data.
- Each batch lives in its own hive-partitioned directory with a manifest.
- Atomic writes (tmp → rename) for both parquet and manifest.
- Rate limiting at 300 ms / call (~200 calls/min).
- Exponential-backoff retry.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import tushare as ts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BatchManifest
# ---------------------------------------------------------------------------

@dataclass
class BatchManifest:
    """Metadata for a single download batch."""

    batch_id: str
    interface: str
    params: dict
    requested_at: str      # ISO-8601
    completed_at: str      # ISO-8601
    row_count: int
    status: str            # "success" | "partial" | "failed"
    error_message: Optional[str] = None

    # serialisation helpers --------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> BatchManifest:
        return cls(**d)

    @classmethod
    def from_json(cls, text: str) -> BatchManifest:
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# TushareCollector
# ---------------------------------------------------------------------------

class TushareCollector:
    """Append-only Tushare data downloader.

    Parameters
    ----------
    token : str
        Tushare Pro API token.
    raw_dir : str | Path
        Root directory for raw parquet storage.  Default ``data/raw``.
    call_interval : float
        Minimum seconds between API calls (300 ms ≈ 200 calls/min).
    max_retries : int
        Default retry count for a single ``download()`` call.
    backoff_base : float
        Base delay (seconds) for exponential back-off.
    """

    def __init__(
        self,
        token: str,
        raw_dir: str | Path = "data/raw",
        call_interval: float = 0.3,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        self.pro = ts.pro_api(token)
        self.raw_dir = Path(raw_dir)
        self._call_interval = call_interval
        self._last_call_ts: float = 0.0
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        interface: str,
        params: dict,
        fields: Optional[list[str]] = None,
    ) -> BatchManifest:
        """Download one batch for *interface* with given *params*.

        Returns a :class:`BatchManifest` regardless of success/failure.
        On failure the manifest is written and the original exception is
        re-raised after recording.
        """
        batch_id = uuid.uuid4().hex[:8]
        ingest_date = datetime.now().strftime("%Y%m%d")
        requested_at = datetime.now().isoformat()

        batch_dir = self.raw_dir / interface / f"ingest_date={ingest_date}" / f"batch_id={batch_id}"
        batch_dir.mkdir(parents=True, exist_ok=True)

        try:
            # -- throttle -------------------------------------------------
            self._throttle()

            # -- API call --------------------------------------------------
            fields_str = ",".join(fields) if fields else None
            if fields_str:
                df: pd.DataFrame = self.pro.query(interface, **params, fields=fields_str)
            else:
                df: pd.DataFrame = self.pro.query(interface, **params)

            # -- empty result (valid) -------------------------------------
            if df is None or len(df) == 0:
                manifest = BatchManifest(
                    batch_id=batch_id,
                    interface=interface,
                    params=params,
                    requested_at=requested_at,
                    completed_at=datetime.now().isoformat(),
                    row_count=0,
                    status="success",
                    error_message=None,
                )
                self._write_manifest(batch_dir, manifest)
                logger.info("Batch %s: 0 rows for %s %s", batch_id, interface, params)
                return manifest

            # -- write parquet (atomic) ------------------------------------
            self._write_parquet_atomic(batch_dir, df)

            # -- build & persist manifest ----------------------------------
            manifest = BatchManifest(
                batch_id=batch_id,
                interface=interface,
                params=params,
                requested_at=requested_at,
                completed_at=datetime.now().isoformat(),
                row_count=len(df),
                status="success",
                error_message=None,
            )
            self._write_manifest(batch_dir, manifest)
            logger.info("Batch %s: %d rows for %s %s", batch_id, len(df), interface, params)
            return manifest

        except Exception as exc:
            manifest = BatchManifest(
                batch_id=batch_id,
                interface=interface,
                params=params,
                requested_at=requested_at,
                completed_at=datetime.now().isoformat(),
                row_count=0,
                status="failed",
                error_message=str(exc),
            )
            self._write_manifest(batch_dir, manifest)
            logger.error("Batch %s FAILED for %s %s: %s", batch_id, interface, params, exc)
            raise

    def download_with_retry(
        self,
        interface: str,
        params: dict,
        fields: Optional[list[str]] = None,
        max_retries: Optional[int] = None,
    ) -> BatchManifest:
        """``download()`` with exponential-backoff retry."""
        retries = max_retries if max_retries is not None else self.max_retries
        last_exc: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                return self.download(interface, params, fields)
            except Exception as exc:
                last_exc = exc
                delay = self.backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %d/%d failed for %s: %s – retrying in %.1fs",
                    attempt, retries, interface, exc, delay,
                )
                time.sleep(delay)

        # All retries exhausted – last_exc is guaranteed non-None here
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_latest_batch(self, interface: str, params: dict) -> Optional[Path]:
        """Return path to the newest ``data.parquet`` whose manifest
        matches *params* and has ``status == 'success'``.

        Returns *None* if nothing matches.
        """
        interface_dir = self.raw_dir / interface
        if not interface_dir.exists():
            return None

        ingest_dates = sorted(
            (d.name.replace("ingest_date=", "") for d in interface_dir.iterdir() if d.is_dir()),
            reverse=True,
        )

        for ingest_date in ingest_dates:
            ingest_dir = interface_dir / f"ingest_date={ingest_date}"
            for batch_dir in sorted(ingest_dir.iterdir(), reverse=True):
                if not batch_dir.is_dir():
                    continue
                manifest_path = batch_dir / "manifest.json"
                if not manifest_path.exists():
                    continue
                manifest = self._read_manifest(manifest_path)
                if manifest is not None and manifest.params == params and manifest.status == "success":
                    return batch_dir / "data.parquet"

        return None

    def list_batches(
        self,
        interface: str,
        status_filter: Optional[str] = None,
    ) -> list[BatchManifest]:
        """Return all manifests for *interface*, optionally filtered by status."""
        interface_dir = self.raw_dir / interface
        if not interface_dir.exists():
            return []

        results: list[BatchManifest] = []
        for manifest_path in interface_dir.rglob("manifest.json"):
            m = self._read_manifest(manifest_path)
            if m is None:
                continue
            if status_filter and m.status != status_filter:
                continue
            results.append(m)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if necessary to respect the rate limit."""
        elapsed = time.time() - self._last_call_ts
        if elapsed < self._call_interval:
            time.sleep(self._call_interval - elapsed)
        self._last_call_ts = time.time()

    @staticmethod
    def _write_parquet_atomic(batch_dir: Path, df: pd.DataFrame) -> None:
        """Write ``data.parquet`` atomically (tmp → rename)."""
        target = batch_dir / "data.parquet"
        tmp = batch_dir / "data.parquet.tmp"
        df.to_parquet(tmp, index=False)
        tmp.rename(target)

    @staticmethod
    def _write_manifest(batch_dir: Path, manifest: BatchManifest) -> None:
        """Write ``manifest.json`` atomically (tmp → rename)."""
        target = batch_dir / "manifest.json"
        tmp = batch_dir / "manifest.json.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(manifest.to_json())
        tmp.rename(target)

    @staticmethod
    def _read_manifest(path: Path) -> Optional[BatchManifest]:
        """Read a manifest file, returning *None* on any parse error."""
        try:
            with open(path, encoding="utf-8") as fh:
                return BatchManifest.from_json(fh.read())
        except Exception:
            return None
