"""
股票列表本地存储 - SQLite 持久化，支持分页、搜索与每日更新
"""
import os
import sqlite3
import threading
from datetime import datetime, timezone, date
from typing import List, Dict, Optional, Tuple, Callable

try:
    from pypinyin import lazy_pinyin, Style
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    lazy_pinyin = None
    Style = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "stock_list.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def _init_db() -> None:
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT NOT NULL PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            market TEXT NOT NULL DEFAULT '',
            updated_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stocks_market_symbol ON stocks(market, symbol)")
    conn.commit()


_init_db()


def get_last_updated() -> Optional[str]:
    """返回本地库最后更新日期 (YYYY-MM-DD)，无数据返回 None"""
    conn = _get_conn()
    row = conn.execute("SELECT MAX(updated_at) AS u FROM stocks").fetchone()
    if row and row["u"]:
        return str(row["u"])[:10]
    return None


def get_count(search: Optional[str] = None) -> int:
    """符合条件的总数，search 为空则全量数量"""
    conn = _get_conn()
    if search and search.strip():
        q = "%" + search.strip() + "%"
        row = conn.execute(
            "SELECT COUNT(1) AS c FROM stocks WHERE symbol LIKE ? OR name LIKE ?",
            (q, q),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(1) AS c FROM stocks").fetchone()
    return int(row["c"]) if row else 0


def _get_pinyin_initials(name: str) -> str:
    """获取股票名称的拼音首字母"""
    if not PYPINYIN_AVAILABLE or not name:
        return ""
    try:
        # 获取拼音首字母
        initials = lazy_pinyin(name, style=Style.FIRST_LETTER)
        return ''.join(initials).lower()
    except Exception:
        return ""

def _get_pinyin_full(name: str) -> str:
    """获取股票名称的完整拼音"""
    if not PYPINYIN_AVAILABLE or not name:
        return ""
    try:
        pinyin_list = lazy_pinyin(name)
        return ''.join(pinyin_list).lower()
    except Exception:
        return ""

def _matches_search(stock: Dict, search_term: str) -> bool:
    """检查股票是否匹配搜索词（支持代码、名称、拼音首字母、完整拼音）"""
    term = search_term.lower().strip()
    if not term:
        return True

    symbol = stock.get("symbol", "").lower()
    name = stock.get("name", "").lower()

    # 直接匹配代码或名称
    if term in symbol or term in name:
        return True

    # 拼音匹配（如果 pypinyin 可用）
    if PYPINYIN_AVAILABLE:
        # 首字母匹配（如：gzmt -> 贵州茅台）
        pinyin_initials = _get_pinyin_initials(name)
        if term in pinyin_initials:
            return True

        # 完整拼音匹配（如：guizhoumaotai -> 贵州茅台）
        pinyin_full = _get_pinyin_full(name)
        if term in pinyin_full:
            return True

    return False

def get_page(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    market: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    """
    分页查询，搜索支持代码、名称、拼音首字母、完整拼音。
    返回 (当前页列表, 总条数)。每项为 {"symbol", "name", "market"}。
    """
    conn = _get_conn()

    # 如果有搜索词且支持拼音，需要在 Python 层过滤
    if search and search.strip() and PYPINYIN_AVAILABLE:
        # 先获取所有数据（不分页）
        if market and market.strip():
            rows = conn.execute(
                "SELECT symbol, name, market FROM stocks WHERE market = ? ORDER BY symbol",
                (market.strip(),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT symbol, name, market FROM stocks ORDER BY symbol").fetchall()

        # 在 Python 层进行拼音匹配
        all_data = [
            {"symbol": str(r["symbol"]), "name": str(r["name"] or ""), "market": str(r["market"] or "")}
            for r in rows
        ]

        # 过滤匹配的股票
        filtered_data = [s for s in all_data if _matches_search(s, search)]
        total = len(filtered_data)

        # 分页
        offset = (page - 1) * page_size
        data = filtered_data[offset:offset + page_size]
        return data, total

    # 普通搜索（数据库层 LIKE）
    params: list = []
    conditions: List[str] = []
    if search and search.strip():
        q = "%" + search.strip() + "%"
        conditions.append("(symbol LIKE ? OR name LIKE ?)")
        params.extend([q, q])
    if market and market.strip():
        conditions.append("market = ?")
        params.append(market.strip())

    where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
    count_sql = f"SELECT COUNT(1) AS c FROM stocks{where_sql}"
    total = int(conn.execute(count_sql, params).fetchone()["c"])

    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    list_sql = f"""
        SELECT symbol, name, market FROM stocks
        {where_sql}
        ORDER BY symbol
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(list_sql, params).fetchall()
    data = [
        {"symbol": str(r["symbol"]), "name": str(r["name"] or ""), "market": str(r["market"] or "")}
        for r in rows
    ]
    return data, total


def get_all(market: Optional[str] = None) -> List[Dict]:
    """全量列表（用于兼容旧接口），仅返回 symbol, name, market"""
    conn = _get_conn()
    if market and market.strip():
        rows = conn.execute(
            "SELECT symbol, name, market FROM stocks WHERE market = ? ORDER BY symbol",
            (market.strip(),),
        ).fetchall()
    else:
        rows = conn.execute("SELECT symbol, name, market FROM stocks ORDER BY symbol").fetchall()
    return [
        {"symbol": str(r["symbol"]), "name": str(r["name"] or ""), "market": str(r["market"] or "")}
        for r in rows
    ]


def get_symbol_name_map() -> Dict[str, str]:
    """返回 symbol -> name 映射，供行情等接口用，避免全量加载列表"""
    conn = _get_conn()
    rows = conn.execute("SELECT symbol, name FROM stocks").fetchall()
    return {str(r["symbol"]): str(r["name"] or "") for r in rows}


def save_all(items: List[Dict], market: str = "沪深A股") -> None:
    """全量写入或更新（REPLACE），items 每项需含 symbol, name，可选 market"""
    if not items:
        return
    conn = _get_conn()
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT OR REPLACE INTO stocks (symbol, name, market, updated_at)
        VALUES (?, ?, ?, ?)
    """
    data = [
        (
            str(r.get("symbol", "")).strip(),
            str(r.get("name", "")).strip(),
            str(r.get("market", market)).strip() or market,
            updated_at,
        )
        for r in items
    ]
    conn.executemany(sql, data)
    conn.commit()


def is_stale(max_age_days: int = 1) -> bool:
    """本地数据是否过期（超过 max_age_days 天未更新或为空）"""
    last = get_last_updated()
    if not last:
        return True
    try:
        last_date = datetime.strptime(last[:10], "%Y-%m-%d").date()
        return (date.today() - last_date).days >= max_age_days
    except Exception:
        return True


def ensure_initialized(fetcher: Callable[[], List[Dict]], force_refresh: bool = False) -> None:
    """
    若本地无数据或已过期，则调用 fetcher 拉取全量列表并写入本地。
    fetcher 应返回 [{"symbol", "name", "market"}, ...]。
    仅用 is_stale() 判断（无数据时 get_last_updated() 为 None，is_stale 为 True），避免每次请求全表 get_count()。
    """
    if force_refresh or is_stale():
        items = fetcher()
        if items:
            save_all(items)
