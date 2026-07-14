"""
SQLite persistence for simulation trading state.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional


class SimulationStore:
    def __init__(self, db_path: str = "app/data/simulation_state.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def save_json(self, key: str, payload: Any) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO kv (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (key, text),
            )
            conn.commit()
        finally:
            conn.close()

    def load_json(self, key: str) -> Optional[Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            return json.loads(row[0])
        finally:
            conn.close()


simulation_store = SimulationStore()
