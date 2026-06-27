# AI量化交易系统技术架构 Review 意见

> Review Date: 2026-06-28  
> Reviewer: tq

---

## 总体评价

整体来看，项目完成度较高，已经具备前后端分离架构、回测能力、模拟交易、风控模块、Web UI 与自动部署能力。

不过，从一个**可长期演进的量化交易系统**来看，目前文档仍偏向"功能展示"，缺少一些量化系统最重要的基础能力。

当前最大的风险不是缺少更多功能，而是：

> **数据语义、交易制度、状态一致性和架构扩展性仍未完全建立。**

---

## 一、重新评估 P0 优先级

### 1. 不建议把"接入实时行情"作为最高优先级

真正需要先解决的是：
- 回测使用什么价格？
- 模拟交易使用什么价格成交？
- 持仓市值使用什么价格？
- 非交易时间如何计算？
- 停牌怎么办？
- 涨跌停怎么办？
- 除权复权怎么办？

**建议优先建立统一的 `MarketDataService`：**

```
MarketDataService
├── Historical Price      # 历史价格（回测用）
├── Latest Price          # 最新价格（模拟交易/持仓估值）
├── Realtime Quote        # 实时行情（盘中监控）
├── Minute Bar            # 分钟线（高频策略）
└── Daily Bar             # 日线（常规策略）
```

所有模块（回测、模拟交易、风控、图表）统一访问这一层，而不是直接访问 JoinQuant/AkShare/Tushare。

---

## 二、模拟交易持久化需要进一步完善

建议数据库至少包含：

| 表名 | 说明 |
|------|------|
| `accounts` | 账户信息（初始资金、可用资金、冻结资金） |
| `orders` | 订单记录（下单时间、状态、价格、数量） |
| `trades` | 真实成交（成交时间、价格、数量、手续费） |
| `positions` | 持仓（可由 trades 重建，但需要缓存加速） |
| `cash_ledger` | 资金流水（每笔资金变动） |
| `account_snapshots` | 账户快照（每日/每次交易后） |

**建议：**
- trades 保存真实成交
- cash_ledger 保存资金流水
- positions 可由 trades 重建
- snapshot 用于快速恢复
- 撮合全过程使用数据库事务

否则容易出现现金、持仓不一致，且无法审计。

---

## 三、风控增加审计能力

除了：
- `risk_rules` - 风控规则
- `blacklist` - 黑名单
- `stop_loss` - 止损止盈

**建议增加：**

| 表名 | 说明 |
|------|------|
| `risk_events` | 风控事件（触发记录） |
| `risk_decisions` | 风控决策（拒单/通过/告警） |

**记录内容：**
- 为什么拒单
- 哪条规则触发
- 风控计算结果
- 时间
- 参数

方便问题排查和历史分析。

---

## 四、回测完成度建议重新评估

**建议将回测完成度从 90% 调整至 60%~70%。**

需要确认：

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 是否存在未来函数 | ❓ | 信号是否使用了未来数据 |
| 是否正确处理复权 | ✅ | 已实现前复权/后复权 |
| 是否处理停牌 | ❌ | 未处理 |
| 是否处理涨跌停 | ❌ | 未处理 |
| 是否支持 T+1 | ❌ | 未实现 |
| 是否考虑滑点 | ✅ | 已实现 |
| 是否考虑手续费 | ✅ | 已实现 |
| 是否区分 Signal/Order/Fill 时间 | ❌ | 未区分 |

**建议增加指标：**

| 指标 | 说明 |
|------|------|
| Benchmark | 基准对比（沪深300） |
| 最大回撤 | Maximum Drawdown |
| Sharpe Ratio | 夏普比率 |
| Sortino Ratio | 索提诺比率 |
| 胜率 | Win Rate |
| 盈亏比 | Profit/Loss Ratio |
| 年化收益 | Annualized Return |
| 月收益统计 | Monthly Returns |

---

## 五、数据源抽象层提前

**建议提升到 P0/P1。**

建议抽象：

```python
class DataProvider(ABC):
    """数据源抽象基类"""
    
    @abstractmethod
    def get_stock_list(self) -> List[Dict]:
        """获取股票列表"""
        pass
    
    @abstractmethod
    def get_daily_bars(self, symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> List[Dict]:
        """获取日线数据"""
        pass
    
    @abstractmethod
    def get_minute_bars(self, symbol: str, freq: str = "5min") -> List[Dict]:
        """获取分钟线"""
        pass
    
    @abstractmethod
    def get_latest_price(self, symbols: List[str]) -> List[Dict]:
        """获取最新价格"""
        pass
    
    @abstractmethod
    def get_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历"""
        pass


class TushareProvider(DataProvider):
    """Tushare 数据源"""
    pass


class JoinQuantProvider(DataProvider):
    """JoinQuant 数据源"""
    pass


class AkShareProvider(DataProvider):
    """AkShare 数据源"""
    pass
```

业务层不依赖具体数据源。

---

## 六、AI 能力建议提前体现

当前系统更像：
> A股量化回测与模拟交易平台

若继续使用"AI量化交易系统"名称，建议增加：

| AI能力 | 说明 | 优先级 |
|--------|------|--------|
| AI策略参数优化 | 使用遗传算法/贝叶斯优化 | P2 |
| AI策略解释 | 解释策略逻辑和信号原因 | P2 |
| AI选股分析 | 基于基本面/技术面的选股建议 | P2 |
| AI风险提示 | 异常检测和风险预警 | P2 |
| AI回测结果总结 | 自动生成回测报告摘要 | P2 |
| 自然语言生成策略配置 | 用自然语言描述策略 | P3 |

机器学习模型仍可放在 P3。

---

## 七、建议新增基础设施模块

### 7.1 Trading Calendar（交易日历）

**职责：**
- 是否交易日
- 是否开盘
- 节假日
- 提前收盘

```python
class TradingCalendar:
    def is_trading_day(self, date: str) -> bool:
        """是否交易日"""
        pass
    
    def is_market_open(self, datetime: str) -> bool:
        """是否开盘"""
        pass
    
    def get_next_trading_day(self, date: str) -> str:
        """获取下一个交易日"""
        pass
    
    def get_trading_days(self, start_date: str, end_date: str) -> List[str]:
        """获取区间内所有交易日"""
        pass
```

### 7.2 Adjustment Manager（复权管理）

**统一处理：**
- 前复权
- 后复权
- 不复权

```python
class AdjustmentManager:
    def adjust_price(self, price: float, adj_factor: float, latest_adj_factor: float, method: str = "qfq") -> float:
        """复权价格计算"""
        pass
    
    def get_adj_factor(self, symbol: str, date: str) -> float:
        """获取复权因子"""
        pass
```

### 7.3 Stock Status（股票状态）

**统一处理：**
- 停牌
- ST
- 退市
- 涨跌停

```python
class StockStatus:
    def is_suspended(self, symbol: str, date: str) -> bool:
        """是否停牌"""
        pass
    
    def is_st(self, symbol: str, date: str) -> bool:
        """是否ST"""
        pass
    
    def is_limit_up(self, symbol: str, date: str) -> bool:
        """是否涨停"""
        pass
    
    def is_limit_down(self, symbol: str, date: str) -> bool:
        """是否跌停"""
        pass
    
    def get_limit_price(self, symbol: str, date: str) -> Tuple[float, float]:
        """获取涨跌停价格"""
        pass
```

### 7.4 Data Quality（数据质量）

**增加：**
- K线缺失检测
- 数据异常检测
- 数据连续性检查

```python
class DataQualityChecker:
    def check_missing_bars(self, symbol: str, start_date: str, end_date: str) -> List[str]:
        """检测缺失K线"""
        pass
    
    def check_price_anomaly(self, bars: List[Dict]) -> List[Dict]:
        """检测价格异常"""
        pass
    
    def check_continuity(self, bars: List[Dict]) -> bool:
        """检查数据连续性"""
        pass
```

---

## 八、建议补充参考项目

除 vnpy、abu、adata 外，建议增加：

| 项目 | Stars | 特点 | 参考价值 |
|------|-------|------|----------|
| **Backtrader** | 13k+ | Broker/Order/Position 设计 | 交易制度实现 |
| **vectorbt** | 4k+ | 向量化回测 | 高性能回测引擎 |
| **Qlib** | 15k+ | 微软开源，AI量化 | 机器学习集成 |
| **RQAlpha** | 5k+ | A股交易制度 | T+1/涨跌停/停牌处理 |

**Backtrader 参考点：**
- Broker 模式（模拟券商）
- Order 生命周期（Created → Submitted → Accepted → Completed/Cancelled）
- Position 管理
- 佣金模型

**RQAlpha 参考点：**
- A股交易制度（T+1、涨跌停、停牌）
- 交易日历
- 复权处理
- 风险管理

---

## 九、建议重新排序 TODO

### P0（可信） - 核心基础设施

| # | 任务 | 说明 | 预估工时 |
|---|------|------|----------|
| 1 | **DataProvider 抽象层** | 统一数据接口，解耦业务与数据源 | 2天 |
| 2 | **Trading Calendar** | 交易日历，处理节假日/开盘时间 | 1天 |
| 3 | **Adjustment Manager** | 统一复权处理 | 1天 |
| 4 | **Stock Status** | 停牌/ST/涨跌停统一处理 | 1天 |
| 5 | **模拟交易持久化** | accounts/orders/trades/positions/cash_ledger | 3天 |
| 6 | **风控事件记录** | risk_events/risk_decisions 审计 | 1天 |
| 7 | **回测成交模型修正** | 处理停牌/涨跌停/T+1 | 2天 |
| 8 | **核心单元测试** | 覆盖率 60%+ | 2天 |

### P1（稳定） - 质量保障

| # | 任务 | 说明 | 预估工时 |
|---|------|------|----------|
| 1 | API 统一格式 | `{ success, data?, error?, message? }` | 1天 |
| 2 | 错误处理规范 | 统一异常体系 | 1天 |
| 3 | 配置管理 | Pydantic Settings | 1天 |
| 4 | 日志规范 | 结构化日志 + 请求ID | 1天 |
| 5 | 数据源降级 | 主备数据源切换 | 1天 |
| 6 | Health Check | DB/数据源连通性检测 | 0.5天 |

### P2（体验） - 功能增强

| # | 任务 | 说明 | 预估工时 |
|---|------|------|----------|
| 1 | 策略模板 | 模板与回测参数联动 | 1天 |
| 2 | 更多策略 | MACD/布林带等 | 2天 |
| 3 | 回测报告增强 | Sharpe/Sortino/最大回撤/月收益 | 2天 |
| 4 | 数据源插件 | 可配置的数据源切换 | 2天 |
| 5 | AI策略参数优化 | 遗传算法/贝叶斯优化 | 3天 |
| 6 | AI回测结果总结 | 自动生成报告摘要 | 2天 |
| 7 | E2E测试 | 完整链路测试 | 2天 |
| 8 | 运维文档 | 环境变量/部署排错 | 1天 |

### P3（产品化） - 长期演进

| # | 任务 | 说明 | 预估工时 |
|---|------|------|----------|
| 1 | AI策略解释 | 解释策略逻辑和信号原因 | 3天 |
| 2 | AI选股分析 | 基本面/技术面选股 | 3天 |
| 3 | 多用户支持 | 用户体系、资源隔离 | 3天 |
| 4 | 实盘交易接口 | 对接券商API | 10天 |
| 5 | 多品种扩展 | 港股/期货 | 5天 |
| 6 | 异步任务队列 | Celery/RQ | 3天 |
| 7 | 自然语言策略 | 用自然语言描述策略 | 5天 |

---

## 十、总结

**建议后续开发重点不要继续增加页面，而应优先完善四项基础设施：**

1. **统一的数据语义**（MarketData）
2. **完整的交易制度**（Trading Rules）
3. **可靠的状态一致性**（Persistence）
4. **良好的架构扩展能力**（Provider / Plugin）

**建议系统定位调整为：**

> **先成为一个可信的量化研究平台，再逐步演进为 AI 驱动的量化交易平台。**

---

## 附录：当前架构问题清单

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 数据语义不统一 | 回测/模拟/风控使用不同价格 | P0 |
| 交易制度缺失 | 无法正确处理T+1/涨跌停/停牌 | P0 |
| 状态不持久 | 重启丢失所有数据 | P0 |
| 回测过于理想 | 未来函数/停牌/涨跌停未处理 | P0 |
| 无审计能力 | 无法排查风控/交易问题 | P1 |
| 数据源耦合 | 切换数据源需改业务代码 | P1 |
| 缺少AI能力 | 名不副实 | P2 |

---

*本文档由 tq review 后更新，作为后续开发指导。*
