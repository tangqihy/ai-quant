# 01 - 数据管线总体架构

> 本文档定义量化系统的数据流、分层职责和模块边界。
> 所有下游文档（采集、Normalize、PIT、回测、因子）以此为基准。

---

## 1. 系统全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据采集层 (Collector)                    │
│  Tushare API ──→ DownloadScheduler ──→ Raw Parquet              │
│                  (cron / 手动触发)    (按接口+日期分区)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Normalize 层                              │
│  Raw Parquet ──→ Schema统一 ──→ 去重 ──→ Normalized Parquet      │
│                  (日期/代码/单位/空值)    (DuckDB 直接查询)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PIT 层 (Point-in-Time)                    │
│  Normalized ──→ available_date计算 ──→ PIT视图                   │
│  财务/指数/ST    (ann_date vs download_date)  (回测T日可用数据)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│   因子计算 (Factors)   │   │   回测引擎 (Backtest)  │
│  PIT数据 → 因子值      │   │  信号 → 撮合 → 指标    │
│  (注册机制+IC分析)     │   │  (向量化+A股规则)      │
└───────────────────────┘   └───────────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        展示层 (Frontend)                         │
│  回测结果 / 因子分析 / 数据监控                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 分层职责与边界

### 2.1 Raw 层

**职责：** 原始数据落盘，不做任何修改。

**原则：**
- 完全保留 Tushare 返回结果，包括列名、数据类型、空值
- 按接口名 + 最有意义的维度分区（日期、指数代码等）
- 不做覆盖式更新，已下载的文件不重复拉取
- 支持重跑：删除指定日期的文件后重新下载

**存储格式：** Parquet，分区目录结构

**谁写入：** Collector（data/collector.py）
**谁读取：** Normalize 层

### 2.2 Normalize 层

**职责：** 统一格式，为下游提供干净、一致的数据。

**原则：**
- 日期统一为 `YYYYMMDD` 字符串（与 Tushare 一致，避免类型转换歧义）
- 股票代码统一为 `ts_code` 格式（`600519.SH`）
- 财务金额单位统一为元
- 百分比统一为小数（如 5% 存为 0.05）
- 去重：按主键去重，保留最新下载的版本
- 空值语义明确：`NaN` 表示缺失，`0` 表示真实零值

**存储格式：** Parquet，与 Raw 层分区结构一致

**谁写入：** Normalize 流程（data/normalize.py）
**谁读取：** PIT 层、因子计算、回测引擎

### 2.3 PIT 层

**职责：** 消除未来函数，确保回测数据时序正确。

**原则：**
- 财务数据：在回测日期 T，只能使用 `available_date <= T` 的数据
- 指数成分：成分股变动按公告日期生效
- ST/退市：按公告日期生效，不是按实际生效日期
- 复权：存原始不复权 + 复权因子，本地计算

**实现方式：** DuckDB 视图 + Python 函数封装

**谁写入：** PIT 计算逻辑（data/pit.py）
**谁读取：** 因子计算、回测引擎

### 2.4 因子计算层

**职责：** 从 PIT 数据计算标准化因子值。

**原则：**
- 因子注册机制：装饰器注册，统一接口
- 输入：PIT 层的行情 + 财务 + 指数数据
- 输出：`DataFrame[ts_code, trade_date, factor_name, factor_value]`
- 支持行业中性化、标准化（z-score / rank）
- IC 分析：因子值与未来 N 日收益的相关性

**谁写入：** FactorRegistry（factors/registry.py）
**谁读取：** 回测引擎（多因子选股）、前端展示

### 2.5 回测引擎

**职责：** 基于因子信号执行模拟交易，计算收益指标。

**原则：**
- 向量化计算，不逐行循环
- 严格模拟 A 股交易规则
- 信号延迟：T 日收盘信号 → T+1 日成交
- 费用模型：佣金 + 印花税 + 过户费
- 成交量约束：限制为当日成交额的百分比

**谁写入：** BacktestEngine（backtest/engine_v2.py）
**谁读取：** 前端展示

---

## 3. 目录结构

```
ai-quant/
├── app/
│   ├── data/                          # 数据管线（新增）
│   │   ├── __init__.py
│   │   ├── collector.py               # Tushare 下载器
│   │   ├── scheduler.py               # 下载调度
│   │   ├── normalize.py               # Normalize 层
│   │   ├── pit.py                     # PIT 层
│   │   ├── quality.py                 # 数据质量校验
│   │   └── schemas.py                 # 每个接口的 schema 定义
│   ├── factors/                       # 因子框架（新增）
│   │   ├── __init__.py
│   │   ├── registry.py                # 因子注册机制
│   │   ├── base_factors.py            # 基础因子（市值/PE/PB等）
│   │   ├── financial_factors.py       # 财务因子（ROE/增速等）
│   │   ├── momentum_factors.py        # 动量因子
│   │   ├── neutralize.py              # 行业中性化
│   │   └── ic_analysis.py             # 因子 IC 分析
│   ├── backtest/
│   │   ├── engine.py                  # 旧引擎（保留兼容）
│   │   └── engine_v2.py               # 新向量化引擎
│   ├── providers/                     # 数据源抽象（改造）
│   │   ├── base.py                    # DataProvider 接口
│   │   ├── tushare_provider.py        # 改为读 Parquet
│   │   └── ...
│   └── ...                            # 其他模块不变
├── data/                              # 数据存储（新增，不入git）
│   ├── raw/                           # Raw 层 Parquet
│   │   ├── daily/
│   │   ├── adj_factor/
│   │   ├── daily_basic/
│   │   ├── income/
│   │   ├── balancesheet/
│   │   ├── cashflow/
│   │   ├── fina_indicator/
│   │   ├── forecast/
│   │   ├── express/
│   │   ├── dividend/
│   │   ├── disclosure_date/
│   │   ├── index_weight/
│   │   ├── index_member_all/
│   │   ├── index_classify/
│   │   ├── trade_cal/
│   │   └── stock_basic/
│   ├── normalized/                    # Normalize 层 Parquet
│   │   └── (同 raw 结构)
│   └── pit/                           # PIT 层（DuckDB 视图，不落盘）
├── docs/design/                       # 设计文档（本目录）
│   ├── 01-data-pipeline-architecture.md
│   ├── 02-data-collector.md
│   ├── 03-normalize-layer.md
│   ├── 04-pit-layer.md
│   ├── 05-backtest-engine.md
│   └── 06-factor-framework.md
└── scripts/                           # 运维脚本
    ├── download_all.py                # 全量下载
    ├── download_incremental.py        # 增量下载
    ├── normalize_all.py               # 全量 Normalize
    └── verify_pit.py                  # PIT 完整性验证
```

---

## 4. 数据流详细路径

### 4.1 日常增量流程

```
cron 触发 (每日 17:30)
    │
    ▼
download_incremental.py
    │  1. 查询 trade_cal 获取最近交易日
    │  2. 检查 data/raw/ 下已有文件
    │  3. 下载缺失的 daily / daily_basic / adj_factor
    │  4. 财务数据按季报周期检查（每年 4/8/10/次年4 月）
    │  5. 写入 data/raw/
    ▼
normalize_all.py (增量)
    │  1. 读取 raw 中新增文件
    │  2. 应用 schema 转换
    │  3. 去重（按主键）
    │  4. 写入 data/normalized/
    ▼
完成
```

### 4.2 回测数据读取路径

```
回测引擎请求 (ts_code, start_date, end_date)
    │
    ▼
PIT 层
    │  1. 行情数据：直接从 normalized/daily 读取（无需 PIT）
    │  2. 财务数据：从 normalized/fin_* 读取，按 available_date 过滤
    │  3. 指数成分：从 normalized/index_weight 读取，按 available_date 过滤
    │  4. 复权：读取 normalized/adj_factor + 原始价格，本地计算
    ▼
返回 DataFrame (统一格式，已复权，已 PIT)
```

---

## 5. 关键设计决策

### 5.1 为什么用 Parquet 而不是 SQLite

| 维度 | Parquet | SQLite |
|------|---------|--------|
| 列式存储 | ✅ 因子计算只需读特定列 | ❌ 行式存储 |
| 分区 | ✅ 按日期分区，增量写入自然 | ❌ 需要手动管理 |
| DuckDB 直查 | ✅ `read_parquet('data/...')` | 需要 ATTACH |
| 压缩 | ✅ 自带压缩，体积小 | 需要配置 |
| 并发写 | ❌ 单线程写入 | ❌ 单写多读 |
| 事务 | ❌ 无 | ✅ ACID |

**结论：** 量化场景以读为主（因子计算、回测），Parquet 的列式读取和分区优势更大。SQLite 保留给元数据（账户、订单、配置）。

### 5.2 为什么用 DuckDB 而不是 Pandas 直接读

| 维度 | DuckDB | Pandas |
|------|--------|--------|
| 内存 | 按需加载，不吃满内存 | 全量加载到内存 |
| SQL | ✅ 标准 SQL 查询 | 需要 DataFrame 操作 |
| Parquet 支持 | ✅ 原生，支持分区裁剪 | ✅ pyarrow 读取 |
| 聚合计算 | ✅ 向量化引擎 | ✅ NumPy 后端 |
| 多表关联 | ✅ SQL JOIN | 需要 merge |

**结论：** DuckDB 作为查询层，Pandas/Polars 作为计算层。DuckDB 负责从 Parquet 中筛选和关联数据，Pandas/Polars 负责因子计算和回测逻辑。

### 5.3 复权策略

**不使用 Tushare 的 `pro_bar` 前复权数据。**

原因：`pro_bar` 的前复权价格会根据请求的 `end_date` 动态计算，同一历史日期在不同 `end_date` 下价格不同，不可复现。

**方案：**
1. 存储原始不复权行情（`daily` 接口的 `open/high/low/close`）
2. 存储复权因子（`adj_factor` 接口）
3. 本地计算：`adjusted_price = raw_price * adj_factor / latest_adj_factor`

其中 `latest_adj_factor` 取截至回测结束日的最大复权因子（通常是最新交易日的值）。

### 5.4 PIT 的核心公式

```
available_date = max(ann_date, actual_download_date)
```

- `ann_date`：公告日期（Tushare 财务数据中的字段）
- `actual_download_date`：数据实际被下载到本地的日期

**为什么需要 `actual_download_date`？**
- 回测中，如果我们在 2026-07-10 回测 2026-01-01 的策略
- 2026 年年报（2025 年报）在 2026-04 发布
- 如果我们今天（2026-07-10）才下载这份数据
- 那么在回测 2026-05-01 时，这份数据是可用的（因为实际下载日期 2026-07-10 > 2026-05-01）

**但在实际回测中，我们通常假设：**
- 财务数据在 `ann_date` 当天就可用
- 不考虑数据延迟（除非回测历史数据时，数据确实是在某个日期之后才被拉取）

**简化方案：** 只用 `ann_date` 作为 `available_date`，不考虑下载日期。这是大多数量化框架的做法。

---

## 6. 配置管理

```yaml
# config/quant.yaml
tushare:
  token: ${TUSHARE_TOKEN}
  rate_limit: 200          # 每分钟请求数
  retry_times: 3
  retry_delay: 1           # 秒

data:
  raw_dir: data/raw
  normalized_dir: data/normalized
  parquet_compression: snappy
  parquet_row_group_size: 100000

pit:
  use_download_date: false  # 是否考虑下载日期（通常 false）

backtest:
  commission_rate: 0.00025  # 佣金费率（万2.5）
  commission_min: 5.0       # 最低佣金
  stamp_tax_rate: 0.001     # 印花税（千1，卖出）
  transfer_fee_rate: 0.00001  # 过户费
  slippage_rate: 0.001      # 滑点（千1）
  volume_limit_pct: 0.02    # 成交量限制（当日成交额的2%）
  lot_size: 100             # 最小交易单位

factors:
  neutralize: true          # 是否行业中性化
  standardize: zscore       # 标准化方法：zscore / rank / minmax
  ic_window: 20             # IC 计算窗口（交易日）
```

---

## 7. 模块间依赖关系

```
data/schemas.py          ← 所有模块引用（定义每张表的 schema）
data/collector.py        ← 依赖 tushare 库，写入 raw/
data/normalize.py        ← 读取 raw/，写入 normalized/
data/pit.py              ← 读取 normalized/，提供 PIT 查询
data/quality.py          ← 读取 raw/ 和 normalized/，输出质量报告

factors/registry.py      ← 依赖 data/pit.py
factors/base_factors.py  ← 依赖 registry.py + data/pit.py
factors/ic_analysis.py   ← 依赖 registry.py + data/pit.py

backtest/engine_v2.py    ← 依赖 data/pit.py + factors/registry.py
providers/tushare_provider.py ← 读取 normalized/（替代实时 API 调用）
```

---

## 8. 与现有系统的集成点

| 现有模块 | 改造内容 | 影响范围 |
|----------|----------|----------|
| `providers/tushare_provider.py` | 从实时 Tushare API 调用改为读本地 Parquet | 内部实现，接口不变 |
| `services/kline_store.py` | 从 SQLite 改为读 Parquet | 内部实现，接口不变 |
| `backtest/engine.py` | 保留旧引擎，新增 `engine_v2.py` | 不影响现有功能 |
| `providers/trading_calendar.py` | 从 Tushare 实时查询改为读本地 `trade_cal` Parquet | 内部实现 |
| `providers/stock_status.py` | 从实时查询改为读本地 PIT 数据 | 内部实现 |
| `providers/adjustment_manager.py` | 从读 adj_factor 改为读本地 Parquet | 内部实现 |

**核心原则：** Provider 接口不变，只改内部数据源。上层业务代码（策略、回测、模拟交易）不需要修改。
