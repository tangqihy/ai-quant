"""
自选数据本地存储 - SQLite 持久化
"""
import os
import sqlite3
import threading
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "watchlist.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（线程本地）"""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def _init_db() -> None:
    """初始化数据库表"""
    conn = _get_conn()
    # 分组表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            color TEXT DEFAULT '#1890ff',
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    # 自选股票表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_stocks (
            symbol TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            group_ids TEXT DEFAULT '[]',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    conn.commit()


_init_db()


def _row_to_group(row: sqlite3.Row) -> Dict:
    """将分组行转换为字典"""
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "color": str(row["color"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_stock(row: sqlite3.Row) -> Dict:
    """将股票行转换为字典"""
    return {
        "symbol": str(row["symbol"]),
        "name": str(row["name"]),
        "group_ids": json.loads(row["group_ids"]) if row["group_ids"] else [],
        "note": str(row["note"]) if row["note"] else "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ==================== 分组操作 ====================

def get_groups() -> List[Dict]:
    """获取所有分组"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM watchlist_groups ORDER BY created_at"
    ).fetchall()
    return [_row_to_group(r) for r in rows]


def create_group(group_id: str, name: str, color: str = "#1890ff") -> Dict:
    """创建分组"""
    conn = _get_conn()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO watchlist_groups (id, name, color, created_at) VALUES (?, ?, ?, ?)",
        (group_id, name, color, now),
    )
    conn.commit()
    return {
        "id": group_id,
        "name": name,
        "color": color,
        "created_at": now,
        "updated_at": None,
    }


def update_group(group_id: str, name: Optional[str] = None, color: Optional[str] = None) -> bool:
    """更新分组"""
    conn = _get_conn()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if color is not None:
        updates.append("color = ?")
        params.append(color)
    if not updates:
        return False

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(group_id)

    conn.execute(
        f"UPDATE watchlist_groups SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()
    return True


def delete_group(group_id: str) -> bool:
    """删除分组"""
    conn = _get_conn()
    # 先更新该分组下的股票，移除该分组ID
    stocks = get_stocks()
    for stock in stocks:
        if group_id in stock.get("group_ids", []):
            new_group_ids = [g for g in stock["group_ids"] if g != group_id]
            update_stock_groups(stock["symbol"], new_group_ids)

    # 删除分组
    cursor = conn.execute("DELETE FROM watchlist_groups WHERE id = ?", (group_id,))
    conn.commit()
    return cursor.rowcount > 0


# ==================== 股票操作 ====================

def get_stocks() -> List[Dict]:
    """获取所有自选股票"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM watchlist_stocks ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_stock(r) for r in rows]


def get_stock(symbol: str) -> Optional[Dict]:
    """获取单个自选股票"""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM watchlist_stocks WHERE symbol = ?",
        (symbol,),
    ).fetchone()
    return _row_to_stock(row) if row else None


def add_stock(symbol: str, name: str = "", group_ids: List[str] = None, note: str = "") -> Dict:
    """添加自选股票"""
    conn = _get_conn()
    now = datetime.now().isoformat()
    group_ids_json = json.dumps(group_ids or [])

    conn.execute(
        """INSERT OR REPLACE INTO watchlist_stocks
           (symbol, name, group_ids, note, created_at, updated_at)
           VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM watchlist_stocks WHERE symbol = ?), ?), ?)""",
        (symbol, name, group_ids_json, note, symbol, now, now),
    )
    conn.commit()
    return {
        "symbol": symbol,
        "name": name,
        "group_ids": group_ids or [],
        "note": note,
        "created_at": now,
        "updated_at": now,
    }


def remove_stock(symbol: str) -> bool:
    """移除自选股票"""
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM watchlist_stocks WHERE symbol = ?", (symbol,))
    conn.commit()
    return cursor.rowcount > 0


def update_stock_groups(symbol: str, group_ids: List[str]) -> bool:
    """更新股票所属分组"""
    conn = _get_conn()
    group_ids_json = json.dumps(group_ids)
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "UPDATE watchlist_stocks SET group_ids = ?, updated_at = ? WHERE symbol = ?",
        (group_ids_json, now, symbol),
    )
    conn.commit()
    return cursor.rowcount > 0


def update_stock_note(symbol: str, note: str) -> bool:
    """更新股票备注"""
    conn = _get_conn()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "UPDATE watchlist_stocks SET note = ?, updated_at = ? WHERE symbol = ?",
        (note, now, symbol),
    )
    conn.commit()
    return cursor.rowcount > 0


# ==================== 数据导出 ====================

def get_all_data() -> Dict:
    """获取完整自选数据"""
    return {
        "groups": get_groups(),
        "stocks": get_stocks(),
    }
