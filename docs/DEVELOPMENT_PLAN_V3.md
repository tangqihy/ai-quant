# AI量化交易系统 - 开发计划 V3

> 更新日期：2026-07-10
> 基于 tq Tushare数据分层 + 最低成本框架设计
> 当前状态：P0.1/P0.5/P1 已完成，P2 未开始

---

## 设计理念

**数据管线优先，平台功能后置。**

之前的计划是"先搭平台（FastAPI+React），再填数据"。现在调整为：
先建好数据基础设施（Tushare → Parquet → DuckDB → PIT），再在此基础上
做因子计算、回测和策略。前端可视化是最后一步。

---

## 当前完成度

| 阶段 | 状态 | 说明 |
|------|------|------|
| P0.1 基础层 | ✅ 完成 | DataProvider抽象、TradingCalendar、AdjustmentManager、StockStatus |
| P0.5 Trading Core | ✅ 完成 | Domain模型、Strategy API、Broker、Account/Portfolio、Repository、EventBus、测试 |
| P1 质量保障 | ✅ 完成 | Event Bus、API统一格式、错误处理、配置、日志、数据源降级、Health Check |
| P2 功能增强 | ⏳ 未开始 | **← 本计划重点** |

---

## P2 重构：数据管线优先

### P2.1 数据采集层（Tushare Downloader）

**目标：把 Tushare 第一梯队数据落到本地 Parquet**

| # | 任务 | 说明 |
|---|------|------|
| 1 | **Downloader 框架** | 统一下载器：接口名 + 参数 → Parquet 写入，支持增量更新 |
| 2 | **日线行情** | `daily` + `adj_factor`，按 `trade_date` 分区 |
| 3 | **daily_basic** | PE/PB/PS/股息率/换手率/市值，按 `trade_date` 分区 |
| 4 | **交易日历** | `trade_cal`，全量 |
| 5 | **股票基础信息** | `stock_basic`，增量更新 |
| 6 | **财务报表** | `income`/`balancesheet`/`cashflow`/`fina_indicator`/`forecast`/`express`/`dividend`/`disclosure_date`，按 `period` 分区 |
| 7 | **指数成分** | `index_weight`/`index_member_all`/`index_classify`，按 `index_code` 分区 |
| 8 | **停复牌/上市退市** | `suspend_d`/`stock_basic` 中的 list_date/delist_date |
| 9 | **调度 cron** | 系统 cron，每日盘后自动下载增量数据 |
| 10 | **数据质量校验** | 空值检查、日期连续性、复权因子单调性 |

**详细技术方案：** [docs/design/02-data-collector.md](docs/design/02-data-collector.md)

---

### P2.2 Normalize 层

**目标：统一格式，为 PIT 层和因子计算做准备**

| # | 任务 | 说明 |
|---|------|------|
| 1 | **日期统一** | 所有日期转为 `YYYYMMDD` 字符串 |
| 2 | **股票代码统一** | 统一 `ts_code` 格式（`600519.SH`） |
| 3 | **财务单位统一** | 金额单位统一为元，百分比统一为小数 |
| 4 | **去重主键** | `daily: (ts_code, trade_date)`, `financial: (ts_code, ann_date, end_date, report_type)` |
| 5 | **空值处理** | 明确每列的空值语义（缺失 vs 零 vs 不适用） |
| 6 | **DuckDB 建库** | 用 DuckDB 直接查询 Parquet，建视图/表映射 |

**详细技术方案：** [docs/design/03-normalize-layer.md](docs/design/03-normalize-layer.md)

---

### P2.3 PIT 层（最重要）

**目标：消除未来函数，确保回测数据时序正确**

| # | 任务 | 说明 |
|---|------|------|
| 1 | **available_date 计算** | `available_date = ann_date` |
| 2 | **财务 PIT 视图** | 在回测日期 T，只能使用 `ann_date <= T` 的财务数据 |
| 3 | **指数成分 PIT** | 成分股变动按公告日期生效 |
| 4 | **ST/退市 PIT** | ST 标记和退市状态按公告日期生效 |
| 5 | **复权价格计算** | 存原始不复权 + 复权因子，本地计算前/后复权 |
| 6 | **PIT 完整性测试** | 用已知案例验证无未来函数 |

**详细技术方案：** [docs/design/04-pit-layer.md](docs/design/04-pit-layer.md)

---

### P2.4 回测引擎（向量化日频）

**目标：基于 DuckDB + Polars 的向量化回测，模拟真实 A 股规则**

| # | 任务 | 说明 |
|---|------|------|
| 1 | **向量化信号生成** | 预计算因子列，用 `shift` 产生信号，避免逐行循环 |
| 2 | **成交量约束** | 限制为当日成交额的 1%～5%，小市值策略必须加 |
| 3 | **涨跌停限制** | 一字涨停不能买，一字跌停不能卖 |
| 4 | **停牌处理** | 停牌日不能交易，持仓不变 |
| 5 | **T+1 规则** | 今天买的今天不能卖 |
| 6 | **100股整数手** | 成交量必须为 100 的整数倍 |
| 7 | **费用模型** | 佣金（万2.5，最低5元）+ 印花税（千1，卖出）+ 过户费（十万分之一） |
| 8 | **信号延迟** | 当日收盘信号，最早次日成交（`signal_date + 1 trading day`） |
| 9 | **回测指标** | Sharpe、Sortino、最大回撤、胜率、盈亏比、月度收益 |
| 10 | **基准对比** | 与沪深300/中证500对比 |

**详细技术方案：** [docs/design/05-backtest-engine.md](docs/design/05-backtest-engine.md)

---

### P2.5 因子计算框架

**目标：标准化因子计算流程，支持多因子选股**

| # | 任务 | 说明 |
|---|------|------|
| 1 | **因子注册机制** | `@register_factor(name="pe_ttm")` 装饰器 |
| 2 | **基础因子** | 市值、PE、PB、股息率、换手率、波动率 |
| 3 | **财务因子** | ROE、ROIC、毛利率、营收增速、利润增速 |
| 4 | **动量因子** | 5日/20日/60日收益率、相对强弱 |
| 5 | **行业中性化** | 按申万行业分组，因子标准化 |
| 6 | **因子 IC 分析** | 因子与未来收益的相关性，评估因子有效性 |

**详细技术方案：** [docs/design/06-factor-framework.md](docs/design/06-factor-framework.md)

---

### P2.6 前端适配

**目标：把新的数据管线和回测结果展示到前端**

| # | 任务 | 说明 |
|---|------|------|
| 1 | **API Client 统一** | 适配 `{ success, data?, error?, message? }` 格式 |
| 2 | **TypeScript 类型定义** | Instrument/Order/Trade/Position 等 |
| 3 | **回测结果展示** | 收益曲线、持仓明细、交易记录 |
| 4 | **因子分析页** | 因子 IC、分组收益、因子相关性热力图 |
| 5 | **数据监控页** | 下载状态、数据质量、最新更新时间 |

---

## 里程碑

| 里程碑 | 阶段 | 交付物 |
|--------|------|--------|
| **M1: 数据落盘** | P2.1 | Tushare 第一梯队数据全部入库 Parquet，cron 每日增量 |
| **M2: 数据可用** | P2.2 + P2.3 | DuckDB 查询 + PIT 层，可验证无未来函数 |
| **M3: 回测跑通** | P2.4 | 向量化回测引擎，模拟真实 A 股规则 |
| **M4: 因子选股** | P2.5 | 多因子选股框架，IC 分析 |
| **M5: 前端展示** | P2.6 | 完整的回测 + 因子分析前端 |

---

## 技术栈确认

| 模块 | 选型 | 说明 |
|------|------|------|
| 语言 | Python | 不变 |
| 数据源 | Tushare Pro | 替代 AkShare/JoinQuant |
| 原始存储 | Parquet | 按接口和交易日期分区 |
| 查询引擎 | DuckDB | 直接查 Parquet，不需要导入 |
| 数据处理 | Polars | 比 Pandas 快，API 更干净 |
| 调度 | 系统 cron | 简单可靠 |
| 配置 | YAML + Pydantic | 不变 |
| 元数据 | SQLite | 不变 |
| 后端 | FastAPI | 不变 |
| 前端 | React + TypeScript | 不变 |
| 部署 | PM2 + Nginx | 不变 |

---

## 不做的事

- ❌ Kafka / Airflow / K8s / ClickHouse / 微服务
- ❌ 实时流计算
- ❌ 期货/期权/可转债（先专注 A 股股票）
- ❌ 券商实盘接入（先做模拟盘验证）
- ❌ AI/LLM 集成（先做好数据和因子基础）

---

## 依赖关系

```
P2.1 数据采集
    ↓
P2.2 Normalize
    ↓
P2.3 PIT 层 ← 最关键，影响所有下游
    ↓
P2.4 回测引擎 + P2.5 因子计算（可并行）
    ↓
P2.6 前端适配
```

---

## 与现有代码的衔接

### 保留的模块
- `app/core/` — 基础设施层（config、exceptions、event_bus、logging、health）
- `app/domain/` — 领域模型
- `app/brokers/` — 撮合器（BacktestBroker 需要适配新的回测引擎）
- `app/trading/` — Account/Portfolio
- `app/risk/` — 风控
- `app/repositories/` — 数据访问层

### 需要重写的模块
- `app/providers/tushare_provider.py` — 从"实时调用"改为"读本地 Parquet + DuckDB"
- `app/services/backtest_service.py` — 从 Pandas 逐行改为向量化
- `app/services/kline_store.py` — 从 SQLite 改为 Parquet

### 新增的模块
- `app/data/` — 数据采集层（Downloader、Scheduler、质量校验）
- `app/pit/` — PIT 层（available_date 计算、PIT 视图）
- `app/factors/` — 因子计算框架
- `app/backtest/engine_v2.py` — 向量化回测引擎

---

## 设计文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| **数据管线总体架构** | [docs/design/01-data-pipeline-architecture.md](docs/design/01-data-pipeline-architecture.md) | 系统全景、分层职责、目录结构、关键设计决策 |
| **数据采集层** | [docs/design/02-data-collector.md](docs/design/02-data-collector.md) | Tushare 下载器接口、存储策略、增量逻辑、调度机制 |
| **Normalize 层** | [docs/design/03-normalize-layer.md](docs/design/03-normalize-layer.md) | Schema 定义、转换规则、去重逻辑、DuckDB 查询层 |
| **PIT 层** | [docs/design/04-pit-layer.md](docs/design/04-pit-layer.md) | 未来函数消除、财务/指数/ST 的 PIT 实现、复权计算 |
| **回测引擎** | [docs/design/05-backtest-engine.md](docs/design/05-backtest-engine.md) | A 股交易规则、信号生成、撮合逻辑、指标计算 |
| **因子框架** | [docs/design/06-factor-framework.md](docs/design/06-factor-framework.md) | 因子注册、基础/财务/动量因子、IC 分析、行业中性化 |
| Tushare 数据分层 | [docs/tushare_data_tiers.md](docs/tushare_data_tiers.md) | 第一/二/三梯队数据详解 |
| 最低成本框架 | [docs/quant_framework_design.md](docs/quant_framework_design.md) | 数据分层设计、A股回测规则 |
| P0 架构 Review | [docs/P0_REVIEW.md](docs/P0_REVIEW.md) | Trading Core 设计决策 |
