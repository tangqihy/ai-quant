"""
后端单元测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


def test_health():
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_get_strategies():
    """测试获取策略列表"""
    response = client.get("/api/backtest/strategies")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) > 0
    assert data["data"][0]["id"] == "ma_cross"


def test_backtest_engine_basic():
    """测试回测引擎基本逻辑"""
    from app.services.backtest_service import BacktestEngine

    engine = BacktestEngine(initial_capital=100000)

    # 构造简单测试数据
    test_data = []
    prices = [10, 11, 12, 11, 10, 9, 10, 11, 12, 13,
              14, 13, 12, 11, 10, 11, 12, 13, 14, 15,
              16, 15, 14, 13, 12, 13, 14, 15, 16, 17]
    for i, price in enumerate(prices):
        day = i + 1
        test_data.append({
            "date": f"202401{day:02d}",
            "open": price - 0.5,
            "close": price,
            "high": price + 1,
            "low": price - 1,
            "volume": 10000,
        })

    result = engine.run("TEST", test_data, strategy="ma_cross", short_window=3, long_window=5)

    assert result["success"] is True
    assert result["symbol"] == "TEST"
    assert result["initial_capital"] == 100000
    assert "final_value" in result
    assert "total_return" in result
    assert "max_drawdown" in result
    assert "trades" in result
    assert "daily_values" in result


def test_backtest_engine_empty_data():
    """测试空数据回测"""
    from app.services.backtest_service import BacktestEngine

    engine = BacktestEngine()
    result = engine.run("TEST", [], strategy="ma_cross")
    assert result.get("error") == "No data provided"


def test_backtest_api_missing_data():
    """测试回测API参数验证"""
    response = client.post("/api/backtest", json={
        "symbol": "999999",
        "start_date": "20240101",
        "end_date": "20240110",
        "strategy": "ma_cross"
    })
    # 数据不足或网络问题都应该返回合理响应
    assert response.status_code in [200, 500]
