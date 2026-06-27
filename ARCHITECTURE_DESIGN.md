# AI量化交易系统 - 架构设计原则

> 更新日期：2026-06-28  
> 基于 tq Review 意见

---

## 一、产品愿景

> **打造一个以可信数据、可验证策略、可复现结果为核心的 AI Quant Platform。**

三个核心关键词：

| 关键词 | 说明 | 优先级 |
|--------|------|--------|
| **可信数据** (Trusted Data) | 数据来源清晰、质量可校验 | P0 |
| **可验证策略** (Verifiable Strategy) | 策略行为符合交易规则，避免未来函数和回测偏差 | P0 |
| **可复现结果** (Reproducible Results) | 同一数据、同一参数、同一版本能够得到一致的回测和模拟交易结果 | P0 |

这三个原则比"AI"本身更重要，是整个项目架构演进的指导思想。

---

## 二、领域模型 (Domain Model)

### 2.1 核心领域对象

```
┌─────────────────────────────────────────────────────────────────┐
│                        领域模型 (Domain Model)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Instrument │    │ MarketData  │    │  TradingDay │         │
│  │   (股票)     │    │   (行情)    │    │  (交易日)   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │    Order    │    │    Trade    │    │  Position   │         │
│  │   (订单)    │    │   (成交)    │    │   (持仓)    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Account   │    │  Portfolio  │    │  Strategy   │         │
│  │   (账户)    │    │   (组合)    │    │   (策略)    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  RiskRule   │    │   Broker    │    │  Exchange   │         │
│  │  (风控规则) │    │  (撮合器)   │    │  (交易所)   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 领域对象定义

#### Instrument（股票）
```python
@dataclass
class Instrument:
    symbol: str           # 股票代码 (600519)
    name: str             # 股票名称 (贵州茅台)
    exchange: str         # 交易所 (SH/SZ/BJ)
    market: str           # 市场 (主板/创业板/科创板)
    industry: str         # 行业
    list_date: str        # 上市日期
    status: str           # 状态 (active/suspended/delisted)
```

#### MarketData（行情）
```python
@dataclass
class MarketData:
    symbol: str           # 股票代码
    date: str             # 日期
    open: float           # 开盘价
    high: float           # 最高价
    low: float            # 最低价
    close: float          # 收盘价
    volume: float         # 成交量
    amount: float         # 成交额
    change_pct: float     # 涨跌幅
    turnover: float       # 换手率
    adj_factor: float     # 复权因子
```

#### Order（订单）
```python
@dataclass
class Order:
    order_id: str         # 订单ID
    symbol: str           # 股票代码
    direction: str        # 方向 (buy/sell)
    price: float          # 价格
    quantity: int         # 数量
    order_type: str       # 类型 (limit/market)
    status: str           # 状态 (pending/submitted/accepted/filled/partial/cancelled/rejected)
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    filled_quantity: int  # 已成交数量
    filled_price: float   # 成交均价
    commission: float     # 手续费
    slippage: float       # 滑点
```

#### Trade（成交）
```python
@dataclass
class Trade:
    trade_id: str         # 成交ID
    order_id: str         # 订单ID
    symbol: str           # 股票代码
    direction: str        # 方向 (buy/sell)
    price: float          # 成交价格
    quantity: int         # 成交数量
    commission: float     # 手续费
    slippage: float       # 滑点
    traded_at: datetime   # 成交时间
```

#### Position（持仓）
```python
@dataclass
class Position:
    symbol: str           # 股票代码
    quantity: int         # 持仓数量
    available: int        # 可用数量（T+1后）
    cost_price: float     # 成本价
    market_value: float   # 市值
    unrealized_pnl: float # 浮动盈亏
    realized_pnl: float   # 已实现盈亏
```

#### Account（账户）
```python
@dataclass
class Account:
    account_id: str       # 账户ID
    initial_capital: float # 初始资金
    cash: float           # 可用资金
    frozen: float         # 冻结资金
    total_value: float    # 总资产
    created_at: datetime  # 创建时间
```

#### Portfolio（组合）
```python
@dataclass
class Portfolio:
    portfolio_id: str     # 组合ID
    account_id: str       # 账户ID
    strategy_id: str      # 策略ID
    positions: Dict[str, Position]  # 持仓
    created_at: datetime  # 创建时间
```

#### Strategy（策略）
```python
class Strategy(ABC):
    """策略基类"""
    
    @abstractmethod
    def initialize(self, context: StrategyContext):
        """初始化"""
        pass
    
    @abstractmethod
    def on_bar(self, bar: MarketData):
        """K线更新"""
        pass
    
    @abstractmethod
    def on_tick(self, tick: MarketData):
        """Tick更新"""
        pass
    
    @abstractmethod
    def on_order(self, order: Order):
        """订单更新"""
        pass
    
    @abstractmethod
    def on_trade(self, trade: Trade):
        """成交更新"""
        pass
    
    @abstractmethod
    def on_finish(self):
        """策略结束"""
        pass
```

#### RiskRule（风控规则）
```python
@dataclass
class RiskRule:
    rule_id: str          # 规则ID
    rule_type: str        # 规则类型 (position_limit/stop_loss/blacklist)
    params: Dict          # 参数
    enabled: bool         # 是否启用
    description: str      # 描述
```

#### Broker（撮合器）
```python
class Broker(ABC):
    """撮合器基类"""
    
    @abstractmethod
    def submit_order(self, order: Order) -> bool:
        """提交订单"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        pass
    
    @abstractmethod
    def match(self, bar: MarketData) -> List[Trade]:
        """撮合"""
        pass
```

#### Exchange（交易所规则）
```python
@dataclass
class Exchange:
    name: str             # 交易所名称
    trading_calendar: TradingCalendar  # 交易日历
    tick_size: float      # 最小变动价位
    lot_size: int         # 最小交易单位
    t_plus: int           # T+N (T+1)
    price_limit: float    # 涨跌停限制 (10%/5%/20%)
    commission_rate: float # 佣金率
    stamp_tax_rate: float # 印花税率
    min_commission: float # 最低佣金
```

---

## 三、Broker 拆分设计

### 3.1 当前问题

当前 SimulationService 职责太多：
- 下单
- 撮合
- 更新持仓
- 更新现金
- 风控

### 3.2 建议拆分

```
Strategy
    ↓
Order
    ↓
RiskEngine (风控引擎)
    ↓
Broker (撮合器)
    ↓
Trade
    ↓
Portfolio (组合管理)
    ↓
Account (账户管理)
```

### 3.3 职责划分

| 组件 | 职责 |
|------|------|
| **Strategy** | 生成交易信号，创建订单 |
| **RiskEngine** | 风控检查，是否允许下单 |
| **Broker** | 撮合订单，计算成交价/滑点/手续费，处理T+1/涨跌停/停牌 |
| **Portfolio** | 管理持仓，计算市值/盈亏 |
| **Account** | 管理资金，计算总资产 |

### 3.4 三种 Broker 实现

```python
class BacktestBroker(Broker):
    """回测撮合器"""
    # 使用历史数据撮合
    pass

class PaperBroker(Broker):
    """模拟撮合器"""
    # 使用实时数据撮合
    pass

class LiveBroker(Broker):
    """实盘撮合器"""
    # 对接券商API
    pass
```

三种 Broker 可以复用大量逻辑，只是数据来源不同。

---

## 四、Event Bus（事件总线）

### 4.1 事件驱动架构

```
MarketData Updated (行情更新)
        ↓
    Event Bus (事件总线)
        ↓
   ┌────┴────┐
   ↓         ↓
Strategy   RiskEngine
   ↓         ↓
Order    RiskCheck
   ↓         ↓
Broker   Allow/Reject
   ↓
Trade
   ↓
Portfolio
   ↓
Account
   ↓
Notification
```

### 4.2 事件类型

```python
class EventType(Enum):
    # 行情事件
    MARKET_DATA = "market_data"
    BAR = "bar"
    TICK = "tick"
    
    # 交易事件
    ORDER_CREATED = "order_created"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    TRADE = "trade"
    
    # 账户事件
    POSITION_UPDATED = "position_updated"
    ACCOUNT_UPDATED = "account_updated"
    
    # 风控事件
    RISK_CHECK = "risk_check"
    RISK_ALERT = "risk_alert"
    RISK_REJECT = "risk_reject"
    
    # 系统事件
    STRATEGY_START = "strategy_start"
    STRATEGY_STOP = "strategy_stop"
    SYSTEM_ERROR = "system_error"
```

### 4.3 事件总线实现

```python
class EventBus:
    """事件总线"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def publish(self, event_type: EventType, data: Any = None):
        """发布事件"""
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            handler(data)
```

### 4.4 事件驱动的优势

以后只需要订阅事件，就能实现：
- WebSocket 实时推送
- AI 分析
- 自动提醒
- Telegram/微信通知

而不是互相调用。

---

## 五、Strategy API 设计

### 5.1 固定的策略接口

```python
class Strategy(ABC):
    """策略基类"""
    
    @abstractmethod
    def initialize(self, context: StrategyContext):
        """
        初始化
        
        Args:
            context: 策略上下文，包含：
                - account: 账户信息
                - portfolio: 组合信息
                - subscribe(): 订阅行情
                - order(): 下单
                - cancel(): 撤单
        """
        pass
    
    @abstractmethod
    def on_bar(self, bar: MarketData):
        """
        K线更新
        
        Args:
            bar: K线数据
        """
        pass
    
    @abstractmethod
    def on_tick(self, tick: MarketData):
        """
        Tick更新
        
        Args:
            tick: Tick数据
        """
        pass
    
    @abstractmethod
    def on_order(self, order: Order):
        """
        订单更新
        
        Args:
            order: 订单信息
        """
        pass
    
    @abstractmethod
    def on_trade(self, trade: Trade):
        """
        成交更新
        
        Args:
            trade: 成交信息
        """
        pass
    
    @abstractmethod
    def on_finish(self):
        """策略结束"""
        pass
```

### 5.2 策略上下文

```python
class StrategyContext:
    """策略上下文"""
    
    def subscribe(self, symbols: List[str], frequency: str = "1d"):
        """订阅行情"""
        pass
    
    def order(self, symbol: str, direction: str, quantity: int, price: float = None, order_type: str = "limit"):
        """下单"""
        pass
    
    def cancel(self, order_id: str):
        """撤单"""
        pass
    
    @property
    def account(self) -> Account:
        """获取账户信息"""
        pass
    
    @property
    def portfolio(self) -> Portfolio:
        """获取组合信息"""
        pass
    
    @property
    def positions(self) -> Dict[str, Position]:
        """获取持仓信息"""
        pass
```

### 5.3 策略示例

```python
class MACrossStrategy(Strategy):
    """MA交叉策略"""
    
    def initialize(self, context: StrategyContext):
        self.short_window = 5
        self.long_window = 20
        self.context = context
        context.subscribe(["600519"], "1d")
    
    def on_bar(self, bar: MarketData):
        # 计算MA
        short_ma = self.calculate_ma(bar.symbol, self.short_window)
        long_ma = self.calculate_ma(bar.symbol, self.long_window)
        
        # 金叉买入
        if short_ma > long_ma and not self.has_position(bar.symbol):
            self.context.order(bar.symbol, "buy", 100)
        
        # 死叉卖出
        elif short_ma < long_ma and self.has_position(bar.symbol):
            self.context.order(bar.symbol, "sell", self.get_position(bar.symbol).quantity)
    
    def on_order(self, order: Order):
        pass
    
    def on_trade(self, trade: Trade):
        pass
    
    def on_finish(self):
        pass
```

---

## 六、Account 与 Portfolio 分离

### 6.1 设计原则

- **Account**：负责现金管理
- **Portfolio**：负责组合管理
- **Position**：负责单只股票

### 6.2 关系

```
Account (账户)
    ├── cash: float (现金)
    ├── frozen: float (冻结资金)
    │
    ├── Portfolio 1 (组合1 - 策略A)
    │   ├── Position: 600519
    │   ├── Position: 000858
    │   └── Position: 002624
    │
    ├── Portfolio 2 (组合2 - 策略B)
    │   ├── Position: 300750
    │   └── Position: 601012
    │
    └── Portfolio 3 (组合3 - 策略C)
        └── ...
```

### 6.3 优势

- 一个账户管理多个组合
- 一个组合支持多个策略
- 策略之间互不干扰
- 便于统计每个策略的收益

---

## 七、SQLite 当缓存，不是唯一事实来源

### 7.1 问题

当前把 SQLite 当作唯一事实来源，会导致：
- 数据一致性问题
- 难以扩展到多实例
- 难以支持分布式

### 7.2 建议

```
┌─────────────────────────────────────────────────────────────┐
│                      数据分层架构                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              数据源层 (Data Source)                   │   │
│  │  Tushare / JoinQuant / AkShare / 本地文件            │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              缓存层 (Cache)                          │   │
│  │  SQLite / Redis / 内存缓存                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              服务层 (Service)                        │   │
│  │  MarketDataService / TradingService / RiskService   │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              业务层 (Business)                       │   │
│  │  Strategy / Broker / Portfolio / Account            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 数据流

1. **数据源**：提供原始数据
2. **缓存**：加速访问，减少数据源调用
3. **服务**：统一数据访问接口
4. **业务**：使用数据进行业务逻辑

---

## 八、更新后的 P0 优先级

### P0（可信） - 核心基础设施

| # | 任务 | 说明 | 负责人 | 预估工时 | 状态 |
|---|------|------|--------|----------|------|
| 1 | **DataProvider 抽象层** | 统一数据接口，解耦业务与数据源 | 小猪 | 2天 | ✅ |
| 2 | **Trading Calendar** | 交易日历，处理节假日/开盘时间 | 小猪 | 1天 | ✅ |
| 3 | **Adjustment Manager** | 统一复权处理 | 小猪 | 1天 | ✅ |
| 4 | **Stock Status** | 停牌/ST/涨跌停统一处理 | 小猪 | 1天 | ✅ |
| 5 | **Domain Model** | 领域模型定义 | minimax | 2天 | ⏳ |
| 6 | **Broker 拆分** | 撮合器独立，支持三种实现 | minimax | 3天 | ⏳ |
| 7 | **Strategy API** | 固定策略接口 | minimax | 1天 | ⏳ |
| 8 | **Account/Portfolio 分离** | 账户与组合分离 | minimax | 2天 | ⏳ |
| 9 | **模拟交易持久化** | accounts/orders/trades/positions | 小猪 | 3天 | ⏳ |
| 10 | **风控事件记录** | risk_events/risk_decisions 审计 | 小猪 | 1天 | ⏳ |
| 11 | **回测成交模型修正** | 处理停牌/涨跌停/T+1 | minimax | 2天 | ⏳ |
| 12 | **核心单元测试** | 覆盖率 60%+ | minimax | 2天 | ⏳ |

**P0 预估总工时：21天**

---

## 九、参考项目

| 项目 | Stars | 特点 | 参考价值 |
|------|-------|------|----------|
| **vnpy** | 42k | 插件化架构 | Gateway/Strategy/App 插件设计 |
| **Backtrader** | 13k | Broker/Order/Position | 交易制度实现 |
| **Zipline** | 17k | 事件驱动回测 | Event Bus 设计 |
| **Qlib** | 15k | 微软开源，AI量化 | 机器学习集成 |
| **RQAlpha** | 5k | A股交易制度 | T+1/涨跌停/停牌处理 |

---

## 十、总结

### 核心理念

> **打造一个以可信数据、可验证策略、可复现结果为核心的 AI Quant Platform。**

### 设计原则

1. **领域驱动**：定义稳定的领域对象，而不是到处传 dict/DataFrame
2. **职责单一**：Broker 只负责撮合，Strategy 只负责信号
3. **事件驱动**：通过 Event Bus 解耦组件
4. **数据分层**：SQLite 当缓存，不是唯一事实来源
5. **接口固定**：Strategy API 现在就固定，以后不用改

### 架构演进路线

```
Phase 1: 可信基础设施
    ├── DataProvider
    ├── TradingCalendar
    ├── AdjustmentManager
    ├── StockStatus
    └── Domain Model

Phase 2: 核心能力
    ├── Broker (Backtest/Paper/Live)
    ├── Strategy API
    ├── Account/Portfolio
    └── Event Bus

Phase 3: 稳定性
    ├── 模拟交易持久化
    ├── 风控事件记录
    ├── 回测成交模型
    └── 单元测试

Phase 4: 扩展性
    ├── 多策略支持
    ├── 多市场支持
    ├── AI 能力
    └── 实盘交易
```

---

*本文档基于 tq 的 Review 意见更新，作为架构设计指导。*
