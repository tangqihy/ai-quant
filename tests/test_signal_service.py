"""信号评估与策略会话测试"""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.signal_service import (
    evaluate_signal,
    scan_signal_timeline,
    _in_trading_window,
    _coerce_params,
    parse_as_of,
    _truncate_bars,
)
from app.services.strategy_session_store import StrategySessionStore


def test_trading_window_weekend():
    saturday = datetime(2026, 7, 18, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))  # Sat
    ok, reason = _in_trading_window(now=saturday)
    assert ok is False
    assert "周末" in reason


def test_trading_window_in_morning():
    monday = datetime(2026, 7, 13, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))  # Mon
    ok, reason = _in_trading_window(now=monday)
    assert ok is True


def test_coerce_rsi_params():
    p = _coerce_params("rsi", {"period": "14", "oversold": 30, "overbought": 70})
    assert p["period"] == 14
    assert p["oversold"] == 30


def test_parse_as_of_date_defaults_to_1000():
    dt, has_time = parse_as_of("2026-07-13")
    assert has_time is False
    assert dt.hour == 10
    assert dt.minute == 0


def test_parse_as_of_with_time():
    dt, has_time = parse_as_of("2026-07-13 09:40")
    assert has_time is True
    assert dt.hour == 9
    assert dt.minute == 40


def test_truncate_bars_by_date():
    bars = [
        {"date": "2024-01-01", "close": 1},
        {"date": "2024-01-02", "close": 2},
        {"date": "2024-01-03", "close": 3},
    ]
    dt, has_time = parse_as_of("2024-01-02")
    cut = _truncate_bars(bars, dt, has_time)
    assert len(cut) == 2
    assert cut[-1]["date"] == "2024-01-02"


def _synthetic_bars():
    bars = [
        {
            "date": f"2024-01-{i:02d}",
            "open": 100 + i * 0.1,
            "high": 101 + i * 0.1,
            "low": 99 + i * 0.1,
            "close": 100 + i * 0.1,
            "volume": 1e6,
        }
        for i in range(1, 40)
    ]
    for i in range(len(bars)):
        if i < 20:
            bars[i]["close"] = 100 - i
        else:
            bars[i]["close"] = 80 + (i - 20) * 2
    return bars


def test_evaluate_signal_with_monkeypatch(monkeypatch):
    bars = _synthetic_bars()
    monkeypatch.setattr(
        "app.services.signal_service._load_bars",
        lambda *a, **k: bars,
    )
    monkeypatch.setattr(
        "app.services.signal_service.stock_service.get_realtime_quote",
        lambda symbol: {"price": bars[-1]["close"]},
    )

    now = datetime(2026, 7, 13, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    result = evaluate_signal("600036", "rsi", {"period": 14, "oversold": 30, "overbought": 70}, now=now)
    assert "error" not in result
    assert result["action"] in ("BUY", "SELL", "HOLD")
    assert "reason" in result
    assert result["symbol"] == "600036"
    assert result["in_trading_window"] is True
    assert result["mode"] == "live"


def test_evaluate_as_of_uses_replay_clock_not_machine_now(monkeypatch):
    bars = _synthetic_bars()
    monkeypatch.setattr(
        "app.services.signal_service._load_bars",
        lambda *a, **k: bars,
    )

    # 机器“现在”是周末也不影响：as_of 是周一上午
    result = evaluate_signal(
        "600036",
        "rsi",
        {"period": 14, "oversold": 30, "overbought": 70},
        as_of="2024-01-15",
    )
    assert "error" not in result
    assert result["mode"] == "replay"
    assert result["as_of"] == "2024-01-15"
    assert result["bars_used"] == 15
    assert result["in_trading_window"] is True  # 日线默认 10:00


def test_scan_timeline_stepping(monkeypatch):
    bars = _synthetic_bars()
    monkeypatch.setattr(
        "app.services.signal_service._load_bars",
        lambda *a, **k: bars,
    )
    tl = scan_signal_timeline(
        "600036",
        "rsi",
        {"period": 14, "oversold": 30, "overbought": 70},
        warm_up=10,
    )
    assert "error" not in tl
    assert tl["step_total"] == len(bars) - 10
    assert len(tl["bars"]) == tl["step_total"]
    assert all("action" in b for b in tl["bars"])
    assert len(tl["klines"]) == len(bars)
    assert {"date", "open", "high", "low", "close", "volume"} <= set(tl["klines"][0].keys())
    # events 应为 BUY/SELL 子集
    for e in tl["events"]:
        assert e["action"] in ("BUY", "SELL")


def test_session_store_roundtrip(tmp_path):
    store = StrategySessionStore(tmp_path / "sessions.json")
    s = store.upsert(
        {
            "symbol": "600036",
            "strategy": "rsi",
            "params": {"period": 14, "oversold": 30, "overbought": 70},
            "position_pct": 5,
            "enabled": True,
        }
    )
    assert s["id"]
    assert store.get_active()["symbol"] == "600036"
    store.set_enabled(s["id"], False)
    assert store.get_active() is None
    assert store.delete(s["id"]) is True
