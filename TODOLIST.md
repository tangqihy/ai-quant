# AI量化交易系统 - 任务清单

## 项目信息
- **仓库**: https://github.com/tangqihy/ai-quant
- **成员**: minimax(云端开发), 小猪(服务器部署+前端对接)

## 协作规则
- 飞书：发布任务、汇报、总结
- GitHub：实际分工，通过此文件协调任务
- 各自通过 heartbeat 定时 git pull 更新任务状态
- 遇到阻塞或需要人类决策 → 飞书找 tq

---

## 进行中 🚧

| 任务 | 负责人 | 状态 | 备注 |
|------|--------|------|------|
| 前端 API 服务层搭建 | 小猪 | 🔄 进行中 | axios 封装，对接后端 |
| 服务器部署环境准备 | 小猪 | 🔄 进行中 | pm2 + nginx |

---

## 待办 📋

### Phase 1: 部署 & CI/CD
- [ ] 配置 GitHub Secrets（SERVER_HOST, SERVER_USER, SERVER_SSH_KEY）— 需要 tq 协助
- [x] 小猪服务器 clone 代码 — 小猪 ✅
- [x] 小猪服务器环境搭建（Python、Node、pnpm、pm2）— 小猪 ✅
- [x] 前后端 build 验证通过 — 小猪 ✅
- [ ] nginx 反向代理配置 — 小猪
- [ ] pm2 进程管理配置 — 小猪
- [ ] 后端 pytest 集成到 CI — 小猪
- [ ] 首次完整部署测试 — 小猪

### Phase 2: 前后端联调
- [ ] 创建前端 API 服务层（axios 封装）— 小猪
- [ ] Dashboard 仪表盘对接后端实时数据 — 小猪
- [ ] StockList 股票列表对接 `/api/stocks` + `/api/quotes/realtime` — 小猪
- [ ] K线图组件对接 `/api/stocks/{symbol}/history` — 小猪
- [ ] BacktestConfig 回测配置对接 `/api/backtest` — 小猪
- [ ] Analysis 收益分析对接回测结果 API — 小猪

### Phase 3: 功能完善
- [ ] 完善回测引擎（目前 `/api/backtest` 只是占位）— minimax
- [ ] 添加后端单元测试（pytest）— minimax
- [ ] 回测结果存储和查询 — minimax
- [ ] 图表展示优化 — 小猪
- [ ] README 更新 — 待定

---

## 完成日志 ✅

| 日期 | 完成内容 | 负责人 |
|------|----------|--------|
| 2026-02-28 | 初始化项目 + CI/CD | minimax |
| 2026-02-28 | 服务器环境搭建 + build 验证 | 小猪 |
