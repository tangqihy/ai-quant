"""
风控服务
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from app.models.risk import (
    RiskRule, RiskAlert, StopLossConfig, BlacklistItem,
    RiskCheckResult
)
from app.models.simulation import Position
from app.services.stock_service import stock_service

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """风控状态"""
    rules: Dict[str, RiskRule] = field(default_factory=dict)
    alerts: List[RiskAlert] = field(default_factory=list)
    stop_loss_configs: Dict[str, StopLossConfig] = field(default_factory=dict)  # key: symbol
    blacklist: Dict[str, BlacklistItem] = field(default_factory=dict)  # key: symbol


class RiskService:
    """风控服务"""

    # 默认风控配置
    DEFAULT_RULES = {
        "position_single_limit": {
            "id": "position_single_limit",
            "name": "单票仓位限制",
            "rule_type": "POSITION_LIMIT",
            "enabled": True,
            "params": {"max_position_pct": 50.0}  # 单票最大50%
        },
        "position_total_limit": {
            "id": "position_total_limit",
            "name": "总仓位限制",
            "rule_type": "POSITION_LIMIT",
            "enabled": True,
            "params": {"max_total_position_pct": 80.0}  # 总仓位最大80%
        },
        "min_trade_amount": {
            "id": "min_trade_amount",
            "name": "最小交易单位",
            "rule_type": "TRADE_LIMIT",
            "enabled": True,
            "params": {"min_lot": 100}  # 最小100股
        },
        "max_order_value": {
            "id": "max_order_value",
            "name": "最大订单金额",
            "rule_type": "TRADE_LIMIT",
            "enabled": True,
            "params": {"max_value": 1000000}  # 最大100万
        },
        "st_stock_block": {
            "id": "st_stock_block",
            "name": "ST股限制",
            "rule_type": "BLACKLIST",
            "enabled": True,
            "params": {"block_buy": True, "block_sell": False}
        },
    }

    def __init__(self):
        self._state = RiskState()
        self._init_default_rules()

    def _init_default_rules(self):
        """初始化默认规则"""
        for rule_id, rule_data in self.DEFAULT_RULES.items():
            self._state.rules[rule_id] = RiskRule(**rule_data)

    # ==================== 规则管理 ====================

    def get_rules(self) -> List[RiskRule]:
        """获取所有风控规则"""
        return list(self._state.rules.values())

    def update_rule(self, rule_id: str, enabled: bool, params: Optional[dict] = None) -> Optional[RiskRule]:
        """更新规则"""
        rule = self._state.rules.get(rule_id)
        if not rule:
            return None
        rule.enabled = enabled
        if params:
            rule.params.update(params)
        rule.updated_at = datetime.now()
        return rule

    # ==================== 风控检查 ====================

    def check_order(self, symbol: str, action: str, quantity: int,
                    price: float, account_value: float,
                    positions: Dict[str, Position]) -> RiskCheckResult:
        """检查订单是否符合风控规则"""
        alerts = []
        blocked = False
        message = None

        # 检查黑名单
        blacklist_check = self._check_blacklist(symbol, action)
        if blacklist_check:
            alerts.append(blacklist_check)
            if blacklist_check.alert_type == "BLOCK":
                blocked = True
                message = blacklist_check.message

        # 检查交易单位
        if not blocked:
            lot_check = self._check_trade_lot(quantity)
            if lot_check:
                alerts.append(lot_check)
                if lot_check.alert_type == "BLOCK":
                    blocked = True
                    message = lot_check.message

        # 检查订单金额
        if not blocked:
            value_check = self._check_order_value(price * quantity)
            if value_check:
                alerts.append(value_check)
                if value_check.alert_type == "BLOCK":
                    blocked = True
                    message = value_check.message

        # 检查仓位限制
        if not blocked and action == "BUY":
            position_check = self._check_position_limit(symbol, quantity, price, account_value, positions)
            if position_check:
                alerts.extend(position_check)
                for alert in position_check:
                    if alert.alert_type == "BLOCK":
                        blocked = True
                        message = alert.message
                        break

        # 保存告警
        self._state.alerts.extend(alerts)

        return RiskCheckResult(
            passed=not blocked,
            blocked=blocked,
            alerts=alerts,
            message=message
        )

    def _check_blacklist(self, symbol: str, action: str) -> Optional[RiskAlert]:
        """检查黑名单"""
        item = self._state.blacklist.get(symbol)
        if not item:
            return None

        # 检查是否过期
        if item.expires_at and item.expires_at < datetime.now():
            del self._state.blacklist[symbol]
            return None

        # 检查买卖限制
        rule = self._state.rules.get("st_stock_block")
        if rule and rule.enabled:
            if item.reason == "ST" and action == "BUY":
                return RiskAlert(
                    id=str(uuid.uuid4())[:8],
                    rule_id="st_stock_block",
                    rule_name="ST股限制",
                    alert_type="BLOCK",
                    symbol=symbol,
                    message=f"{symbol} 为ST股票，禁止买入",
                    details={"reason": item.reason, "description": item.description}
                )

        if item.reason in ["LIMIT_UP"] and action == "BUY":
            return RiskAlert(
                id=str(uuid.uuid4())[:8],
                rule_id="price_limit",
                rule_name="涨跌停限制",
                alert_type="BLOCK",
                symbol=symbol,
                message=f"{symbol} 已涨停，禁止买入",
                details={"reason": item.reason}
            )

        if item.reason in ["LIMIT_DOWN"] and action == "SELL":
            return RiskAlert(
                id=str(uuid.uuid4())[:8],
                rule_id="price_limit",
                rule_name="涨跌停限制",
                alert_type="BLOCK",
                symbol=symbol,
                message=f"{symbol} 已跌停，禁止卖出",
                details={"reason": item.reason}
            )

        return None

    def _check_trade_lot(self, quantity: int) -> Optional[RiskAlert]:
        """检查交易单位"""
        rule = self._state.rules.get("min_trade_amount")
        if not rule or not rule.enabled:
            return None

        min_lot = rule.params.get("min_lot", 100)
        if quantity % min_lot != 0:
            return RiskAlert(
                id=str(uuid.uuid4())[:8],
                rule_id=rule.id,
                rule_name=rule.name,
                alert_type="BLOCK",
                message=f"交易数量必须是 {min_lot} 的整数倍",
                details={"quantity": quantity, "min_lot": min_lot}
            )
        return None

    def _check_order_value(self, value: float) -> Optional[RiskAlert]:
        """检查订单金额"""
        rule = self._state.rules.get("max_order_value")
        if not rule or not rule.enabled:
            return None

        max_value = rule.params.get("max_value", 1000000)
        if value > max_value:
            return RiskAlert(
                id=str(uuid.uuid4())[:8],
                rule_id=rule.id,
                rule_name=rule.name,
                alert_type="BLOCK",
                message=f"订单金额 {value:.2f} 超过最大限制 {max_value}",
                details={"order_value": value, "max_value": max_value}
            )
        return None

    def _check_position_limit(self, symbol: str, quantity: int, price: float,
                               account_value: float, positions: Dict[str, Position]) -> List[RiskAlert]:
        """检查仓位限制"""
        alerts = []

        # 单票仓位限制
        single_rule = self._state.rules.get("position_single_limit")
        if single_rule and single_rule.enabled:
            max_pct = single_rule.params.get("max_position_pct", 50.0)
            position = positions.get(symbol)
            current_qty = position.quantity if position else 0
            new_qty = current_qty + quantity
            new_value = new_qty * price
            pct = (new_value / account_value) * 100 if account_value > 0 else 0

            if pct > max_pct:
                alerts.append(RiskAlert(
                    id=str(uuid.uuid4())[:8],
                    rule_id=single_rule.id,
                    rule_name=single_rule.name,
                    alert_type="BLOCK",
                    symbol=symbol,
                    message=f"单票仓位将达到 {pct:.2f}%，超过限制 {max_pct}%",
                    details={"current_pct": pct, "max_pct": max_pct}
                ))

        # 总仓位限制
        total_rule = self._state.rules.get("position_total_limit")
        if total_rule and total_rule.enabled:
            max_total_pct = total_rule.params.get("max_total_position_pct", 80.0)
            # 使用各持仓的实际成本价计算市值
            total_value = sum(p.quantity * p.avg_cost for p in positions.values())
            new_total = total_value + quantity * price
            total_pct = (new_total / account_value) * 100 if account_value > 0 else 0

            if total_pct > max_total_pct:
                alerts.append(RiskAlert(
                    id=str(uuid.uuid4())[:8],
                    rule_id=total_rule.id,
                    rule_name=total_rule.name,
                    alert_type="BLOCK",
                    symbol=symbol,
                    message=f"总仓位将达到 {total_pct:.2f}%，超过限制 {max_total_pct}%",
                    details={"current_pct": total_pct, "max_pct": max_total_pct}
                ))

        return alerts

    # ==================== 止损止盈 ====================

    def set_stop_loss(self, symbol: str, position_id: str,
                      stop_loss_pct: float, stop_profit_pct: Optional[float] = None,
                      trailing_stop: bool = False, trailing_stop_pct: Optional[float] = None) -> StopLossConfig:
        """设置止损止盈"""
        # 获取当前价格
        quote = stock_service.get_realtime_quote(symbol)
        current_price = quote.get("price", 0) if quote else 0

        # 如果无法获取价格，拒绝设置止损止盈
        if current_price <= 0:
            raise ValueError(f"无法获取 {symbol} 的当前价格，无法设置止损止盈")

        stop_loss_price = current_price * (1 - stop_loss_pct / 100)
        stop_profit_price = current_price * (1 + stop_profit_pct / 100) if stop_profit_pct else None

        config = StopLossConfig(
            symbol=symbol,
            position_id=position_id,
            stop_loss_price=stop_loss_price,
            stop_loss_pct=stop_loss_pct,
            stop_profit_price=stop_profit_price,
            stop_profit_pct=stop_profit_pct,
            trailing_stop=trailing_stop,
            trailing_stop_pct=trailing_stop_pct,
            highest_price=current_price if trailing_stop else None
        )
        self._state.stop_loss_configs[symbol] = config
        logger.info(f"Stop loss set for {symbol}: SL={stop_loss_price:.2f} ({stop_loss_pct}%)")
        return config

    def update_stop_loss(self, symbol: str, current_price: float) -> Optional[RiskAlert]:
        """更新止损价格（移动止损）"""
        config = self._state.stop_loss_configs.get(symbol)
        if not config or not config.trailing_stop:
            return None

        # 更新最高价
        if current_price > config.highest_price:
            config.highest_price = current_price
            # 更新止损价格
            if config.trailing_stop_pct:
                config.stop_loss_price = config.highest_price * (1 - config.trailing_stop_pct / 100)
                logger.info(f"Trailing stop updated for {symbol}: SL={config.stop_loss_price:.2f}, High={config.highest_price:.2f}")

        return None

    def check_stop_loss(self, symbol: str, current_price: float) -> Optional[RiskAlert]:
        """检查是否触发止损止盈"""
        config = self._state.stop_loss_configs.get(symbol)
        if not config:
            return None

        # 先更新移动止损
        self.update_stop_loss(symbol, current_price)

        # 检查止损
        if current_price <= config.stop_loss_price:
            return RiskAlert(
                id=str(uuid.uuid4())[:8],
                rule_id="stop_loss",
                rule_name="止损触发",
                alert_type="WARNING",
                symbol=symbol,
                message=f"{symbol} 价格 {current_price:.2f} 触及止损价 {config.stop_loss_price:.2f}",
                details={"current_price": current_price, "stop_loss_price": config.stop_loss_price}
            )

        # 检查止盈
        if config.stop_profit_price and current_price >= config.stop_profit_price:
            return RiskAlert(
                id=str(uuid.uuid4())[:8],
                rule_id="stop_profit",
                rule_name="止盈触发",
                alert_type="WARNING",
                symbol=symbol,
                message=f"{symbol} 价格 {current_price:.2f} 触及止盈价 {config.stop_profit_price:.2f}",
                details={"current_price": current_price, "stop_profit_price": config.stop_profit_price}
            )

        return None

    def remove_stop_loss(self, symbol: str) -> bool:
        """移除止损止盈设置"""
        if symbol in self._state.stop_loss_configs:
            del self._state.stop_loss_configs[symbol]
            return True
        return False

    def get_stop_loss_config(self, symbol: str) -> Optional[StopLossConfig]:
        """获取止损止盈配置"""
        return self._state.stop_loss_configs.get(symbol)

    # ==================== 黑名单管理 ====================

    def add_to_blacklist(self, symbol: str, reason: str,
                         description: str = "", expires_in_hours: Optional[int] = None) -> BlacklistItem:
        """添加到黑名单"""
        expires_at = datetime.now() + timedelta(hours=expires_in_hours) if expires_in_hours else None
        item = BlacklistItem(
            symbol=symbol,
            reason=reason,
            description=description,
            expires_at=expires_at
        )
        self._state.blacklist[symbol] = item
        logger.info(f"Added {symbol} to blacklist: {reason}")
        return item

    def remove_from_blacklist(self, symbol: str) -> bool:
        """从黑名单移除"""
        if symbol in self._state.blacklist:
            del self._state.blacklist[symbol]
            return True
        return False

    def get_blacklist(self) -> List[BlacklistItem]:
        """获取黑名单"""
        # 清理过期项
        now = datetime.now()
        expired = [s for s, item in self._state.blacklist.items()
                   if item.expires_at and item.expires_at < now]
        for s in expired:
            del self._state.blacklist[s]

        return list(self._state.blacklist.values())

    def is_blacklisted(self, symbol: str) -> bool:
        """检查是否在黑名单"""
        item = self._state.blacklist.get(symbol)
        if not item:
            return False
        # 检查是否过期
        if item.expires_at and item.expires_at < datetime.now():
            del self._state.blacklist[symbol]
            return False
        return True

    # ==================== 告警管理 ====================

    def get_alerts(self, acknowledged: Optional[bool] = None, limit: int = 100) -> List[RiskAlert]:
        """获取告警列表"""
        alerts = self._state.alerts
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return sorted(alerts, key=lambda x: x.created_at, reverse=True)[:limit]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        for alert in self._state.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def clear_alerts(self):
        """清空告警"""
        self._state.alerts = []


# 全局实例
risk_service = RiskService()
