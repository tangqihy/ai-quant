"""
回测结果存储服务测试
"""
import pytest
import json
import os
from datetime import datetime
from pathlib import Path

# 必须在导入服务前设置测试环境
os.environ['TESTING'] = 'true'

from app.services.storage_service import BacktestStorage, STORAGE_DIR


class TestBacktestStorage:
    """回测存储服务测试"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """测试前后清理"""
        # 保存原始目录
        self.original_dir = STORAGE_DIR
        # 使用临时测试目录
        self.test_dir = Path(__file__).parent / "test_backtest_results"
        self.test_dir.mkdir(exist_ok=True)

        # 清理测试文件
        for f in self.test_dir.glob("*.json"):
            f.unlink()

        yield

        # 清理
        for f in self.test_dir.glob("*.json"):
            f.unlink()

    def test_save_result(self):
        """测试保存回测结果"""
        result = {
            "symbol": "000001",
            "strategy": "ma_cross",
            "total_return": 15.5,
            "annual_return": 12.3,
            "max_drawdown": -8.2,
            "win_rate": 55.0,
            "total_trades": 20
        }

        task_id = BacktestStorage.save_result(result)

        # 验证返回了任务ID
        assert task_id.startswith("bt_")
        assert "000001" in task_id

        # 验证文件已创建
        file_path = STORAGE_DIR / f"{task_id}.json"
        assert file_path.exists()

        # 验证内容
        with open(file_path, encoding='utf-8') as f:
            saved = json.load(f)
        assert saved['symbol'] == "000001"
        assert saved['task_id'] == task_id
        assert 'created_at' in saved

    def test_get_result(self):
        """测试获取回测结果"""
        # 先保存一个结果
        result = {
            "symbol": "000002",
            "strategy": "dual_ma",
            "total_return": 20.0
        }
        task_id = BacktestStorage.save_result(result)

        # 获取结果
        retrieved = BacktestStorage.get_result(task_id)

        assert retrieved is not None
        assert retrieved['symbol'] == "000002"
        assert retrieved['task_id'] == task_id

    def test_get_nonexistent_result(self):
        """测试获取不存在的结果"""
        result = BacktestStorage.get_result("bt_nonexistent_xxx")
        assert result is None

    def test_list_results(self):
        """测试列出回测结果"""
        # 保存多个结果
        for i in range(3):
            result = {
                "symbol": f"60000{i}",
                "strategy": "ma_cross",
                "total_return": float(i * 10),
                "annual_return": float(i * 8),
                "max_drawdown": -5.0,
                "win_rate": 50.0,
                "total_trades": 10
            }
            BacktestStorage.save_result(result)

        # 列出结果
        results = BacktestStorage.list_results(limit=10)

        assert len(results) >= 3
        assert all('task_id' in r for r in results)
        assert all('symbol' in r for r in results)
        assert all('total_return' in r for r in results)

    def test_list_results_with_symbol_filter(self):
        """测试按股票代码过滤"""
        import time

        # 使用唯一的股票代码避免与其他测试冲突
        unique_symbol = "888887"
        other_symbol = "888886"

        # 保存不同股票的结果
        for i, symbol in enumerate([unique_symbol, other_symbol]):
            result = {
                "symbol": symbol,
                "strategy": "ma_cross",
                "total_return": 10.0 + i,
                "annual_return": 8.0,
                "max_drawdown": -5.0,
                "win_rate": 50.0,
                "total_trades": 10
            }
            BacktestStorage.save_result(result)
            time.sleep(1.1)

        # 过滤查询 - 只查询 unique_symbol
        results = BacktestStorage.list_results(symbol=unique_symbol)

        # 验证过滤功能：只返回指定symbol的结果
        assert len(results) >= 1
        assert all(r['symbol'] == unique_symbol for r in results)

    def test_list_results_limit(self):
        """测试结果数量限制"""
        # 保存多个结果
        for i in range(5):
            result = {
                "symbol": f"60000{i}",
                "strategy": "ma_cross",
                "total_return": float(i),
                "annual_return": float(i),
                "max_drawdown": -5.0,
                "win_rate": 50.0,
                "total_trades": 10
            }
            BacktestStorage.save_result(result)

        # 限制返回数量
        results = BacktestStorage.list_results(limit=2)

        assert len(results) == 2

    def test_delete_result(self):
        """测试删除回测结果"""
        # 保存并删除
        result = {"symbol": "000003", "strategy": "ma_cross", "total_return": 5.0}
        task_id = BacktestStorage.save_result(result)

        success = BacktestStorage.delete_result(task_id)

        assert success is True
        assert BacktestStorage.get_result(task_id) is None

    def test_delete_nonexistent_result(self):
        """测试删除不存在的结果"""
        success = BacktestStorage.delete_result("bt_nonexistent_xxx")
        assert success is False
