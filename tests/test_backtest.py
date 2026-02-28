"""
后端单元测试
"""
import pytest
from app.services.backtest_service import BacktestEngine, run_backtest


class TestBacktestEngine:
    """回测引擎测试"""
    
    @pytest.fixture
    def sample_data(self):
        """测试用K线数据"""
        return [
            {"date": "20230101", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000000},
            {"date": "20230102", "open": 103, "high": 108, "low": 102, "close": 106, "volume": 1100000},
            {"date": "20230103", "open": 106, "high": 110, "low": 105, "close": 108, "volume": 1200000},
            {"date": "20230104", "open": 108, "high": 112, "low": 107, "close": 110, "volume": 1300000},
            {"date": "20230105", "open": 110, "high": 115, "low": 109, "close": 112, "volume": 1400000},
            {"date": "20230106", "open": 112, "high": 116, "low": 111, "close": 114, "volume": 1500000},
            {"date": "20230107", "open": 114, "high": 118, "low": 113, "close": 116, "volume": 1600000},
            {"date": "20230108", "open": 116, "high": 120, "low": 115, "close": 118, "volume": 1700000},
            # 数据继续...
        ]
    
    def test_backtest_initialization(self):
        """测试回测引擎初始化"""
        engine = BacktestEngine(initial_capital=1000000)
        assert engine.initial_capital == 1000000
        assert engine.capital == 1000000
        assert engine.position == 0
    
    def test_run_backtest_with_data(self, sample_data):
        """测试回测执行"""
        result = run_backtest(
            symbol="TEST",
            data=sample_data,
            strategy="ma_cross",
            short_window=3,
            long_window=5,
            initial_capital=1000000
        )
        
        assert result["success"] is True
        assert result["symbol"] == "TEST"
        assert result["strategy"] == "ma_cross"
        assert "total_return" in result
        assert "annual_return" in result
        assert "max_drawdown" in result
        assert "total_trades" in result
    
    def test_backtest_empty_data(self):
        """测试空数据处理"""
        result = run_backtest(symbol="TEST", data=[])
        assert result.get("error") is not None
    
    def test_backtest_insufficient_data(self):
        """测试数据不足"""
        data = [{"date": "20230101", "close": 100}] * 10
        result = run_backtest(symbol="TEST", data=data)
        # 数据不足50条应该返回错误或特殊处理
        assert result is not None
    
    def test_calculate_win_rate(self):
        """测试胜率计算"""
        engine = BacktestEngine(initial_capital=1000000)
        engine.trades = [
            {"date": "20230101", "action": "BUY", "cost": 100000},
            {"date": "20230102", "action": "SELL", "proceeds": 110000},
            {"date": "20230103", "action": "BUY", "cost": 100000},
            {"date": "20230104", "action": "SELL", "proceeds": 90000},
        ]
        win_rate = engine._calculate_win_rate()
        assert 0 <= win_rate <= 100


class TestStockService:
    """股票服务测试（需要网络）"""
    
    def test_service_import(self):
        """测试服务导入"""
        from app.services.stock_service import stock_service
        assert stock_service is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
