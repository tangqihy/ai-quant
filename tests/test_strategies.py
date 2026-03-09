"""
策略插件与指标服务单元测试
"""
import pytest
import pandas as pd
from app.strategies import get, get_all, list_for_api
from app.strategies.ma_cross import MACrossStrategy
from app.strategies.rsi import RSIStrategy
from app.services.indicator_service import indicator_service
from app.services.backtest_service import run_backtest


@pytest.fixture
def sample_klines():
    """约 30 条模拟 K 线"""
    return [
        {
            "date": f"2024-01-{i:02d}",
            "open": 100 + i,
            "high": 102 + i,
            "low": 99 + i,
            "close": 101 + i,
            "volume": 1e6,
        }
        for i in range(1, 31)
    ]


class TestStrategyRegistry:
    """策略注册表"""

    def test_get_ma_cross(self):
        s = get("ma_cross")
        assert s is not None
        assert s.strategy_id == "ma_cross"
        assert s.name == "MA交叉策略"

    def test_get_rsi(self):
        s = get("rsi")
        assert s is not None
        assert s.strategy_id == "rsi"
        assert s.name == "RSI策略"

    def test_get_unknown(self):
        assert get("unknown_strategy") is None

    def test_list_for_api(self):
        data = list_for_api()
        assert len(data) >= 2
        ids = [x["id"] for x in data]
        assert "ma_cross" in ids
        assert "rsi" in ids
        first = next(x for x in data if x["id"] == "ma_cross")
        assert first["params"] == ["short_window", "long_window"]
        assert "description" in first


class TestMACrossStrategy:
    """MA 交叉策略"""

    def test_generate_signals(self, sample_klines):
        df = pd.DataFrame(sample_klines)
        strategy = MACrossStrategy()
        out = strategy.generate_signals(df, short_window=5, long_window=10)
        assert "buy_signal" in out.columns
        assert "sell_signal" in out.columns
        assert "ma_short" in out.columns
        assert "ma_long" in out.columns
        assert out["buy_signal"].dtype == bool
        assert out["sell_signal"].dtype == bool


class TestRSIStrategy:
    """RSI 策略"""

    def test_generate_signals(self, sample_klines):
        df = pd.DataFrame(sample_klines)
        strategy = RSIStrategy()
        out = strategy.generate_signals(df, period=14, oversold=30, overbought=70)
        assert "buy_signal" in out.columns
        assert "sell_signal" in out.columns
        assert "rsi" in out.columns


class TestIndicatorService:
    """指标计算服务"""

    def test_ma(self, sample_klines):
        r = indicator_service.get_indicator(sample_klines, "ma", {"periods": [5, 10]})
        assert "ma5" in r
        assert "ma10" in r
        assert len(r["ma5"]) == len(sample_klines)

    def test_rsi(self, sample_klines):
        r = indicator_service.get_indicator(sample_klines, "rsi", {"period": 14})
        assert "rsi" in r
        assert len(r["rsi"]) == len(sample_klines)

    def test_boll(self, sample_klines):
        r = indicator_service.get_indicator(sample_klines, "boll", {"period": 20})
        assert "boll_upper" in r
        assert "boll_mid" in r
        assert "boll_lower" in r

    def test_macd(self, sample_klines):
        r = indicator_service.get_indicator(sample_klines, "macd", {})
        assert "dif" in r
        assert "dea" in r
        assert "macd" in r

    def test_unknown_indicator(self, sample_klines):
        r = indicator_service.get_indicator(sample_klines, "unknown", {})
        assert r == {}


class TestBacktestWithStrategies:
    """回测引擎使用策略插件"""

    def test_backtest_ma_cross(self, sample_klines):
        res = run_backtest(
            "000001",
            sample_klines,
            strategy="ma_cross",
            short_window=5,
            long_window=20,
        )
        assert res.get("success") is True
        assert res["strategy"] == "ma_cross"
        assert "total_return" in res
        assert "trades" in res

    def test_backtest_rsi(self, sample_klines):
        res = run_backtest(
            "000001",
            sample_klines,
            strategy="rsi",
            period=14,
            oversold=30,
            overbought=70,
        )
        assert res.get("success") is True
        assert res["strategy"] == "rsi"

    def test_backtest_unknown_strategy(self, sample_klines):
        res = run_backtest("000001", sample_klines, strategy="unknown")
        assert "error" in res
        assert "Unknown strategy" in res["error"]

    def test_backtest_no_data(self):
        res = run_backtest("000001", [], strategy="ma_cross")
        assert "error" in res
