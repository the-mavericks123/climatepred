"""
Integration tests for Phase 10 Explainability endpoints in FastAPI.
"""

import pytest
from fastapi.testclient import TestClient
from intelligence.app.main import app

client = TestClient(app)


def test_post_explainability_generate_hazard():
    payload = {
        "target_type": "hazard",
        "target_id": "HAZ-FLOOD-TEST-01",
        "level": "DETAILED",
        "target_object": {
            "hazard_id": "HAZ-FLOOD-TEST-01",
            "hazard": "flood",
            "severity": 0.78,
            "features": {
                "rainfall_mmhr": 60.0,
                "water_level_m": 8.0,
                "soil_moisture_pct": 80.0,
            },
        },
    }
    res = client.post("/api/v1/explainability/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    exp = data["explanation"]
    assert exp["target_id"] == "HAZ-FLOOD-TEST-01"
    assert exp["target_type"] == "hazard"
    assert len(exp["factors"]) == 3
    assert len(exp["provenance_hash"]) == 64


def test_post_explainability_generate_prediction():
    payload = {
        "target_type": "prediction",
        "target_id": "PRED-TEST-01",
        "level": "STANDARD",
        "target_object": {
            "prediction_id": "PRED-TEST-01",
            "forecast_horizon_minutes": 60,
            "severity": 0.85,
            "baseline_severity": 0.45,
            "hazard": "flood",
        },
    }
    res = client.post("/api/v1/explainability/generate", json=payload)
    assert res.status_code == 200
    exp = res.json()["explanation"]
    assert exp["classification"] == "PREDICTED"
    assert len(exp["reasoning_steps"]) >= 4


def test_get_explainability_endpoint():
    # First generate to populate cache
    payload = {
        "target_type": "hazard",
        "target_id": "HAZ-CACHED-01",
        "target_object": {"hazard": "heat", "features": {"temperature_c": 42.0, "humidity_pct": 60.0}},
    }
    client.post("/api/v1/explainability/generate", json=payload)

    # Now GET
    res = client.get("/api/v1/explainability/hazard/HAZ-CACHED-01")
    assert res.status_code == 200
    exp = res.json()["explanation"]
    assert exp["target_id"] == "HAZ-CACHED-01"


def test_explainability_invalid_target_type():
    res = client.get("/api/v1/explainability/nonexistent_type/ID-1")
    assert res.status_code == 422
