"""
财经新闻 / 快讯服务

优先尝试 Tushare news（需单独权限）；无权限时回退东方财富公开资讯接口。
带短时内存缓存，避免频繁请求外部源。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 东方财富「要闻」栏目
_EM_COLUMN = "350"
_EM_URL = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
_CACHE_TTL_SECONDS = 120

_cache: Dict[str, Any] = {"key": None, "expires": 0.0, "items": []}


def _normalize_item(
    *,
    title: str,
    summary: str = "",
    source: str = "",
    published_at: str = "",
    url: str = "",
    provider: str = "",
) -> Dict[str, str]:
    title = (title or "").strip()
    summary = (summary or "").strip()
    if not title and summary:
        # 快讯常把标题写在摘要里，如 【标题】正文
        if summary.startswith("【") and "】" in summary:
            title = summary[1 : summary.index("】")]
            summary = summary[summary.index("】") + 1 :].strip()
        else:
            title = summary[:80]
    return {
        "title": title,
        "summary": summary,
        "source": source or provider,
        "published_at": published_at,
        "url": url,
        "provider": provider,
    }


def _fetch_tushare(limit: int) -> List[Dict[str, str]]:
    """Tushare 新闻快讯（需单独开通权限）。"""
    token = settings.tushare_token
    if not token:
        return []
    try:
        import tushare as ts

        ts.set_token(token)
        pro = ts.pro_api()
        end = datetime.now()
        start = end - timedelta(hours=12)
        df = pro.news(
            src="sina",
            start_date=start.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=end.strftime("%Y-%m-%d %H:%M:%S"),
        )
        if df is None or df.empty:
            return []
        items: List[Dict[str, str]] = []
        for _, row in df.head(limit).iterrows():
            items.append(
                _normalize_item(
                    title=str(row.get("title") or ""),
                    summary=str(row.get("content") or ""),
                    source="新浪财经",
                    published_at=str(row.get("datetime") or ""),
                    provider="tushare",
                )
            )
        return items
    except Exception as e:
        logger.debug("Tushare news unavailable: %s", e)
        return []


def _fetch_eastmoney(limit: int) -> List[Dict[str, str]]:
    """东方财富公开要闻接口。"""
    params = {
        "client": "web",
        "biz": "web_news_col",
        "column": _EM_COLUMN,
        "order": "1",
        "needInteractData": "0",
        "page_index": "1",
        "page_size": str(min(max(limit, 1), 50)),
        "req_trace": str(int(time.time() * 1000)),
        "fields": "code,showTime,title,mediaName,summary,url,uniqueUrl",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.eastmoney.com/",
    }
    with httpx.Client(timeout=10.0, headers=headers) as client:
        resp = client.get(_EM_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
    rows = ((payload.get("data") or {}).get("list")) or []
    items: List[Dict[str, str]] = []
    for row in rows:
        items.append(
            _normalize_item(
                title=str(row.get("title") or ""),
                summary=str(row.get("summary") or ""),
                source=str(row.get("mediaName") or "东方财富"),
                published_at=str(row.get("showTime") or ""),
                url=str(row.get("uniqueUrl") or row.get("url") or ""),
                provider="eastmoney",
            )
        )
    return items


def get_news(limit: int = 20, src: str = "auto") -> List[Dict[str, str]]:
    """
    获取财经新闻列表。

    src:
      - auto: 先 Tushare，失败则东方财富
      - tushare / eastmoney: 指定来源
    """
    limit = min(max(int(limit or 20), 1), 50)
    src = (src or "auto").lower()
    cache_key = f"{src}:{limit}"
    now = time.time()
    if _cache["key"] == cache_key and now < _cache["expires"]:
        return list(_cache["items"])

    items: List[Dict[str, str]] = []
    errors: List[str] = []

    if src in ("auto", "tushare"):
        try:
            items = _fetch_tushare(limit)
        except Exception as e:
            errors.append(f"tushare: {e}")
            logger.warning("fetch tushare news failed: %s", e)

    if not items and src in ("auto", "eastmoney"):
        try:
            items = _fetch_eastmoney(limit)
        except Exception as e:
            errors.append(f"eastmoney: {e}")
            logger.warning("fetch eastmoney news failed: %s", e)

    if not items and errors:
        raise RuntimeError("; ".join(errors))

    _cache["key"] = cache_key
    _cache["expires"] = now + _CACHE_TTL_SECONDS
    _cache["items"] = items
    return list(items)


news_service = type("NewsService", (), {"get_news": staticmethod(get_news)})()
