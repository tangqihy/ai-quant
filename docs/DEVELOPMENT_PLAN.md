# AI-Quant 项目开发计划

> 基于现有代码分析的完整开发计划，包含性能优化、功能扩展、实盘接入、技术债务与优先级规划。

---

## 一、当前架构概览

### 1.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React 18 + TypeScript + Vite | Ant Design、ECharts、Framer Motion |
| 后端 | FastAPI + Python 3.11 | 同步接口，无异步数据层 |
| 数据 | AkShare | 东方财富 + 腾讯降级，内存缓存 + 本地 JSON |
| 回测 | 自研 BacktestEngine | 单策略 MA 交叉，Pandas 逐行循环 |
| 存储 | 文件系统 | `data/backtest_results/*.json`，无数据库 |

### 1.2 目录与职责

```
app/
├── main.py              # 入口、CORS
├── api/routes.py        # 所有 API 定义 + 部分业务逻辑
├── services/
│   ├── stock_service.py   # 行情、列表、缓存
│   ├── backtest_service.py # 回测引擎
│   └── storage_service.py  # 回测结果持久化
frontend/src/
├── pages/               # Dashboard, StockList, BacktestConfig, Analysis, StockDetail, WatchlistManager
├── components/charts/   # KLineChart, RevenueChart
├── services/api.ts      # axios 封装
```

### 1.3 已发现的问题摘要

- **数据**：股票列表全量拉取后内存分页，实时行情东方财富不稳定时逐只请求腾讯，无持久化 K 线库。
- **回测**：仅 `ma_cross` 真正实现，`dual_ma` 未实现；`df.iterrows()` 性能差；无滑点/手续费/仓位管理。
- **前端**：Dashboard 收益曲线为假数据；StockDetail 与 KLineChart 接口不一致（传 `data`/`height` 未被使用）；API 无统一错误码与重试。
- **实盘**：无券商 API、无模拟交易、无风控模块。

---

## 二、性能优化方案

### 2.1 数据获取

| 项目 | 现状 | 建议 | 优先级 |
|------|------|------|--------|
| 股票列表 | 全量拉取 + 内存分页，易超时 | 后端分页：AkShare 或本地 DB 分页查询；或预生成 `stock_list.json` 按需分片读取 | P0 |
| 列表缓存 | 内存 24h，无持久化 | 增加本地文件/Redis 缓存，启动时预热；可选用 `diskcache` 或 SQLite | P1 |
| K 线 | 每次请求实时拉取 | 引入本地 K 线存储（SQLite/Parquet），按日增量更新；接口先查本地再补全 | P0 |
| 实时行情 | 东方财富失败后逐只请求腾讯 | 限制单次 symbols 数量（如 20），超量分批；增加 2 分钟缓存 key 按 symbols 粒度 | P1 |
| 并发与超时 | 同步调用，无超时控制 | 为 AkShare 调用加 `asyncio.to_thread` + 统一超时（如 15s），避免阻塞事件循环 | P1 |

**可执行步骤：**

1. **股票列表分页**：在 `routes.py` 的 `get_stocks` 中，若 `stock_service.get_stock_list()` 返回全量，则在服务层新增 `get_stock_list_paged(market, page, page_size, search)`，内部使用缓存后的全量列表做切片，并限制 `search` 最大长度与结果上限（如 500 条）。
2. **K 线本地化**：新建 `app/services/kline_store.py`，用 SQLite 表 `(symbol, date, open, high, low, close, volume, adjust)`，`get_stock_history` 先查 DB，缺失日期再调 AkShare 并写回。
3. **缓存键与 TTL**：`DataCache` 的 key 包含 `symbol/dates/adjust`，历史 K 线 `max_age=3600`，实时行情 `max_age=120`；大批量行情请求拆分为多 key 或不分片但限制 `symbols` 数量。

### 2.2 回测引擎

| 项目 | 现状 | 建议 | 优先级 |
|------|------|------|--------|
| 循环方式 | `for i, row in df.iterrows()` | 用 NumPy/Pandas 向量化：预计算 MA 列，用 `shift` 比较产生信号，再按信号索引成交 | P0 |
| 数据结构 | 每行 Python dict | 全程 DataFrame，只在最后输出时转为 `list[dict]` | P1 |
| 多策略 | 仅 MA 交叉 | 抽象策略接口（如 `generate_signals(df) -> Series`），再统一执行引擎 | P1 |
| 滑点与费用 | 无 | 成交价 ± 滑点，每笔扣除佣金（可配置比例或最低 5 元） | P2 |

**可执行步骤：**

1. **向量化示例**（保留原有字段名与返回值结构）：

```python
# 计算信号
df['ma_short'] = df['close'].rolling(short_window).mean()
df['ma_long'] = df['close'].rolling(long_window).mean()
df['prev_ma_short'] = df['ma_short'].shift(1)
df['prev_ma_long'] = df['ma_long'].shift(1)
# 上穿：前一根 short<=long 且当前 short>long
df['buy_signal'] = (df['prev_ma_short'] <= df['prev_ma_long']) & (df['ma_short'] > df['ma_long'])
df['sell_signal'] = (df['prev_ma_short'] >= df['prev_ma_long']) & (df['ma_short'] < df['ma_long'])
# 再按 buy_signal/sell_signal 向量化计算仓位变化与资金曲线
```

2. **滑点与手续费**：在 `BacktestEngine` 中增加 `slippage_bps=5, commission_rate=0.0003, min_commission=5`，在每笔成交的 `cost`/`proceeds` 上应用后再更新 `capital` 与 `position`。

### 2.3 前端渲染

| 项目 | 现状 | 建议 | 优先级 |
|------|------|------|--------|
| 大列表 | 股票列表一页 20 条，无虚拟滚动 | 超过 50 条考虑 `react-window` 或 Ant Design Table 虚拟滚动（若支持） | P2 |
| 图表 | ECharts 全量数据 | 数据点 >2000 时做抽样或后端返回聚合后的时间序列 | P1 |
| 打包 | 已做 vendor 分包 | 路由级懒加载：`React.lazy(() => import('./pages/Analysis'))`，减少首屏体积 | P1 |
| 请求 | 无统一重试与取消 | 在 `api.ts` 里用 axios 拦截器统一重试（如 2 次）、请求超时 30s；列表/详情页用 AbortController 在切换时取消未完成请求 | P1 |

**可执行步骤：**

1. **路由懒加载**：在 `App.tsx` 中将 `Dashboard`、`StockList`、`BacktestConfig`、`Analysis`、`StockDetail`、`WatchlistManager` 改为 `React.lazy` + `Suspense`，fallback 使用现有 `PageLoading`。
2. **收益曲线数据量**：后端 `daily_values` 当前只返回最近 100 条；若前端需要完整曲线，可单独提供「净值曲线」接口，支持按周/月聚合。
3. **API 层**：封装 `request<T>(config)`，内部使用 `axios`，统一 `baseURL`、`timeout`、`onAbort` 与重试逻辑，所有 `get/post` 通过该封装调用。

---

## 三、功能丰富计划

### 3.1 策略

| 功能 | 说明 | 实现要点 |
|------|------|----------|
| 真正实现 dual_ma | 与 ma_cross 区分或合并为同一策略不同参数 | 统一为“双均线”，通过参数区分 short/long；或保留 dual_ma 为别名 |
| 策略插件化 | 支持从配置/模块加载策略 | 定义 `StrategyProtocol`：`name, params_schema, run(df, **params) -> signals`；`backtest_service` 根据 `strategy` 名选择实现 |
| 新策略示例 | RSI、布林带、MACD 等 | 先实现 1～2 个（如 RSI 超卖买、超买卖），用同一回测引擎跑 | P1 |

**可执行步骤：**

1. 在 `app/strategies/` 下新建 `base.py`（协议/基类）、`ma_cross.py`（现有逻辑迁移）、`rsi.py`（RSI 周期与阈值可配置）。
2. `BacktestEngine.run()` 接收 `strategy_id` 和 `strategy_params`，内部调用 `get_strategy(strategy_id).run(df, **strategy_params)` 得到信号序列，再统一执行买卖与资金曲线计算。
3. `GET /api/backtest/strategies` 改为从策略注册表返回，包含 `id, name, params_schema, description`。

### 3.2 指标

| 功能 | 说明 | 实现要点 |
|------|------|----------|
| 通用指标计算 | MA、EMA、RSI、MACD、布林带等 | 后端提供 `GET /api/indicators/{symbol}/series?indicator=ma&window=20&start_date=&end_date=` 或在前端用 lightweight 库计算（如 ta-lib 或 pandas 复刻） |
| K 线叠加 | 在 K 线图叠加 MA/BOLL 等 | 前端 KLineChart 支持 `overlays: [{ type: 'ma', period: 20 }]`，数据由后端或前端根据 K 线计算 | P1 |

**可执行步骤：**

1. 后端新增 `app/services/indicator_service.py`：输入 `symbol, start_date, end_date, indicator_name, params`，从 K 线库取数据，用 Pandas 计算指标，返回 `{ dates, values }` 或与 K 线合并返回。
2. 前端 KLineChart 增加 props `overlays`，请求指标接口或使用同一 K 线数据在 frontend 用简单公式计算 MA，再传入 ECharts series。

### 3.3 可视化

| 功能 | 说明 | 实现要点 |
|------|------|----------|
| Dashboard 收益曲线真实化 | 当前为随机数 | 从最近一次回测结果或指定 task_id 读取 `daily_values` 展示；或展示“示例回测”的固定 task_id | P0 |
| 回测结果与 K 线同屏 | 在 K 线上标出买卖点 | 回测结果返回 `trades` 的 date+action+price，前端在 K 线图用 markPoint 标注 | P1 |
| 多回测对比 | 多条收益曲线对比 | 后端支持批量 task_id 或一次回测多策略；前端同一图表多 series，图例区分 | P2 |
| 导出图表/报告 | 导出 PNG 或 PDF | ECharts 使用 `getDataURL('png')`；后端可提供「回测报告」HTML/PDF 生成（如 WeasyPrint） | P2 |

**可执行步骤：**

1. **Dashboard**：`RevenueChart` 改为接收 `taskId?: string` 或 `dailyValues?: { date, value }[]`，若存在则用真实数据，否则显示“暂无数据”或跳转回测页提示。
2. **买卖点标注**：Analysis 页的 KLineChart 传入 `trades={result.trades}`，KLineChart 内将 trades 转为 ECharts `markPoint` 的 data 数组。
3. **策略列表与参数**：BacktestConfig 的策略下拉与 Analysis 页的策略选择，改为请求 `GET /api/backtest/strategies` 动态生成，并支持根据 `params_schema` 渲染表单项。

---

## 四、真实交易接口接入方案

### 4.1 券商 API 与抽象

| 项目 | 说明 |
|------|------|
| 券商选择 | 国内常见：华泰、中信、国信、东方财富等，多提供 Python SDK 或 HTTP API；先选一家做对接（如券商提供的量化接口或 QMT/掘金等） |
| 抽象层 | 定义统一接口：`get_balance()`, `get_positions()`, `place_order(symbol, side, qty, price?)`, `cancel_order(order_id)`, `query_orders()`, `subscribe_quotes(symbols)` 等，再实现 `BrokerA`、`BrokerB` |
| 配置 | 券商账号、密钥、环境（实盘/模拟）通过环境变量或配置文件加载，不入库、不提交到 Git |

**可执行步骤：**

1. 新建 `app/broker/`：`base.py` 定义抽象类或 Protocol，`broker_xxx.py` 实现一家券商（或先用 Mock 实现）。
2. 配置使用 `pydantic-settings`：从 env 读取 `BROKER_TYPE=mock|xxx`、`BROKER_ACCOUNT`、`BROKER_PASSWORD` 等，仅在非 mock 时校验必填项。

### 4.2 模拟交易

| 项目 | 说明 |
|------|------|
| 目标 | 与回测共用策略逻辑，但订单发往模拟撮合，资金与持仓独立于实盘 |
| 撮合 | 用当前行情或最近收盘价模拟成交，可选滑点；订单表记录 symbol、side、qty、price、status、filled_at |
| 资金与持仓 | 独立账户表：初始资金、可用、冻结、持仓（symbol、volume、cost）、当日委托/成交 |

**可执行步骤：**

1. 新建 `app/trading/`：`sim_engine.py`（模拟撮合）、`sim_account.py`（资金与持仓）、`order_store.py`（订单持久化，可用 SQLite）。
2. 提供 `POST /api/sim/order`（下单）、`GET /api/sim/orders`、`GET /api/sim/positions`、`GET /api/sim/balance`；策略端可定时（如每分钟）根据信号调用 `POST /api/sim/order`，或单独做「模拟交易任务」从配置的策略与标的读取信号再下单。
3. 前端增加「模拟交易」菜单：账户总览、持仓、委托/成交记录、简单下单表单（可选后期再做）。

### 4.3 风控

| 项目 | 说明 |
|------|------|
| 单笔/单日限额 | 单笔最大金额、单日最大亏损比例/金额；超过则拒绝下单或停止策略 |
| 仓位上限 | 单标的仓位占比、总仓位占比 |
| 熔断 | 账户回撤超过阈值（如 5%）暂停新开仓或全部平仓 |
| 日志与告警 | 所有实盘/模拟订单与风控触发写入日志，可选告警（邮件/钉钉/飞书） |

**可执行步骤：**

1. 新建 `app/risk/`：`rules.py`（配置：单笔最大、日亏最大、单标的最大仓位等）、`checker.py`（下单前检查余额、持仓、当日亏损、回撤），在 `place_order` 调用前执行 `risk_checker.check(order, account, positions)`。
2. 风控配置可从配置文件或 DB 读取，便于按环境区分（模拟宽松、实盘严格）。
3. 实盘/模拟的每笔订单与风控拒绝原因写入 `app/data/logs/trade.log` 或 DB，便于审计。

---

## 五、技术债务与代码重构建议

### 5.1 后端

| 问题 | 位置 | 建议 |
|------|------|------|
| 业务逻辑进路由 | `routes.py` 中回测流程（取数据、跑回测、存结果） | 抽到 `app/services/backtest_runner.py` 或 `backtest_service.run_backtest_flow(symbol, config)`，路由只做参数校验与调用 | P0 |
| 策略硬编码 | `get_strategies` 返回写死的列表，且 dual_ma 未实现 | 见 3.1：策略注册表 + 真正实现或合并 dual_ma | P0 |
| 配置分散 | 缓存 TTL、数据目录等散落在代码中 | 使用 `pydantic-settings` 的 `Settings`，从 env 和 `.env` 加载，如 `CACHE_TTL_HISTORY=3600`、`DATA_DIR=./data` | P1 |
| 依赖注入 | 各 service 单例在模块内创建 | 使用 FastAPI 的 `Depends()` 注入 `StockService`、`BacktestStorage`，便于测试时替换 | P1 |
| 测试覆盖 | 仅部分路由与 storage 有测试，且 storage 测试写错目录 | `test_storage.py` 中应 mock 或替换 `STORAGE_DIR` 为临时目录（当前写到 `test_backtest_results` 但实际仍用 `STORAGE_DIR`），见下方说明 | P0 |
| 类型与校验 | 部分接口未严格校验 symbol 格式、日期范围 | 使用 Pydantic 模型校验 symbol（6 位数字）、start_date/end_date 合法性 | P1 |

**test_storage 问题说明：**  
`TestBacktestStorage` 里 `self.test_dir` 被赋值但 `BacktestStorage.save_result` 仍使用模块级 `STORAGE_DIR`，因此测试会写入正式目录。应在测试中 monkeypatch `storage_service.STORAGE_DIR` 为 `self.test_dir`，或让 `BacktestStorage` 支持通过构造函数注入存储路径。

### 5.2 前端

| 问题 | 位置 | 建议 |
|------|------|------|
| KLineChart 接口不一致 | `StockDetail` 传 `data={klineData}`、`height={400}`，KLineChart 只接受 `symbol` | 统一接口：要么 KLineChart 只接受 `symbol` 并自己请求（则 StockDetail 只传 `symbol`，并修 getStockHistory 第二个参数为 start/end）；要么 KLineChart 支持 `data`+`height`，由父组件请求后传入。推荐后者便于复用与测试 | P0 |
| getStockHistory 参数错误 | StockDetail 中 `getStockHistory(symbol, 'daily')` | API 定义是 `startDate?, endDate?, adjust`，应传日期范围而非 `'daily'`；若需「最近一年」可在前端用 dayjs 算 start/end | P0 |
| RevenueChart 假数据 | Dashboard 使用随机数 | 见 3.3：改为真实回测结果或“暂无数据” | P0 |
| API 类型与错误 | api.ts 返回类型不完整，错误未统一 | 定义 `ApiResponse<T>`，后端统一 `{ success, data?, error? }`；前端在 axios 响应拦截器里检查 `success`，失败时抛出带 `error` 的异常，便于页面统一提示 | P1 |
| 重复请求 | 列表与详情可能重复请求同一 symbol 行情 | 可引入 React Query 或 SWR，按 symbol 缓存；或简单用 Context 缓存当前页的 quotes | P2 |

### 5.3 通用

| 项目 | 建议 |
|------|------|
| 日志 | 使用 `structlog` 或 `loguru`，请求 ID、symbol、耗时统一记录，便于排查数据与回测问题 |
| 文档 | FastAPI 已有 OpenAPI，可补充「回测参数说明」「策略列表」「错误码」在 description 中；前端可考虑用 OpenAPI 生成 api.ts 类型与请求函数（可选） |
| 错误码 | 定义业务错误码（如 DATA_NOT_ENOUGH、SYMBOL_INVALID、BACKTEST_FAILED），后端返回 `error_code`+`message`，前端根据 code 做文案或跳转 |

---

## 六、优先级排序与时间规划

### 6.1 优先级矩阵

| 优先级 | 含义 | 建议时间 |
|--------|------|----------|
| P0 | 阻塞性问题/错误/一致性，必须先修 | 1～2 周内 |
| P1 | 核心体验与可扩展性，短期要做 | 2～6 周 |
| P2 | 体验增强与中长期能力 | 1～3 个月 |

### 6.2 建议排期（按阶段）

**Phase A：修坑与一致性（1～2 周）**

- 修复 StockDetail 与 KLineChart 的 props 及 `getStockHistory(symbol, 'daily')` 调用。
- Dashboard 收益曲线改为真实数据或“暂无数据”。
- 回测：策略列表与 dual_ma 要么实现要么从列表移除；业务逻辑从 routes 抽到 service。
- 测试：修正 test_storage 的 STORAGE_DIR 使用，保证回测与存储测试不写生产目录。

**Phase B：性能与数据（2～4 周）**

- 股票列表：分页/缓存策略落地；K 线本地化（SQLite/Parquet）与增量更新。
- 回测引擎：向量化改造 + 滑点/手续费。
- 前端：路由懒加载、API 超时与重试、收益曲线数据量控制。

**Phase C：策略与可视化（2～4 周）**

- 策略插件化与 1～2 个新策略（如 RSI）。
- 指标服务与 K 线叠加。
- K 线买卖点标注、BacktestConfig/Analysis 策略动态拉取。

**Phase D：模拟交易与风控（4～8 周）**

- 券商抽象层 + Mock 实现。
- 模拟撮合、账户与订单持久化、REST 接口。
- 风控规则与下单前检查。
- 前端模拟交易页（账户、持仓、委托）。

**Phase E：实盘与运维（按需）**

- 对接一家真实券商 API。
- 日志、告警、错误码与文档完善。
- 可选：回测报告导出、多回测对比。

### 6.3 里程碑与交付物

| 里程碑 | 交付物 | 目标时间 |
|--------|--------|----------|
| M1 | 前端无错误调用、Dashboard 真实/空状态、回测逻辑归位、测试可重复跑 | 2 周 |
| M2 | K 线本地化可用、回测向量化+费用、前端懒加载与 API 健壮性 | 6 周 |
| M3 | 策略可插拔、2+ 策略、指标与 K 线增强 | 10 周 |
| M4 | 模拟交易全流程 + 风控 | 18 周 |
| M5 | 实盘对接（可选） | 按需 |

---

## 七、附录：关键代码索引

- 股票数据与缓存：`app/services/stock_service.py`（DataCache、get_stock_list、get_stock_history、get_realtime_quotes）
- 回测入口与引擎：`app/api/routes.py`（POST /backtest）、`app/services/backtest_service.py`（BacktestEngine.run）
- 回测存储：`app/services/storage_service.py`（STORAGE_DIR、save_result、list_results）
- 前端 API：`frontend/src/services/api.ts`
- K 线图：`frontend/src/components/charts/KLineChart.tsx`（仅 symbol）
- 收益图：`frontend/src/components/charts/RevenueChart.tsx`（假数据）
- StockDetail 调用：`frontend/src/pages/StockDetail.tsx`（getStockHistory(symbol, 'daily')，KLineChart data/height）

以上计划可直接按 Phase 拆分为 GitHub Issues 或 TODOLIST 条目，便于分工与跟踪。
