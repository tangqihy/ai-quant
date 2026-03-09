"""
指标计算服务 - 提供 MA、RSI、MACD、布林带等常用技术指标
接口：get_indicator(symbol, indicator_name, params)
"""
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np


def _ensure_df(data: Any) -> pd.DataFrame:
    """将 K 线数据转为 DataFrame（按 date 排序）"""
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = pd.DataFrame(data)
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ---------- MA 均线 ----------
def calc_ma(close: pd.Series, period: int) -> pd.Series:
    """单条均线"""
    return close.rolling(window=period).mean()


def compute_ma(
    data: List[Dict] | pd.DataFrame,
    periods: List[int] | None = None,
) -> Dict[str, List[Optional[float]]]:
    """
    计算多条 MA。periods 默认 [5, 10, 20]。
    返回 { "ma5": [...], "ma10": [...], "ma20": [...] }，与日期一一对应。
    """
    df = _ensure_df(data)
    if "close" not in df.columns:
        return {}
    close = df["close"]
    periods = periods or [5, 10, 20]
    result = {}
    for p in periods:
        s = calc_ma(close, p)
        result[f"ma{p}"] = s.tolist()
    return result


# ---------- RSI ----------
def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI 指标"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def compute_rsi(
    data: List[Dict] | pd.DataFrame,
    period: int = 14,
) -> Dict[str, List[Optional[float]]]:
    """计算 RSI。返回 { "rsi": [...] }"""
    df = _ensure_df(data)
    if "close" not in df.columns:
        return {}
    s = calc_rsi(df["close"], period=period)
    return {"rsi": s.tolist()}


# ---------- MACD ----------
def calc_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple:
    """MACD：返回 (dif, dea, macd_bar)"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_bar = (dif - dea) * 2
    return dif, dea, macd_bar


def compute_macd(
    data: List[Dict] | pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, List[Optional[float]]]:
    """计算 MACD。返回 { "dif": [...], "dea": [...], "macd": [...] }"""
    df = _ensure_df(data)
    if "close" not in df.columns:
        return {}
    dif, dea, macd_bar = calc_macd(df["close"], fast=fast, slow=slow, signal=signal)
    return {
        "dif": dif.tolist(),
        "dea": dea.tolist(),
        "macd": macd_bar.tolist(),
    }


# ---------- 布林带 ----------
def calc_boll(
    close: pd.Series,
    period: int = 20,
    std_mult: float = 2.0,
) -> tuple:
    """布林带：中轨=MA(close, period)，上下轨=中轨 ± std_mult * std"""
    mid = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    std = std.fillna(0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def compute_boll(
    data: List[Dict] | pd.DataFrame,
    period: int = 20,
    std_mult: float = 2.0,
) -> Dict[str, List[Optional[float]]]:
    """计算布林带。返回 { "boll_upper": [...], "boll_mid": [...], "boll_lower": [...] }"""
    df = _ensure_df(data)
    if "close" not in df.columns:
        return {}
    upper, mid, lower = calc_boll(df["close"], period=period, std_mult=std_mult)
    return {
        "boll_upper": upper.tolist(),
        "boll_mid": mid.tolist(),
        "boll_lower": lower.tolist(),
    }


# ---------- 统一入口 ----------
INDICATOR_FUNCS = {
    "ma": compute_ma,
    "rsi": compute_rsi,
    "macd": compute_macd,
    "boll": compute_boll,
}


class IndicatorService:
    """指标计算服务：依赖外部传入 K 线数据，按 indicator_name 与 params 计算"""

    def get_indicator(
        self,
        data: List[Dict] | pd.DataFrame,
        indicator_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Optional[float]]]:
        """
        计算单个指标。
        :param data: K 线列表或 DataFrame，需含 open/high/low/close/date
        :param indicator_name: ma | rsi | macd | boll
        :param params: 指标参数，如 {"periods": [5,10,20]}, {"period": 14}, {"period": 20, "std_mult": 2}
        :return: 指标序列字典，与 data 行一一对应
        """
        params = params or {}
        name = indicator_name.lower().strip()
        if name not in INDICATOR_FUNCS:
            return {}
        fn = INDICATOR_FUNCS[name]
        if name == "ma":
            return fn(data, periods=params.get("periods") or [5, 10, 20])
        if name == "rsi":
            return fn(data, period=params.get("period", 14))
        if name == "macd":
            return fn(
                data,
                fast=params.get("fast", 12),
                slow=params.get("slow", 26),
                signal=params.get("signal", 9),
            )
        if name == "boll":
            return fn(
                data,
                period=params.get("period", 20),
                std_mult=params.get("std_mult", 2.0),
            )
        return fn(data, **params)


# 单例
indicator_service = IndicatorService()
