"""
领域模型单元测试
"""
import pytest
from datetime import datetime

from app.domain import (
    Instrument, MarketData, Order, Trade, Position,
    Account, Portfolio, RiskRule, ExchangeInfo, Strategy,
    OrderDirection, OrderType, OrderStatus, RiskRuleType,
    Exchange, Market, Frequency
)


class TestInstrument:
    """测试 Instrument"""
    
    def test_create_instrument(self):
        """测试创建股票"""
        instrument = Instrument(
            symbol='600519',
            name='贵州茅台',
            exchange=Exchange.SH,
            market=Market.MAIN,
            industry='白酒'
        )
        
        assert instrument.symbol == '600519'
        assert instrument.name == '贵州茅台'
        assert instrument.exchange == Exchange.SH
        assert instrument.market == Market.MAIN
        assert instrument.industry == '白酒'
    
    def test_ts_code(self):
        """测试Tushare代码"""
        instrument = Instrument(
            symbol='600519',
            name='贵州茅台',
            exchange=Exchange.SH,
            market=Market.MAIN
        )
        
        assert instrument.ts_code == '600519.SH'
    
    def test_is_st(self):
        """测试ST判断"""
        # 正常股票
        instrument1 = Instrument(
            symbol='600519',
            name='贵州茅台',
            exchange=Exchange.SH,
            market=Market.MAIN
        )
        assert not instrument1.is_st
        
        # ST股票
        instrument2 = Instrument(
            symbol='000001',
            name='ST平安',
            exchange=Exchange.SZ,
            market=Market.MAIN
        )
        assert instrument2.is_st
        
        # *ST股票
        instrument3 = Instrument(
            symbol='000002',
            name='*ST万科',
            exchange=Exchange.SZ,
            market=Market.MAIN
        )
        assert instrument3.is_st
    
    def test_get_price_limit(self):
        """测试涨跌停限制"""
        # 主板
        instrument1 = Instrument(
            symbol='600519',
            name='贵州茅台',
            exchange=Exchange.SH,
            market=Market.MAIN
        )
        assert instrument1.get_price_limit() == 0.10
        
        # ST股票
        instrument2 = Instrument(
            symbol='000001',
            name='ST平安',
            exchange=Exchange.SZ,
            market=Market.MAIN
        )
        assert instrument2.get_price_limit() == 0.05
        
        # 科创板
        instrument3 = Instrument(
            symbol='688001',
            name='华兴源创',
            exchange=Exchange.SH,
            market=Market.STAR
        )
        assert instrument3.get_price_limit() == 0.20


class TestMarketData:
    """测试 MarketData"""
    
    def test_create_market_data(self):
        """测试创建行情数据"""
        bar = MarketData(
            symbol='600519',
            datetime=datetime.now(),
            open=1200.0,
            high=1250.0,
            low=1180.0,
            close=1220.0,
            volume=50000,
            amount=60000000
        )
        
        assert bar.symbol == '600519'
        assert bar.open == 1200.0
        assert bar.high == 1250.0
        assert bar.low == 1180.0
        assert bar.close == 1220.0
        assert bar.volume == 50000
    
    def test_typical_price(self):
        """测试典型价格"""
        bar = MarketData(
            symbol='600519',
            datetime=datetime.now(),
            open=1200.0,
            high=1250.0,
            low=1180.0,
            close=1220.0,
            volume=50000,
            amount=60000000
        )
        
        expected = (1250.0 + 1180.0 + 1220.0) / 3
        assert abs(bar.typical_price - expected) < 0.01
    
    def test_vwap(self):
        """测试VWAP"""
        bar = MarketData(
            symbol='600519',
            datetime=datetime.now(),
            open=1200.0,
            high=1250.0,
            low=1180.0,
            close=1220.0,
            volume=50000,
            amount=60000000
        )
        
        expected = 60000000 / 50000
        assert abs(bar.vwap - expected) < 0.01


class TestOrder:
    """测试 Order"""
    
    def test_create_order(self):
        """测试创建订单"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        
        assert order.symbol == '600519'
        assert order.direction == OrderDirection.BUY
        assert order.price == 1200.0
        assert order.quantity == 100
        assert order.order_type == OrderType.LIMIT
        assert order.status == OrderStatus.PENDING
    
    def test_fill_order(self):
        """测试订单成交"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        
        order.fill(1200.0, 100, commission=36.0)
        
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 100
        assert order.filled_price == 1200.0
        assert order.commission == 36.0
    
    def test_cancel_order(self):
        """测试撤销订单"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        
        order.cancel()
        
        assert order.status == OrderStatus.CANCELLED
    
    def test_reject_order(self):
        """测试拒绝订单"""
        order = Order(
            symbol='600519',
            direction=OrderDirection.BUY,
            price=1200.0,
            quantity=100,
            order_type=OrderType.LIMIT
        )
        
        order.reject("风控拒绝")
        
        assert order.status == OrderStatus.REJECTED
        assert order.reject_reason == "风控拒绝"


class TestPosition:
    """测试 Position"""
    
    def test_create_position(self):
        """测试创建持仓"""
        position = Position(
            symbol='600519',
            quantity=100,
            available=100,
            cost_price=1200.0
        )
        
        assert position.symbol == '600519'
        assert position.quantity == 100
        assert position.available == 100
        assert position.cost_price == 1200.0
    
    def test_buy_position(self):
        """测试买入持仓"""
        position = Position(symbol='600519')
        position.buy(1200.0, 100)
        
        assert position.quantity == 100
        assert position.available == 100
        assert position.cost_price == 1200.0
    
    def test_sell_position(self):
        """测试卖出持仓"""
        position = Position(symbol='600519')
        position.buy(1200.0, 100)
        
        pnl = position.sell(1300.0, 100)
        
        assert position.quantity == 0
        assert position.available == 0
        assert pnl == 10000.0  # (1300 - 1200) * 100


class TestAccount:
    """测试 Account"""
    
    def test_create_account(self):
        """测试创建账户"""
        account = Account(initial_capital=1000000)
        
        assert account.initial_capital == 1000000
        assert account.cash == 1000000
        assert account.frozen == 0
        assert account.total_value == 1000000
    
    def test_deposit(self):
        """测试入金"""
        account = Account(initial_capital=1000000)
        account.deposit(500000)
        
        assert account.cash == 1500000
    
    def test_withdraw(self):
        """测试出金"""
        account = Account(initial_capital=1000000)
        account.withdraw(500000)
        
        assert account.cash == 500000
    
    def test_freeze(self):
        """测试冻结资金"""
        account = Account(initial_capital=1000000)
        account.freeze(200000)
        
        assert account.cash == 800000
        assert account.frozen == 200000
    
    def test_unfreeze(self):
        """测试解冻资金"""
        account = Account(initial_capital=1000000)
        account.freeze(200000)
        account.unfreeze(200000)
        
        assert account.cash == 1000000
        assert account.frozen == 0


class TestRiskRule:
    """测试 RiskRule"""
    
    def test_position_limit(self):
        """测试仓位限制"""
        rule = RiskRule(
            rule_type=RiskRuleType.POSITION_LIMIT,
            params={'max_ratio': 0.5}
        )
        
        assert rule.check({'position_ratio': 0.3})
        assert not rule.check({'position_ratio': 0.6})
    
    def test_stop_loss(self):
        """测试止损"""
        rule = RiskRule(
            rule_type=RiskRuleType.STOP_LOSS,
            params={'stop_loss': -0.1}
        )
        
        assert rule.check({'pnl_ratio': -0.05})
        assert not rule.check({'pnl_ratio': -0.15})
    
    def test_blacklist(self):
        """测试黑名单"""
        rule = RiskRule(
            rule_type=RiskRuleType.BLACKLIST,
            params={'blacklist': ['000001', '000002']}
        )
        
        assert rule.check({'symbol': '600519'})
        assert not rule.check({'symbol': '000001'})


class TestExchangeInfo:
    """测试 ExchangeInfo"""
    
    def test_calculate_commission(self):
        """测试计算手续费"""
        exchange = ExchangeInfo(
            name='上交所',
            exchange=Exchange.SH,
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            min_commission=5.0
        )
        
        # 买入
        commission1 = exchange.calculate_commission(120000, OrderDirection.BUY)
        assert commission1 == 36.0  # 120000 * 0.0003
        
        # 卖出（含印花税）
        commission2 = exchange.calculate_commission(120000, OrderDirection.SELL)
        assert commission2 == 156.0  # 120000 * 0.0003 + 120000 * 0.001
    
    def test_round_price(self):
        """测试价格取整"""
        exchange = ExchangeInfo(
            name='上交所',
            exchange=Exchange.SH,
            tick_size=0.01
        )
        
        assert exchange.round_price(1200.123) == 1200.12
        assert exchange.round_price(1200.126) == 1200.13
    
    def test_round_quantity(self):
        """测试数量取整"""
        exchange = ExchangeInfo(
            name='上交所',
            exchange=Exchange.SH,
            lot_size=100
        )
        
        assert exchange.round_quantity(150) == 100
        assert exchange.round_quantity(250) == 200
