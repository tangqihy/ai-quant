"""
Stock Canvas 数据层与业务层测试
"""
import json
import subprocess
import sys

import pytest

from app.models.canvas import (
    AddCardRequest,
    CanvasStatus,
    CardType,
    CreateCanvasRequest,
    EdgeType,
    UpdateCanvasRequest,
    UpdateCardRequest,
)
from app.services.canvas_service import (
    CanvasAlreadyExistsError,
    CanvasNotFoundError,
    CanvasService,
    CardNotFoundError,
    InvalidLinkError,
)
from app.services.canvas_store import CanvasStore


@pytest.fixture()
def store(tmp_path):
    return CanvasStore(str(tmp_path / "canvas.db"))


@pytest.fixture()
def service(store):
    return CanvasService(store)


def _create_canvas(service: CanvasService, ts_code: str = "01810.HK", name: str = "小米集团"):
    return service.create_canvas(CreateCanvasRequest(ts_code=ts_code, name=name))


def _add_card(service: CanvasService, ts_code: str, card_type: CardType = CardType.NOTE,
              title: str = "测试卡片", **kwargs):
    return service.add_card(ts_code, AddCardRequest(
        card_type=card_type, title=title, **kwargs
    ))


class TestCanvasCRUD:
    def test_create_and_get(self, service):
        canvas = _create_canvas(service)
        assert canvas.ts_code == "01810.HK"
        assert canvas.status == CanvasStatus.WATCHING

        fetched = service.get_canvas("01810.HK")
        assert fetched.name == "小米集团"

    def test_create_duplicate_raises(self, service):
        _create_canvas(service)
        with pytest.raises(CanvasAlreadyExistsError):
            _create_canvas(service)

    def test_get_missing_raises(self, service):
        with pytest.raises(CanvasNotFoundError):
            service.get_canvas("NOPE.SZ")

    def test_list_and_filter_status(self, service):
        _create_canvas(service, "01810.HK")
        _create_canvas(service, "002624.SZ", "完美世界")
        service.set_status("002624.SZ", CanvasStatus.HOLDING)

        assert len(service.list_canvases()) == 2
        holding = service.list_canvases(status="holding")
        assert len(holding) == 1
        assert holding[0].ts_code == "002624.SZ"

    def test_update_canvas(self, service):
        _create_canvas(service)
        updated = service.update_canvas("01810.HK", UpdateCanvasRequest(
            status=CanvasStatus.HOLDING, metadata={"cost": 30.5},
        ))
        assert updated.status == CanvasStatus.HOLDING
        assert updated.metadata == {"cost": 30.5}

    def test_archive(self, service):
        _create_canvas(service)
        archived = service.archive_canvas("01810.HK")
        assert archived.status == CanvasStatus.ARCHIVED


class TestCardCRUD:
    def test_add_and_get(self, service):
        _create_canvas(service)
        card = _add_card(service, "01810.HK", CardType.THESIS, "看好小米",
                         structured_data={"direction": "bullish", "target_price": 50},
                         tags=["MiMo", "AI"], importance=4)
        assert card.id

        fetched = service.get_card(card.id)
        assert fetched.card_type == CardType.THESIS
        assert fetched.structured_data["target_price"] == 50
        assert fetched.tags == ["MiMo", "AI"]
        assert fetched.importance == 4

    def test_add_to_missing_canvas_raises(self, service):
        with pytest.raises(CanvasNotFoundError):
            _add_card(service, "NOPE.SZ")

    def test_update_card(self, service):
        _create_canvas(service)
        card = _add_card(service, "01810.HK")
        updated = service.update_card(card.id, UpdateCardRequest(
            title="新标题", importance=5, position={"x": 100, "y": 200},
        ))
        assert updated.title == "新标题"
        assert updated.importance == 5
        assert updated.position == {"x": 100, "y": 200}

    def test_update_missing_card_raises(self, service):
        with pytest.raises(CardNotFoundError):
            service.update_card("missing-id", UpdateCardRequest(title="x"))

    def test_delete_card(self, service):
        _create_canvas(service)
        card = _add_card(service, "01810.HK")
        service.delete_card(card.id)
        with pytest.raises(CardNotFoundError):
            service.get_card(card.id)

    def test_list_cards_filter(self, service):
        _create_canvas(service)
        _add_card(service, "01810.HK", CardType.THESIS, "论点", tags=["半年报"])
        _add_card(service, "01810.HK", CardType.RISK, "风险", tags=["估值"])
        _add_card(service, "01810.HK", CardType.NOTE, "笔记")

        assert len(service.list_cards("01810.HK")) == 3
        assert len(service.list_cards("01810.HK", card_type=CardType.RISK)) == 1
        assert len(service.list_cards("01810.HK", tag="半年报")) == 1


class TestEdge:
    def test_link_and_list(self, service):
        _create_canvas(service)
        thesis = _add_card(service, "01810.HK", CardType.THESIS, "看多")
        catalyst = _add_card(service, "01810.HK", CardType.CATALYST, "MiMo v3 发布")

        edge = service.link_cards(catalyst.id, thesis.id, EdgeType.SUPPORTS, "新品支撑论点")
        assert edge.source_card_id == catalyst.id

        detail = service.get_canvas_detail("01810.HK")
        assert len(detail.edges) == 1
        assert len(detail.cards) == 2

    def test_link_missing_card_raises(self, service):
        _create_canvas(service)
        card = _add_card(service, "01810.HK")
        with pytest.raises(CardNotFoundError):
            service.link_cards(card.id, "missing-id", EdgeType.RELATES)

    def test_cross_canvas_link_raises(self, service):
        _create_canvas(service, "01810.HK")
        _create_canvas(service, "002624.SZ", "完美世界")
        a = _add_card(service, "01810.HK")
        b = _add_card(service, "002624.SZ")
        with pytest.raises(InvalidLinkError):
            service.link_cards(a.id, b.id, EdgeType.RELATES)


class TestSearch:
    def test_search_hits_title_content_tags(self, service):
        _create_canvas(service)
        _add_card(service, "01810.HK", CardType.NOTE, "内存涨价跟踪")
        _add_card(service, "01810.HK", CardType.NOTE, "无关笔记", content="提到内存涨价趋势")
        _add_card(service, "01810.HK", CardType.NOTE, "打标签", tags=["内存涨价"])
        _add_card(service, "01810.HK", CardType.NOTE, "完全无关")

        results = service.search_cards("内存涨价")
        assert len(results) == 3

    def test_search_scoped_by_canvas_and_type(self, service):
        _create_canvas(service, "01810.HK")
        _create_canvas(service, "002624.SZ", "完美世界")
        _add_card(service, "01810.HK", CardType.THESIS, "看好逻辑")
        _add_card(service, "002624.SZ", CardType.RISK, "看好但贵")

        assert len(service.search_cards("看好", ts_code="01810.HK")) == 1
        assert len(service.search_cards("看好", card_type=CardType.RISK)) == 1


class TestTimelineAndDecisions:
    def test_timeline_derived_and_sorted(self, service):
        _create_canvas(service)
        _add_card(service, "01810.HK", CardType.CATALYST, "半年报",
                  structured_data={"event_date": "2026-08-15"})
        _add_card(service, "01810.HK", CardType.TRADE_RECORD, "买入",
                  structured_data={"traded_at": "2026-08-01T10:30:00"})
        _add_card(service, "01810.HK", CardType.CATALYST, "MiMo v3 发布",
                  structured_data={"event_date": "2026-09-01"})

        timeline = service.get_timeline("01810.HK")
        assert len(timeline) == 3
        dates = [e["date"] for e in timeline]
        assert dates == sorted(dates)
        assert timeline[0]["title"] == "买入"
        assert timeline[-1]["title"] == "MiMo v3 发布"

    def test_decisions_only_decision_cards(self, service):
        _create_canvas(service)
        _add_card(service, "01810.HK", CardType.THESIS, "看多")
        _add_card(service, "01810.HK", CardType.ENTRY_PLAN, "28买20%",
                  structured_data={"trigger_price": 28.0, "position_pct": 0.2})
        _add_card(service, "01810.HK", CardType.EXIT_PLAN, "止盈40",
                  structured_data={"trigger_price": 40.0})
        _add_card(service, "01810.HK", CardType.TRADE_RECORD, "买入",
                  structured_data={"direction": "buy", "price": 30.0})

        decisions = service.get_decisions("01810.HK")
        assert len(decisions) == 3
        assert all(c.card_type in {
            CardType.ENTRY_PLAN, CardType.EXIT_PLAN, CardType.TRADE_RECORD
        } for c in decisions)


class TestCLISmoke:
    """CLI 冒烟：临时库上跑 create → add-card → show"""

    def _run_cli(self, db_path: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "app.cli.canvas_cli", *args],
            capture_output=True, text=True,
            env={"CANVAS_DB_PATH": db_path, "PATH": "/usr/bin:/bin"},
            cwd=str(__import__("pathlib").Path(__file__).parent.parent),
        )

    def test_cli_flow(self, tmp_path):
        db = str(tmp_path / "cli.db")

        r = self._run_cli(db, "create", "--code", "01810.HK", "--name", "小米集团", "--json")
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["ts_code"] == "01810.HK"

        r = self._run_cli(db, "add-card", "--canvas", "01810.HK", "--type", "thesis",
                          "--title", "看好小米", "--data", '{"direction":"bullish","target_price":50}',
                          "--json")
        assert r.returncode == 0, r.stderr
        card = json.loads(r.stdout)
        assert card["structured_data"]["target_price"] == 50

        r = self._run_cli(db, "show", "--canvas", "01810.HK", "--json")
        assert r.returncode == 0, r.stderr
        detail = json.loads(r.stdout)
        assert len(detail["cards"]) == 1

        r = self._run_cli(db, "search", "--keyword", "小米", "--json")
        assert r.returncode == 0, r.stderr
        assert len(json.loads(r.stdout)) == 1
