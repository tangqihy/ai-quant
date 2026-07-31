# AI量化交易系统 - 开发计划 V3（最终版）

> 更新日期：2026-07-10
> 经三轮架构评审后收敛的最终方案
> 核心原则：**数据和交易语义按专业标准设计，实现方式按个人系统规模简化**

---

## 当前完成度

| 阶段 | 状态 | 说明 |
|------|------|------|
| P0.1 基础层 | ✅ 完成 | DataProvider抽象、TradingCalendar、AdjustmentManager、StockStatus |
| P0.5 Trading Core | ✅ 完成 | Domain模型、Strategy API、Broker、Account/Portfolio、Repository、EventBus、测试 |
| P1 质量保障 | ✅ 完成 | Event Bus、API统一格式、错误处理、配置、日志、数据源降级、Health Check |
| P2 功能增强 | ⏳ 未开始 | **← 本计划重点** |

---

## 五条不可简化的语义

| # | 语义 | 实现方式 |
|---|------|----------|
| 1 | 数据什么时候可见 | `published_at` + 无时间时默认下一交易日可用 |
| 2 | 状态什么时候生效 | `announced_date` + `effective_date`，无明确生效日时默认下一交易日 |
| 3 | 回测用了哪个数据版本 | `BacktestRunManifest` + `dataset_version` |
| 4 | 信号如何转化成订单和成交 | Signal → OrderIntent → Order → Trade，完整生命周期 |
| 5 | 成交如何影响现金与持仓 | 订单账本：submit→freeze→fill→settle，lot tracking |

---

## 最终架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据采集层 (Collector)                    │
│  Tushare API ──→ DownloadScheduler ──→ Raw Parquet              │
│                  (cron / 手动触发)    (append-only, 按批次存储)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Normalize 层                              │
│  Raw Parquet ──→ 类型统一 ──→ 单位统一 ──→ 版本化存储            │
│                  (DATE类型)    (FieldSpec)  (latest + 版本历史)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PIT 层 (Point-in-Time)                    │
│  published_at <= as_of → 选择最新修订 → 状态类用 effective_date  │
│  公告默认下一交易日可用 | ingested_at 仅用于审计和 tiebreaker     │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│   因子计算 (Factors)   │   │   回测引擎 (Backtest)  │
│  向量化计算             │   │  因子：向量化           │
│  oriented_factor       │   │  撮合：状态化           │
│  raw_ic / tradable_ic  │   │  Signal→Order→Trade    │
└───────────────────────┘   └───────────────────────┘
```

---

## P0：先保证结果可信

| # | 任务 | 说明 |
|---|------|------|
| 1 | **PIT 可见时间规则** | `published_at` 为核心，无时间时默认下一交易日可用 |
| 2 | **历史证券主数据** | `instrument_history` 表，消除幸存者偏差 |
| 3 | **latest view vs PIT view** | Normalize 层区分两个视图 |
| 4 | **Signal/Order/Trade 分离** | 领域模型拆分，Signal 不携带执行结果 |
| 5 | **订单资金账本** | submit→freeze→fill→settle，完整生命周期 |
| 6 | **IC 执行时点修正** | 使用 T+1 可执行价格，区分 raw_ic / tradable_ic |
| 7 | **BacktestRunManifest** | 记录策略版本、数据版本、配置、代码提交 |
| 8 | **复权 as_of_date** | 显式传入，数据截断到 as_of_date |

---

## P1：再完善数据工程

| # | 任务 | 说明 |
|---|------|------|
| 1 | **Raw append-only** | 按批次存储，不覆盖旧数据 |
| 2 | **轻量 batch manifest** | 记录 batch_id、interface、request_params、row_count |
| 3 | **财务自动回看** | 每次采集时回看最近2-4个报告期 |
| 4 | **FieldSpec 单位规范** | 每个字段显式定义源单位和标准单位 |
| 5 | **watermark 质量校验** | 行数、唯一性、非空率、最大日期 |
| 6 | **Normalize 月度压实** | 按月合并分区，控制查询文件数 |
| 7 | **状态类双日期模型** | announced_date + effective_date |
| 8 | **JSON 状态文件** | 原子写入、schema_version、状态标记 |

---

## P2：后续研究增强

| # | 任务 | 说明 |
|---|------|------|
| 1 | **截面回归中性化** | factor ~ industry_dummy + log_market_cap |
| 2 | **样本内外验证** | 滚动窗口、不同时期稳定性 |
| 3 | **更精细成交模型** | conservative 撮合模式 |
| 4 | **多数据源校验** | Tushare vs AkShare 一致性 |
| 5 | **高级数据血缘** | 字段级来源追踪 |

---

## 技术栈

| 模块 | 选型 |
|------|------|
| 语言 | Python |
| 数据源 | Tushare Pro |
| 原始存储 | Parquet（append-only，按批次） |
| 查询引擎 | DuckDB |
| 数据处理 | Polars |
| 调度 | 系统 cron |
| 配置 | YAML + Pydantic |
| 元数据 | SQLite（账户/订单）+ JSON（任务状态） |
| 后端 | FastAPI |
| 前端 | React + TypeScript |

---

## 设计文档索引

| 文档 | 说明 |
|------|------|
| [01-data-pipeline-architecture.md](design/01-data-pipeline-architecture.md) | 系统全景、分层职责 |
| [02-data-collector.md](design/02-data-collector.md) | 数据采集层 |
| [03-normalize-layer.md](design/03-normalize-layer.md) | Normalize 层 |
| [04-pit-layer.md](design/04-pit-layer.md) | PIT 层 |
| [05-backtest-engine.md](design/05-backtest-engine.md) | 回测引擎 |
| [06-factor-framework.md](design/06-factor-framework.md) | 因子框架 |
| [07-stock-canvas.md](design/07-stock-canvas.md) | 股票无限画布（结构化研究知识库） |
