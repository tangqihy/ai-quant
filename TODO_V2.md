# AI量化交易系统 - TODO（修订版）

> 更新日期：2026-06-28  
> 基于 tq Review 意见重新排序

---

## 核心理念

> **打造一个以可信数据、可验证策略、可复现结果为核心的 AI Quant Platform。**

三个核心关键词：
- **可信数据** (Trusted Data)：数据来源清晰、质量可校验
- **可验证策略** (Verifiable Strategy)：策略行为符合交易规则，避免未来函数和回测偏差
- **可复现结果** (Reproducible Results)：同一数据、同一参数、同一版本能够得到一致的回测和模拟交易结果

---

## P0（可信） - 核心基础设施

**目标：建立可信的量化研究基础**

| # | 任务 | 说明 | 负责人 | 预估工时 | 状态 |
|---|------|------|--------|----------|------|
| 1 | **DataProvider 抽象层** | 统一数据接口，解耦业务与数据源 | 小猪 | 2天 | ✅ |
| 2 | **Trading Calendar** | 交易日历，处理节假日/开盘时间 | 小猪 | 1天 | ✅ |
| 3 | **Adjustment Manager** | 统一复权处理 | 小猪 | 1天 | ✅ |
| 4 | **Stock Status** | 停牌/ST/涨跌停统一处理 | 小猪 | 1天 | ✅ |
| 5 | **Domain Model** | 领域模型定义（Instrument/Order/Trade/Position/Account/Portfolio/Strategy/RiskRule/Broker/Exchange） | minimax | 2天 | ✅ |
| 6 | **Broker 拆分** | 撮合器独立，支持三种实现（BacktestBroker/PaperBroker/LiveBroker） | minimax | 3天 | ✅ |
| 7 | **Strategy API** | 固定策略接口（initialize/on_bar/on_tick/on_order/on_trade/on_finish） | minimax | 1天 | ✅ |
| 8 | **Account/Portfolio 分离** | 账户负责现金，组合负责持仓 | minimax | 2天 | ✅ |
| 9 | **模拟交易持久化** | accounts/orders/trades/positions/cash_ledger | 小猪 | 3天 | ✅ |
| 10 | **风控事件记录** | risk_events/risk_decisions 审计 | 小猪 | 1天 | ✅ |
| 11 | **回测成交模型修正** | 处理停牌/涨跌停/T+1 | minimax | 2天 | ✅ |
| 12 | **核心单元测试** | 覆盖率 60%+ | minimax | 2天 | ✅ |

**P0 预估总工时：21天**

---

## P1（稳定） - 质量保障

**目标：代码质量和系统稳定性**

| # | 任务 | 说明 | 负责人 | 预估工时 | 状态 |
|---|------|------|--------|----------|------|
| 1 | **Event Bus** | 事件总线，解耦组件 | minimax | 2天 | ⏳ |
| 2 | **API 统一格式** | `{ success, data?, error?, message? }` | 小猪 | 1天 | ✅ |
| 3 | **错误处理规范** | 统一异常体系 | 小猪 | 1天 | ✅ |
| 4 | **配置管理** | Pydantic Settings | minimax | 1天 | ✅ |
| 5 | **日志规范** | 结构化日志 + 请求ID | minimax | 1天 | ✅ |
| 6 | **数据源降级** | 主备数据源切换 | 小猪 | 1天 | ✅ |
| 7 | **Health Check** | DB/数据源连通性检测 | 小猪 | 0.5天 | ✅ |

**P1 预估总工时：7.5天**

---

## P2（体验） - 功能增强

**目标：增强功能和AI能力**

| # | 任务 | 说明 | 负责人 | 预估工时 | 状态 |
|---|------|------|--------|----------|------|
| 1 | **策略模板** | 模板与回测参数联动 | 小猪 | 1天 | ⏳ |
| 2 | **更多策略** | MACD/布林带等 | minimax | 2天 | ⏳ |
| 3 | **回测报告增强** | Sharpe/Sortino/最大回撤/月收益 | minimax | 2天 | ⏳ |
| 4 | **数据源插件** | 可配置的数据源切换 | minimax | 2天 | ⏳ |
| 5 | **AI策略参数优化** | 遗传算法/贝叶斯优化 | 待定 | 3天 | ⏳ |
| 6 | **AI回测结果总结** | 自动生成报告摘要 | 待定 | 2天 | ⏳ |
| 7 | **E2E测试** | 完整链路测试 | minimax | 2天 | ⏳ |
| 8 | **运维文档** | 环境变量/部署排错 | 小猪 | 1天 | ⏳ |

**P2 预估总工时：15天**

---

## P3（产品化） - 长期演进

**目标：产品化和多用户支持**

| # | 任务 | 说明 | 负责人 | 预估工时 | 状态 |
|---|------|------|--------|----------|------|
| 1 | **AI策略解释** | 解释策略逻辑和信号原因 | 待定 | 3天 | ⏳ |
| 2 | **AI选股分析** | 基本面/技术面选股 | 待定 | 3天 | ⏳ |
| 3 | **多用户支持** | 用户体系、资源隔离 | 待定 | 3天 | ⏳ |
| 4 | **实盘交易接口** | 对接券商API | 待定 | 10天 | ⏳ |
| 5 | **多品种扩展** | 港股/期货 | 待定 | 5天 | ⏳ |
| 6 | **异步任务队列** | Celery/RQ | 待定 | 3天 | ⏳ |
| 7 | **自然语言策略** | 用自然语言描述策略 | 待定 | 5天 | ⏳ |

**P3 预估总工时：32天**

---

## 优先级调整说明

### 新增任务

| 任务 | 优先级 | 说明 |
|------|--------|------|
| Domain Model | P0 | 定义稳定的领域对象 |
| Broker 拆分 | P0 | 撮合器独立，支持三种实现 |
| Strategy API | P0 | 固定策略接口 |
| Account/Portfolio 分离 | P0 | 账户与组合分离 |
| Event Bus | P1 | 事件驱动架构 |

### 设计原则

1. **领域驱动**：定义稳定的领域对象，而不是到处传 dict/DataFrame
2. **职责单一**：Broker 只负责撮合，Strategy 只负责信号
3. **事件驱动**：通过 Event Bus 解耦组件
4. **数据分层**：SQLite 当缓存，不是唯一事实来源
5. **接口固定**：Strategy API 现在就固定，以后不用改

---

## 当前完成度

| 模块 | 完成度 | 说明 |
|------|--------|------|
| DataProvider | ✅ | 已实现 |
| Trading Calendar | ✅ | 已实现 |
| Adjustment Manager | ✅ | 已实现 |
| Stock Status | ✅ | 已实现 |
| Domain Model | ⏳ | 待实现 |
| Broker | ⏳ | 待拆分 |
| Strategy API | ⏳ | 待固定 |
| Account/Portfolio | ⏳ | 待分离 |

**P0 完成度：33%（4/12）**

---

## 架构演进路线

```
Phase 1: 可信基础设施 ✅
    ├── DataProvider ✅
    ├── TradingCalendar ✅
    ├── AdjustmentManager ✅
    ├── StockStatus ✅
    └── Domain Model ⏳

Phase 2: 核心能力 ⏳
    ├── Broker (Backtest/Paper/Live)
    ├── Strategy API
    ├── Account/Portfolio
    └── Event Bus

Phase 3: 稳定性 ⏳
    ├── 模拟交易持久化
    ├── 风控事件记录
    ├── 回测成交模型
    └── 单元测试

Phase 4: 扩展性 ⏳
    ├── 多策略支持
    ├── 多市场支持
    ├── AI 能力
    └── 实盘交易
```

---

*本文档基于 tq 的 Review 意见更新，作为后续开发指导。*
