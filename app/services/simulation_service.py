"""
模拟交易服务
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, field

from app.models.simulation import Order, Trade, Position, Account
from app.services.stock_service import stock_service

logger = logging.getLogger(__name__)


@dataclass
class SimulationState:
    """模拟交易状态（内存存储）"""
    account: Account = field(default_factory=lambda: Account(user_id="default", initial_capital=1000000.0, cash=1000000.0, total_value=1000000.0))
    orders: Dict[str, Order] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    positions: Dict[str, Position] = field(default_factory=dict)


class SimulationService:
    """模拟交易服务"""

    # 手续费率配置
    COMMISSION_RATE = 0.0003  # 佣金 0.03%
    COMMISSION_MIN = 5.0  # 最低佣金 5元
    STAMP_TAX_RATE = 0.001  # 印花税 0.1%（卖出）
    TRANSFER_FEE_RATE = 0.00001  # 过户费 0.001%（沪市）

    def __init__(self):
        self._state = SimulationState()

    def reset_account(self, initial_capital: float = 1000000.0):
        """重置账户"""
        self._state = SimulationState()
        self._state.account = Account(
            user_id="default",
            initial_capital=initial_capital,
            cash=initial_capital,
            total_value=initial_capital
        )
        logger.info(f"Account reset with initial capital: {initial_capital}")

    def get_account(self) -> Account:
        """获取账户信息"""
        self._update_account_value()
        return self._state.account

    def _update_account_value(self):
        """更新账户市值"""
        positions_value = 0.0
        for position in self._state.positions.values():
            # 获取最新价格
            quote = stock_service.get_realtime_quote(position.symbol)
            if quote and quote.get("price", 0) > 0:
                position.market_price = quote["price"]
            position.market_value = position.quantity * position.market_price
            position.unrealized_pnl = position.market_value - position.quantity * position.avg_cost
            if position.avg_cost > 0:
                position.unrealized_pnl_pct = (position.unrealized_pnl / (position.quantity * position.avg_cost)) * 100
            positions_value += position.market_value

        self._state.account.positions_value = positions_value
        self._state.account.total_value = self._state.account.cash + positions_value
        self._state.account.updated_at = datetime.now()

    def create_order(self, symbol: str, action: Literal["BUY", "SELL"],
                     order_type: Literal["LIMIT", "MARKET"],
                     price: Optional[float], quantity: int) -> Order:
        """创建订单"""
        order_id = str(uuid.uuid4())[:8]

        # 风控检查
        rejection_reason = self._check_risk(symbol, action, price, quantity)
        if rejection_reason:
            order = Order(
                id=order_id,
                symbol=symbol,
                action=action,
                order_type=order_type,
                price=price,
                quantity=quantity,
                status="REJECTED",
                rejected_reason=rejection_reason
            )
            self._state.orders[order_id] = order
            logger.warning(f"Order rejected: {rejection_reason}")
            return order

        # 冻结资金（买入时）
        if action == "BUY":
            estimated_cost = self._estimate_cost(action, price, quantity, order_type)
            if self._state.account.cash < estimated_cost:
                order = Order(
                    id=order_id,
                    symbol=symbol,
                    action=action,
                    order_type=order_type,
                    price=price,
                    quantity=quantity,
                    status="REJECTED",
                    rejected_reason="资金不足"
                )
                self._state.orders[order_id] = order
                return order
            self._state.account.frozen_cash += estimated_cost
            self._state.account.cash -= estimated_cost

        # 冻结持仓（卖出时）
        if action == "SELL":
            position = self._state.positions.get(symbol)
            if not position or position.quantity < quantity:
                order = Order(
                    id=order_id,
                    symbol=symbol,
                    action=action,
                    order_type=order_type,
                    price=price,
                    quantity=quantity,
                    status="REJECTED",
                    rejected_reason="持仓不足"
                )
                self._state.orders[order_id] = order
                return order

        order = Order(
            id=order_id,
            symbol=symbol,
            action=action,
            order_type=order_type,
            price=price,
            quantity=quantity,
            status="PENDING"
        )
        self._state.orders[order_id] = order
        logger.info(f"Order created: {order_id} {action} {symbol} {quantity}@{price}")

        # 立即撮合市价单
        if order_type == "MARKET":
            self._match_order(order)

        return order

    def _estimate_cost(self, action: str, price: Optional[float], quantity: int,
                       order_type: str) -> float:
        """预估成本"""
        if order_type == "MARKET":
            # 市价单使用最新价估算
            quote = stock_service.get_realtime_quote("symbol")  # 这里需要传入实际symbol
            price = quote.get("price", 0) if quote else 0

        if not price:
            return float('inf')

        amount = price * quantity
        commission = max(amount * self.COMMISSION_RATE, self.COMMISSION_MIN)
        stamp_tax = amount * self.STAMP_TAX_RATE if action == "SELL" else 0
        transfer_fee = amount * self.TRANSFER_FEE_RATE

        return amount + commission + stamp_tax + transfer_fee

    def _check_risk(self, symbol: str, action: str, price: Optional[float],
                    quantity: int) -> Optional[str]:
        """风控检查，返回拒绝原因或None"""
        # 检查最小交易单位（100股）
        if quantity % 100 != 0:
            return "交易数量必须是100的整数倍"

        # 检查单票仓位上限（50%）
        if action == "BUY":
            position = self._state.positions.get(symbol)
            current_qty = position.quantity if position else 0
            # 简化计算，假设价格为100
            est_price = price or 100
            new_value = (current_qty + quantity) * est_price
            if new_value > self._state.account.total_value * 0.5:
                return "单票仓位不能超过50%"

        return None

    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        order = self._state.orders.get(order_id)
        if not order:
            return False

        if order.status not in ["PENDING", "PARTIAL_FILLED"]:
            return False

        # 解冻资金
        if order.action == "BUY":
            unfilled = order.quantity - order.filled_quantity
            estimated_cost = self._estimate_cost(order.action, order.price, unfilled, order.order_type)
            self._state.account.frozen_cash -= estimated_cost
            self._state.account.cash += estimated_cost

        order.status = "CANCELLED"
        order.updated_at = datetime.now()
        logger.info(f"Order cancelled: {order_id}")
        return True

    def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """获取订单列表"""
        orders = list(self._state.orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return sorted(orders, key=lambda x: x.created_at, reverse=True)

    def get_trades(self) -> List[Trade]:
        """获取成交记录"""
        return sorted(self._state.trades, key=lambda x: x.timestamp, reverse=True)

    def get_positions(self) -> List[Position]:
        """获取持仓列表"""
        self._update_account_value()
        positions = [p for p in self._state.positions.values() if p.quantity > 0]
        return sorted(positions, key=lambda x: x.market_value, reverse=True)

    def _match_order(self, order: Order):
        """撮合单个订单"""
        # 获取当前市价
        quote = stock_service.get_realtime_quote(order.symbol)
        if not quote or quote.get("price", 0) <= 0:
            logger.warning(f"Cannot match order {order.id}: no market data")
            return

        market_price = quote["price"]

        # 检查是否可成交
        if order.order_type == "LIMIT" and order.price:
            if order.action == "BUY" and market_price > order.price:
                return  # 买价低于市价，无法成交
            if order.action == "SELL" and market_price < order.price:
                return  # 卖价高于市价，无法成交

        # 执行成交
        fill_price = order.price if order.order_type == "LIMIT" else market_price
        fill_qty = order.quantity - order.filled_quantity

        self._execute_trade(order, fill_price, fill_qty)

    def _execute_trade(self, order: Order, price: float, quantity: int):
        """执行成交"""
        # 计算费用
        amount = price * quantity
        commission = max(amount * self.COMMISSION_RATE, self.COMMISSION_MIN)
        stamp_tax = amount * self.STAMP_TAX_RATE if order.action == "SELL" else 0
        transfer_fee = amount * self.TRANSFER_FEE_RATE if order.symbol.startswith("6") else 0
        total_fee = commission + stamp_tax + transfer_fee

        # 创建成交记录
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            order_id=order.id,
            symbol=order.symbol,
            action=order.action,
            price=price,
            quantity=quantity,
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            total_fee=total_fee
        )
        self._state.trades.append(trade)

        # 更新订单状态
        order.filled_quantity += quantity
        if order.filled_quantity >= order.quantity:
            order.status = "FILLED"
        else:
            order.status = "PARTIAL_FILLED"
        order.updated_at = datetime.now()

        # 更新持仓
        if order.action == "BUY":
            self._update_position_buy(order.symbol, price, quantity)
            actual_cost = amount + total_fee
            self._state.account.frozen_cash -= actual_cost
            # 解冻多余资金
            if order.order_type == "LIMIT":
                estimated = self._estimate_cost(order.action, order.price, quantity, order.order_type)
                self._state.account.cash += estimated - actual_cost
        else:  # SELL
            self._update_position_sell(order.symbol, price, quantity)
            actual_proceeds = amount - total_fee
            self._state.account.cash += actual_proceeds
            self._state.account.frozen_cash -= amount  # 解冻卖出金额

        # 更新账户统计
        self._state.account.total_commission += commission
        self._state.account.total_stamp_tax += stamp_tax
        self._state.account.total_transfer_fee += transfer_fee

        logger.info(f"Trade executed: {trade.id} {order.action} {order.symbol} {quantity}@{price}")

    def _update_position_buy(self, symbol: str, price: float, quantity: int):
        """更新持仓（买入）"""
        position = self._state.positions.get(symbol)
        if position:
            # 更新平均成本
            total_cost = position.avg_cost * position.quantity + price * quantity
            position.quantity += quantity
            position.avg_cost = total_cost / position.quantity
        else:
            # 新建持仓
            self._state.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_cost=price,
                market_price=price
            )

    def _update_position_sell(self, symbol: str, price: float, quantity: int):
        """更新持仓（卖出）"""
        position = self._state.positions.get(symbol)
        if position:
            # 计算实现盈亏
            realized_pnl = (price - position.avg_cost) * quantity
            self._state.account.realized_pnl += realized_pnl

            position.quantity -= quantity
            if position.quantity <= 0:
                position.quantity = 0
                position.avg_cost = 0

    def match_orders(self) -> List[Trade]:
        """撮合所有待成交订单"""
        pending_orders = [o for o in self._state.orders.values()
                         if o.status in ["PENDING", "PARTIAL_FILLED"]]

        trades = []
        for order in pending_orders:
            self._match_order(order)
            # 收集本次撮合产生的成交
            recent_trades = [t for t in self._state.trades if t.order_id == order.id]
            trades.extend(recent_trades)

        return trades


# 全局实例
simulation_service = SimulationService()
