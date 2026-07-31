"""
Stock Canvas 业务逻辑层

CLI / MCP / 未来 REST API 共用的薄业务层。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.canvas import (
    AddCardRequest,
    Canvas,
    CanvasDetail,
    CanvasStatus,
    Card,
    CardType,
    CreateCanvasRequest,
    Edge,
    EdgeType,
    UpdateCanvasRequest,
    UpdateCardRequest,
)
from app.services.canvas_store import CanvasStore

DECISION_CARD_TYPES = {CardType.ENTRY_PLAN, CardType.EXIT_PLAN, CardType.TRADE_RECORD}


class CanvasNotFoundError(ValueError):
    """画布不存在"""


class CardNotFoundError(ValueError):
    """卡片不存在"""


class CanvasAlreadyExistsError(ValueError):
    """画布已存在"""


class InvalidLinkError(ValueError):
    """非法关联（卡片不存在或不属于同一画布）"""


class CanvasService:
    """画布业务逻辑，store 可注入便于测试"""

    def __init__(self, store: Optional[CanvasStore] = None) -> None:
        self.store = store or CanvasStore()

    # ==================== Canvas ====================

    def create_canvas(self, request: CreateCanvasRequest) -> Canvas:
        if self.store.get_canvas(request.ts_code):
            raise CanvasAlreadyExistsError(f"画布已存在: {request.ts_code}")
        canvas = Canvas(
            ts_code=request.ts_code,
            name=request.name,
            status=request.status,
        )
        return self.store.create_canvas(canvas)

    def get_canvas(self, ts_code: str) -> Canvas:
        canvas = self.store.get_canvas(ts_code)
        if not canvas:
            raise CanvasNotFoundError(f"画布不存在: {ts_code}")
        return canvas

    def get_canvas_detail(self, ts_code: str) -> CanvasDetail:
        canvas = self.get_canvas(ts_code)
        return CanvasDetail(
            canvas=canvas,
            cards=self.store.list_cards(ts_code),
            edges=self.store.list_edges_for_canvas(ts_code),
        )

    def list_canvases(self, status: Optional[str] = None) -> List[Canvas]:
        return self.store.list_canvases(status=status)

    def update_canvas(self, ts_code: str, request: UpdateCanvasRequest) -> Canvas:
        fields = request.model_dump(exclude_none=True)
        if not self.store.update_canvas(ts_code, fields):
            raise CanvasNotFoundError(f"画布不存在或无更新: {ts_code}")
        return self.get_canvas(ts_code)

    def set_status(self, ts_code: str, status: CanvasStatus) -> Canvas:
        if not self.store.update_canvas(ts_code, {"status": status}):
            raise CanvasNotFoundError(f"画布不存在: {ts_code}")
        return self.get_canvas(ts_code)

    def archive_canvas(self, ts_code: str) -> Canvas:
        return self.set_status(ts_code, CanvasStatus.ARCHIVED)

    # ==================== Card ====================

    def add_card(self, ts_code: str, request: AddCardRequest) -> Card:
        self.get_canvas(ts_code)  # 校验画布存在
        card = Card(
            id=CanvasStore.new_id(),
            ts_code=ts_code,
            card_type=request.card_type,
            title=request.title,
            content=request.content,
            structured_data=request.structured_data,
            tags=request.tags,
            importance=request.importance,
            source=request.source,
            source_ref=request.source_ref,
            expires_at=request.expires_at,
        )
        return self.store.add_card(card)

    def get_card(self, card_id: str) -> Card:
        card = self.store.get_card(card_id)
        if not card:
            raise CardNotFoundError(f"卡片不存在: {card_id}")
        return card

    def list_cards(
        self,
        ts_code: str,
        card_type: Optional[CardType] = None,
        tag: Optional[str] = None,
    ) -> List[Card]:
        self.get_canvas(ts_code)
        return self.store.list_cards(
            ts_code,
            card_type=card_type.value if card_type else None,
            tag=tag,
        )

    def update_card(self, card_id: str, request: UpdateCardRequest) -> Card:
        fields = request.model_dump(exclude_none=True)
        if not self.store.update_card(card_id, fields):
            raise CardNotFoundError(f"卡片不存在或无更新: {card_id}")
        return self.get_card(card_id)

    def delete_card(self, card_id: str) -> None:
        if not self.store.delete_card(card_id):
            raise CardNotFoundError(f"卡片不存在: {card_id}")

    # ==================== Edge ====================

    def link_cards(
        self,
        source_card_id: str,
        target_card_id: str,
        edge_type: EdgeType,
        label: Optional[str] = None,
    ) -> Edge:
        source = self.store.get_card(source_card_id)
        target = self.store.get_card(target_card_id)
        if not source or not target:
            raise CardNotFoundError("源卡片或目标卡片不存在")
        if source.ts_code != target.ts_code:
            raise InvalidLinkError("不允许跨画布建立关联")
        edge = Edge(
            id=CanvasStore.new_id(),
            source_card_id=source_card_id,
            target_card_id=target_card_id,
            edge_type=edge_type,
            label=label,
        )
        return self.store.add_edge(edge)

    def delete_edge(self, edge_id: str) -> None:
        if not self.store.delete_edge(edge_id):
            raise ValueError(f"关联不存在: {edge_id}")

    # ==================== 查询 ====================

    def search_cards(
        self,
        keyword: str,
        ts_code: Optional[str] = None,
        card_type: Optional[CardType] = None,
    ) -> List[Card]:
        return self.store.search_cards(
            keyword,
            ts_code=ts_code,
            card_type=card_type.value if card_type else None,
        )

    def get_timeline(self, ts_code: str) -> List[Dict[str, Any]]:
        """时间线视图：从卡片日期字段派生，按日期升序。

        - catalyst → structured_data.event_date
        - trade_record → structured_data.traded_at
        - 其余卡片 → created_at
        """
        cards = self.list_cards(ts_code)
        events: List[Dict[str, Any]] = []
        for card in cards:
            date_str = self._card_event_date(card)
            events.append({
                "date": date_str,
                "card_id": card.id,
                "card_type": card.card_type.value,
                "title": card.title,
                "structured_data": card.structured_data,
            })
        events.sort(key=lambda e: e["date"] or "")
        return events

    def get_decisions(self, ts_code: str) -> List[Card]:
        """决策清单：入场/出场计划与交易记录"""
        cards = self.list_cards(ts_code)
        return [c for c in cards if c.card_type in DECISION_CARD_TYPES]

    @staticmethod
    def _card_event_date(card: Card) -> Optional[str]:
        if card.card_type == CardType.CATALYST:
            date = card.structured_data.get("event_date")
            if date:
                return str(date)
        if card.card_type == CardType.TRADE_RECORD:
            traded_at = card.structured_data.get("traded_at")
            if traded_at:
                return str(traded_at)
        if card.created_at:
            return card.created_at.isoformat()
        return None


canvas_service = CanvasService()
