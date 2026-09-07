"""
Integration tests for Phase 9 Response Planner API Endpoints.
Tests:
- GET /api/v1/response/current
- POST /api/v1/response/evaluate
- POST /api/v1/response/simulate
"""

import pytest
from fastapi.testclient import TestClient
from intelligence.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_current_response_plan(client):
    response = client.get("/api/v1/response/current")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "plan" in data
    assert "plan_id" in data["plan"]
    assert "alert_level" in data["plan"]
    assert "actions" in data["plan"]
    assert "provenance_hash" in data["plan"]
    assert data["plan"]["simulated"] is False


def test_post_evaluate_response_plan_nominal(client):
    response = client.post("/api/v1/response/evaluate", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"]["alert_level"] in ("GREEN", "YELLOW", "ORANGE", "RED")
    assert len(data["plan"]["actions"]) >= 1


def test_post_evaluate_response_plan_custom_telemetry(client):
    custom_telemetry = {
        "node_id": "STATION-RIVER-01",
        "timestamp": "2026-09-07T14:30:00Z",
        "location": {"lat": 37.77, "lon": -122.42},
        "measurements": {
            "temperature": 25.0,
            "humidity": 90.0,
            "rainfall": 120.0,  # Extreme flood
            "water_level": 18.5,
            "soil_moisture": 98.0,
        },
        "quality": {"source": "STATION-RIVER-01", "received_at": "2026-09-07T14:30:00Z"},
    }



    response = client.post("/api/v1/response/evaluate", json={"telemetry": custom_telemetry})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Flood severity is extreme -> alert level should be RED or ORANGE
    assert data["plan"]["alert_level"] in ("RED", "ORANGE")
    actions = data["plan"]["actions"]
    evac_or_warn = [a for a in actions if a["action"] in ("EVACUATE_ZONE", "ISSUE_WARNING", "PREPARE_EVACUATION")]
    assert len(evac_or_warn) >= 1


def test_post_simulate_response_plan_valid(client):
    sim_payload = {
        "scenario_id": "SCN-RAIN-20",
        "changes": {"rainfall_multiplier": 1.20},
    }
    response = client.post("/api/v1/response/simulate", json=sim_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"]["simulated"] is True
    assert "SCN-RAIN-20" in data["plan"]["plan_id"]
    for act in data["plan"]["actions"]:
        assert act["simulated"] is True


def test_post_simulate_response_plan_invalid_scenario_404(client):
    sim_payload = {
        "scenario_id": "SCN-NON-EXISTENT-XYZ",
    }
    response = client.post("/api/v1/response/simulate", json=sim_payload)
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_post_evaluate_malformed_telemetry_422(client):
    bad_payload = {
        "telemetry": {
            "telemetry_id": "TEL-BAD",
            "sensors": {
                "temperature_celsius": "NOT_A_FLOAT",
            }
        }
    }
    response = client.post("/api/v1/response/evaluate", json=bad_payload)
    assert response.status_code == 422
