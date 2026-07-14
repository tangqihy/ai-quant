"""
Backtest v2 service based on engine_v2 order ledger.

This service keeps API compatibility with the old backtest response while
using v2 execution rules (T+1, lot size, price-limit checks, fee model).
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from app.backtest.engine_v2 import (
    CashAccount,
    FeeModel,
    MatchingMode,
    OrderIntent,
    OrderLedger,
    Portfolio,
    Signal,
    calculate_max_drawdown,
    calculate_sharpe,
)
from app.strategies import get_strategy


def _calc_limit_prices(price: float, symbol: str) -> tuple[float, float]:
    if price <= 0:
        return 0.0, 0.0
    if symbol.startswith("30") or symbol.startswith("68"):
        pct = 0.20
    elif symbol.startswith("8"):
        pct = 0.30
    else:
        pct = 0.10
    return round(price * (1 + pct), 2), round(price * (1 - pct), 2)


def _to_trades_payload(ledger: OrderLedger) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for trade in ledger.trades:
        payload.append(
            {
                "date": trade.trade_date,
                "action": "BUY" if trade.direction == "buy" else "SELL",
                "price": round(trade.price, 2),
                "shares": int(trade.quantity),
                "cost": round(trade.amount + trade.commission, 2)
                if trade.direction == "buy"
                else None,
                "proceeds": round(trade.amount - trade.commission, 2)
                if trade.direction == "sell"
                else None,
            }
        )
    return payload


def run_backtest_v2(
    symbol: str,
    data: List[Dict[str, Any]],
    strategy: str = "ma_cross",
    short_window: int = 5,
    long_window: int = 20,
    initial_capital: float = 1_000_000,
    **strategy_params: Any,
) -> Dict[str, Any]:
    if not data:
        return {"error": "No data provided"}

    strategy_obj = get_strategy(strategy)
    if strategy_obj is None:
        return {"error": f"Unknown strategy: {strategy}"}

    df = pd.DataFrame(data).sort_values("date").reset_index(drop=True)
    if len(df) < 2:
        return {"error": "数据不足"}

    params = dict(strategy_params)
    params.setdefault("short_window", short_window)
    params.setdefault("long_window", long_window)
    df = strategy_obj.generate_signals(df, **params)
    df["buy_signal"] = df.get("buy_signal", False).fillna(False)
    df["sell_signal"] = df.get("sell_signal", False).fillna(False)

    account = CashAccount(initial_capital)
    portfolio = Portfolio()
    ledger = OrderLedger(
        account=account,
        portfolio=portfolio,
        fee_model=FeeModel(),
        matching_mode=MatchingMode.STRICT,
        participation_rate=0.2,
    )

    equity_records: List[Dict[str, Any]] = []
    prev_close = float(df.iloc[0]["close"] or 0)

    for _, row in df.iterrows():
        trade_date = str(row["date"])
        open_p = float(row.get("open", row.get("close", 0)) or 0)
        high_p = float(row.get("high", open_p) or open_p)
        low_p = float(row.get("low", open_p) or open_p)
        close_p = float(row.get("close", open_p) or open_p)
        vol_hands = float(row.get("volume", 0) or 0)
        limit_up, limit_down = _calc_limit_prices(prev_close or close_p, symbol)

        bar_data = {
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "vol": vol_hands,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "suspended": False,
        }

        sellable = portfolio.get_sellable_quantity(symbol, trade_date)
        if bool(row["sell_signal"]) and sellable > 0:
            intent = OrderIntent(
                ts_code=symbol,
                direction="sell",
                target_quantity=sellable,
                execute_date=trade_date,
                source_signal=Signal(
                    ts_code=symbol,
                    signal_date=trade_date,
                    direction="sell",
                    weight=1.0,
                ),
            )
            ledger.submit(intent, bar_data)

        if bool(row["buy_signal"]) and close_p > 0:
            target_qty = int(account.available * 0.95 / close_p)
            target_qty = (target_qty // 100) * 100
            if target_qty > 0:
                intent = OrderIntent(
                    ts_code=symbol,
                    direction="buy",
                    target_quantity=target_qty,
                    execute_date=trade_date,
                    source_signal=Signal(
                        ts_code=symbol,
                        signal_date=trade_date,
                        direction="buy",
                        weight=1.0,
                    ),
                )
                ledger.submit(intent, bar_data)

        remaining_qty = portfolio.get_remaining_quantity(symbol)
        total_equity = account.cash + remaining_qty * close_p
        equity_records.append(
            {
                "date": trade_date,
                "value": round(total_equity, 2),
                "capital": round(account.cash, 2),
                "position_value": round(remaining_qty * close_p, 2),
            }
        )
        prev_close = close_p

    eq_df = pd.DataFrame(equity_records)
    if eq_df.empty:
        return {"error": "回测失败：未产生净值曲线"}

    daily_returns = eq_df["value"].pct_change().dropna()
    final_value = float(eq_df.iloc[-1]["value"])
    total_return_pct = (final_value - initial_capital) / initial_capital * 100
    max_drawdown_pct = calculate_max_drawdown(eq_df["value"]) * 100
    sharpe = calculate_sharpe(daily_returns) if len(daily_returns) > 0 else 0.0

    try:
        start_ts = pd.to_datetime(eq_df.iloc[0]["date"])
        end_ts = pd.to_datetime(eq_df.iloc[-1]["date"])
        days = max((end_ts - start_ts).days, 1)
        annual_return_pct = ((1 + total_return_pct / 100) ** (365.0 / days) - 1) * 100
    except Exception:
        annual_return_pct = 0.0

    trades_payload = _to_trades_payload(ledger)
    sell_trades = [t for t in trades_payload if t["action"] == "SELL"]
    win_count = 0
    for t in sell_trades:
        proceeds = t.get("proceeds") or 0
        # Very lightweight approximation: profitable if proceeds > 0.
        if proceeds > 0:
            win_count += 1
    win_rate = (win_count / len(sell_trades) * 100) if sell_trades else 0.0

    return {
        "success": True,
        "engine": "v2",
        "symbol": symbol,
        "strategy": strategy,
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),
        "total_return": round(total_return_pct, 2),
        "annual_return": round(annual_return_pct, 2),
        "max_drawdown": round(max_drawdown_pct, 2),
        "sharpe": round(float(sharpe), 4),
        "total_trades": len(trades_payload),
        "trades": trades_payload[-200:],
        "daily_values": equity_records[-500:],
        "win_rate": round(win_rate, 2),
    }
