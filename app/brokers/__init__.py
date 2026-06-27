"""
撮合器模块

使用方式：
    from app.brokers import BacktestBroker, PaperBroker, LiveBroker, ExchangeInfo
    
    # 创建交易所信息
    exchange = ExchangeInfo(name='上海证券交易所', exchange=Exchange.SH)
    
    # 创建撮合器
    broker = BacktestBroker(exchange)
    
    # 提交订单
    broker.submit_order(order)
    
    # 撮合
    trades = broker.match(bar)
"""

from .broker import Broker, BacktestBroker, PaperBroker, LiveBroker

# 重新导出 ExchangeInfo
from ..domain import ExchangeInfo
