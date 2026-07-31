"""
Stock Canvas REST API 接口测试
"""
import os

import pytest
from fastapi.testclient import TestClient

import app.api.canvas_routes as canvas_routes_module
from app.main import app
from app.services.canvas_service import CanvasService
from app.services.canvas_store import CanvasStore

os.environ.setdefault("QUANT_AUTH_PASSWORD", "testpass")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """每个测试用独立临时库的 TestClient，并附带鉴权头"""
    service = CanvasService(CanvasStore(str(tmp_path / "canvas.db")))
    monkeypatch.setattr(canvas_routes_module, "_service", service)
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"password": "testpass"})
        assert r.status_code == 200
        c.headers["Authorization"] = f"Bearer {r.json()['token']}"
        yield c


def _create(client, ts_code="01810.HK", name="小米集团"):
    return client.post("/api/canvas", json={"ts_code": ts_code, "name": name})


class TestCanvasAPI:
    def test_create_and_list(self, client):
        r = _create(client)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["ts_code"] == "01810.HK"

        r = client.get("/api/canvas")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1

    def test_create_duplicate_409(self, client):
        _create(client)
        r = _create(client)
        assert r.status_code == 409

    def test_detail_404(self, client):
        r = client.get("/api/canvas/NOPE.SZ")
        assert r.status_code == 404

    def test_detail_includes_cards_edges(self, client):
        _create(client)
        r1 = client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "thesis", "title": "看多",
            "structured_data": {"direction": "bullish", "target_price": 50},
        })
        assert r1.status_code == 200
        thesis_id = r1.json()["data"]["id"]

        r2 = client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "catalyst", "title": "MiMo v3 发布",
            "structured_data": {"event_date": "2026-09-01"},
        })
        catalyst_id = r2.json()["data"]["id"]

        r3 = client.post("/api/canvas/edges", json={
            "source_card_id": catalyst_id, "target_card_id": thesis_id,
            "edge_type": "supports",
        })
        assert r3.status_code == 200

        r = client.get("/api/canvas/01810.HK")
        data = r.json()["data"]
        assert len(data["cards"]) == 2
        assert len(data["edges"]) == 1

    def test_update_and_delete_canvas(self, client):
        _create(client)
        r = client.patch("/api/canvas/01810.HK", json={"status": "holding"})
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "holding"

        r = client.get("/api/canvas", params={"status": "holding"})
        assert len(r.json()["data"]) == 1

        r = client.delete("/api/canvas/01810.HK")
        assert r.status_code == 200
        assert client.get("/api/canvas").json()["data"] == []


class TestCardAPI:
    def test_card_crud(self, client):
        _create(client)
        r = client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "note", "title": "研究笔记", "tags": ["内存涨价"],
        })
        card_id = r.json()["data"]["id"]

        r = client.patch(f"/api/canvas/cards/{card_id}", json={
            "title": "改标题", "importance": 5,
        })
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "改标题"
        assert r.json()["data"]["importance"] == 5

        r = client.delete(f"/api/canvas/cards/{card_id}")
        assert r.status_code == 200

        r = client.patch(f"/api/canvas/cards/{card_id}", json={"title": "x"})
        assert r.status_code == 404

    def test_add_card_missing_canvas_404(self, client):
        r = client.post("/api/canvas/NOPE.SZ/cards", json={
            "card_type": "note", "title": "x",
        })
        assert r.status_code == 404

    def test_cross_canvas_link_400(self, client):
        _create(client, "01810.HK")
        _create(client, "002624.SZ", "完美世界")
        a = client.post("/api/canvas/01810.HK/cards",
                        json={"card_type": "note", "title": "a"}).json()["data"]["id"]
        b = client.post("/api/canvas/002624.SZ/cards",
                        json={"card_type": "note", "title": "b"}).json()["data"]["id"]
        r = client.post("/api/canvas/edges", json={
            "source_card_id": a, "target_card_id": b, "edge_type": "relates",
        })
        assert r.status_code == 400


class TestQueryAPI:
    def test_search(self, client):
        _create(client)
        client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "note", "title": "内存涨价跟踪",
        })
        client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "note", "title": "无关笔记",
        })
        r = client.get("/api/canvas-search", params={"keyword": "内存涨价"})
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1

    def test_timeline(self, client):
        _create(client)
        client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "catalyst", "title": "半年报",
            "structured_data": {"event_date": "2026-08-15"},
        })
        client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "trade_record", "title": "买入",
            "structured_data": {"traded_at": "2026-08-01T10:30:00"},
        })
        r = client.get("/api/canvas/01810.HK/timeline")
        events = r.json()["data"]
        assert len(events) == 2
        assert events[0]["title"] == "买入"
        assert events[1]["title"] == "半年报"

    def test_decisions(self, client):
        _create(client)
        client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "thesis", "title": "看多",
        })
        client.post("/api/canvas/01810.HK/cards", json={
            "card_type": "entry_plan", "title": "28买20%",
            "structured_data": {"trigger_price": 28.0},
        })
        r = client.get("/api/canvas/01810.HK/decisions")
        cards = r.json()["data"]
        assert len(cards) == 1
        assert cards[0]["card_type"] == "entry_plan"
