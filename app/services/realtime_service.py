"""
实时行情数据服务 - 新浪主数据源 + 腾讯降级 + 本地缓存
只查询传入的自选 symbol 列表，不全量获取。
"""
import logging
import re
import time
import urllib.request
import urllib.error
from typing import List, Dict, Optional
import threading

logger = logging.getLogger(__name__)

# 统一行情字段（与前端 /api/quotes/realtime 约定一致）
QUOTE_KEYS = (
    "symbol", "name", "price", "change_pct", "change_amount",
    "open", "high", "low", "volume", "amount", "turnover",
)


def _symbol_to_sina_code(symbol: str) -> str:
    """A股代码转新浪 list 代码：6 -> sh，0/3 -> sz"""
    s = symbol.strip()
    if not s:
        return ""
    if s.startswith(("6", "5")):  # 上海
        return f"sh{s}" if not s.startswith("sh") else s
    if s.startswith(("0", "3")):  # 深圳
        return f"sz{s}" if not s.startswith("sz") else s
    return s


def _symbol_to_tencent_code(symbol: str) -> str:
    """A股代码转腾讯 q= 代码"""
    return _symbol_to_sina_code(symbol)


def _sina_code_to_symbol(code: str) -> str:
    """新浪 list 代码转回 symbol（去掉 sh/sz 前缀）"""
    if code.startswith("sh") or code.startswith("sz"):
        return code[2:]
    return code


class SinaDataProvider:
    """新浪财经实时行情（主数据源）"""

    BASE_URL = "https://hq.sinajs.cn/list="

    def fetch(self, symbols: List[str]) -> List[Dict]:
        """
        从新浪拉取实时行情。symbols 为纯代码如 ['600519','000001']。
        返回与 QUOTE_KEYS 一致的字典列表，失败抛异常。
        """
        if not symbols:
            return []

        codes = []
        for s in symbols:
            c = _symbol_to_sina_code(s)
            if c:
                codes.append(c)
        if not codes:
            return []

        url = self.BASE_URL + ",".join(codes)
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read()
                # 新浪常返回 gbk
                try:
                    text = raw.decode("gbk")
                except Exception:
                    text = raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as e:
            logger.warning("SinaDataProvider fetch error: %s", e)
            raise

        # 解析 var hq_str_sh600519="..."; 或 var hq_str_sz000001="...";
        pattern = re.compile(r'var\s+hq_str_(sh\d+|sz\d+)="([^"]*)"', re.IGNORECASE)
        results = []
        for m in pattern.finditer(text):
            code = m.group(1).lower()
            data_str = m.group(2).strip()
            if not data_str:
                continue
            parts = data_str.split(",")
            # 沪深A股字段：0名称 1今开 2昨收 3现价 4最高 5最低 6买一 7卖一 8成交量 9成交额 ...
            if len(parts) < 10:
                continue
            try:
                name = parts[0].strip()
                open_p = float(parts[1]) if parts[1] else 0.0
                prev_close = float(parts[2]) if parts[2] else 0.0
                price = float(parts[3]) if parts[3] else 0.0
                high = float(parts[4]) if parts[4] else 0.0
                low = float(parts[5]) if parts[5] else 0.0
                # 成交量 8：有的说是手（*100），文档说 22114263 需除以100 -> 手
                vol_raw = float(parts[8]) if parts[8] else 0.0
                volume = vol_raw  # 保持与常见用法一致，如需手则 /100
                amount_raw = float(parts[9]) if parts[9] else 0.0
                amount = amount_raw  # 元
                change = price - prev_close if prev_close else 0.0
                change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0
                change_amount = round(change, 2)
                # 换手率新浪 A 股接口不一定有，在更后字段；无则填 0
                turnover = 0.0
                if len(parts) > 38 and parts[38]:
                    try:
                        turnover = float(parts[38])
                    except ValueError:
                        pass
                results.append({
                    "symbol": _sina_code_to_symbol(code),
                    "name": name,
                    "price": round(price, 2),
                    "change_pct": change_pct,
                    "change_amount": change_amount,
                    "open": round(open_p, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "volume": round(volume, 0),
                    "amount": round(amount, 2),
                    "turnover": round(turnover, 2),
                })
            except (ValueError, IndexError) as e:
                logger.debug("SinaDataProvider parse skip %s: %s", code, e)
                continue

        if len(results) != len(symbols):
            logger.debug("SinaDataProvider got %d quotes for %d symbols", len(results), len(symbols))
        return results


class TencentDataProvider:
    """腾讯财经实时行情（备用数据源）"""

    BASE_URL = "http://qt.gtimg.cn/q="

    def fetch(self, symbols: List[str]) -> List[Dict]:
        """
        从腾讯拉取实时行情。symbols 为纯代码。
        返回与 QUOTE_KEYS 一致的字典列表，失败抛异常。
        """
        if not symbols:
            return []

        codes = [_symbol_to_tencent_code(s) for s in symbols if s.strip()]
        if not codes:
            return []

        url = self.BASE_URL + ",".join(codes)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read()
                text = raw.decode("gbk", errors="replace")
        except (urllib.error.URLError, OSError) as e:
            logger.warning("TencentDataProvider fetch error: %s", e)
            raise

        # 格式: v_sh600519="~name~code~price~prev~open~...";
        pattern = re.compile(r'v_(sh\d+|sz\d+)="([^"]*)"', re.IGNORECASE)
        results = []
        for m in pattern.finditer(text):
            code = m.group(1).lower()
            data_str = m.group(2).strip()
            if not data_str:
                continue
            parts = data_str.split("~")
            # 1名字 2代码 3现价 4昨收 5今开 6成交量 31涨跌 32涨跌% 33最高 34最低 36量 37额(万) 38换手
            if len(parts) < 35:
                continue
            try:
                name = parts[1] if len(parts) > 1 else ""
                price = float(parts[3]) if parts[3] else 0.0
                prev_close = float(parts[4]) if parts[4] else 0.0
                open_p = float(parts[5]) if parts[5] else 0.0
                vol_s = float(parts[6]) if len(parts) > 6 and parts[6] else 0.0
                change_amount = float(parts[31]) if len(parts) > 31 and parts[31] else 0.0
                change_pct = float(parts[32]) if len(parts) > 32 and parts[32] else 0.0
                high = float(parts[33]) if len(parts) > 33 and parts[33] else 0.0
                low = float(parts[34]) if len(parts) > 34 and parts[34] else 0.0
                volume = float(parts[36]) if len(parts) > 36 and parts[36] else vol_s
                amount_wan = float(parts[37]) if len(parts) > 37 and parts[37] else 0.0
                amount = amount_wan * 10000
                turnover = float(parts[38]) if len(parts) > 38 and parts[38] else 0.0
                results.append({
                    "symbol": _sina_code_to_symbol(code),
                    "name": name,
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "change_amount": round(change_amount, 2),
                    "open": round(open_p, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "volume": round(volume, 0),
                    "amount": round(amount, 2),
                    "turnover": round(turnover, 2),
                })
            except (ValueError, IndexError) as e:
                logger.debug("TencentDataProvider parse skip %s: %s", code, e)
                continue

        return results


class CachedDataProvider:
    """带本地缓存的行情提供者包装：先走缓存（5–15 秒），未命中或过期再请求底层 provider。"""

    def __init__(self, provider, ttl_seconds: int = 10):
        """
        :param provider: 具备 fetch(symbols) -> List[Dict] 的实例（如 Sina 或 Fallback）
        :param ttl_seconds: 缓存有效期秒数，建议 5–15
        """
        self._provider = provider
        self._ttl = max(5, min(15, ttl_seconds))
        self._cache: Dict[str, tuple] = {}  # key -> (data_list, timestamp)
        self._lock = threading.Lock()

    def get_realtime_quotes(self, symbols: List[str], allow_stale: bool = False) -> List[Dict]:
        """
        获取实时行情。若 allow_stale=True 且底层请求失败，则返回过期缓存（若有）。
        """
        if not symbols:
            return []

        cache_key = ",".join(sorted(s.strip() for s in symbols if s.strip()))
        if not cache_key:
            return []

        stale_data = None
        with self._lock:
            if cache_key in self._cache:
                data, ts = self._cache[cache_key]
                if time.time() - ts <= self._ttl:
                    logger.debug("realtime cache hit key=%s", cache_key[:50])
                    return list(data)
                if allow_stale:
                    stale_data = list(data)

        try:
            data = self._provider.fetch(symbols)
            with self._lock:
                self._cache[cache_key] = (data, time.time())
            return data
        except Exception as e:
            logger.warning("CachedDataProvider fetch failed: %s", e)
            if allow_stale and stale_data is not None:
                return stale_data
            with self._lock:
                if cache_key in self._cache:
                    return list(self._cache[cache_key][0])
            raise


class FallbackProvider:
    """组合主备：先 primary.fetch，失败则 fallback.fetch。"""

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def fetch(self, symbols: List[str]) -> List[Dict]:
        try:
            return self._primary.fetch(symbols)
        except Exception as e:
            logger.info("FallbackProvider trying fallback after primary error: %s", e)
            return self._fallback.fetch(symbols)


# 单例：新浪 -> 腾讯 降级，再包一层 5–15 秒缓存
_primary = SinaDataProvider()
_fallback = TencentDataProvider()
_chain = FallbackProvider(_primary, _fallback)
_cached = CachedDataProvider(_chain, ttl_seconds=10)


def get_realtime_quotes(symbols: List[str]) -> List[Dict]:
    """
    批量获取实时行情（仅查询传入的自选列表）。
    策略：先走缓存(5–15s)；未命中则新浪 -> 腾讯 降级；若都失败则返回过期缓存（若有）。
    """
    if not symbols:
        return []

    symbols = [s.strip() for s in symbols if s.strip()]
    if not symbols:
        return []

    try:
        return _cached.get_realtime_quotes(symbols, allow_stale=True)
    except Exception as e:
        logger.exception("get_realtime_quotes failed: %s", e)
        raise
