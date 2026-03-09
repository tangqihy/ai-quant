"""
策略基类与接口定义 - 所有回测策略需实现此接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import pandas as pd


class BaseStrategy(ABC):
    """回测策略抽象基类"""

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """策略唯一标识，用于 API 与注册表"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """策略显示名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """策略描述"""
        pass

    @property
    @abstractmethod
    def param_schema(self) -> List[Dict[str, Any]]:
        """
        参数 schema，每项包含 name, type, default, description。
        例如: [{"name": "short_window", "type": "int", "default": 5, "description": "短期均线周期"}]
        """
        pass

    @abstractmethod
    def generate_signals(
        self,
        df: pd.DataFrame,
        **params: Any,
    ) -> pd.DataFrame:
        """
        在 DataFrame 上计算买卖信号，需新增列：
        - buy_signal: bool
        - sell_signal: bool
        可选：buy_price, sell_price（若不设置，回测引擎会按 close ± 滑点计算）
        返回带信号的 df（可原地修改后返回）。
        """
        pass
