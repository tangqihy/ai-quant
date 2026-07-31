"""
股票研究画布数据模型（Stock Canvas）

设计文档：docs/design/07-stock-canvas.md
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CardType(str, Enum):
    """卡片类型"""
    # 研究类
    NOTE = "note"                    # 自由笔记
    THESIS = "thesis"                # 投资论点（看多/看空/中性）
    CATALYST = "catalyst"            # 事件催化剂
    RISK = "risk"                    # 风险提示
    # 数据类（系统自动生成）
    FINANCIAL = "financial"          # 财务数据快照
    VALUATION = "valuation"          # 估值分析
    SENTIMENT = "sentiment"          # 舆论情绪（可选）
    # 决策类
    ENTRY_PLAN = "entry_plan"        # 入场计划
    EXIT_PLAN = "exit_plan"          # 出场计划
    TRADE_RECORD = "trade_record"    # 交易记录


class EdgeType(str, Enum):
    """卡片关联类型"""
    SUPPORTS = "supports"            # 支持（利好→论点）
    CONTRADICTS = "contradicts"      # 矛盾（利空→看多论点）
    CAUSES = "causes"                # 因果（事件→影响）
    RELATES = "relates"              # 相关
    TRIGGERS = "triggers"            # 触发（催化剂→入场计划）


class CanvasStatus(str, Enum):
    """画布状态"""
    WATCHING = "watching"
    HOLDING = "holding"
    SOLD = "sold"
    ARCHIVED = "archived"


class Canvas(BaseModel):
    """股票研究画布，每只股票一个，ts_code 为主键"""
    ts_code: str = Field(..., description="股票代码，如 002624.SZ")
    name: str = Field(default="", description="股票名称")
    status: CanvasStatus = Field(default=CanvasStatus.WATCHING, description="画布状态")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    metadata: Dict = Field(default_factory=dict, description="扩展字段（成本价、仓位等）")


class Card(BaseModel):
    """画布卡片"""
    id: str = Field(..., description="卡片ID（UUID）")
    ts_code: str = Field(..., description="所属画布（股票代码）")
    card_type: CardType = Field(..., description="卡片类型")
    title: str = Field(..., description="卡片标题")
    content: str = Field(default="", description="正文（Markdown）")
    structured_data: Dict = Field(default_factory=dict, description="结构化数据（按类型不同）")
    tags: List[str] = Field(default_factory=list, description="标签")
    importance: int = Field(default=3, ge=1, le=5, description="重要性 1-5")
    source: str = Field(default="user", description="来源 user|system|crawler|agent")
    source_ref: str = Field(default="", description="来源引用（聊天记录ID、URL 等）")
    position: Dict = Field(default_factory=dict, description="画布位置 {x, y}（前端用）")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间（时效性信息）")


class Edge(BaseModel):
    """卡片关联"""
    id: str = Field(..., description="关联ID（UUID）")
    source_card_id: str = Field(..., description="源卡片ID")
    target_card_id: str = Field(..., description="目标卡片ID")
    edge_type: EdgeType = Field(..., description="关联类型")
    label: Optional[str] = Field(None, description="关系描述")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class CanvasDetail(BaseModel):
    """画布详情（含卡片与关联）"""
    canvas: Canvas
    cards: List[Card] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)


# ==================== 请求模型 ====================

class CreateCanvasRequest(BaseModel):
    """创建画布请求"""
    ts_code: str = Field(..., description="股票代码")
    name: str = Field(default="", description="股票名称")
    status: CanvasStatus = Field(default=CanvasStatus.WATCHING, description="初始状态")


class UpdateCanvasRequest(BaseModel):
    """更新画布请求"""
    name: Optional[str] = Field(None, description="股票名称")
    status: Optional[CanvasStatus] = Field(None, description="状态")
    metadata: Optional[Dict] = Field(None, description="扩展字段")


class AddCardRequest(BaseModel):
    """添加卡片请求"""
    card_type: CardType = Field(..., description="卡片类型")
    title: str = Field(..., description="卡片标题")
    content: str = Field(default="", description="正文")
    structured_data: Dict = Field(default_factory=dict, description="结构化数据")
    tags: List[str] = Field(default_factory=list, description="标签")
    importance: int = Field(default=3, ge=1, le=5, description="重要性")
    source: str = Field(default="user", description="来源")
    source_ref: str = Field(default="", description="来源引用")
    expires_at: Optional[datetime] = Field(None, description="过期时间")


class UpdateCardRequest(BaseModel):
    """更新卡片请求"""
    title: Optional[str] = Field(None, description="标题")
    content: Optional[str] = Field(None, description="正文")
    structured_data: Optional[Dict] = Field(None, description="结构化数据")
    tags: Optional[List[str]] = Field(None, description="标签")
    importance: Optional[int] = Field(None, ge=1, le=5, description="重要性")
    position: Optional[Dict] = Field(None, description="画布位置")
    expires_at: Optional[datetime] = Field(None, description="过期时间")


class LinkCardsRequest(BaseModel):
    """建立卡片关联请求"""
    source_card_id: str = Field(..., description="源卡片ID")
    target_card_id: str = Field(..., description="目标卡片ID")
    edge_type: EdgeType = Field(..., description="关联类型")
    label: Optional[str] = Field(None, description="关系描述")
