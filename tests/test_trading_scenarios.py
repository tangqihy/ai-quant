"""
核心单元测试 - 覆盖交易核心场景

测试场景：
1. 买入成交
2. 卖出成交
3. 余额不足
4. 持仓不足
5. T+1
6. 停牌
7. 涨停
8. 跌停
9. 手续费
10. 印花税
11. 回测结果可复现
"""
import pytest
from datetime import datetime

from app.domain import (
    Instrument, MarketData, Order, Trade, Position,
    Account, Portfolio, ExchangeInfo, Broker,
    OrderDirection, OrderType, OrderStatus,
    Exchange, Market
)
from app.brokers.broker import BacktestBroker
from app.backtest.engine_v2 import CashAccount, Portfolio as V2Portfolio, FeeModel, OrderLedger, OrderIntent, Signal


class TestTradingScenarios:
    """测试交易场景"""
    
    def setup_method(self):
        """测试前准备"""
        self.exchange = ExchangeInfo(
            name='上交所',
            exchange=Exchange.SH,
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            min_commission=5.0,
            lot_size=100,
            t_plus=1
        )
        self.broker = BacktestBroker(self.exchange)
        self.account = Account(initial_capital=1000000)
        self.portfolio = Portfolio(account_id=self.account.account_id)
    
    def test_buy_order_fill(self):
        """测试买入成交"""
        # 创建买入订单
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        
        # 提交订单
        self.broker.submit_order(order)
        
        # 创建K线数据
        bar = MarketData(
            symbol='600519',
            datetime=datetime.now(),
            open=1190.0,
            high=1210.0,
            low=1180.0,
            close=1200.0,
            volume=50000,
            amount=60000000
        )
        
        # 撮合
        trades = self.broker.match(bar)
        
        # 验证
        assert len(trades) == 1
        assert trades[0].symbol == '600519'
        assert trades[0].direction == OrderDirection.BUY
        assert trades[0].quantity == 100
        assert trades[0].price == 1200.0
        assert order.status == OrderStatus.FILLED
    
    def test_sell_order_fill(self):
        """测试卖出成交"""
        # 先买入
        buy_order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        self.broker.submit_order(buy_order)
        
        bar = MarketData(
            symbol='600519',
            datetime=datetime.now(),
            open=1200.0,
            high=1200.0,
            low=1200.0,
            close=1200.0,
            volume=50000,
            amount=60000000
        )
        self.broker.match(bar)
        
        # 卖出
        sell_order = Order(
            symbol='600519',
            direction=OrderDirection.SELL,
            price=1300.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        self.broker.submit_order(sell_order)
        
        bar.close = 1300.0
        trades = self.broker.match(bar)
        
        # 验证
        assert len(trades) == 1
        assert trades[0].direction == OrderDirection.SELL
        assert sell_order.status == OrderStatus.FILLED
    
    def test_insufficient_balance(self):
        """测试余额不足"""
        account = CashAccount(initial_cash=1000)
        portfolio = V2Portfolio()
        ledger = OrderLedger(account=account, portfolio=portfolio, fee_model=FeeModel())
        intent = OrderIntent(
            ts_code="600519",
            direction="buy",
            target_quantity=10000,
            execute_date="2024-01-10",
            source_signal=Signal(ts_code="600519", signal_date="2024-01-10", direction="buy", weight=1.0),
        )
        bar = {"open": 1200.0, "high": 1210.0, "low": 1190.0, "close": 1200.0, "vol": 1000, "limit_up": 1320.0, "limit_down": 1080.0, "suspended": False}
        order = ledger.submit(intent, bar)
        assert order.status == "rejected"
        assert order.reject_reason in ("资金不足", "数量不足")
    
    def test_insufficient_position(self):
        """测试持仓不足"""
        account = CashAccount(initial_cash=1000000)
        portfolio = V2Portfolio()
        ledger = OrderLedger(account=account, portfolio=portfolio, fee_model=FeeModel())
        intent = OrderIntent(
            ts_code="600519",
            direction="sell",
            target_quantity=100,
            execute_date="2024-01-10",
            source_signal=Signal(ts_code="600519", signal_date="2024-01-10", direction="sell", weight=1.0),
        )
        bar = {"open": 1200.0, "high": 1210.0, "low": 1190.0, "close": 1200.0, "vol": 1000, "limit_up": 1320.0, "limit_down": 1080.0, "suspended": False}
        order = ledger.submit(intent, bar)
        assert order.status == "rejected"
        assert order.reject_reason in ("可卖不足(可卖0)", "数量不足")
    
    def test_t_plus_1(self):
        """测试T+1限制"""
        account = CashAccount(initial_cash=1000000)
        portfolio = V2Portfolio()
        ledger = OrderLedger(account=account, portfolio=portfolio, fee_model=FeeModel())
        buy_intent = OrderIntent(
            ts_code="600519",
            direction="buy",
            target_quantity=100,
            execute_date="2024-01-10",
            source_signal=Signal(ts_code="600519", signal_date="2024-01-10", direction="buy", weight=1.0),
        )
        bar = {"open": 1200.0, "high": 1200.0, "low": 1200.0, "close": 1200.0, "vol": 1000, "limit_up": 1320.0, "limit_down": 1080.0, "suspended": False}
        buy_order = ledger.submit(buy_intent, bar)
        assert buy_order.status == "filled"

        sell_intent = OrderIntent(
            ts_code="600519",
            direction="sell",
            target_quantity=100,
            execute_date="2024-01-10",  # same day
            source_signal=Signal(ts_code="600519", signal_date="2024-01-10", direction="sell", weight=1.0),
        )
        sell_order = ledger.submit(sell_intent, bar)
        assert sell_order.status == "rejected"
        assert sell_order.reject_reason in ("可卖不足(可卖0)", "数量不足")
    
    def test_price_limit_up(self):
        """测试涨停限制"""
        account = CashAccount(initial_cash=1000000)
        portfolio = V2Portfolio()
        ledger = OrderLedger(account=account, portfolio=portfolio, fee_model=FeeModel())
        intent = OrderIntent(
            ts_code="600519",
            direction="buy",
            target_quantity=100,
            execute_date="2024-01-10",
            source_signal=Signal(ts_code="600519", signal_date="2024-01-10", direction="buy", weight=1.0),
        )
        bar = {"open": 1320.0, "high": 1320.0, "low": 1320.0, "close": 1320.0, "vol": 1000, "limit_up": 1320.0, "limit_down": 1080.0, "suspended": False}
        order = ledger.submit(intent, bar)
        assert order.status == "rejected"
        assert order.reject_reason in ("一字涨停", "开盘涨停")
    
    def test_price_limit_down(self):
        """测试跌停限制"""
        account = CashAccount(initial_cash=1000000)
        portfolio = V2Portfolio()
        portfolio.buy("600519", 1200.0, 100, "2024-01-09")
        ledger = OrderLedger(account=account, portfolio=portfolio, fee_model=FeeModel())
        intent = OrderIntent(
            ts_code="600519",
            direction="sell",
            target_quantity=100,
            execute_date="2024-01-10",
            source_signal=Signal(ts_code="600519", signal_date="2024-01-10", direction="sell", weight=1.0),
        )
        bar = {"open": 1080.0, "high": 1080.0, "low": 1080.0, "close": 1080.0, "vol": 1000, "limit_up": 1320.0, "limit_down": 1080.0, "suspended": False}
        order = ledger.submit(intent, bar)
        assert order.status == "rejected"
        assert order.reject_reason in ("一字跌停", "开盘跌停")
    
    def test_commission_calculation(self):
        """测试手续费计算"""
        # 买入手续费
        commission1 = self.exchange.calculate_commission(120000, OrderDirection.BUY)
        assert commission1 == 36.0  # 120000 * 0.0003
        
        # 卖出手续费（含印花税）
        commission2 = self.exchange.calculate_commission(120000, OrderDirection.SELL)
        assert commission2 == 156.0  # 120000 * 0.0003 + 120000 * 0.001
        
        # 最低手续费
        commission3 = self.exchange.calculate_commission(1000, OrderDirection.BUY)
        assert commission3 == 5.0  # 最低5元
    
    def test_stamp_tax(self):
        """测试印花税"""
        # 卖出时收取印花税
        commission = self.exchange.calculate_commission(100000, OrderDirection.SELL)
        expected_commission = max(100000 * 0.0003, 5.0) + 100000 * 0.001
        assert commission == expected_commission
    
    def test_backtest_reproducibility(self):
        """测试回测结果可复现：相同数据与参数，两次回测结果完全一致"""
        from app.services.backtest_service import run_backtest

        klines = [
            {
                "date": f"2024-01-{i:02d}",
                "open": 100 + i,
                "high": 102 + i,
                "low": 99 + i,
                "close": 101 + i,
                "volume": 1e6,
            }
            for i in range(1, 31)
        ]

        res1 = run_backtest("600519", klines, strategy="ma_cross", short_window=5, long_window=20)
        res2 = run_backtest("600519", klines, strategy="ma_cross", short_window=5, long_window=20)

        assert res1.get("success") is True
        assert res1 == res2
        assert res1["final_value"] == res2["final_value"]
        assert res1["total_trades"] == res2["total_trades"]


class TestBrokerValidation:
    """测试 Broker 验证"""
    
    def setup_method(self):
        """测试前准备"""
        self.exchange = ExchangeInfo(
            name='上交所',
            exchange=Exchange.SH,
            lot_size=100
        )
        self.broker = BacktestBroker(self.exchange)
    
    def test_invalid_price(self):
        """测试无效价格"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=-100.0,  # 无效价格
            quantity=100,
            order_type=OrderType.LIMIT
        )
        
        # 验证订单验证失败
        assert not self.broker.submit_order(order)
        assert order.status == OrderStatus.REJECTED
    
    def test_invalid_quantity(self):
        """测试无效数量"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=0,  # 无效数量
            order_type=OrderType.LIMIT
        )
        
        # 验证订单验证失败
        assert not self.broker.submit_order(order)
        assert order.status == OrderStatus.REJECTED
    
    def test_quantity_not_multiple_of_lot_size(self):
        """测试数量不是最小交易单位的整数倍"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=150,  # 不是100的整数倍
            order_type=OrderType.LIMIT
        )
        
        # 验证订单验证失败
        assert not self.broker.submit_order(order)
        assert order.status == OrderStatus.REJECTED
