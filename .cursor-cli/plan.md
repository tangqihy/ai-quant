# AI-Quant 前端优化开发计划

## 项目分析

### 当前技术栈
- React 18 + TypeScript
- Vite 构建工具
- Ant Design 5.x UI组件库
- ECharts 图表库
- React Router 6
- Day.js 日期处理

### 现有页面结构
```
frontend/src/
├── pages/
│   ├── Dashboard.tsx      # 仪表盘 - 已美化
│   ├── StockList.tsx      # 股票列表 - 基础完成
│   ├── BacktestConfig.tsx # 回测配置 - 基础完成
│   └── Analysis.tsx       # 收益分析 - 基础完成
├── components/
│   ├── charts/
│   │   └── RevenueChart.tsx
│   └── layout/
│       └── MainLayout.tsx
├── services/
│   └── api.ts
└── App.tsx
```

---

## Phase 1: 动效增强与用户体验 (2-3天)

### 1.1 全局加载动画组件
**目标**: 创建统一的加载体验

**新建文件**:
- `frontend/src/components/common/PageLoading.tsx` - 全页加载动画
- `frontend/src/components/common/SkeletonCard.tsx` - 卡片骨架屏
- `frontend/src/components/common/DataLoading.tsx` - 数据加载状态

**技术方案**:
- 使用 Framer Motion 或 CSS Animation
- 设计品牌色系的加载动画（蓝色 #1890ff 主题）
- 支持多种尺寸：fullscreen / inline / overlay

### 1.2 页面切换过渡效果
**修改文件**:
- `frontend/src/App.tsx` - 添加路由过渡动画
- `frontend/src/components/layout/MainLayout.tsx` - 内容区域动画包装

**技术方案**:
- React Transition Group 或 Framer Motion
- 淡入淡出 + 轻微位移效果
- 保持60fps流畅度

### 1.3 卡片和数据展示动效
**修改文件**:
- `frontend/src/pages/Dashboard.tsx` - 统计卡片入场动画
- `frontend/src/pages/StockList.tsx` - 表格行 hover 效果

**动效细节**:
- 卡片 hover: scale(1.02) + shadow 增强
- 数字变化: CountUp 动画效果
- 表格行: 斑马纹 + hover 高亮

---

## Phase 2: 自选股分组管理系统 (4-5天)

### 2.0 需求调整
- 股票详情页**仅对自选股票开放**
- 自选股支持**多分组管理**（一个股票可在多个分组）
- 新增"自选管理"独立页面

### 2.1 数据结构设计
```typescript
// 自选股数据结构
interface WatchlistGroup {
  id: string;
  name: string;           // 分组名称：如"科技股"
  color: string;          // 分组颜色标识
  stocks: WatchlistItem[];
  createdAt: number;
}

interface WatchlistItem {
  symbol: string;         // 股票代码
  name: string;           // 股票名称
  addedAt: number;        // 添加时间
  note?: string;          // 用户备注
  groups: string[];       // 所属分组ID列表
}

// localStorage key: ai-quant-watchlists-v1
```

### 2.2 新建文件清单
**核心组件**:
- `frontend/src/types/watchlist.ts` - 类型定义
- `frontend/src/hooks/useWatchlist.ts` - 自选股状态管理 Hook
- `frontend/src/services/watchlistStorage.ts` - localStorage 持久化

**页面**:
- `frontend/src/pages/WatchlistManager.tsx` - 自选管理主页面
- `frontend/src/pages/StockDetail.tsx` - 股票详情页（仅自选可访问）

**组件**:
- `frontend/src/components/watchlist/GroupCard.tsx` - 分组卡片
- `frontend/src/components/watchlist/StockTag.tsx` - 股票标签（显示所属分组）
- `frontend/src/components/watchlist/AddToWatchlistModal.tsx` - 添加到自选弹窗
- `frontend/src/components/watchlist/GroupSelector.tsx` - 分组选择器
- `frontend/src/components/charts/KLineChart.tsx` - K线图

### 2.3 路由配置修改
**修改文件**: `frontend/src/App.tsx`
```typescript
// 新路由
/stocks              -> StockList (原列表，添加"加自选"按钮)
/watchlist           -> WatchlistManager (自选管理)
/stocks/:symbol      -> StockDetail (仅当在自选中时允许访问)
```

### 2.4 各页面改造细节

#### StockList.tsx 改造
- 每行添加"⭐ 加自选"按钮
- 已自选股票显示分组标签
- 点击股票代码：如果在自选中则跳转详情，否则提示先添加自选

#### WatchlistManager.tsx 布局
```
┌─────────────────────────────────────────────┐
│  标题: 我的自选                    [+新建分组] │
├─────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐            │
│  │ 📁 科技股    │  │ 📁 价值股    │            │
│  │   12只      │  │   8只       │            │
│  │ [管理][删除] │  │ [管理][删除] │            │
│  └─────────────┘  └─────────────┘            │
├─────────────────────────────────────────────┤
│  全部自选股票 (20只)                           │
│  ┌──────────────────────────────────────┐    │
│  │ 代码   名称   价格   涨跌幅   所属分组   │    │
│  │ 600519 茅台   1800   +1.2%   价值股     │    │
│  │ 000001 平安   12.5   -0.5%   价值股,金融 │    │
│  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

#### StockDetail.tsx 权限控制
```typescript
// 进入页面时检查
const { isInWatchlist } = useWatchlist();
if (!isInWatchlist(symbol)) {
  message.warning('该股票不在您的自选列表中');
  navigate('/watchlist');
  return;
}
```

### 2.2 页面布局设计
```
StockDetail 页面结构:
┌─────────────────────────────────────┐
│  股票基本信息 (名称、代码、价格、涨跌幅)    │
├─────────────────────────────────────┤
│                                     │
│         K线走势图 (ECharts)          │
│                                     │
├─────────────────────────────────────┤
│  技术指标区 | 成交量 | MACD | RSI     │
├─────────────────────────────────────┤
│  关键数据: 市值 | 市盈率 | 换手率...   │
└─────────────────────────────────────┘
```

### 2.3 API 接口扩展
**修改文件**:
- `frontend/src/services/api.ts`
  - 添加 `getStockDetail(symbol)` - 股票详细信息
  - 添加 `getStockKLine(symbol, period)` - K线数据
  - 添加 `getStockIndicators(symbol)` - 技术指标

### 2.4 交互功能
- 时间周期切换: 日K / 周K / 月K
- 指标叠加: MA5 / MA10 / MA20 / MA60
- 缩放和平移: ECharts dataZoom

---

## Phase 3: 暗色模式 (2-3天)

### 3.1 主题配置系统
**新建文件**:
- `frontend/src/styles/theme.ts` - 主题配置对象
- `frontend/src/hooks/useTheme.ts` - 主题切换 Hook
- `frontend/src/components/common/ThemeToggle.tsx` - 主题切换按钮

**技术方案**:
- Ant Design 5.x ConfigProvider 主题配置
- CSS Variables 实现平滑过渡
- localStorage 持久化用户偏好

### 3.2 颜色映射表
```typescript
const lightTheme = {
  bgPrimary: '#f5f7fa',
  bgSecondary: '#ffffff',
  textPrimary: '#262626',
  textSecondary: '#8c8c8c',
  border: '#f0f0f0',
  // ...
};

const darkTheme = {
  bgPrimary: '#141414',
  bgSecondary: '#1f1f1f',
  textPrimary: '#ffffff',
  textSecondary: '#a6a6a6',
  border: '#434343',
  // ...
};
```

### 3.3 组件适配
**需修改的文件**:
- `frontend/src/components/layout/MainLayout.tsx` - 侧边栏和头部
- `frontend/src/pages/Dashboard.tsx` - 卡片背景
- `frontend/src/pages/StockList.tsx` - 表格样式
- `frontend/src/pages/BacktestConfig.tsx` - 表单区域
- `frontend/src/pages/Analysis.tsx` - 图表配色

### 3.4 图表暗色适配
- ECharts 主题切换
- 坐标轴颜色、网格线调整
- Tooltip 样式适配

---

## 依赖安装清单

```bash
cd frontend

# 动效库
pnpm add framer-motion

# 数字动画
pnpm add react-countup

# 图标增强 (Ant Design 已包含大部分)
# 无需额外安装

# 主题管理 (使用 Ant Design 内置 ConfigProvider)
# 无需额外安装
```

---

## 实施顺序建议

### 推荐方案 A: 渐进式迭代
1. **Week 1**: Phase 1 (动效) → 快速看到效果
2. **Week 2**: Phase 3 (暗色模式) → 提升用户体验
3. **Week 3**: Phase 2 (股票详情页) → 核心功能增强

### 推荐方案 B: 功能优先 (采用)
1. **Week 1**: Phase 2 (自选股分组管理 + 详情页权限) → 核心功能
2. **Week 2**: Phase 1 (动效) → 体验优化
3. **Week 3**: Phase 3 (暗色模式) → 锦上添花

---

## 验收标准

### Phase 1
- [ ] 所有页面有统一的加载状态
- [ ] 页面切换有平滑过渡动画
- [ ] Dashboard 数字有计数动画
- [ ] 卡片 hover 有明显反馈

### Phase 2
- [ ] 点击股票列表可进入详情页
- [ ] K线图支持缩放和时间切换
- [ ] 显示至少 3 个技术指标
- [ ] 响应式布局正常

### Phase 3
- [ ] 一键切换明暗主题
- [ ] 刷新后保持主题偏好
- [ ] 所有组件正确适配暗色
- [ ] 图表在暗色下可读性良好

---

## 风险评估

| 风险点 | 影响 | 缓解措施 |
|--------|------|----------|
| 动效性能问题 | 中 | 使用 CSS transform, 避免重排 |
| ECharts 暗色适配复杂 | 低 | 使用官方 dark 主题作为基础 |
| 移动端适配 | 中 | 优先桌面端，移动端后续迭代 |

---

*计划制定时间: 2026-03-06*
*负责人: 小猪 🐷*
