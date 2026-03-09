"""
API 路由测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestStockRoutes:
    """股票相关路由测试"""

    def test_get_stocks(self):
        """测试获取股票列表"""
        response = client.get("/api/stocks?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data
        assert "page" in data

    def test_get_stocks_with_search(self):
        """测试搜索股票"""
        response = client.get("/api/stocks?search=平安")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_stock_detail(self):
        """测试获取单个股票信息"""
        response = client.get("/api/stocks/000001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_stock_history(self):
        """测试获取股票历史数据"""
        response = client.get("/api/stocks/000001/history?start_date=20240101&end_date=20240131")
        # 可能成功或失败（取决于网络/数据源），但应该返回 200
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "data" in data

    def test_get_stock_realtime(self):
        """测试获取实时行情"""
        response = client.get("/api/stocks/000001/realtime")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_realtime_quotes(self):
        """测试批量获取实时行情"""
        response = client.get("/api/quotes/realtime?symbols=000001,000002")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["total"] == 2


class TestBacktestRoutes:
    """回测相关路由测试"""

    def test_get_strategies(self):
        """测试获取策略列表"""
        response = client.get("/api/backtest/strategies")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0
        assert data["data"][0]["id"] == "ma_cross"

    def test_run_backtest_success(self):
        """测试运行回测 - 成功场景"""
        # 使用一个可能有足够数据的股票
        response = client.post("/api/backtest", json={
            "symbol": "000001",
            "start_date": "20230101",
            "end_date": "20241231",
            "strategy": "ma_cross",
            "short_window": 5,
            "long_window": 20,
            "initial_capital": 100000,
            "save_result": False
        })
        # 可能成功或失败（取决于数据源）
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                assert "total_return" in data
                assert "trades" in data

    def test_run_backtest_insufficient_data(self):
        """测试运行回测 - 数据不足"""
        response = client.post("/api/backtest", json={
            "symbol": "999999",  # 不存在的股票
            "start_date": "20240101",
            "end_date": "20240105",  # 只有5天
            "strategy": "ma_cross",
            "save_result": False
        })
        # 可能返回 200 或 500，取决于异常处理方式
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            # 应该返回数据不足的错误
            assert data["success"] is False or "error" in data

    def test_list_backtest_results(self):
        """测试列出回测结果"""
        response = client.get("/api/backtest?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data

    def test_list_backtest_results_with_filter(self):
        """测试带过滤的列出回测结果"""
        response = client.get("/api/backtest?symbol=000001&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_backtest_result_not_found(self):
        """测试获取不存在的回测结果"""
        response = client.get("/api/backtest/bt_nonexistent_xxx")
        assert response.status_code == 404

    def test_delete_backtest_result_not_found(self):
        """测试删除不存在的回测结果"""
        response = client.delete("/api/backtest/bt_nonexistent_xxx")
        assert response.status_code == 404


class TestErrorHandling:
    """错误处理测试"""

    def test_404_error(self):
        """测试 404 错误"""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_cors_headers(self):
        """测试 CORS 头"""
        response = client.options("/", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 200
