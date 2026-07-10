# Tushare 数据分层指南（tq经验总结）

## 第一梯队：量化底座（必接）

### 1. 日线行情 + 复权 + 交易状态
- `daily` / `adj_factor` / `pro_bar` / `trade_cal` / `stock_basic` / `stk_limit`
- 适用：趋势动量、波动率、横截面多因子、小市值、低估值、行业轮动、周/月频调仓
- ⚠️ `pro_bar` 前复权会随 `end_date` 动态变化 → **存原始不复权 + 复权因子，本地自行计算**

### 2. daily_basic（2000积分，最实用）
- PE/PE TTM、PB、PS/PS TTM、股息率、换手率、自由流通换手率
- 总市值/流通市值、总股本/自由流通股本、量比、涨跌停状态
- 适用：小市值、价值、质量、流动性、拥挤度因子
- 5000积分取消常规总量限制

### 3. 财务报表与财务指标（2000积分）
- `income` / `balancesheet` / `cashflow` / `fina_indicator`
- `forecast` / `express` / `dividend` / `disclosure_date` / `fina_mainbz`
- 适用：ROE/ROIC/毛利率/现金流质量、营收利润增速、盈利稳定性、资产负债率、业绩超预期、高股息、基本面质量因子
- ⚠️ **必须按公告日期做 Point-in-Time（PIT）数据**，否则产生严重未来函数

### 4. 指数成分、权重和申万行业（2000积分）
- `index_weight` / `index_member_all` / `index_classify` / `index_daily` / `index_dailybasic`
- 适用：沪深300/中证500/中证1000增强、行业中性化、风格暴露、指数调入调出事件、相对基准收益

---

## 第二梯队：事件策略（按需接入）

| 接口 | 用途 | 积分 |
|------|------|------|
| `repurchase` | 股票回购公告后中期表现 | 2000 |
| `share_float` | 限售解禁压力 | 3000 |
| `stk_holdertrade` | 股东增减持风险 | 2000 |
| `stk_holdernumber` | 股东户数下降 | 2000 |
| `pledge_detail` / `pledge_stat` | 股权质押 | 2000 |
| `top_list` / `top_inst` | 龙虎榜机构参与 | 2000 |
| `block_trade` | 大宗交易 | 2000 |
| `margin` / `margin_detail` | 融资融券余额变化 | 2000 |
| `hk_hold` | 北向持仓变化 | 2000 |
| `moneyflow` | 资金流向（⚠️仅辅助信号，不同数据商定义不同） | 2000 |

---

## 第三梯队：按品种选择

- **ETF/公募基金**：净值、日线、持仓、分红
- **期货**：日线、持仓排名、仓单、结算参数
- **期权**：合约和日线
- **可转债**：基础信息、发行、日线
- **宏观**：SHIBOR、LPR等

基金/期货/可转债日频数据通常 2000 积分可用。
