"""
Integration tests for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence endpoints.
Validates POST /api/v1/evacuation/evaluate, GET /api/v1/evacuation/routes, and GET /api/v1/evacuation/current.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(filename: str):
    path = FIXTURES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


class TestEvacuationAPI:
    def test_evaluate_normal_standby(self):
        payload = _load_fixture("evacuation_normal.json")
        res = client.post("/api/v1/evacuation/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["recommendation_count"] == 1
        assert data["total_evacuated_population"] == 0
        rec = data["recommendations"][0]
        assert rec["population_to_evacuate"] == 0
        assert rec["status"] == "RECOMMENDED"
        assert "shelter in place" in rec["reason"].lower()

    def test_evaluate_flood_evacuation(self):
        payload = _load_fixture("evacuation_flood.json")
        res = client.post("/api/v1/evacuation/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["recommendation_count"] == 1
        assert data["total_evacuated_population"] > 0
        rec = data["recommendations"][0]
        assert rec["status"] == "RECOMMENDED"
        assert rec["destination"] is not None
        assert rec["destination"]["shelter_id"] == "SHELTER-NORTH"
        assert rec["route"] is not None
        assert rec["route"]["destination_node"] == "SHELTER-NORTH"
        assert len(rec["route"]["nodes"]) >= 2
        assert rec["confidence"] > 0.60

    def test_evaluate_empty_zones_returns_422(self):
        payload = _load_fixture("evacuation_flood.json")
        payload["zones"] = []
        res = client.post("/api/v1/evacuation/evaluate", json=payload)
        assert res.status_code == 422
        assert res.json()["success"] is False

    def test_evaluate_empty_shelters_returns_422(self):
        payload = _load_fixture("evacuation_flood.json")
        payload["shelters"] = []
        res = client.post("/api/v1/evacuation/evaluate", json=payload)
        assert res.status_code == 422
        assert res.json()["success"] is False

    def test_evaluate_invalid_road_network_returns_422(self):
        payload = _load_fixture("evacuation_flood.json")
        payload["road_network"] = "not_a_dict"
        res = client.post("/api/v1/evacuation/evaluate", json=payload)
        assert res.status_code == 422

    def test_get_evacuation_routes_endpoints(self):
        # First evaluate a scenario
        payload = _load_fixture("evacuation_flood.json")
        post_res = client.post("/api/v1/evacuation/evaluate", json=payload)
        assert post_res.status_code == 200

        # Now query GET /api/v1/evacuation/routes
        res1 = client.get("/api/v1/evacuation/routes")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is True
        assert data1["recommendation_count"] >= 1

        # Query GET /api/v1/evacuation/current
        res2 = client.get("/api/v1/evacuation/current")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["success"] is True
        assert data2["recommendation_count"] == data1["recommendation_count"]
