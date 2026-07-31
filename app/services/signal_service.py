"""
盘中信号评估：复用回测 BaseStrategy.generate_signals，输出最新一根的动作建议。
支持 as_of 历史回放与逐根时间轴扫描（盘后自测）。
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from app.strategies import get_strategy, list_strategies
from app.services.stock_service import stock_service
from app.services.tushare_service import tushare_service

CN_TZ = ZoneInfo("Asia/Shanghai")

# 与本周规则书对齐的默认允许下单时段
DEFAULT_WINDOWS = [
    (time(9, 35), time(10, 30)),
    (time(13, 30), time(14, 30)),
]

# 日线 as_of 仅有日期时，用该时刻判断时段（贴近规则书上午窗）
DAILY_WINDOW_CLOCK = time(10, 0)

SNAPSHOT_KEYS = (
    "close",
    "rsi",
    "ma_short",
    "ma_long",
    "open",
    "high",
    "low",
    "volume",
)


def _in_trading_window(
    now: Optional[datetime] = None,
    windows: Optional[List[tuple[time, time]]] = None,
) -> tuple[bool, str]:
    now = now or datetime.now(CN_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CN_TZ)
    else:
        now = now.astimezone(CN_TZ)

    if now.weekday() >= 5:
        return False, "非交易日（周末）"

    t = now.time()
    windows = windows or DEFAULT_WINDOWS
    for start, end in windows:
        if start <= t <= end:
            return True, f"在允许时段 {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    parts = [f"{a.strftime('%H:%M')}-{b.strftime('%H:%M')}" for a, b in windows]
    return False, f"不在允许时段（允许: {', '.join(parts)}）"


def parse_as_of(as_of: str) -> Tuple[datetime, bool]:
    """
    解析回放时点。
    返回 (datetime Asia/Shanghai, has_time)。
    仅日期时 has_time=False，窗口时钟取 DAILY_WINDOW_CLOCK。
    """
    raw = (as_of or "").strip()
    if not raw:
        raise ValueError("as_of 为空")

    normalized = raw.replace("/", "-").replace("T", " ")
    has_time = False
    dt: Optional[datetime] = None

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y%m%d %H:%M:%S",
        "%Y%m%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d",
    ):
        try:
            dt = datetime.strptime(normalized, fmt)
            has_time = "%H" in fmt
            break
        except ValueError:
            continue

    if dt is None:
        raise ValueError(f"无法解析 as_of: {as_of}")

    if not has_time:
        dt = dt.replace(hour=DAILY_WINDOW_CLOCK.hour, minute=DAILY_WINDOW_CLOCK.minute, second=0)
    return dt.replace(tzinfo=CN_TZ), has_time


def _bar_datetime(date_val: Any) -> datetime:
    """K 线 date 字段 → 带时区 datetime。"""
    raw = str(date_val).strip()
    s = raw.replace("/", "-").replace("T", " ")
    date_only = " " not in s and ":" not in s

    dt: Optional[datetime] = None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d %H:%M:%S",
        "%Y%m%d %H:%M",
        "%Y%m%d",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue

    if dt is None:
        dt = pd.to_datetime(s).to_pydatetime()

    if getattr(dt, "tzinfo", None) is None:
        if date_only or (dt.hour == 0 and dt.minute == 0 and dt.second == 0 and date_only):
            dt = dt.replace(
                hour=DAILY_WINDOW_CLOCK.hour,
                minute=DAILY_WINDOW_CLOCK.minute,
                second=0,
            )
        dt = dt.replace(tzinfo=CN_TZ)
    return dt.astimezone(CN_TZ)


def _truncate_bars(bars: List[Dict[str, Any]], as_of_dt: datetime, has_time: bool) -> List[Dict[str, Any]]:
    """截断到 as_of（含）。仅日期时保留当日全部 bar。"""
    out: List[Dict[str, Any]] = []
    as_of_date = as_of_dt.date()
    for bar in bars:
        try:
            bdt = _bar_datetime(bar.get("date"))
        except Exception:
            continue
        if has_time:
            if bdt <= as_of_dt:
                out.append(bar)
        else:
            if bdt.date() <= as_of_date:
                out.append(bar)
    return out


def _load_bars(
    symbol: str,
    period: str = "daily",
    lookback_days: int = 120,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if end_date:
        end_ymd = "".join(ch for ch in str(end_date) if ch.isdigit())[:8]
        try:
            end_dt = datetime.strptime(end_ymd, "%Y%m%d")
        except ValueError:
            end_dt = datetime.now(CN_TZ)
            end_ymd = end_dt.strftime("%Y%m%d")
    else:
        end_dt = datetime.now(CN_TZ)
        end_ymd = end_dt.strftime("%Y%m%d")

    start = (end_dt - timedelta(days=lookback_days)).strftime("%Y%m%d")

    if period and period != "daily":
        return tushare_service.get_stock_minutes(
            symbol=symbol,
            freq=period,
            start_date=start,
            end_date=end_ymd,
        ) or []
    return stock_service.get_stock_history(
        symbol=symbol,
        start_date=start,
        end_date=end_ymd,
        adjust="qfq",
    ) or []


def _coerce_params(strategy_id: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = next((s for s in list_strategies() if s["id"] == strategy_id), None)
    out: Dict[str, Any] = {}
    if meta:
        for p in meta.get("param_schema") or []:
            name = p["name"]
            default = p.get("default")
            raw = (params or {}).get(name, default)
            if p.get("type") == "int":
                out[name] = int(raw)
            elif p.get("type") == "float":
                out[name] = float(raw)
            else:
                out[name] = raw
    elif params:
        out.update(params)
    return out


def _row_snapshot(row: pd.Series) -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    for key in SNAPSHOT_KEYS:
        if key not in row.index:
            continue
        val = row[key]
        if pd.isna(val):
            snap[key] = None
        elif hasattr(val, "item"):
            try:
                snap[key] = float(val)
            except Exception:
                snap[key] = None
        else:
            try:
                snap[key] = float(val)
            except Exception:
                snap[key] = val
    return snap


def _build_reason(
    action: str,
    strategy_id: str,
    snapshot: Dict[str, Any],
    params: Dict[str, Any],
    buy: bool,
    sell: bool,
) -> str:
    if strategy_id == "rsi":
        rsi = snapshot.get("rsi")
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        if buy:
            return f"RSI 上穿超卖线 {oversold}（当前 RSI={rsi:.2f}）" if rsi is not None else "RSI 买入信号"
        if sell:
            return f"RSI 下穿超买线 {overbought}（当前 RSI={rsi:.2f}）" if rsi is not None else "RSI 卖出信号"
        if rsi is not None:
            return f"无交叉信号，当前 RSI={rsi:.2f}（超卖={oversold}/超买={overbought}）"
        return "无交叉信号"
    if strategy_id == "ma_cross":
        short_w = params.get("short_window", 5)
        long_w = params.get("long_window", 20)
        ma_s = snapshot.get("ma_short")
        ma_l = snapshot.get("ma_long")
        if buy:
            return f"MA{short_w} 上穿 MA{long_w}（金叉）"
        if sell:
            return f"MA{short_w} 下穿 MA{long_w}（死叉）"
        if ma_s is not None and ma_l is not None:
            relation = "上方" if ma_s > ma_l else "下方"
            return f"无交叉，MA{short_w}={ma_s:.2f} 在 MA{long_w}={ma_l:.2f} {relation}"
        return "无交叉信号"
    if buy:
        return "买入信号触发"
    if sell:
        return "卖出信号触发"
    return "持有观望"


def _action_from_flags(buy: bool, sell: bool) -> str:
    if buy and not sell:
        return "BUY"
    if sell and not buy:
        return "SELL"
    return "HOLD"


def _prepare_signal_frame(
    symbol: str,
    strategy: str,
    params: Optional[Dict[str, Any]],
    period: str,
    as_of: Optional[str],
    lookback_days: int,
) -> Tuple[Optional[pd.DataFrame], Dict[str, Any], Optional[str]]:
    """
    加载并截断 K 线、生成信号列。
    成功返回 (df, coerced, None)；失败返回 (None, {}, error)。
    """
    strategy_obj = get_strategy(strategy)
    if strategy_obj is None:
        return None, {}, f"未知策略: {strategy}"

    as_of_dt: Optional[datetime] = None
    has_time = False
    end_ymd: Optional[str] = None
    if as_of:
        try:
            as_of_dt, has_time = parse_as_of(as_of)
            end_ymd = as_of_dt.strftime("%Y%m%d")
        except ValueError as e:
            return None, {}, str(e)

    bars = _load_bars(symbol, period=period, lookback_days=lookback_days, end_date=end_ymd)
    if as_of_dt is not None:
        bars = _truncate_bars(bars, as_of_dt, has_time)

    if not bars or len(bars) < 5:
        return None, {}, "K线数据不足，无法评估信号"

    coerced = _coerce_params(strategy, params)
    df = pd.DataFrame(bars).sort_values("date").reset_index(drop=True)
    df = strategy_obj.generate_signals(df, **coerced)
    df["buy_signal"] = df.get("buy_signal", False)
    df["sell_signal"] = df.get("sell_signal", False)
    if hasattr(df["buy_signal"], "fillna"):
        df["buy_signal"] = df["buy_signal"].fillna(False)
        df["sell_signal"] = df["sell_signal"].fillna(False)
    return df, coerced, None


def evaluate_signal(
    symbol: str,
    strategy: str = "rsi",
    params: Optional[Dict[str, Any]] = None,
    period: str = "daily",
    now: Optional[datetime] = None,
    as_of: Optional[str] = None,
    lookback_days: int = 120,
) -> Dict[str, Any]:
    """
    评估最新一根（或 as_of 截断后最后一根）K 线的策略信号。
    action: BUY | SELL | HOLD
    """
    strategy_obj = get_strategy(strategy)
    if strategy_obj is None:
        return {"error": f"未知策略: {strategy}"}

    mode = "replay" if as_of else "live"
    as_of_dt: Optional[datetime] = None
    has_time = False
    window_clock_note = None

    if as_of:
        try:
            as_of_dt, has_time = parse_as_of(as_of)
        except ValueError as e:
            return {"error": str(e)}
        if not has_time:
            window_clock_note = f"日线回放默认用 {DAILY_WINDOW_CLOCK.strftime('%H:%M')} 判断时段"
        now = as_of_dt

    df, coerced, err = _prepare_signal_frame(
        symbol, strategy, params, period, as_of, lookback_days
    )
    if err:
        return {"error": err}
    assert df is not None

    last = df.iloc[-1]
    buy = bool(last["buy_signal"])
    sell = bool(last["sell_signal"])
    action = _action_from_flags(buy, sell)

    snapshot = _row_snapshot(last)
    in_window, window_reason = _in_trading_window(now=now)
    reason = _build_reason(action, strategy, snapshot, coerced, buy, sell)

    quote_price = None
    if mode == "live":
        try:
            q = stock_service.get_realtime_quote(symbol)
            if q:
                quote_price = float(q.get("price") or 0) or None
        except Exception:
            quote_price = None

    bar_date = str(last.get("date"))
    return {
        "symbol": symbol,
        "strategy": strategy,
        "strategy_name": strategy_obj.name,
        "period": period,
        "params": coerced,
        "mode": mode,
        "as_of": bar_date,
        "as_of_requested": as_of,
        "bar_index": int(len(df) - 1),
        "bar_total": int(len(df)),
        "bars_used": int(len(df)),
        "window_clock_note": window_clock_note,
        "evaluated_at": datetime.now(CN_TZ).isoformat(),
        "action": action,
        "buy_signal": buy,
        "sell_signal": sell,
        "reason": reason,
        "in_trading_window": in_window,
        "window_reason": window_reason,
        "snapshot": snapshot,
        "quote_price": quote_price,
        "suggested_price": quote_price or snapshot.get("close"),
        "executable": action in ("BUY", "SELL") and in_window,
    }


def scan_signal_timeline(
    symbol: str,
    strategy: str = "rsi",
    params: Optional[Dict[str, Any]] = None,
    period: str = "daily",
    as_of: Optional[str] = None,
    lookback_days: int = 120,
    warm_up: int = 30,
) -> Dict[str, Any]:
    """
    一次生成整段时间轴，供前端逐根步进（无需每根重新拉数）。
    warm_up: 前 N 根仅作指标预热，不进入可步进列表。
    """
    strategy_obj = get_strategy(strategy)
    if strategy_obj is None:
        return {"error": f"未知策略: {strategy}"}

    df, coerced, err = _prepare_signal_frame(
        symbol, strategy, params, period, as_of, lookback_days
    )
    if err:
        return {"error": err}
    assert df is not None

    start_i = min(max(warm_up, 0), max(len(df) - 1, 0))
    bars_out: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    def _bar_num(row: pd.Series, key: str, default: float = 0.0) -> float:
        try:
            v = row[key] if key in row.index else default
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return default
            return float(v)
        except Exception:
            return default

    klines: List[Dict[str, Any]] = []
    for i in range(len(df)):
        row = df.iloc[i]
        close_v = _bar_num(row, "close")
        klines.append(
            {
                "date": str(row["date"] if "date" in row.index else ""),
                "open": _bar_num(row, "open", close_v),
                "high": _bar_num(row, "high", close_v),
                "low": _bar_num(row, "low", close_v),
                "close": close_v,
                "volume": _bar_num(row, "volume"),
            }
        )

    for i in range(start_i, len(df)):
        row = df.iloc[i]
        buy = bool(row["buy_signal"])
        sell = bool(row["sell_signal"])
        action = _action_from_flags(buy, sell)
        snapshot = _row_snapshot(row)
        try:
            clock = _bar_datetime(row.get("date"))
        except Exception:
            clock = datetime.now(CN_TZ)
        in_window, window_reason = _in_trading_window(now=clock)
        reason = _build_reason(action, strategy, snapshot, coerced, buy, sell)
        item = {
            "index": i,
            "step": i - start_i,
            "date": str(row.get("date")),
            "action": action,
            "buy_signal": buy,
            "sell_signal": sell,
            "reason": reason,
            "close": snapshot.get("close"),
            "in_trading_window": in_window,
            "window_reason": window_reason,
            "snapshot": snapshot,
            "executable": action in ("BUY", "SELL") and in_window,
        }
        bars_out.append(item)
        if action in ("BUY", "SELL"):
            events.append(
                {
                    "index": i,
                    "step": i - start_i,
                    "date": item["date"],
                    "action": action,
                    "reason": reason,
                    "close": item["close"],
                    "in_trading_window": in_window,
                }
            )

    return {
        "symbol": symbol,
        "strategy": strategy,
        "strategy_name": strategy_obj.name,
        "period": period,
        "params": coerced,
        "mode": "replay",
        "as_of_requested": as_of,
        "warm_up": start_i,
        "bar_total": len(df),
        "step_total": len(bars_out),
        "klines": klines,
        "bars": bars_out,
        "events": events,
        "window_clock_note": f"日线 bar 默认用 {DAILY_WINDOW_CLOCK.strftime('%H:%M')} 判断时段",
    }


signal_service = type(
    "SignalService",
    (),
    {
        "evaluate": staticmethod(evaluate_signal),
        "scan": staticmethod(scan_signal_timeline),
    },
)()
