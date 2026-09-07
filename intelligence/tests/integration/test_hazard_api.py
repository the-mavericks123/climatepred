"""Integration tests for POST /api/v1/hazards/evaluate endpoint.

Verifies:
  - Evaluation of normal, hot, flood, and drought fixtures
  - Missing sensor results in UNAVAILABLE status without null-to-zero conversion
  - Strict validation of invalid payloads with structured error response
  - Hazard filtering functionality
  - Request ID and timing headers preservation
  - Forecast horizon remains 0 and simulated is False
"""

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from intelligence.app.main import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_evaluate_normal_telemetry():
    telemetry = load_fixture("normal_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "hazards" in data
        assert len(data["hazards"]) == 3

        # Normal telemetry should result in NORMAL classification for all
        for h in data["hazards"]:
            assert h["status"] in ["NOT_DETECTED", "DETECTED"]
            assert h["classification"] in ["NORMAL", "LOW"]
            assert 0.0 <= h["severity"] < 0.40
            assert 0.0 <= h["confidence"] <= 1.0
            assert h["forecast_horizon_minutes"] == 0
            assert h["simulated"] is False

        assert "X-Request-ID" in resp.headers
        assert "X-Response-Time-Ms" in resp.headers


@pytest.mark.asyncio
async def test_evaluate_heat_telemetry():
    telemetry = load_fixture("heat_critical_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
        assert resp.status_code == 200
        data = resp.json()

        heat_results = [h for h in data["hazards"] if h["hazard"] == "heat"]
        assert len(heat_results) == 1
        heat = heat_results[0]
        assert heat["classification"] == "CRITICAL"
        assert heat["status"] == "DETECTED"
        assert heat["severity"] >= 0.80
        assert heat["model_version"] == "heat-v1"


@pytest.mark.asyncio
async def test_evaluate_critical_flood_telemetry():
    telemetry = load_fixture("critical_flood_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
        assert resp.status_code == 200
        data = resp.json()

        flood_results = [h for h in data["hazards"] if h["hazard"] == "flood"]
        assert len(flood_results) == 1
        flood = flood_results[0]
        assert flood["classification"] == "CRITICAL"
        assert flood["status"] == "DETECTED"
        assert flood["severity"] >= 0.80
        assert flood["model_version"] == "flood-v1"


@pytest.mark.asyncio
async def test_evaluate_critical_drought_telemetry():
    telemetry = load_fixture("drought_critical_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
        assert resp.status_code == 200
        data = resp.json()

        drought_results = [h for h in data["hazards"] if h["hazard"] == "drought"]
        assert len(drought_results) == 1
        drought = drought_results[0]
        assert drought["classification"] == "CRITICAL"
        assert drought["status"] == "DETECTED"
        assert drought["severity"] >= 0.80
        assert drought["model_version"] == "drought-v1"


@pytest.mark.asyncio
async def test_evaluate_missing_sensor_unavailable_status():
    telemetry = load_fixture("missing_sensor_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
        assert resp.status_code == 200
        data = resp.json()

        # In missing_sensor_telemetry.json, water_level is null.
        # Flood requires water_level, so flood status must be UNAVAILABLE
        flood_results = [h for h in data["hazards"] if h["hazard"] == "flood"]
        assert len(flood_results) == 1
        flood = flood_results[0]
        assert flood["status"] == "UNAVAILABLE"
        assert flood["severity"] == 0.0
        assert flood["classification"] is None
        assert any("water_level" in d for d in flood["drivers"])


@pytest.mark.asyncio
async def test_evaluate_hazard_filtering():
    telemetry = load_fixture("normal_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/hazards/evaluate",
            json={"telemetry": telemetry, "hazards": ["flood"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hazards"]) == 1
        assert data["hazards"][0]["hazard"] == "flood"


@pytest.mark.asyncio
async def test_evaluate_missing_telemetry_payload_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_evaluate_invalid_telemetry_rejected():
    telemetry = load_fixture("invalid_telemetry.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
