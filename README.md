# AI量化交易系统

> 基于 React + FastAPI 的量化交易回测平台

## 项目简介

一个完整的A股量化交易回测系统，支持：
- 📊 股票数据查询（实时行情、历史K线）
- ⚙️ 回测引擎（MA交叉策略）
- 📈 收益分析（收益率、最大回撤、胜率）
- 🔄 CI/CD 自动化部署

## 技术栈

### 前端
- React 18 + TypeScript
- Vite 构建工具
- Ant Design UI组件库
- ECharts 图表库
- React Router 路由

### 后端
- Python 3.11 + FastAPI
- AkShare 金融数据源
- Pandas 数据处理

### 部署
- GitHub Actions CI/CD
- PM2 进程管理
- Nginx 反向代理

## 项目结构

```
ai-quant/
├── frontend/                 # React前端
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   │   ├── Dashboard.tsx    # 仪表盘
│   │   │   ├── StockList.tsx    # 股票列表
│   │   │   ├── BacktestConfig.tsx  # 回测配置
│   │   │   └── Analysis.tsx      # 收益分析
│   │   ├── components/     # 公共组件
│   │   │   └── charts/     # 图表组件
│   │   └── services/       # API服务
│   └── package.json
│
├── app/                    # FastAPI后端
│   ├── api/
│   │   └── routes.py      # API路由
│   ├── services/
│   │   ├── stock_service.py    # 股票数据服务
│   │   ├── backtest_service.py # 回测引擎
│   │   └── storage_service.py  # 结果存储
│   └── main.py            # 应用入口
│
├── tests/                  # 单元测试
│   └── test_backtest.py
│
├── .github/workflows/      # CI/CD配置
│   └── ci-cd.yml
│
├── requirements.txt        # Python依赖
└── TASKS.md               # 任务跟踪
```

## 快速开始

### 前端运行

```bash
cd frontend
pnpm install
pnpm dev
```

访问 http://localhost:5173

### 后端运行

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置访问密码（可选，未设置则无法登录）
export QUANT_AUTH_PASSWORD=your_password

# 启动服务
uvicorn app.main:app --reload --port 8000
```

API文档：http://localhost:8000/docs

## API 接口

除鉴权接口外，所有 `/api/*` 接口均需在请求头中携带有效 token：`Authorization: Bearer <token>`。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 登录，body: `{"password":"xxx"}`，返回 `token` |
| `/api/auth/verify` | GET | 验证当前 token 是否有效 |
| `/api/stocks` | GET | 获取股票列表 |
| `/api/stocks/{symbol}/history` | GET | 获取历史K线 |
| `/api/quotes/realtime` | GET | 批量实时行情 |
| `/api/backtest` | POST | 运行回测 |
| `/api/backtest` | GET | 历史回测列表 |
| `/api/backtest/{task_id}` | GET | 回测详情 |

## 回测策略

### MA交叉策略
- 短期均线上穿长期均线 → 买入
- 短期均线下穿长期均线 → 卖出

参数：
- `short_window`: 短期均线周期（默认5）
- `long_window`: 长期均线周期（默认20）

## 部署

### 部署到服务器

**重要：** 后端使用 `app` 包结构，必须在项目根目录下并设置 `PYTHONPATH`，否则会报 `ModuleNotFoundError: No module named 'app'`。

推荐使用项目自带的 `ecosystem.config.js` 和 `start.sh`（已正确设置 PYTHONPATH 和 uvicorn）：

```bash
# 克隆代码
git clone git@github.com:tangqihy/ai-quant.git
cd ai-quant

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && pnpm install && pnpm build

# 使用 ecosystem 启动（start.sh 会设置 PYTHONPATH 并启动 uvicorn）
pm2 start ecosystem.config.js

# 验证接口
curl http://localhost:8000/health
curl "http://localhost:8000/api/stocks?page=1&page_size=5"
```

**手动启动（开发或调试）：**

```bash
# 方式一：使用 start.sh（推荐）
./start.sh

# 方式二：设置 PYTHONPATH 后用 uvicorn
export PYTHONPATH=/root/.openclaw/workspace/ai-quant   # 或 export PYTHONPATH=$(pwd)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 方式三：设置 PYTHONPATH 后直接运行 main.py
export PYTHONPATH=$(pwd)
python app/main.py
```

**若 500 错误：** 查看 `pm2 logs quant-backend`，常见原因：网络/akshare 数据源异常、或依赖未安装。

### CI/CD 自动部署

推送到 main 分支自动触发：
1. 后端 pytest 测试
2. 前端 build
3. 部署到服务器

## 贡献

任务跟踪：查看 TASKS.md

## 许可证

MIT
