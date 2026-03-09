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
| AkShare 网络问题排查 | 小猪 | ⚠️ 阻塞 | 东方财富数据源连接被拒，可能是服务器IP限流 |

---

## 待办 📋

### Phase 1: 部署 & CI/CD
- [x] 配置 GitHub Secrets — tq ✅
- [x] 小猪服务器 clone 代码 — 小猪 ✅
- [x] 小猪服务器环境搭建（Python、Node、pnpm、pm2）— 小猪 ✅
- [x] 前后端 build 验证通过 — 小猪 ✅
- [x] nginx 反向代理配置（端口3000）— 小猪 ✅
- [x] pm2 进程管理配置 — 小猪 ✅
- [x] 后端 pytest 集成到 CI — 小猪 ✅
- [ ] 首次完整 CI/CD 部署测试 — 待触发

### Phase 2: 前后端联调
- [x] 创建前端 API 服务层（axios 封装）— 小猪 ✅
- [x] Dashboard 仪表盘对接后端实时数据 — 小猪 ✅
- [x] StockList 股票列表对接 — 小猪 ✅
- [x] K线图组件对接 — 小猪 ✅
- [x] BacktestConfig 回测配置对接 — minimax ✅
- [x] Analysis 收益分析对接回测API — 小猪 ✅

### Phase 3: 功能完善
- [x] 回测引擎基础版（MA交叉策略）— minimax ✅
- [x] 修复 backtest_service 日期格式兼容 — 小猪 ✅
- [ ] 添加后端单元测试（pytest）— minimax
- [ ] 回测结果存储和查询 — minimax
- [ ] 图表展示优化 — 小猪
- [ ] AkShare 网络稳定性优化（重试/缓存）— 待定
- [ ] README 更新 — 待定

---

## 已知问题 ⚠️

- AkShare 东方财富数据源在服务器上连接不稳定（RemoteDisconnected），可能需要加代理或换数据源

---

## 完成日志 ✅

| 日期 | 完成内容 | 负责人 |
|------|----------|--------|
| 2026-02-28 | 初始化项目 + CI/CD | minimax |
| 2026-02-28 | 服务器环境搭建 + build 验证 | 小猪 |
| 2026-02-28 | GitHub Secrets 配置 | tq |
| 2026-02-28 | nginx + pm2 部署，前端API对接(Dashboard/StockList/KLine) | 小猪 |
| 2026-02-28 | 回测引擎基础版 + BacktestConfig对接 | minimax |
| 2026-02-28 | Analysis收益分析对接 + 日期格式bug修复 + dayjs依赖 | 小猪 |
