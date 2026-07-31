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


def _series_to_list(s: pd.Series) -> List[Optional[float]]:
    """序列转 JSON 安全列表：NaN/Inf → None。"""
    return [None if pd.isna(v) or (isinstance(v, float) and np.isinf(v)) else float(v) for v in s.tolist()]


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
        result[f"ma{p}"] = _series_to_list(s)
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
    return {"rsi": _series_to_list(s)}


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
        "dif": _series_to_list(dif),
        "dea": _series_to_list(dea),
        "macd": _series_to_list(macd_bar),
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
        "boll_upper": _series_to_list(upper),
        "boll_mid": _series_to_list(mid),
        "boll_lower": _series_to_list(lower),
    }


# ---------- 通达信「分时T加0」 ----------
def _tdx_ema(close: pd.Series, n: int) -> pd.Series:
    """通达信 EMA：等价于 ewm(span=n, adjust=False)。"""
    return close.ewm(span=n, adjust=False).mean()


def _tdx_cross(a: pd.Series, b: pd.Series) -> pd.Series:
    """CROSS(A,B)：A 上穿 B。"""
    return (a > b) & (a.shift(1) <= b.shift(1))


def _tdx_longcross(a: pd.Series, b: pd.Series, n: int = 2) -> pd.Series:
    """
    LONGCROSS(A,B,N)：A 上穿 B，且之后连续 N 根保持 A>B。
    信号打在满足“穿越后第 N 根仍站上”的那一根。
    """
    crossed = _tdx_cross(a, b)
    above = a > b
    out = pd.Series(False, index=a.index)
    for i in range(len(a)):
        start = i - n + 1
        if start < 0:
            continue
        if bool(crossed.iloc[start]) and bool(above.iloc[start : i + 1].all()):
            out.iloc[i] = True
    return out


def compute_fenshi_t0(
    data: List[Dict] | pd.DataFrame,
    fast: int = 30,
    slow: int = 900,
    resist_ratio: float = 7 / 8,
    support_ratio: float = 0.5 / 8,
) -> Dict[str, List[Optional[float]]]:
    """
    通达信「分时T加0」近似实现（建议用 1min/5min K 线）。

    DYNAINFO 近似（按当日区间通道解读，最贴合该公式做 T 用途）：
      GRXY02 ≈ 当日累计最高
      GRXY03 ≈ 当日累计最低
      GRXY04 = 高低差
      阻力 = 低 + 差 * 7/8
      支撑 = 低 + 差 * 0.5/8

    返回字段：
      grxy01, strength(强弱), resistance(阻力), support(支撑),
      buy_signal(★B), resist_cross(★)
    """
    df = _ensure_df(data)
    if "close" not in df.columns or df.empty:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close

    if "date" in df.columns:
        session = df["date"].astype(str).str.slice(0, 10)
    else:
        session = pd.Series(["all"] * len(df))

    day_high = high.groupby(session).cummax()
    day_low = low.groupby(session).cummin()
    span = (day_high - day_low).clip(lower=0)

    grxy01 = _tdx_ema(close, fast)
    strength = _tdx_ema(close, slow)
    resistance = day_low + span * resist_ratio
    support = day_low + span * support_ratio

    buy_signal = _tdx_longcross(support, close, 2)
    resist_cross = _tdx_longcross(close, resistance, 2)

    def _num(s: pd.Series) -> List[Optional[float]]:
        return [None if pd.isna(v) else float(v) for v in s.tolist()]

    def _flag(s: pd.Series) -> List[Optional[float]]:
        return [1.0 if bool(v) else 0.0 for v in s.tolist()]

    return {
        "grxy01": _num(grxy01),
        "strength": _num(strength),
        "resistance": _num(resistance),
        "support": _num(support),
        "buy_signal": _flag(buy_signal),
        "resist_cross": _flag(resist_cross),
    }


# ---------- 通达信「主力/大盘资金 + 趋势」 ----------
def _tdx_sma(series: pd.Series, n: int, m: int = 1) -> pd.Series:
    """通达信 SMA(X,N,M)：Y=(M*X+(N-M)*Y')/N。"""
    values: List[float] = []
    prev: Optional[float] = None
    for x in series.tolist():
        if x is None or (isinstance(x, float) and np.isnan(x)):
            values.append(np.nan)
            continue
        xf = float(x)
        if prev is None or (isinstance(prev, float) and np.isnan(prev)):
            prev = xf
        else:
            prev = (m * xf + (n - m) * prev) / n
        values.append(prev)
    return pd.Series(values, index=series.index)


def _tdx_filter(cond: pd.Series, n: int) -> pd.Series:
    """FILTER(X,N)：信号成立后 N 根内不再重复发出。"""
    out = pd.Series(False, index=cond.index)
    cooldown = 0
    for i, v in enumerate(cond.tolist()):
        if cooldown > 0:
            cooldown -= 1
            continue
        if bool(v):
            out.iloc[i] = True
            cooldown = n
    return out


def _align_index_ohlc(
    stock_df: pd.DataFrame,
    index_data: List[Dict] | pd.DataFrame | None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """把指数 K 线按 date 对齐到股票序列；缺失时用股票 OHLC 兜底。"""
    close = stock_df["close"].astype(float)
    high = stock_df["high"].astype(float) if "high" in stock_df.columns else close
    low = stock_df["low"].astype(float) if "low" in stock_df.columns else close
    if index_data is None:
        return high, low, close

    idx = _ensure_df(index_data)
    if idx.empty or "date" not in stock_df.columns or "date" not in idx.columns:
        return high, low, close

    left = stock_df[["date"]].copy()
    right = idx[["date", "high", "low", "close"]].copy()
    right = right.rename(columns={"high": "index_high", "low": "index_low", "close": "index_close"})
    merged = left.merge(right, on="date", how="left")
    ih = merged["index_high"].astype(float).fillna(high)
    il = merged["index_low"].astype(float).fillna(low)
    ic = merged["index_close"].astype(float).fillna(close)
    return ih, il, ic


def compute_capital_trend(
    data: List[Dict] | pd.DataFrame,
    index_data: List[Dict] | pd.DataFrame | None = None,
) -> Dict[str, List[Optional[float]]]:
    """
    通达信「主力进撤 + 大盘资金 + 趋势线买卖」近似实现。

    依赖：
      - 个股 OHLCV
      - 可选指数 OHLCV（INDEXH/INDEXL/INDEXC）；缺省时用个股近似（大盘段会失真）

    主要输出：
      main_in / main_out          主力进 / 主力撤
      index_in / index_out        大盘资金进场 / 撤走
      trend                       趋势线
      prepare_cash / buy_stock / sell_edge  信号旗标
    """
    df = _ensure_df(data)
    if "close" not in df.columns or df.empty:
        return {}

    c = df["close"].astype(float)
    h = df["high"].astype(float) if "high" in df.columns else c
    l = df["low"].astype(float) if "low" in df.columns else c

    # --- 个股主力 ---
    grxy31 = (c * 2 + h + l) / 4 * 10
    grxy32 = _tdx_ema(grxy31, 13) - _tdx_ema(grxy31, 34)
    grxy33 = _tdx_ema(grxy32, 5)
    grxy34 = 2 * (grxy32 - grxy33) * 5.5
    main_out = grxy34.where(grxy34 <= 0, 0.0)
    main_in = grxy34.where(grxy34 >= 0, 0.0)

    # --- 大盘资金（INDEX*）；原公式 GRXY35/36 未进入最终信号，这里直接算 GRXY311 ---
    index_h, index_l, index_c = _align_index_ohlc(df, index_data)
    grxy38 = (index_c * 2 + index_h + index_l) / 4
    grxy39 = _tdx_ema(grxy38, 13) - _tdx_ema(grxy38, 34)
    grxy310 = _tdx_ema(grxy39, 3)
    grxy311 = (grxy39 - grxy310) / 2
    index_in = grxy311.where(grxy311 >= 0, 0.0)
    index_out = grxy311.where(grxy311 <= 0, 0.0)

    # --- 趋势线与买卖 ---
    den55 = (h.rolling(55).max() - l.rolling(55).min()).replace(0, np.nan)
    rsv55 = (c - l.rolling(55).min()) / den55 * 100
    sma1 = _tdx_sma(rsv55, 5, 1)
    sma2 = _tdx_sma(sma1, 3, 1)
    grxy3011 = 3 * sma1 - 2 * sma2
    trend = _tdx_ema(grxy3011, 3)
    ref_trend = trend.shift(1)
    grxy312 = (trend - ref_trend) / ref_trend.replace(0, np.nan) * 100

    prepare_raw = trend <= 13
    prepare = _tdx_filter(prepare_raw, 15)
    buy_raw = (trend <= 13) & (grxy312 > 13)
    buy = _tdx_filter(buy_raw, 10)
    sell_edge = (trend > 90) & (trend > ref_trend)

    def _num(s: pd.Series) -> List[Optional[float]]:
        return [None if pd.isna(v) else float(v) for v in s.tolist()]

    def _flag(s: pd.Series) -> List[Optional[float]]:
        return [1.0 if bool(v) else 0.0 for v in s.fillna(False).tolist()]

    return {
        "main_in": _num(main_in),
        "main_out": _num(main_out),
        "index_in": _num(index_in),
        "index_out": _num(index_out),
        "trend": _num(trend),
        "trend_chg": _num(grxy312),
        "prepare_cash": _flag(prepare),
        "buy_stock": _flag(buy),
        "sell_edge": _flag(sell_edge),
    }


# ---------- 统一入口 ----------
INDICATOR_FUNCS = {
    "ma": compute_ma,
    "rsi": compute_rsi,
    "macd": compute_macd,
    "boll": compute_boll,
    "fenshi_t0": compute_fenshi_t0,
    "capital_trend": compute_capital_trend,
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
        :param indicator_name: ma | rsi | macd | boll | fenshi_t0 | capital_trend
        :param params: 指标参数；capital_trend 可传 index_data（指数K线列表）
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
        if name == "fenshi_t0":
            return fn(
                data,
                fast=params.get("fast", 30),
                slow=params.get("slow", 900),
                resist_ratio=params.get("resist_ratio", 7 / 8),
                support_ratio=params.get("support_ratio", 0.5 / 8),
            )
        if name == "capital_trend":
            return fn(data, index_data=params.get("index_data"))
        return fn(data, **params)


# 单例
indicator_service = IndicatorService()
