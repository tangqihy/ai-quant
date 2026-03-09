"""
K线数据本地存储 - SQLite 持久化，支持按 symbol + date 查询与增量更新
"""
import os
import sqlite3
import threading
from typing import List, Dict, Optional

# 与 stock_service 保持一致的数据目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "klines.db")

# 线程局部存储，避免多线程共用一个连接
_local = threading.local()


def _get_conn():
    """获取当前线程的 DB 连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def _init_db():
    """初始化表结构：symbol + date + adjust 唯一，支持增量更新"""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS klines (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            adjust TEXT NOT NULL DEFAULT '',
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            change_pct REAL,
            turnover REAL,
            updated_at TEXT,
            PRIMARY KEY (symbol, date, adjust)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_symbol_date ON klines(symbol, date)")
    conn.commit()


# 模块加载时初始化
_init_db()


def get(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
) -> List[Dict]:
    """
    按 symbol + 日期范围查询 K 线。
    返回与 stock_service.get_stock_history 一致的字段格式。
    """
    conn = _get_conn()
    adjust = adjust or ""
    params = [symbol, adjust]
    conditions = ["symbol = ?", "adjust = ?"]
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    sql = f"SELECT date, open, high, low, close, volume, amount, change_pct, turnover FROM klines WHERE {' AND '.join(conditions)} ORDER BY date"
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "date": str(r["date"]),
            "open": float(r["open"] or 0),
            "high": float(r["high"] or 0),
            "low": float(r["low"] or 0),
            "close": float(r["close"] or 0),
            "volume": float(r["volume"] or 0),
            "amount": float(r["amount"] or 0),
            "change_pct": float(r["change_pct"] or 0),
            "turnover": float(r["turnover"] or 0),
        }
        for r in rows
    ]


def save(symbol: str, rows: List[Dict], adjust: str = "qfq") -> None:
    """
    写入或更新 K 线（按 symbol + date + adjust 做 REPLACE，实现增量更新）。
    rows 每项需包含 date, open, high, low, close, volume, amount, change_pct, turnover。
    """
    if not rows:
        return
    conn = _get_conn()
    adjust = adjust or ""
    from datetime import datetime, timezone
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT OR REPLACE INTO klines
        (symbol, date, adjust, open, high, low, close, volume, amount, change_pct, turnover, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    data = []
    for r in rows:
        date_val = str(r.get("date", ""))
        if not date_val:
            continue
        data.append((
            symbol,
            date_val,
            adjust,
            float(r.get("open", 0)),
            float(r.get("high", 0)),
            float(r.get("low", 0)),
            float(r.get("close", 0)),
            float(r.get("volume", 0)),
            float(r.get("amount", 0)),
            float(r.get("change_pct", 0)),
            float(r.get("turnover", 0)),
            updated_at,
        ))
    conn.executemany(sql, data)
    conn.commit()


def get_date_range(symbol: str, adjust: str = "qfq") -> Optional[tuple]:
    """
    返回该 symbol 在本地库中的 (min_date, max_date)，若无数据返回 None。
    用于判断是否需要增量拉取以及缺失的日期区间。
    """
    conn = _get_conn()
    adjust = adjust or ""
    row = conn.execute(
        "SELECT MIN(date) AS min_d, MAX(date) AS max_d FROM klines WHERE symbol = ? AND adjust = ?",
        (symbol, adjust),
    ).fetchone()
    if row and row["min_d"] and row["max_d"]:
        return (row["min_d"], row["max_d"])
    return None
