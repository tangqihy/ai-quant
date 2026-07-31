# 07 - 股票无限画布（Stock Canvas）

> 模块状态：MVP 已落地（Phase 1/3/4 完成，Phase 2 的 Hermes 集成待做）
> 创建日期：2026-07-31
> 修订日期：2026-08-01（对齐代码现状、简化架构、重排实施顺序；Phase 1/3/4 已交付）
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
│                 写入通道（高频，IM-first）             │
│  微信/飞书 IM → Hermes Agent → CLI/MCP → service     │
│  自然语言输入    LLM 解析意图    进程内调用  → SQLite │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 浏览通道（低频）                       │
│  浏览器 → React Flow 画布 → REST API → service → SQLite│
│  可视化   无限画布+卡片      查询接口                 │
└─────────────────────────────────────────────────────┘
```

**关键区别：写入通道不经过 REST API。**

CLI 与 MCP tool 都在本机进程内直接调用 `canvas_service`，读写同一个 SQLite 文件。REST API 只服务于前端浏览通道（以及未来可能的远程访问）。这样：

- 写入无需 FastAPI 服务常驻、无需 token 鉴权
- Hermes 在 IM 中随时可用，与服务是否启动无关
- service 层是唯一业务逻辑入口，CLI / MCP / REST 三个薄壳共享

**设计原则：**
1. **IM-first**：80%的操作通过聊天完成，不需要打开浏览器
2. **结构化存储**：自然语言输入由 LLM 解析为结构化卡片（解析是 Hermes 的能力，后端不写规则解析器）
3. **画布可视化**：前端用于浏览全局、发现关联、辅助决策
4. **CLI/MCP 双入口**：CLI 供脚本/手动调用，MCP 供 Agent 自动调用

---

## 2. 数据模型

### 2.1 Canvas（画布）

每只股票一个画布，以股票代码为主键。

```python
class Canvas(BaseModel):
    ts_code: str               # 股票代码 "002624.SZ"，主键
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
    SENTIMENT = "sentiment"    # 舆论情绪（可选，见 2.5）

    # 决策类
    ENTRY_PLAN = "entry_plan"  # 入场计划（价格、仓位、条件）
    EXIT_PLAN = "exit_plan"    # 出场计划（止盈、止损）
    TRADE_RECORD = "trade_record"  # 交易记录

class Card(BaseModel):
    id: str                    # UUID
    ts_code: str               # 所属画布（股票代码）
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

> 注：初版设计中有 TIMELINE 卡片类型，已删除。时间线是查询视图，
> 从 catalyst（event_date）、trade_record（traded_at）等日期字段派生，
> 不需要单独的卡片类型。

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

# risk（风险提示）
{
    "severity": "high",        # high | medium | low
    "risk_type": "fundamental",# fundamental | valuation | policy | liquidity | sentiment
    "status": "open",          # open | mitigated | materialized
}

# entry_plan / exit_plan
{
    "trigger_price": 28.0,     # 触发价格
    "position_pct": 0.2,       # 仓位比例
    "conditions": ["半年报低于预期", "跌破28支撑位"],
    "status": "pending",       # pending | triggered | cancelled
}

# trade_record（交易记录）
{
    "direction": "buy",        # buy | sell
    "price": 32.5,
    "shares": 1000,
    "amount": 32500.0,
    "traded_at": "2026-08-01T10:30:00",
    "order_ref": None,         # 关联的模拟/实盘订单ID（自动写入时填）
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

# sentiment（舆论情绪，可选）
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

### 2.5 关于舆论情绪

股吧爬虫工作量大、易失效，且项目中没有现成的爬虫基础。**sentiment 自动采集后置为可选目标**；在此之前，sentiment 卡片仅支持手动录入或 Hermes Agent 凭检索结果写入，`source` 标为 `user` / `agent`。

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
canvas timeline --canvas <code>                # 时间线视图（从卡片日期字段派生）
canvas decisions --canvas <code>               # 只看决策类卡片

# 系统自动任务（Phase 5）
canvas auto-update --canvas <code>             # 自动拉取财务/估值数据
```

### 3.3 MCP Tool 设计

供 Hermes Agent 自动调用，也支持其他 MCP 客户端。实现形态与现有 `tushare-mcp` 一致：独立目录 `~/.hermes/skills/canvas-mcp/`，脚本通过 subprocess 或直接 import 调用 ai-quant 的 `canvas_service`（参考 `app/providers/tushare_provider.py` 调用 `~/.hermes/skills/tushare-mcp/scripts/tushare_api.py` 的模式）。

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
    description: 获取画布时间线（按日期排序的事件，从卡片日期字段派生）
    input:
      ts_code: string

  - name: canvas_decisions
    description: 获取画布上的决策卡片（入场/出场计划）
    input:
      ts_code: string

  # 自动更新（Phase 5）
  - name: canvas_auto_sync
    description: 自动同步财务数据、估值到画布
    input:
      ts_code: string
```

### 3.4 自然语言 → 结构化操作的约定

**后端不写关键词解析器。** 自然语言理解是 Hermes（LLM Agent）自身的能力；后端只需要稳定、易用的 CLI/MCP 接口。

Hermes skill（`~/.hermes/skills/` 下的 skill 文档 / system prompt）通过约定指导 LLM 产出调用，例如：

- "XX 目标价 Y，看好/看空" → thesis 卡片
- "XX 的风险是..." → risk 卡片
- "XX 半年报/财报/发布会" → catalyst 卡片（带 event_date）
- "记录：XX..." → note 卡片
- "XX 入场计划：28 买 20% 仓位" → entry_plan 卡片
- "XX 止盈 40 止损 28" → exit_plan 卡片
- "XX 卖出" → 更新 canvas status + trade_record 卡片
- 日常聊天中提到股票观点时，Hermes 主动确认后记录："要记录到画布吗？"

这些约定写在 Hermes skill 文档里随用随调，不需要后端代码支持。

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

自动布局使用 **dagre**（新增依赖共两个：`@xyflow/react`、`dagre`）。

### 4.2 页面结构

```
/stock-canvas                    # 画布列表页
/stock-canvas/:ts_code           # 单只股票画布页
```

接入点（跟随现有惯例）：
- `frontend/src/App.tsx` 注册两条路由（鉴权后访问）
- `frontend/src/layouts/MainLayout.tsx` 侧边栏菜单新增"研究画布"项

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

| 类型 | 渲染方式 | 优先级 |
|------|---------|--------|
| note | Markdown 渲染 | MVP |
| thesis | 方向标签(多/空/中) + 置信度条 + 目标价 | MVP |
| catalyst | 日期 + 事件类型标签 + 影响方向 | MVP |
| risk | 红色警告样式 + 严重度/状态 | MVP |
| financial | Ant Design Table (PE/PB/营收/利润) | 后置 |
| valuation | ECharts PE/PB Band 图 | 后置 |
| sentiment | 情绪仪表盘 + 热词云（可选，见 2.5） | 后置 |
| entry_plan / exit_plan | 触发条件 + 价格 + 仓位 + 状态 | 后置 |
| trade_record | 买卖方向 + 价格 + 盈亏 | 后置 |

MVP 阶段画布为**只读浏览**（卡片增删改都在 IM/CLI 完成）；前端编辑、拖拽持久化布局后置。

### 4.4 自动布局

使用 dagre 自动布局算法，按卡片类型分层：

```
研究层（左）：thesis → catalyst → risk
数据层（中）：financial → valuation → sentiment
决策层（右）：entry_plan → exit_plan → trade_record
```

箭头表示因果/支持/矛盾关系。手动拖拽调整与位置持久化（`PATCH .../layout`）属于后置能力。

### 4.5 画布间跳转

卡片中引用其他股票时，点击可跳转到对应画布。
例：小米画布中提到"长鑫上市缓解内存涨价" → 点击跳转到长鑫画布。

---

## 5. API 设计

REST API 只服务前端浏览通道（写入走 CLI/MCP 直调 service）。所有接口挂在现有 `/api` router 下，沿用现有 token 鉴权，无需单独处理。

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
GET    /api/canvas-search?keyword=xxx            # 跨画布搜索
GET    /api/canvas/{ts_code}/timeline            # 时间线（从卡片日期字段派生）
GET    /api/canvas/{ts_code}/decisions           # 决策卡片
POST   /api/canvas/{ts_code}/auto-sync           # 自动同步数据（Phase 5）
```

> **路径冲突注意**：`GET /api/canvas/search` 会被 `GET /api/canvas/{ts_code}`
> 吞掉（`search` 被当成股票代码）。跨画布搜索使用独立的 `/api/canvas-search`
> 路径规避；timeline/decisions 在 `{ts_code}` 之下，无冲突。

### 5.2 前端画布状态同步（后置能力）

```python
# 保存画布布局（前端拖拽后调用，MVP 只读阶段不实现）
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

跟随项目现有 `app/models/ + app/services/ + app/api/` 分层约定，不新建独立包：

```
ai-quant/
├── app/
│   ├── models/
│   │   └── canvas.py                # Pydantic models (Canvas, Card, Edge)
│   ├── services/
│   │   ├── canvas_store.py          # SQLite CRUD（app/data/canvas.db，WAL 模式）
│   │   ├── canvas_service.py        # 业务逻辑（CLI/MCP/REST 共用）
│   │   └── canvas_auto_sync.py      # 自动数据同步（财务/估值，Phase 5）
│   ├── api/
│   │   └── canvas_routes.py         # REST API 路由（挂到 routes.py 的 /api router）
│   └── cli/
│       └── canvas_cli.py            # CLI 入口（直调 canvas_service）
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── CanvasList.tsx       # 画布列表页
│       │   └── StockCanvas.tsx      # 单股画布页
│       ├── components/
│       │   └── canvas/
│       │       ├── CanvasBoard.tsx      # React Flow 画布主体
│       │       ├── CardShell.tsx        # 通用卡片壳
│       │       ├── cards/
│       │       │   ├── NoteCard.tsx         # MVP
│       │       │   ├── ThesisCard.tsx       # MVP
│       │       │   ├── CatalystCard.tsx     # MVP
│       │       │   ├── RiskCard.tsx         # MVP
│       │       │   ├── FinancialCard.tsx    # 后置
│       │       │   ├── ValuationCard.tsx    # 后置
│       │       │   ├── SentimentCard.tsx    # 后置（可选）
│       │       │   ├── EntryPlanCard.tsx    # 后置
│       │       │   ├── ExitPlanCard.tsx     # 后置
│       │       │   └── TradeRecordCard.tsx  # 后置
│       │       ├── CanvasSidebar.tsx    # 侧边栏
│       │       └── layout.ts            # dagre 自动布局工具函数
│       └── services/
│           └── canvasApi.ts           # canvas API 调用（独立文件，同 watchlistApi.ts 惯例）
├── scripts/
│   └── canvas                         # CLI 可执行入口（python -m app.cli.canvas_cli）
└── tests/
    └── test_canvas.py
```

外部（非本仓库）：
- `~/.hermes/skills/canvas-mcp/` — MCP server，调用 canvas_service（模式同 tushare-mcp）
- Hermes skill 文档 — 记录 3.4 节的自然语言约定

---

## 7. 实施计划

按 IM-first 原则排序：**写入通道（CLI/MCP/IM）先于浏览通道（REST/前端）**。
先在 IM 里把数据模型用熟，再决定前端怎么展示。

### Phase 1：数据层 + service（1-2天）✅ 已完成（2026-08-01）
- [x] 数据模型（`app/models/canvas.py`）
- [x] `canvas_store.py`（SQLite CRUD，WAL 模式，参照 watchlist_store）
- [x] `canvas_service.py`（业务逻辑：卡片增删改、关联、搜索、时间线派生）
- [x] 单元测试（pytest，tmp_path 指向临时 db，参照现有测试风格）
- 验收：`canvas create / add-card / search` 全流程单测通过

### Phase 2：CLI + Hermes 集成（1-2天）
- [x] CLI 命令（`app/cli/canvas_cli.py`，直调 service，入口 `scripts/canvas`）
- [ ] `~/.hermes/skills/canvas-mcp/` MCP server
- [ ] Hermes skill 文档（3.4 节约定）+ IM 实测
- 验收：在微信里用自然语言记录一张 thesis 卡片，`canvas show` 能查到

### Phase 3：REST API（0.5-1天）✅ 已完成（2026-08-01）
- [x] `app/api/canvas_routes.py`（挂到 `routes.py`，沿用 token 鉴权）
- [x] 接口测试（TestClient，`tests/test_canvas_api.py`）
- 验收：前端可调通列表/详情/搜索接口

### Phase 4：前端画布 MVP（2-3天，只读）✅ 已完成（2026-08-01）
- [x] 安装 `@xyflow/react`、`dagre`
- [x] CanvasList 页面 + 路由 + 菜单接入
- [x] StockCanvas 页面 + CanvasBoard（dagre 自动布局）
- [x] CardShell + 4 种 MVP 卡片（note/thesis/catalyst/risk），其余类型通用兜底渲染
- 验收：浏览器打开画布页能看到 IM 写入的卡片及关联

### Phase 5：自动同步 + 前端增强（后置，按需排期）
- [ ] financial/valuation 自动同步（复用 tushare_service / factor_service）
- [ ] 模拟成交自动写 trade_record（对接 simulation_service）
- [ ] 风控告警自动写 risk 卡片（对接 risk_service）
- [ ] 前端其余卡片组件 + 拖拽编辑 + layout 持久化
- [ ] （可选）sentiment 股吧爬虫
- 验收：模拟交易一笔后画布自动出现 trade_record 卡片

---

## 8. 与现有模块的关系

| 现有模块 | 与 Canvas 的关系 | 集成时点 |
|---------|-----------------|---------|
| Watchlist | Canvas 是 Watchlist 的深度版。Watchlist 管"看哪些"，Canvas 管"研究了什么" | 初始即可从自选一键建画布 |
| Factor | 因子数据可自动写入 Canvas 的 valuation/financial 卡片 | Phase 5 |
| Backtest | 回测策略可关联到 Canvas 的 thesis 卡片 | Phase 5 |
| Simulation | 模拟交易记录自动写入 trade_record 卡片 | Phase 5 |
| Risk | 风控规则可触发 Canvas 的 risk 卡片生成 | Phase 5 |
| News | 新闻可自动关联到对应股票的 Canvas | Phase 5 |

---

## 9. 关键设计决策

### Q: 为什么不用 Obsidian/Notion 等现有工具？
A: 需要与 Tushare 数据、ECharts 图表、交易系统深度集成。通用工具做不到自动同步财务数据和生成估值卡片。

### Q: 为什么前端用 React Flow 而不是 tldraw？
A: tldraw 许可证禁止生产环境使用（需付费）。React Flow 是 MIT 许可，且自定义 Node 天然支持嵌入 React 组件。

### Q: 为什么需要 CLI 和 MCP 两套接口？
A: CLI 供脚本/手动调用（Hermes 也可通过 terminal tool 使用），MCP 供 Hermes 及其他 Agent 以标准协议调用。两者都是薄壳，直调同一个 `canvas_service`，不经过 REST API。

### Q: 为什么后端不写自然语言解析器？
A: NLU 是 Hermes（LLM）的核心能力，用关键词规则在后端重造一份既脆弱又重复。后端提供稳定的结构化接口，解析约定写在 Hermes skill 文档里，随用随调。

### Q: 画布数据存在哪？
A: 独立的 `app/data/canvas.db`（SQLite），跟随项目"每模块一个库文件"的惯例（如 `app/data/watchlist.db`、`data/trading.db`）。开启 WAL 模式，保证 CLI 进程与 FastAPI 进程并发读写安全。
