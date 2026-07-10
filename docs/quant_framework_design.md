# A股量化最低成本框架（tq设计）

## 技术栈

```
Tushare
    ↓
Downloader / Scheduler
    ↓
Raw Parquet
    ↓
DuckDB
    ↓
Point-in-Time 数据层
    ↓
因子计算
    ↓
组合构建与回测
    ↓
模拟盘 / 券商执行适配器
```

## 推荐组件

| 模块 | 建议 |
|------|------|
| 语言 | Python |
| 原始存储 | Parquet，按接口和交易日期分区 |
| 查询引擎 | DuckDB |
| 数据处理 | Polars 或 Pandas |
| 调度 | 系统 cron / Windows 任务计划 |
| 配置 | YAML + Pydantic |
| 回测 | 初期自己写向量化日频回测 |
| 报表 | Plotly、Matplotlib 或 Streamlit |
| 元数据 | SQLite |
| 部署 | PC、NAS或现有服务器 |

### ❌ 不建议一开始上

- Kafka、Kubernetes、Airflow、ClickHouse、微服务、实时流计算
- 对个人日频量化，工程复杂度会超过策略本身

---

## 数据分层设计

### Raw 层
完全保留 Tushare 返回结果，不做覆盖式清洗：
```
data/raw/
├── daily/trade_date=20260709/*.parquet
├── daily_basic/trade_date=20260709/*.parquet
├── adj_factor/trade_date=20260709/*.parquet
├── income/period=20260331/*.parquet
└── index_weight/index_code=000300.SH/*.parquet
```
好处：上游纠错后重建、对比数据版本、排查复权异常、重跑因子

### Normalize 层
统一：日期类型、股票代码、单位、空值、去重主键、公告时间、数据版本

关键主键：
- daily: `(ts_code, trade_date)`
- financial: `(ts_code, ann_date, end_date, report_type)`
- index_weight: `(index_code, con_code, trade_date)`

### PIT 层（最重要）
```python
available_date = max(ann_date, actual_download_date)
```
在回测日期 T，只能使用 `available_date <= T` 的数据。
业绩预告、财报、指数成分、ST状态、退市状态都要遵守。

---

## 回测必须模拟的A股规则

1. **涨跌停限制** — 一字涨停不能买，一字跌停不能卖
2. **停牌不能交易**
3. **100股整数手** 成交
4. **T+1** — 今天买的今天不能卖
5. **费用** — 佣金最低收费 + 印花税 + 过户费
6. **信号延迟** — 当日收盘信号，最早次日成交
7. **排除异常状态** — 未上市、已退市、特殊状态证券
8. **成交量约束** — 限制为当日成交额的 1%～5%
