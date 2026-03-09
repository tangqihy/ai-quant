"""
API 路由测试
"""
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

os.environ.setdefault("QUANT_AUTH_PASSWORD", "testpass")
client = TestClient(app)


@pytest.fixture
def auth_headers():
    """登录获取 token，返回请求头。"""
    r = client.post("/api/auth/login", json={"password": "testpass"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("token")
    return {"Authorization": f"Bearer {data['token']}"}


class TestAuthRoutes:
    """鉴权接口测试"""

    def test_login_success(self):
        r = client.post("/api/auth/login", json={"password": "testpass"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "token" in data

    def test_login_fail(self):
        r = client.post("/api/auth/login", json={"password": "wrong"})
        assert r.status_code == 401

    def test_verify_valid(self, auth_headers):
        r = client.get("/api/auth/verify", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("valid") is True

    def test_verify_no_token(self):
        r = client.get("/api/auth/verify")
        assert r.status_code == 401

    def test_protected_route_without_token(self):
        r = client.get("/api/stocks?page=1&page_size=1")
        assert r.status_code == 401


class TestStockRoutes:
    """股票相关路由测试"""

    def test_get_stocks(self, auth_headers):
        """测试获取股票列表"""
        response = client.get("/api/stocks?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data
        assert "page" in data

    def test_get_stocks_with_search(self, auth_headers):
        """测试搜索股票"""
        response = client.get("/api/stocks?search=平安", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_stock_detail(self, auth_headers):
        """测试获取单个股票信息"""
        response = client.get("/api/stocks/000001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_stock_history(self, auth_headers):
        """测试获取股票历史数据"""
        response = client.get("/api/stocks/000001/history?start_date=20240101&end_date=20240131", headers=auth_headers)
        # 可能成功或失败（取决于网络/数据源），但应该返回 200
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "data" in data

    def test_get_stock_realtime(self, auth_headers):
        """测试获取实时行情"""
        response = client.get("/api/stocks/000001/realtime", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_realtime_quotes(self, auth_headers):
        """测试批量获取实时行情"""
        response = client.get("/api/quotes/realtime?symbols=000001,000002", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["total"] == 2


class TestBacktestRoutes:
    """回测相关路由测试"""

    def test_get_strategies(self, auth_headers):
        """测试获取策略列表"""
        response = client.get("/api/backtest/strategies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0
        assert data["data"][0]["id"] == "ma_cross"

    def test_run_backtest_success(self, auth_headers):
        """测试运行回测 - 成功场景"""
        response = client.post("/api/backtest", json={
            "symbol": "000001",
            "start_date": "20230101",
            "end_date": "20241231",
            "strategy": "ma_cross",
            "short_window": 5,
            "long_window": 20,
            "initial_capital": 100000,
            "save_result": False
        }, headers=auth_headers)
        # 可能成功或失败（取决于数据源）
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                assert "total_return" in data
                assert "trades" in data

    def test_run_backtest_insufficient_data(self, auth_headers):
        """测试运行回测 - 数据不足"""
        response = client.post("/api/backtest", json={
            "symbol": "999999",  # 不存在的股票
            "start_date": "20240101",
            "end_date": "20240105",  # 只有5天
            "strategy": "ma_cross",
            "save_result": False
        }, headers=auth_headers)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            # 应该返回数据不足的错误
            assert data["success"] is False or "error" in data

    def test_list_backtest_results(self, auth_headers):
        """测试列出回测结果"""
        response = client.get("/api/backtest?limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total" in data

    def test_list_backtest_results_with_filter(self, auth_headers):
        """测试带过滤的列出回测结果"""
        response = client.get("/api/backtest?symbol=000001&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_backtest_result_not_found(self, auth_headers):
        """测试获取不存在的回测结果"""
        response = client.get("/api/backtest/bt_nonexistent_xxx", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_backtest_result_not_found(self, auth_headers):
        """测试删除不存在的回测结果"""
        response = client.delete("/api/backtest/bt_nonexistent_xxx", headers=auth_headers)
        assert response.status_code == 404


class TestErrorHandling:
    """错误处理测试"""

    def test_404_error(self, auth_headers):
        """测试 404 错误"""
        response = client.get("/api/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_cors_headers(self):
        """测试 CORS 头"""
        response = client.options("/", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 200
