"""
Stock Canvas SQLite 持久化

每模块一个库文件的惯例（参照 simulation_store / watchlist_store）；
WAL 模式保证 CLI 进程与 FastAPI 进程并发读写安全。
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.canvas import Canvas, CanvasStatus, Card, CardType, Edge, EdgeType

DEFAULT_DB_PATH = "app/data/canvas.db"

_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def _now() -> str:
    return datetime.now().strftime(_DATETIME_FMT)


def _dt_to_str(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime(_DATETIME_FMT)


def _dt_from_str(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, _DATETIME_FMT)
    except ValueError:
        return datetime.fromisoformat(value)


class CanvasStore:
    """画布/卡片/关联的 SQLite 存储"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # 支持环境变量覆盖，便于测试与 CLI 指定临时库
        self.db_path = Path(db_path or os.environ.get("CANVAS_DB_PATH") or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS canvases (
                    ts_code TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    status TEXT DEFAULT 'watching',
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY,
                    ts_code TEXT NOT NULL REFERENCES canvases(ts_code) ON DELETE CASCADE,
                    card_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    structured_data TEXT DEFAULT '{}',
                    tags TEXT DEFAULT '[]',
                    importance INTEGER DEFAULT 3,
                    source TEXT DEFAULT 'user',
                    source_ref TEXT DEFAULT '',
                    position TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    expires_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_cards_ts_code ON cards(ts_code);
                CREATE INDEX IF NOT EXISTS idx_cards_type ON cards(card_type);

                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    source_card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                    target_card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                    edge_type TEXT NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_card_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_card_id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ==================== 行转换 ====================

    @staticmethod
    def _row_to_canvas(row: sqlite3.Row) -> Canvas:
        return Canvas(
            ts_code=row["ts_code"],
            name=row["name"],
            status=CanvasStatus(row["status"]),
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=_dt_from_str(row["created_at"]) or datetime.now(),
            updated_at=_dt_from_str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> Card:
        return Card(
            id=row["id"],
            ts_code=row["ts_code"],
            card_type=CardType(row["card_type"]),
            title=row["title"],
            content=row["content"] or "",
            structured_data=json.loads(row["structured_data"] or "{}"),
            tags=json.loads(row["tags"] or "[]"),
            importance=row["importance"],
            source=row["source"] or "user",
            source_ref=row["source_ref"] or "",
            position=json.loads(row["position"] or "{}"),
            created_at=_dt_from_str(row["created_at"]) or datetime.now(),
            updated_at=_dt_from_str(row["updated_at"]),
            expires_at=_dt_from_str(row["expires_at"]),
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> Edge:
        return Edge(
            id=row["id"],
            source_card_id=row["source_card_id"],
            target_card_id=row["target_card_id"],
            edge_type=EdgeType(row["edge_type"]),
            label=row["label"],
            created_at=_dt_from_str(row["created_at"]) or datetime.now(),
        )

    # ==================== Canvas CRUD ====================

    def create_canvas(self, canvas: Canvas) -> Canvas:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO canvases (ts_code, name, status, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    canvas.ts_code,
                    canvas.name,
                    canvas.status.value,
                    json.dumps(canvas.metadata, ensure_ascii=False),
                    _dt_to_str(canvas.created_at),
                    _dt_to_str(canvas.updated_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return canvas

    def get_canvas(self, ts_code: str) -> Optional[Canvas]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM canvases WHERE ts_code = ?", (ts_code,)
            ).fetchone()
            return self._row_to_canvas(row) if row else None
        finally:
            conn.close()

    def list_canvases(self, status: Optional[str] = None) -> List[Canvas]:
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM canvases WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM canvases ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_canvas(r) for r in rows]
        finally:
            conn.close()

    def update_canvas(self, ts_code: str, fields: Dict[str, Any]) -> bool:
        allowed = {"name", "status", "metadata"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return False
        if "status" in updates and isinstance(updates["status"], CanvasStatus):
            updates["status"] = updates["status"].value
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            updates["metadata"] = json.dumps(updates["metadata"], ensure_ascii=False)
        updates["updated_at"] = _now()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn = self._connect()
        try:
            cur = conn.execute(
                f"UPDATE canvases SET {set_clause} WHERE ts_code = ?",
                (*updates.values(), ts_code),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_canvas(self, ts_code: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM canvases WHERE ts_code = ?", (ts_code,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ==================== Card CRUD ====================

    def add_card(self, card: Card) -> Card:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO cards (
                    id, ts_code, card_type, title, content, structured_data,
                    tags, importance, source, source_ref, position,
                    created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.id,
                    card.ts_code,
                    card.card_type.value,
                    card.title,
                    card.content,
                    json.dumps(card.structured_data, ensure_ascii=False),
                    json.dumps(card.tags, ensure_ascii=False),
                    card.importance,
                    card.source,
                    card.source_ref,
                    json.dumps(card.position, ensure_ascii=False),
                    _dt_to_str(card.created_at),
                    _dt_to_str(card.updated_at),
                    _dt_to_str(card.expires_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return card

    def get_card(self, card_id: str) -> Optional[Card]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            return self._row_to_card(row) if row else None
        finally:
            conn.close()

    def list_cards(
        self,
        ts_code: str,
        card_type: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Card]:
        sql = "SELECT * FROM cards WHERE ts_code = ?"
        params: List[Any] = [ts_code]
        if card_type:
            sql += " AND card_type = ?"
            params.append(card_type)
        sql += " ORDER BY created_at ASC"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            cards = [self._row_to_card(r) for r in rows]
        finally:
            conn.close()
        if tag:
            cards = [c for c in cards if tag in c.tags]
        return cards

    def update_card(self, card_id: str, fields: Dict[str, Any]) -> bool:
        allowed = {"title", "content", "structured_data", "tags", "importance", "position", "expires_at"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return False
        for key in ("structured_data", "tags", "position"):
            if key in updates and isinstance(updates[key], (dict, list)):
                updates[key] = json.dumps(updates[key], ensure_ascii=False)
        if "expires_at" in updates and isinstance(updates["expires_at"], datetime):
            updates["expires_at"] = _dt_to_str(updates["expires_at"])
        updates["updated_at"] = _now()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn = self._connect()
        try:
            cur = conn.execute(
                f"UPDATE cards SET {set_clause} WHERE id = ?",
                (*updates.values(), card_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_card(self, card_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def search_cards(
        self,
        keyword: str,
        ts_code: Optional[str] = None,
        card_type: Optional[str] = None,
    ) -> List[Card]:
        like = f"%{keyword}%"
        sql = """
            SELECT * FROM cards
            WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)
        """
        params: List[Any] = [like, like, like]
        if ts_code:
            sql += " AND ts_code = ?"
            params.append(ts_code)
        if card_type:
            sql += " AND card_type = ?"
            params.append(card_type)
        sql += " ORDER BY created_at DESC"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_card(r) for r in rows]
        finally:
            conn.close()

    # ==================== Edge CRUD ====================

    def add_edge(self, edge: Edge) -> Edge:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO edges (id, source_card_id, target_card_id, edge_type, label, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.source_card_id,
                    edge.target_card_id,
                    edge.edge_type.value,
                    edge.label,
                    _dt_to_str(edge.created_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return edge

    def delete_edge(self, edge_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def list_edges_for_canvas(self, ts_code: str) -> List[Edge]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT e.* FROM edges e
                JOIN cards c ON e.source_card_id = c.id
                WHERE c.ts_code = ?
                ORDER BY e.created_at ASC
                """,
                (ts_code,),
            ).fetchall()
            return [self._row_to_edge(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())
