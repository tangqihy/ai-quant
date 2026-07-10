"""
Hybrid backtest engine v2.

Based on docs/design/05-backtest-engine.md:
- Vectorised signal generation + stateful order matching
- Domain models: Signal → OrderIntent → Order → Trade
- OrderLedger: submit → freeze → fill → settle (cancel / reject)
- Portfolio with lot tracking (PositionLot)
- A-stock rules: T+1, 100-share lots, limit up/down, suspension,
  commission (万2.5 min ¥5) + stamp tax (千1 sell) + transfer fee
- BacktestRunManifest for reproducibility
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ======================================================================
# Domain Models
# ======================================================================


@dataclass
class Signal:
    """Strategy signal – what the strategy *wants* to do.

    Does **not** carry execution results (price, quantity, commission).
    """
    ts_code: str           # stock code
    signal_date: str       # date the signal was generated (T close)
    direction: str         # "buy" or "sell"
    weight: float          # target weight (0~1)
    reason: str = ""       # human-readable reason


@dataclass
class OrderIntent:
    """Order intent – converted from Signal with execution constraints.

    Attributes
    ----------
    ts_code : str
        Stock code.
    direction : str
        "buy" or "sell".
    target_quantity : int
        Desired quantity (shares).
    price_limit : float | None
        Limit price (None = market).
    execute_date : str
        Execution date (typically T+1).
    source_signal : Signal
        The originating signal.
    """
    ts_code: str
    direction: str
    target_quantity: int
    price_limit: Optional[float] = None
    execute_date: str = ""
    source_signal: Optional[Signal] = None


@dataclass
class Order:
    """Order – submitted to the matching engine.

    State machine: pending → submitted → filled / cancelled / rejected
    """
    order_id: str
    ts_code: str
    direction: str
    price: float               # commission price
    quantity: int              # commission quantity
    order_type: str            # "limit" / "market"
    status: str                # "pending" / "submitted" / "filled" / "cancelled" / "rejected"

    # fund states
    frozen_amount: float = 0.0
    frozen_quantity: int = 0

    # timestamps
    created_at: str = ""
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None

    # provenance
    source_intent: Optional[OrderIntent] = None
    execute_date: str = ""
    reject_reason: str = ""

    def fill(self, fill_price: float, fill_quantity: int, commission: float) -> None:
        self.status = "filled"
        self.filled_at = datetime.now().isoformat()

    def cancel(self, reason: str = "") -> None:
        self.status = "cancelled"
        self.reject_reason = reason

    def reject(self, reason: str = "") -> None:
        self.status = "rejected"
        self.reject_reason = reason


@dataclass
class Trade:
    """Trade – the result of a filled order."""
    trade_id: str
    order_id: str
    ts_code: str
    direction: str
    price: float
    quantity: int
    amount: float
    commission: float
    trade_date: str = ""
    source_order: Optional[Order] = None


# ======================================================================
# Enumerations
# ======================================================================


class MatchingMode(Enum):
    """Matching mode for limit-price checks."""
    STRICT = "strict"   # 一字涨停不可买 / 一字跌停不可卖
    SIMPLE = "simple"   # open == limit_up/down → blocked


# ======================================================================
# Fee Model – A-stock
# ======================================================================


@dataclass
class FeeModel:
    """A-share fee schedule.

    Defaults (2024+):
    - commission_rate: 0.00025 (万2.5), min ¥5
    - stamp_tax_rate:  0.001 (千1, sell only)
    - transfer_fee_rate: 0.00001 (万0.1, both sides)
    """
    commission_rate: float = 0.00025
    commission_min: float = 5.0
    stamp_tax_rate: float = 0.001
    transfer_fee_rate: float = 0.00001

    def calculate(self, amount: float, direction: str) -> Dict[str, float]:
        """Return fee breakdown dict."""
        commission = max(amount * self.commission_rate, self.commission_min)
        stamp_tax = amount * self.stamp_tax_rate if direction == "sell" else 0.0
        transfer_fee = amount * self.transfer_fee_rate
        total = commission + stamp_tax + transfer_fee
        return {
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "transfer_fee": round(transfer_fee, 2),
            "total": round(total, 2),
        }


# ======================================================================
# Position Lot
# ======================================================================


@dataclass
class PositionLot:
    """A single lot of shares purchased on a specific date."""
    ts_code: str
    acquired_date: str       # buy date (YYYY-MM-DD)
    quantity: int            # original quantity
    remaining_quantity: int  # remaining (after partial sells)
    cost_price: float        # per-share cost


# ======================================================================
# Portfolio
# ======================================================================


class Portfolio:
    """Portfolio with lot-level tracking.

    Supports freeze / unfreeze for order lifecycle.
    """

    def __init__(self) -> None:
        # ts_code → list of PositionLot
        self.lots: Dict[str, List[PositionLot]] = {}

    # --- T+1 update ---

    def update_sellable(self, current_date: str) -> None:
        """Mark lots acquired before *current_date* as sellable (T+1 unlock).

        In practice, lots acquired on dates < current_date are already
        sellable; lots acquired *on* current_date are not.  The check
        happens in :meth:`get_sellable_quantity`.
        """
        pass  # remaining_quantity already tracks state

    # --- Buy / Sell ---

    def buy(self, ts_code: str, price: float, quantity: int, date: str) -> None:
        lot = PositionLot(
            ts_code=ts_code,
            acquired_date=date,
            quantity=quantity,
            remaining_quantity=quantity,
            cost_price=price,
        )
        self.lots.setdefault(ts_code, []).append(lot)

    def sell(self, ts_code: str, quantity: int) -> None:
        lots = self.lots.get(ts_code, [])
        remaining = quantity
        for lot in lots:
            if lot.remaining_quantity <= 0:
                continue
            sell_qty = min(remaining, lot.remaining_quantity)
            lot.remaining_quantity -= sell_qty
            remaining -= sell_qty
            if remaining <= 0:
                break
        # clean up empty lots
        self.lots[ts_code] = [l for l in lots if l.remaining_quantity > 0]

    # --- Quantity queries ---

    def get_total_quantity(self, ts_code: str) -> int:
        return sum(l.quantity for l in self.lots.get(ts_code, []))

    def get_remaining_quantity(self, ts_code: str) -> int:
        return sum(l.remaining_quantity for l in self.lots.get(ts_code, []))

    def get_sellable_quantity(self, ts_code: str, current_date: str) -> int:
        """Lots acquired **before** current_date are sellable (T+1 rule)."""
        return sum(
            l.remaining_quantity
            for l in self.lots.get(ts_code, [])
            if l.acquired_date < current_date
        )

    # --- Freeze / Unfreeze ---

    def freeze(self, ts_code: str, quantity: int) -> None:
        remaining = quantity
        for lot in self.lots.get(ts_code, []):
            freeze_qty = min(remaining, lot.remaining_quantity)
            lot.remaining_quantity -= freeze_qty
            remaining -= freeze_qty
            if remaining <= 0:
                break

    def unfreeze(self, ts_code: str, quantity: int) -> None:
        remaining = quantity
        for lot in reversed(self.lots.get(ts_code, [])):
            unfreeze_qty = min(remaining, lot.quantity - lot.remaining_quantity)
            lot.remaining_quantity += unfreeze_qty
            remaining -= unfreeze_qty
            if remaining <= 0:
                break

    # --- Market value ---

    def get_market_value(self, prices: Dict[str, float]) -> float:
        total = 0.0
        for ts_code, lots in self.lots.items():
            price = prices.get(ts_code, 0.0)
            total += sum(l.remaining_quantity * price for l in lots)
        return total


# ======================================================================
# Cash Account
# ======================================================================


class CashAccount:
    """Simple cash account with freeze/unfreeze."""

    def __init__(self, initial_cash: float) -> None:
        self.cash: float = initial_cash
        self.frozen: float = 0.0

    @property
    def available(self) -> float:
        return self.cash - self.frozen

    def freeze(self, amount: float) -> None:
        self.frozen += amount

    def unfreeze(self, amount: float) -> None:
        self.frozen = max(0.0, self.frozen - amount)

    def withdraw(self, amount: float) -> None:
        self.cash -= amount

    def deposit(self, amount: float) -> None:
        self.cash += amount


# ======================================================================
# Order Ledger
# ======================================================================


class OrderLedger:
    """Full order lifecycle manager.

    submit → freeze → fill → settle  (or cancel / reject at any stage)
    """

    def __init__(
        self,
        account: CashAccount,
        portfolio: Portfolio,
        fee_model: FeeModel,
        matching_mode: MatchingMode = MatchingMode.STRICT,
        participation_rate: float = 0.02,
    ) -> None:
        self.account = account
        self.portfolio = portfolio
        self.fee_model = fee_model
        self.matching_mode = matching_mode
        self.participation_rate = participation_rate
        self.orders: List[Order] = []
        self.trades: List[Trade] = []

    # --- Public API ---

    def submit(self, intent: OrderIntent, bar_data: dict) -> Order:
        """Validate, price, freeze, and create an Order.

        *bar_data* is the daily bar dict for the stock on *execute_date*.
        Keys: open, high, low, close, vol, limit_up, limit_down, suspended, name.
        """
        now_iso = datetime.now().isoformat()

        # 1. Tradable check
        tradable, reason = self._is_tradable(bar_data, intent.direction)
        if not tradable:
            return self._make_rejected(intent, reason, now_iso)

        # 2. Determine execution price (open price for market orders)
        price = bar_data.get("open", 0.0)
        if price <= 0:
            return self._make_rejected(intent, "无效开盘价", now_iso)

        # 3. Determine quantity
        quantity = self._determine_quantity(intent, price, bar_data)
        if quantity <= 0:
            return self._make_rejected(intent, "数量不足", now_iso)

        # 4. Freeze funds / shares
        frozen_amount = 0.0
        frozen_quantity = 0
        if intent.direction == "buy":
            fees = self.fee_model.calculate(price * quantity, "buy")
            frozen_amount = price * quantity + fees["total"]
            if self.account.available < frozen_amount:
                return self._make_rejected(intent, "资金不足", now_iso)
            self.account.freeze(frozen_amount)
        else:
            sellable = self.portfolio.get_sellable_quantity(intent.ts_code, intent.execute_date)
            if sellable < quantity:
                return self._make_rejected(intent, f"可卖不足(可卖{sellable})", now_iso)
            self.portfolio.freeze(intent.ts_code, quantity)
            frozen_quantity = quantity

        # 5. Create Order
        order = Order(
            order_id=str(uuid.uuid4()),
            ts_code=intent.ts_code,
            direction=intent.direction,
            price=price,
            quantity=quantity,
            order_type="market",
            status="submitted",
            frozen_amount=frozen_amount,
            frozen_quantity=frozen_quantity,
            created_at=now_iso,
            submitted_at=now_iso,
            source_intent=intent,
            execute_date=intent.execute_date,
        )
        self.orders.append(order)

        # 6. Immediate fill (we assume open-price execution)
        self._fill(order, price, quantity, intent.execute_date)

        return order

    def cancel(self, order: Order, reason: str = "") -> None:
        if order.status not in ("pending", "submitted"):
            return
        if order.direction == "buy":
            self.account.unfreeze(order.frozen_amount)
        else:
            self.portfolio.unfreeze(order.ts_code, order.frozen_quantity)
        order.cancel(reason)

    # --- Internal ---

    def _fill(self, order: Order, fill_price: float, fill_quantity: int, trade_date: str) -> Trade:
        amount = fill_price * fill_quantity
        fees = self.fee_model.calculate(amount, order.direction)

        if order.direction == "buy":
            self.account.unfreeze(order.frozen_amount)
            self.account.withdraw(amount + fees["total"])
            self.portfolio.buy(order.ts_code, fill_price, fill_quantity, trade_date)
        else:
            self.portfolio.unfreeze(order.ts_code, order.frozen_quantity)
            self.portfolio.sell(order.ts_code, fill_quantity)
            self.account.deposit(amount - fees["total"])

        order.fill(fill_price, fill_quantity, fees["total"])

        trade = Trade(
            trade_id=str(uuid.uuid4()),
            order_id=order.order_id,
            ts_code=order.ts_code,
            direction=order.direction,
            price=fill_price,
            quantity=fill_quantity,
            amount=amount,
            commission=fees["total"],
            trade_date=trade_date,
            source_order=order,
        )
        self.trades.append(trade)
        return trade

    def _make_rejected(self, intent: OrderIntent, reason: str, now_iso: str) -> Order:
        order = Order(
            order_id=str(uuid.uuid4()),
            ts_code=intent.ts_code,
            direction=intent.direction,
            price=0.0,
            quantity=0,
            order_type="market",
            status="rejected",
            created_at=now_iso,
            source_intent=intent,
            execute_date=intent.execute_date,
            reject_reason=reason,
        )
        self.orders.append(order)
        return order

    def _is_tradable(self, bar_data: dict, direction: str) -> Tuple[bool, str]:
        if bar_data.get("suspended", False):
            return False, "停牌"
        if bar_data.get("open", 0.0) <= 0:
            return False, "无行情数据"

        limit_up = bar_data.get("limit_up", 0.0)
        limit_down = bar_data.get("limit_down", 0.0)
        o = bar_data.get("open", 0.0)
        h = bar_data.get("high", 0.0)
        lo = bar_data.get("low", 0.0)

        if direction == "buy":
            if self.matching_mode == MatchingMode.STRICT:
                if limit_up > 0 and o == h == lo == limit_up:
                    return False, "一字涨停"
            else:  # SIMPLE
                if limit_up > 0 and o >= limit_up:
                    return False, "开盘涨停"
        elif direction == "sell":
            if self.matching_mode == MatchingMode.STRICT:
                if limit_down > 0 and o == h == lo == limit_down:
                    return False, "一字跌停"
            else:
                if limit_down > 0 and o <= limit_down:
                    return False, "开盘跌停"

        return True, "可交易"

    def _determine_quantity(
        self,
        intent: OrderIntent,
        price: float,
        bar_data: dict,
    ) -> int:
        """Round to 100-share lots and apply volume constraint."""
        target = intent.target_quantity

        if intent.direction == "buy":
            # volume constraint
            day_volume_shares = bar_data.get("vol", 0) * 100  # Tushare vol in 手 → 股
            max_qty = int(day_volume_shares * self.participation_rate)
            max_qty = (max_qty // 100) * 100

            # cash constraint
            fees_est = self.fee_model.calculate(price * target, "buy")
            max_affordable = int(self.account.available / (price + fees_est["total"] / target)) if target > 0 else 0
            max_affordable = (max_affordable // 100) * 100

            target = min(target, max_qty, max_affordable)
        else:
            sellable = self.portfolio.get_sellable_quantity(intent.ts_code, intent.execute_date)
            target = min(target, sellable)

        # round down to 100
        return (target // 100) * 100


# ======================================================================
# Backtest Run Manifest
# ======================================================================


@dataclass
class BacktestRunManifest:
    """Metadata for a backtest run – reproducibility."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = ""
    strategy_version: str = ""
    parameters: dict = field(default_factory=dict)

    start_date: str = ""
    end_date: str = ""

    universe_definition: str = ""
    dataset_version: str = ""
    data_cutoff: str = ""

    adjustment_mode: str = "qfq"
    broker_model: str = "strict"
    fee_model: dict = field(default_factory=dict)

    code_commit: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # results (filled after run)
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


# ======================================================================
# Performance Metrics
# ======================================================================


def calculate_sharpe(returns: pd.Series, risk_free_rate: float = 0.03, periods: int = 252) -> float:
    """Annualised Sharpe ratio."""
    if returns.std() == 0:
        return 0.0
    excess = returns - risk_free_rate / periods
    return float(excess.mean() / excess.std() * np.sqrt(periods))


def calculate_sortino(returns: pd.Series, risk_free_rate: float = 0.03, periods: int = 252) -> float:
    """Annualised Sortino ratio (downside deviation only)."""
    excess = returns - risk_free_rate / periods
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(periods))


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown as a positive fraction."""
    cummax = equity_curve.cummax()
    drawdowns = (equity_curve - cummax) / cummax
    return float(abs(drawdowns.min())) if len(drawdowns) > 0 else 0.0


def calculate_win_rate(trades: List[Trade]) -> float:
    """Fraction of sell trades that are profitable.

    Pairs each sell trade with its corresponding buy cost.
    """
    from collections import defaultdict
    buys: Dict[str, list] = defaultdict(list)  # ts_code → [(price, qty)]
    wins = 0
    total = 0

    for t in trades:
        if t.direction == "buy":
            buys[t.ts_code].append([t.price, t.quantity])
        elif t.direction == "sell":
            remaining = t.quantity
            cost_sum = 0.0
            while remaining > 0 and buys.get(t.ts_code):
                lot_price, lot_qty = buys[t.ts_code][0]
                take = min(remaining, lot_qty)
                cost_sum += lot_price * take
                buys[t.ts_code][0][1] -= take
                remaining -= take
                if buys[t.ts_code][0][1] <= 0:
                    buys[t.ts_code].pop(0)
            avg_cost = cost_sum / t.quantity if t.quantity > 0 else 0
            total += 1
            if t.price > avg_cost:
                wins += 1

    return wins / total if total > 0 else 0.0


# ======================================================================
# Backtest Result
# ======================================================================


@dataclass
class BacktestResult:
    """Aggregated backtest results."""
    manifest: BacktestRunManifest
    trades: List[Trade]
    equity_curve: pd.DataFrame          # columns: date, equity
    daily_returns: pd.Series
    metrics: dict = field(default_factory=dict)


# ======================================================================
# BacktestEngine V2 – Hybrid Architecture
# ======================================================================


class BacktestEngineV2:
    """Hybrid backtest engine: vectorised signals + stateful matching.

    Usage::

        engine = BacktestEngineV2(pit=pit_query, initial_cash=1_000_000)
        result = engine.run(
            signal_fn=my_signal_function,
            start_date="20230101",
            end_date="20260630",
            strategy_name="small_cap_value",
        )
    """

    def __init__(
        self,
        pit,
        initial_cash: float = 1_000_000.0,
        matching_mode: MatchingMode = MatchingMode.STRICT,
        fee_model: Optional[FeeModel] = None,
        participation_rate: float = 0.02,
    ) -> None:
        self.pit = pit
        self.initial_cash = initial_cash
        self.matching_mode = matching_mode
        self.fee_model = fee_model or FeeModel()
        self.participation_rate = participation_rate

    def run(
        self,
        signal_fn: Callable[[str, "PITQuery"], pd.DataFrame],
        start_date: str,
        end_date: str,
        strategy_name: str = "",
        strategy_version: str = "",
        parameters: Optional[dict] = None,
    ) -> BacktestResult:
        """Run a full backtest.

        Parameters
        ----------
        signal_fn : callable
            ``(date: str, pit: PITQuery) -> pd.DataFrame``
            Must return DataFrame with columns: ts_code, direction, weight.
        start_date / end_date : str
            YYYYMMDD or YYYY-MM-DD.
        """
        # --- Manifest ---
        manifest = BacktestRunManifest(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            parameters=parameters or {},
            start_date=_norm_date(start_date),
            end_date=_norm_date(end_date),
            broker_model=self.matching_mode.value,
            fee_model={
                "commission_rate": self.fee_model.commission_rate,
                "commission_min": self.fee_model.commission_min,
                "stamp_tax_rate": self.fee_model.stamp_tax_rate,
                "transfer_fee_rate": self.fee_model.transfer_fee_rate,
            },
        )

        # --- State ---
        account = CashAccount(self.initial_cash)
        portfolio = Portfolio()
        ledger = OrderLedger(
            account=account,
            portfolio=portfolio,
            fee_model=self.fee_model,
            matching_mode=self.matching_mode,
            participation_rate=self.participation_rate,
        )

        # --- Trading days ---
        trading_days = self._get_trading_days(start_date, end_date)
        if not trading_days:
            logger.warning("No trading days found between %s and %s", start_date, end_date)
            return BacktestResult(
                manifest=manifest,
                trades=[],
                equity_curve=pd.DataFrame(columns=["date", "equity"]),
                daily_returns=pd.Series(dtype=float),
            )

        equity_records: List[dict] = []

        for idx, date in enumerate(trading_days):
            # 1. Update T+1 sellable
            portfolio.update_sellable(date)

            # 2. Vectorised signal generation
            try:
                signals_df = signal_fn(date, self.pit)
            except Exception:
                logger.debug("signal_fn failed on %s", date, exc_info=True)
                signals_df = pd.DataFrame()

            # 3. Process sell signals first (free up cash)
            if len(signals_df) > 0:
                sell_signals = signals_df[signals_df["direction"] == "sell"]
                buy_signals = signals_df[signals_df["direction"] == "buy"]

                for _, row in sell_signals.iterrows():
                    self._process_signal(row, date, account, portfolio, ledger)

                for _, row in buy_signals.iterrows():
                    self._process_signal(row, date, account, portfolio, ledger)

            # 4. Record equity
            prices = self._get_close_prices(date)
            mv = portfolio.get_market_value(prices)
            total_equity = account.cash + mv
            equity_records.append({"date": date, "equity": total_equity})

        # --- Metrics (vectorised) ---
        eq_df = pd.DataFrame(equity_records)
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.set_index("date")

        daily_ret = eq_df["equity"].pct_change().dropna()

        metrics = {
            "total_return": (eq_df["equity"].iloc[-1] / self.initial_cash - 1) if len(eq_df) else 0.0,
            "annual_return": 0.0,
            "max_drawdown": calculate_max_drawdown(eq_df["equity"]),
            "sharpe": calculate_sharpe(daily_ret) if len(daily_ret) > 0 else 0.0,
            "sortino": calculate_sortino(daily_ret) if len(daily_ret) > 0 else 0.0,
            "win_rate": calculate_win_rate(ledger.trades),
            "trade_count": len(ledger.trades),
            "final_equity": eq_df["equity"].iloc[-1] if len(eq_df) else self.initial_cash,
        }

        if len(eq_df) > 1:
            days = (eq_df.index[-1] - eq_df.index[0]).days
            if days > 0:
                metrics["annual_return"] = (1 + metrics["total_return"]) ** (365.0 / days) - 1

        manifest.total_return = metrics["total_return"]
        manifest.annual_return = metrics["annual_return"]
        manifest.max_drawdown = metrics["max_drawdown"]
        manifest.sharpe_ratio = metrics["sharpe"]

        return BacktestResult(
            manifest=manifest,
            trades=ledger.trades,
            equity_curve=eq_df.reset_index(),
            daily_returns=daily_ret,
            metrics=metrics,
        )

    # --- Helpers ---

    def _process_signal(
        self,
        row: pd.Series,
        date: str,
        account: CashAccount,
        portfolio: Portfolio,
        ledger: OrderLedger,
    ) -> Optional[Order]:
        ts_code = row["ts_code"]
        direction = row["direction"]
        weight = float(row.get("weight", 0.0))

        # Compute target quantity from weight
        prices = self._get_close_prices(date)
        price = prices.get(ts_code, 0.0)
        if price <= 0:
            return None

        total_equity = account.cash + portfolio.get_market_value(prices)
        target_value = total_equity * weight

        if direction == "sell":
            # sell all or weight-proportion
            sellable = portfolio.get_sellable_quantity(ts_code, date)
            if weight >= 1.0:
                target_qty = sellable
            else:
                target_qty = int(target_value / price)
                target_qty = min(target_qty, sellable)
        else:
            target_qty = int(target_value / price)

        target_qty = (target_qty // 100) * 100
        if target_qty <= 0:
            return None

        signal = Signal(
            ts_code=ts_code,
            signal_date=date,
            direction=direction,
            weight=weight,
        )
        intent = OrderIntent(
            ts_code=ts_code,
            direction=direction,
            target_quantity=target_qty,
            execute_date=date,
            source_signal=signal,
        )

        bar_data = self._get_bar_data(ts_code, date)
        if not bar_data:
            return None

        return ledger.submit(intent, bar_data)

    def _get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        try:
            dates = self.pit.client.get_trade_dates(start_date, end_date)
            return [_norm_date(d) for d in dates]
        except Exception:
            logger.debug("get_trade_dates failed", exc_info=True)
            return []

    def _get_close_prices(self, date: str) -> Dict[str, float]:
        """Get close prices for all stocks on *date*."""
        try:
            self.pit.client._ensure_view("daily")
            df = self.pit.client.query(
                f"SELECT ts_code, close FROM daily WHERE trade_date = '{_norm_date(date)}'"
            )
            if len(df) == 0:
                return {}
            return dict(zip(df["ts_code"], df["close"]))
        except Exception:
            return {}

    def _get_bar_data(self, ts_code: str, date: str) -> dict:
        """Get full bar data for a single stock on *date*."""
        try:
            self.pit.client._ensure_view("daily")
            df = self.pit.client.query(
                f"""
                SELECT ts_code, open, high, low, close, vol
                FROM daily
                WHERE ts_code = ? AND trade_date = ?
                """,
                [ts_code, _norm_date(date)],
            )
            if df.empty:
                return {}

            row = df.iloc[0].to_dict()

            # Determine limit prices
            limit_up, limit_down = self._calc_limit_prices(row.get("close", 0.0), ts_code)

            row["limit_up"] = limit_up
            row["limit_down"] = limit_down
            row["suspended"] = False  # if bar exists, not suspended

            return row
        except Exception:
            return {}

    def _calc_limit_prices(self, prev_close: float, ts_code: str) -> Tuple[float, float]:
        """Estimate limit-up/down based on prev_close and board type."""
        if prev_close <= 0:
            return 0.0, 0.0

        # Determine limit percentage
        if ts_code.startswith("30") or ts_code.startswith("68"):
            pct = 0.20  # 创业板 / 科创板
        elif ts_code.startswith("8"):
            pct = 0.30  # 北交所
        else:
            pct = 0.10  # 主板

        # Round to 0.01
        limit_up = round(prev_close * (1 + pct), 2)
        limit_down = round(prev_close * (1 - pct), 2)

        return limit_up, limit_down


# ======================================================================
# Helpers
# ======================================================================


def _norm_date(d: str) -> str:
    """YYYYMMDD → YYYY-MM-DD."""
    s = str(d).replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return str(d)
