# P0 架构 Review - Trading Core Refactor

> 来源：tq Review 意见  
> 更新日期：2026-06-28

## 总体评价

当前 P1（基础设施层）已经完成得比较成熟，包括统一 API 响应、异常体系、配置管理、结构化日志、Event Bus、Health Check、DataProvider 降级等。

**建议下一阶段不要继续横向增加功能，而是集中完成交易内核重构（Trading Core）。**

---

## 一、P0 剩余任务优先级

建议顺序：

1. **Domain Model** - 领域模型定义
2. **Strategy API** - 策略接口固定
3. **Broker** - 撮合器独立
4. **Account / Portfolio** - 账户与组合分离
5. **Repository** - 数据访问层
6. **Event Bus 集成** - 关键事件接入
7. **前端 API 适配** - 统一 API Client

---

## 二、Domain Model（最高优先级）

建议定义的核心领域对象：

| 对象 | 说明 |
|------|------|
| `Instrument` | 标的（股票代码、名称、交易所、状态） |
| `Bar` | K线（开高低收、成交量、时间） |
| `Tick` | 逐笔/报价（盘口数据） |
| `Signal` | 策略信号（买卖方向、价格、数量、原因） |
| `Order` | 订单（状态机：pending→submitted→filled/cancelled/rejected） |
| `Trade` | 成交（价格、数量、手续费、滑点） |
| `Position` | 持仓（数量、成本、可卖、盈亏） |
| `Portfolio` | 组合（持仓集合、市值、收益） |
| `Account` | 账户（现金、冻结、总资产） |
| `StrategyContext` | 策略上下文（当前Bar、历史数据、账户状态） |
| `RiskDecision` | 风控决策（通过/拒绝、原因） |

**这些对象应成为整个系统的统一语言。**

---

## 三、Strategy API

建议固定的生命周期接口：

```python
class Strategy(ABC):
    @abstractmethod
    def initialize(self, context: StrategyContext) -> None:
        """初始化，加载参数、历史数据"""
        pass
    
    @abstractmethod
    def on_start(self) -> None:
        """策略启动"""
        pass
    
    @abstractmethod
    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """K线到达，返回信号"""
        pass
    
    @abstractmethod
    def on_tick(self, tick: Tick) -> Optional[Signal]:
        """Tick到达（盘中）"""
        pass
    
    @abstractmethod
    def on_order(self, order: Order) -> None:
        """订单状态变化"""
        pass
    
    @abstractmethod
    def on_trade(self, trade: Trade) -> None:
        """成交回报"""
        pass
    
    @abstractmethod
    def on_finish(self) -> None:
        """策略结束"""
        pass
```

**即使目前仅实现 `on_bar`，也建议预留完整接口。**

---

## 四、Broker 拆分

Broker 建议独立于 `backtest_service`。

### 职责清单

- [ ] 撮合（价格优先、时间优先）
- [ ] 滑点模拟
- [ ] 手续费计算
- [ ] T+1 限制
- [ ] 涨跌停限制
- [ ] 停牌处理
- [ ] 部分成交
- [ ] 撤单处理

### 三种实现

| Broker | 场景 | 特点 |
|--------|------|------|
| `BacktestBroker` | 回测 | 历史数据驱动，模拟撮合 |
| `PaperBroker` | 模拟盘 | 实时行情，虚拟撮合 |
| `LiveBroker` | 实盘 | 对接券商API |

---

## 五、Account / Portfolio

### 职责划分

**Account（账户）**
- 现金余额
- 冻结资金（挂单占用）
- 总资产

**Portfolio（组合）**
- 组合收益率
- 市值
- Position 集合

**Position（持仓）**
- 持仓数量
- 可卖数量（T+1）
- 成本价
- 已实现收益
- 未实现收益（浮动盈亏）

---

## 六、Repository

建议新增 `app/repositories/` 目录：

```
app/repositories/
├── order_repository.py
├── trade_repository.py
├── position_repository.py
├── portfolio_repository.py
└── account_repository.py
```

**避免 Service 直接操作 SQLite，通过 Repository 抽象数据访问。**

---

## 七、Event Bus 集成建议

建议只接关键事件：

| 事件 | 触发时机 | 用途 |
|------|----------|------|
| `ORDER_SUBMITTED` | 订单提交 | 审计、日志 |
| `ORDER_CANCELLED` | 订单撤销 | 审计 |
| `ORDER_FILLED` | 订单成交 | 更新持仓、推送 |
| `POSITION_CHANGED` | 持仓变化 | WebSocket 推送 |
| `RISK_REJECTED` | 风控拒绝 | 告警、日志 |
| `BACKTEST_FINISHED` | 回测完成 | 保存结果、AI分析 |

**主要用于：审计、日志、WebSocket、AI Agent**

**避免所有业务都事件化。**

---

## 八、测试建议

优先覆盖的场景：

| 场景 | 测试点 |
|------|--------|
| 买入成交 | 正常下单、资金扣减、持仓增加 |
| 卖出成交 | 正常下单、资金增加、持仓减少 |
| 余额不足 | 买入被拒绝 |
| 持仓不足 | 卖出被拒绝 |
| T+1 | 当日买入不可卖出 |
| 停牌 | 停牌股不可交易 |
| 涨停 | 涨停价买入、涨停价卖出限制 |
| 跌停 | 跌停价买入、跌停价卖出限制 |
| 手续费 | 最低5元、费率计算 |
| 印花税 | 卖出千分之一 |
| 回测可复现 | 同参数同结果 |

---

## 九、前端建议

当前阶段：

- [ ] 统一 API Client（封装 fetch/axios）
- [ ] 统一错误处理（toast 提示）
- [ ] 保持 CyberCard / Dashboard 稳定

**暂不建议大规模修改 UI。**

---

## 最终建议

> 下一阶段目标：将系统从 Service CRUD 架构升级为 **Domain + Strategy + Broker + Portfolio** 的交易内核架构。
>
> 完成这一阶段后，再继续 AI、Agent、多市场、实盘等能力建设。
