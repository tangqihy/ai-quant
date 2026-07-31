# 07 - 股票无限画布（Stock Canvas）

> 模块状态：设计阶段
> 创建日期：2026-07-31
> 作者：tq + Hermes

---

## 1. 核心理念

**不是画图工具，是结构化的个股研究知识库。**

传统问题：
- 研究散落在聊天记录、笔记本、脑子里
- 决策时靠记忆，容易"刻舟求剑"
- 情绪来了重仓，没有对照清单

Stock Canvas 解决的是：**把研究沉淀成可查询、可对照、可回顾的结构化数据，辅助理性决策。**

### 1.1 双通道架构

```
┌─────────────────────────────────────────────────────┐
│                    写入通道（高频）                    │
│  微信/飞书 IM  →  CLI / MCP  →  Canvas API  →  SQLite│
│  自然语言输入     结构化解析      REST接口      持久化   │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                    浏览通道（低频）                    │
│  浏览器  →  React Flow 画布  →  Canvas API  →  SQLite │
│  可视化     无限画布+卡片        查询接口      持久化   │
└─────────────────────────────────────────────────────┘
```

**设计原则：**
1. **IM-first**：80%的操作通过聊天完成，不需要打开浏览器
2. **结构化存储**：自然语言输入会被解析为结构化卡片
3. **画布可视化**：前端用于浏览全局、发现关联、辅助决策
4. **CLI/MCP 双入口**：CLI 供脚本/手动调用，MCP 供 Agent 自动调用

---

## 2. 数据模型

### 2.1 Canvas（画布）

每只股票一个画布，以股票代码为唯一标识。

```python
class Canvas(BaseModel):
    id: str                    # 自增ID
    ts_code: str               # 股票代码 "002624.SZ"
    name: str                  # 股票名称 "完美世界"
    status: str                # "watching" | "holding" | "sold" | "archived"
    created_at: datetime
    updated_at: datetime
    metadata: dict             # 扩展字段（成本价、仓位等）
```

### 2.2 Card（卡片）

画布上的每个节点是一张卡片，有明确的类型和结构。

```python
class CardType(str, Enum):
    # 研究类
    NOTE = "note"              # 自由笔记
    THESIS = "thesis"          # 投资论点（看多/看空/中性）
    CATALYST = "catalyst"      # 事件催化剂
    RISK = "risk"              # 风险提示

    # 数据类（系统自动生成）
    FINANCIAL = "financial"    # 财务数据快照
    VALUATION = "valuation"    # 估值分析
    SENTIMENT = "sentiment"    # 舆论情绪
    TIMELINE = "timeline"      # 关键时间节点

    # 决策类
    ENTRY_PLAN = "entry_plan"  # 入场计划（价格、仓位、条件）
    EXIT_PLAN = "exit_plan"    # 出场计划（止盈、止损）
    TRADE_RECORD = "trade_record"  # 交易记录

class Card(BaseModel):
    id: str                    # UUID
    canvas_id: str             # 所属画布
    card_type: CardType
    title: str                 # 卡片标题
    content: str               # 正文（Markdown）
    structured_data: dict      # 结构化数据（根据类型不同）
    tags: list[str]            # 标签 ["内存涨价", "半年报"]
    importance: int            # 重要性 1-5
    source: str                # 来源 "user" | "system" | "crawler"
    source_ref: str            # 来源引用（聊天记录ID、新闻URL等）
    position: dict             # 画布位置 {"x": 100, "y": 200}（前端用）
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None  # 过期时间（用于时效性信息）
```

### 2.3 Edge（关联）

卡片之间的关系。

```python
class EdgeType(str, Enum):
    SUPPORTS = "supports"      # 支持（利好→论点）
    CONTRADICTS = "contradicts"  # 矛盾（利空→看多论点）
    CAUSES = "causes"          # 因果（事件→影响）
    RELATES = "relates"        # 相关
    TRIGGERS = "triggers"      # 触发（催化剂→入场计划）

class Edge(BaseModel):
    id: str
    source_card_id: str
    target_card_id: str
    edge_type: EdgeType
    label: str | None          # 关系描述
    created_at: datetime
```

### 2.4 structured_data 各类型示例

```python
# thesis（投资论点）
{
    "direction": "bullish",    # bullish | bearish | neutral
    "confidence": 0.7,         # 置信度 0-1
    "time_horizon": "medium",  # short(< 1w) | medium(1-3m) | long(> 3m)
    "target_price": 45.0,
    "stop_loss": 28.0,
}

# catalyst（事件催化剂）
{
    "event_date": "2026-08-15",
    "event_type": "earnings",  # earnings | product | policy | macro | ipo
    "expected_impact": "bearish",  # 预期影响方向
    "actual_impact": None,     # 实际影响（事后填）
    "price_before": 32.5,
    "price_after": None,
}

# entry_plan / exit_plan
{
    "trigger_price": 28.0,     # 触发价格
    "position_pct": 0.2,       # 仓位比例
    "conditions": ["半年报低于预期", "跌破28支撑位"],
    "status": "pending",       # pending | triggered | cancelled
}

# financial（财务快照）
{
    "period": "2026Q2",
    "revenue": 15.6e8,
    "net_profit": 2.1e8,
    "pe_ttm": 25.3,
    "pb": 3.2,
    "market_cap": 350e8,
}

# sentiment（舆论情绪）
{
    "source": "eastmoney_guba",  # 数据来源
    "positive_ratio": 0.35,
    "negative_ratio": 0.45,
    "neutral_ratio": 0.20,
    "hot_topics": ["半年报", "AI游戏", "裁员"],
    "sample_count": 1200,
    "snapshot_date": "2026-07-31",
}
```

---

## 3. 写入通道：CLI / MCP

### 3.1 设计目标

用户在微信/飞书里说一句话，Hermes 解析后写入画布。

**交互示例：**

```
用户: 小米半年报可能不好，但mimo v3出来后看好，目标价50

Hermes 解析后调用:
  canvas add-card --canvas 01810.HK --type thesis \
    --title "看好小米MiMo v3+AI Agent" \
    --direction bullish --confidence 0.6 \
    --target-price 50 --time-horizon medium \
    --tags "MiMo,AI,智能家居" \
    --note "半年报可能不好看，但下半年mimo v3+AI Agent是催化剂"
```

### 3.2 CLI 命令设计

```bash
# 画布管理
canvas list                          # 列出所有画布
canvas create --code 01810.HK --name 小米集团
canvas status --code 01810.HK --status holding
canvas archive --code 01810.HK

# 卡片操作
canvas add-card --canvas <code> --type <type> [options]
canvas edit-card --card-id <id> [options]
canvas delete-card --card-id <id>
canvas list-cards --canvas <code> [--type <type>] [--tag <tag>]

# 关联操作
canvas link --from <card-id> --to <card-id> --type <edge-type> [--label "..."]

# 查询
canvas show --canvas <code>                    # 显示画布摘要
canvas search --keyword "内存涨价"              # 跨画布搜索
canvas timeline --canvas <code>                # 时间线视图
canvas decisions --canvas <code>               # 只看决策类卡片

# 系统自动任务
canvas auto-update --canvas <code>             # 自动拉取财务/估值数据
canvas sentiment-sync --canvas <code>          # 同步舆论情绪
```

### 3.3 MCP Tool 设计

供 Hermes Agent 自动调用，也支持其他 MCP 客户端。

```yaml
tools:
  # 画布 CRUD
  - name: canvas_create
    description: 为股票创建研究画布
    input:
      ts_code: string        # 股票代码
      name: string           # 股票名称
      status: string         # watching|holding|sold|archived

  - name: canvas_list
    description: 列出所有画布
    input:
      status: string | null  # 可选筛选

  - name: canvas_get
    description: 获取画布详情及所有卡片
    input:
      ts_code: string

  # 卡片 CRUD
  - name: card_add
    description: 向画布添加卡片（笔记/论点/催化剂/风险/计划等）
    input:
      ts_code: string
      card_type: string
      title: string
      content: string
      structured_data: object | null
      tags: string[] | null
      importance: number | null

  - name: card_update
    description: 更新卡片内容
    input:
      card_id: string
      title: string | null
      content: string | null
      structured_data: object | null
      tags: string[] | null
      importance: number | null

  - name: card_delete
    description: 删除卡片
    input:
      card_id: string

  # 关联
  - name: card_link
    description: 建立卡片关联
    input:
      source_card_id: string
      target_card_id: string
      edge_type: string
      label: string | null

  # 查询
  - name: canvas_search
    description: 跨画布搜索卡片
    input:
      keyword: string
      card_type: string | null
      ts_code: string | null

  - name: canvas_timeline
    description: 获取画布时间线（按日期排序的事件）
    input:
      ts_code: string

  - name: canvas_decisions
    description: 获取画布上的决策卡片（入场/出场计划）
    input:
      ts_code: string

  # 自动更新
  - name: canvas_auto_sync
    description: 自动同步财务数据、估值、舆论情绪到画布
    input:
      ts_code: string
```

### 3.4 自然语言解析策略

Hermes 在 IM 中收到消息后，通过以下策略解析为 canvas 操作：

**关键词触发：**
- 包含股票代码或名称 + 看好/看空/风险/催化剂/目标价 → 自动创建卡片
- "XX目标价Y" → thesis 卡片
- "XX风险是..." → risk 卡片
- "XX什么时候..." → timeline 卡片
- "XX半年报/财报" → catalyst 卡片

**显式命令：**
- "记录：小米..." → note 卡片
- "小米入场计划：28买20%仓位" → entry_plan 卡片
- "小米止盈40止损28" → exit_plan 卡片
- "小米卖出" → 更新 canvas status + trade_record

**被动收集：**
- 日常聊天中提到股票相关判断，Hermes 主动确认后记录
- "你刚才说的关于小米的观点，要记录到画布吗？"

---

## 4. 浏览通道：前端画布

### 4.1 技术选型

**核心：@xyflow/react (React Flow) v12**

理由：
- MIT 许可，无商业限制
- 自定义 Node = React 组件，直接嵌入 ECharts/Ant Design
- 无限画布 + 缩放 + 小地图，开箱即用
- JSON 序列化，状态存后端
- npm 周下载 9.5M，生态最成熟
- 与现有 React 18 + Ant Design + ECharts 技术栈完美匹配

### 4.2 页面结构

```
/stock-canvas                    # 画布列表页
/stock-canvas/:ts_code           # 单只股票画布页
```

**画布页布局：**

```
┌──────────────────────────────────────────────────┐
│  顶部栏：股票名 | 状态标签 | 最后更新时间 | 操作按钮 │
├──────────────────────────────────────────────────┤
│          │                                       │
│  侧边栏   │         React Flow 画布               │
│          │                                       │
│  ·全部卡片 │    ┌──────┐     ┌──────┐             │
│  ·按类型   │    │ 论点  │────▶│ 催化剂 │             │
│  ·按标签   │    │ 看多  │     │ 半年报 │             │
│  ·时间线   │    └──────┘     └──────┘             │
│  ·决策清单 │         │                             │
│          │    ┌──────┐     ┌──────┐             │
│          │    │ 风险  │     │ 入场   │             │
│          │    │ 提示  │────▶│ 计划   │             │
│          │    └──────┘     └──────┘             │
├──────────────────────────────────────────────────┤
│  底部栏：快捷操作 | 搜索 | 筛选                      │
└──────────────────────────────────────────────────┘
```

### 4.3 卡片组件设计

每种 CardType 对应一个 React 组件：

**通用卡片壳：**
```tsx
<CardShell type={card.card_type} importance={card.importance}>
  <CardTitle>{card.title}</CardTitle>
  <CardBody>{renderByType(card)}</CardBody>
  <CardMeta tags={card.tags} source={card.source} />
  <CardActions onEdit onDelete onLink />
</CardShell>
```

**各类型卡片渲染：**

| 类型 | 渲染方式 |
|------|---------|
| note | Markdown 渲染 |
| thesis | 方向标签(多/空/中) + 置信度条 + 目标价 |
| catalyst | 日期 + 事件类型标签 + 影响方向 |
| risk | 红色警告样式 + 影响评估 |
| financial | Ant Design Table (PE/PB/营收/利润) |
| valuation | ECharts PE/PB Band 图 |
| sentiment | 情绪仪表盘 + 热词云 |
| timeline | 日期轴 + 事件标记 |
| entry_plan / exit_plan | 触发条件 + 价格 + 仓位 + 状态 |
| trade_record | 买卖方向 + 价格 + 盈亏 |

### 4.4 自动布局

使用 dagre 自动布局算法，按卡片类型分层：

```
研究层（左）：thesis → catalyst → risk
数据层（中）：financial → valuation → sentiment
决策层（右）：entry_plan → exit_plan → trade_record
```

箭头表示因果/支持/矛盾关系。用户可以手动拖拽调整。

### 4.5 画布间跳转

卡片中引用其他股票时，点击可跳转到对应画布。
例：小米画布中提到"长鑫上市缓解内存涨价" → 点击跳转到长鑫画布。

---

## 5. API 设计

### 5.1 RESTful 接口

```
# 画布
GET    /api/canvas                        # 列表
POST   /api/canvas                        # 创建
GET    /api/canvas/{ts_code}              # 详情（含所有卡片和边）
PATCH  /api/canvas/{ts_code}              # 更新状态
DELETE /api/canvas/{ts_code}              # 删除

# 卡片
POST   /api/canvas/{ts_code}/cards        # 添加卡片
PATCH  /api/canvas/cards/{card_id}        # 更新卡片
DELETE /api/canvas/cards/{card_id}        # 删除卡片

# 关联
POST   /api/canvas/edges                  # 创建关联
DELETE /api/canvas/edges/{edge_id}        # 删除关联

# 查询
GET    /api/canvas/search?keyword=xxx     # 跨画布搜索
GET    /api/canvas/{ts_code}/timeline     # 时间线
GET    /api/canvas/{ts_code}/decisions    # 决策卡片
POST   /api/canvas/{ts_code}/auto-sync    # 自动同步数据
```

### 5.2 前端画布状态同步

```python
# 保存画布布局（前端拖拽后调用）
PATCH /api/canvas/{ts_code}/layout
{
    "positions": {
        "card-uuid-1": {"x": 100, "y": 200},
        "card-uuid-2": {"x": 400, "y": 150}
    },
    "viewport": {"x": 0, "y": 0, "zoom": 1}
}
```

---

## 6. 目录结构

```
ai-quant/
├── app/
│   ├── canvas/                     # 新模块
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic models (Canvas, Card, Edge)
│   │   ├── repository.py          # SQLite CRUD
│   │   ├── service.py             # 业务逻辑
│   │   ├── cli.py                 # CLI 命令入口
│   │   ├── mcp_tools.py           # MCP tool 定义
│   │   ├── auto_sync.py           # 自动数据同步（财务/估值/情绪）
│   │   └── nl_parser.py           # 自然语言解析（IM消息→结构化操作）
│   ├── api/
│   │   ├── canvas_routes.py       # REST API 路由
│   │   └── ...
│   └── main.py                    # 注册 canvas router
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── CanvasList.tsx     # 画布列表页
│   │   │   └── StockCanvas.tsx    # 单股画布页
│   │   ├── components/
│   │   │   └── canvas/
│   │   │       ├── CanvasBoard.tsx      # React Flow 画布主体
│   │   │       ├── CardShell.tsx        # 通用卡片壳
│   │   │       ├── cards/
│   │   │       │   ├── NoteCard.tsx
│   │   │       │   ├── ThesisCard.tsx
│   │   │       │   ├── CatalystCard.tsx
│   │   │       │   ├── RiskCard.tsx
│   │   │       │   ├── FinancialCard.tsx
│   │   │       │   ├── ValuationCard.tsx
│   │   │       │   ├── SentimentCard.tsx
│   │   │       │   ├── TimelineCard.tsx
│   │   │       │   ├── EntryPlanCard.tsx
│   │   │       │   ├── ExitPlanCard.tsx
│   │   │       │   └── TradeRecordCard.tsx
│   │   │       ├── CanvasSidebar.tsx    # 侧边栏
│   │   │       └── AutoLayout.tsx       # 自动布局工具
│   │   └── services/
│   │       └── api.ts                   # canvas API 调用
│   └── package.json                     # 新增 @xyflow/react 依赖
└── tests/
    └── test_canvas.py
```

---

## 7. 实施计划

### Phase 1：数据层 + CLI（1-2天）
- [ ] 数据模型（models.py）
- [ ] SQLite 表结构 + repository.py
- [ ] CLI 命令（canvas add/list/show/add-card）
- [ ] 单元测试

### Phase 2：REST API（1天）
- [ ] canvas_routes.py
- [ ] 接口测试
- [ ] 注册到 main.py

### Phase 3：前端画布（2-3天）
- [ ] 安装 @xyflow/react
- [ ] CanvasList 页面
- [ ] StockCanvas 页面 + CanvasBoard 组件
- [ ] CardShell + 各类型卡片组件（先做 note/thesis/catalyst/risk）
- [ ] 自动布局

### Phase 4：MCP + IM 集成（1-2天）
- [ ] MCP tool 定义
- [ ] 自然语言解析器（nl_parser.py）
- [ ] Hermes skill 集成（从 IM 直接写入画布）

### Phase 5：自动数据同步（1-2天）
- [ ] 财务数据自动同步（Tushare → canvas financial cards）
- [ ] 估值分析自动计算
- [ ] 舆论情绪爬虫集成

---

## 8. 与现有模块的关系

| 现有模块 | 与 Canvas 的关系 |
|---------|-----------------|
| Watchlist | Canvas 是 Watchlist 的深度版。Watchlist 管"看哪些"，Canvas 管"研究了什么" |
| Factor | 因子数据可自动写入 Canvas 的 valuation/financial 卡片 |
| Backtest | 回测策略可关联到 Canvas 的 thesis 卡片 |
| Simulation | 模拟交易记录自动写入 trade_record 卡片 |
| Risk | 风控规则可触发 Canvas 的 risk 卡片生成 |
| News | 新闻可自动关联到对应股票的 Canvas |

---

## 9. 关键设计决策

### Q: 为什么不用 Obsidian/Notion 等现有工具？
A: 需要与 Tushare 数据、ECharts 图表、交易系统深度集成。通用工具做不到自动同步财务数据和生成估值卡片。

### Q: 为什么前端用 React Flow 而不是 tldraw？
A: tldraw 许可证禁止生产环境使用（需付费）。React Flow 是 MIT 许可，且自定义 Node 天然支持嵌入 React 组件。

### Q: 为什么需要 CLI 和 MCP 两套接口？
A: CLI 供 Hermes Agent 在 IM 中调用（通过 terminal tool），MCP 供其他 Agent 或工具链调用。两套共享同一个 service 层。

### Q: 画布数据存在哪？
A: SQLite，与现有 ai-quant 的 trading/factor 数据同库。Canvas 表独立，不影响现有模块。
