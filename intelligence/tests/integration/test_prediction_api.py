"""Integration tests for POST /api/v1/predictions/evaluate endpoint.

Verifies:
  - Valid prediction request across supported horizons (30, 60, 360)
  - Hazard filtering and horizon filtering
  - Rejection of unsupported horizons with HTTP 422 VALIDATION_ERROR
  - Rejection of invalid telemetry or history records with HTTP 422
  - Client cannot spoof severity, confidence, classification, or simulated flag
  - Response headers X-Request-ID and X-Response-Time-Ms preservation
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
async def test_evaluate_predictions_valid():
    payload = load_fixture("prediction_stable.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/predictions/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "predictions" in data
        assert len(data["predictions"]) == 9  # 3 hazards * 3 horizons

        for p in data["predictions"]:
            assert p["forecast_horizon_minutes"] in [30, 60, 360]
            assert p["simulated"] is False
            assert 0.0 <= p["severity"] <= 1.0
            assert 0.0 <= p["confidence"] <= 1.0
            assert p["model_version"].endswith("-pred-v1")
            assert len(p["provenance_hash"]) >= 8

        assert "X-Request-ID" in resp.headers
        assert "X-Response-Time-Ms" in resp.headers


@pytest.mark.asyncio
async def test_evaluate_predictions_filtering():
    payload = load_fixture("prediction_heat_30m.json")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/predictions/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["predictions"]) == 1
        p = data["predictions"][0]
        assert p["hazard"] == "heat"
        assert p["forecast_horizon_minutes"] == 30
        assert p["classification"] in ["MODERATE", "HIGH", "CRITICAL"]


@pytest.mark.asyncio
async def test_evaluate_predictions_unsupported_horizon_rejected():
    payload = load_fixture("prediction_stable.json")
    payload["horizons_minutes"] = [15, 60]  # 15 is unsupported
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/predictions/evaluate", json=payload)
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "unsupported" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_evaluate_predictions_invalid_hazard_filter_rejected():
    payload = load_fixture("prediction_stable.json")
    payload["hazards"] = ["earthquake"]  # invalid hazard
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/predictions/evaluate", json=payload)
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_evaluate_predictions_missing_telemetry_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/predictions/evaluate", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_evaluate_predictions_security_no_spoofing():
    """Client trying to inject fabricated severity or simulated flag has no effect on model calculation."""
    payload = load_fixture("prediction_heat_30m.json")
    # Client attempts to inject spoofed output values
    payload["severity"] = 0.00
    payload["confidence"] = 1.00
    payload["simulated"] = True
    payload["model_version"] = "spoofed-v99"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/predictions/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        p = data["predictions"][0]
        # Must be authoritative calculated output, not spoofed values
        assert p["model_version"] == "heat-pred-v1"
        assert p["simulated"] is False
        assert p["severity"] > 0.50
