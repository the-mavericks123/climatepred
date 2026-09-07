"""
Phase 4 Live Smoke Test: Compound & Cascading Disaster Engine.
Exercises POST /api/v1/compound/evaluate and GET /api/v1/compound-events/current.
"""

from datetime import datetime, timezone
import json
import sys
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from fastapi.testclient import TestClient

from intelligence.app.main import app

client = TestClient(app)
T_NOW = datetime.now(timezone.utc).isoformat()


def run_live_smoke():
    print("=" * 60)
    print("CLIMATE EYE VIEW — PHASE 4 COMPOUND & CASCADE SMOKE AUDIT")
    print("=" * 60)

    # 1. Normal conditions
    r = client.post("/api/v1/compound/evaluate", json={"hazards": [], "predictions": []})
    assert r.status_code == 200, f"Normal failed: {r.text}"
    body = r.json()
    assert body["success"] is True
    assert body["event_count"] == 0
    print("[PASS] Normal baseline -> 0 events")

    # 2. Compound Heat + Drought
    heat_hazard = {
        "hazard_id": "HAZ-HEAT-001",
        "hazard": "heat",
        "status": "DETECTED",
        "severity": 0.84,
        "confidence": 0.90,
        "classification": "CRITICAL",
        "timestamp": T_NOW,
        "forecast_horizon_minutes": 0,
        "location": {"lat": 37.7749, "lon": -122.4194},
        "features": {"temperature": 45.0, "humidity": 15.0},
        "drivers": ["Extreme ambient temperature"],
        "model_version": "heat-v1",
        "provenance_hash": "a" * 64,
        "simulated": False,
    }
    drought_hazard = {
        "hazard_id": "HAZ-DROUGHT-001",
        "hazard": "drought",
        "status": "DETECTED",
        "severity": 0.80,
        "confidence": 0.88,
        "classification": "CRITICAL",
        "timestamp": T_NOW,
        "forecast_horizon_minutes": 0,
        "location": {"lat": 37.7749, "lon": -122.4194},
        "features": {"soil_moisture": 6.0},
        "drivers": ["Severe soil moisture deficit"],
        "model_version": "drought-v1",
        "provenance_hash": "b" * 64,
        "simulated": False,
    }

    r = client.post("/api/v1/compound/evaluate", json={"hazards": [heat_hazard, drought_hazard]})
    assert r.status_code == 200, f"Compound failed: {r.text}"
    body = r.json()
    assert body["event_count"] >= 1
    compound_event = next(e for e in body["events"] if e["event_type"] == "COMPOUND")
    assert "heat" in compound_event["chain"]
    assert "drought" in compound_event["chain"]
    assert 0.0 <= compound_event["severity"] <= 1.0
    assert 0.0 <= compound_event["confidence"] <= 1.0
    print(f"[PASS] Compound Heat + Drought -> Event {compound_event['event_id']}, sev={compound_event['severity']}, conf={compound_event['confidence']}")

    # 3. Cascade: Heavy Rain -> Soil Saturation -> Flood -> Road Inundation -> Access Loss
    flood_hazard = {
        "hazard_id": "HAZ-FLOOD-001",
        "hazard": "flood",
        "status": "DETECTED",
        "severity": 0.88,
        "confidence": 0.91,
        "classification": "CRITICAL",
        "timestamp": T_NOW,
        "forecast_horizon_minutes": 0,
        "location": {"lat": 37.7749, "lon": -122.4194},
        "features": {"water_level": 14.5, "rainfall": 85.0},
        "drivers": ["Intense precipitation", "Rising river stage"],
        "model_version": "flood-v1",
        "provenance_hash": "c" * 64,
        "simulated": False,
    }
    r = client.post("/api/v1/compound/evaluate", json={"hazards": [flood_hazard]})
    assert r.status_code == 200, f"Cascade failed: {r.text}"
    body = r.json()
    assert body["event_count"] >= 1
    cascade_event = next(e for e in body["events"] if e["event_type"] == "CASCADE")
    assert "flood" in cascade_event["chain"]
    assert "inferred_road_failure_risk" in cascade_event["chain"]
    print(f"[PASS] Flood Cascade -> Chain: {' -> '.join(cascade_event['chain'])}")

    # 4. Predicted flood cascade at +60m
    pred_flood = {
        "prediction_id": "PRED-FLOOD-060",
        "hazard": "flood",
        "status": "DETECTED",
        "severity": 0.86,
        "confidence": 0.85,
        "classification": "CRITICAL",
        "prediction_time": T_NOW,
        "forecast_time": T_NOW,
        "forecast_horizon_minutes": 60,
        "predicted_features": {"water_level": 12.0},
        "drivers": ["Projected river crest in 60m"],
        "model_version": "prediction-flood-v1",
        "provenance_hash": "d" * 64,
        "simulated": False,
    }
    r = client.post("/api/v1/compound/evaluate", json={"predictions": [pred_flood]})
    assert r.status_code == 200
    body = r.json()
    assert body["event_count"] >= 1
    pred_cascade = next(e for e in body["events"] if e["event_type"] == "CASCADE")
    assert "predicted_access_loss" in pred_cascade["chain"]
    print(f"[PASS] Predicted Flood Cascade -> Chain: {' -> '.join(pred_cascade['chain'])}")

    # 5. GET /api/v1/compound-events/current
    r = client.get("/api/v1/compound-events/current")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["event_count"] >= 1
    print(f"[PASS] GET /api/v1/compound-events/current -> {body['event_count']} active events retrieved")

    # 6. Negative test: Out of bounds severity rejected
    r = client.post("/api/v1/compound/evaluate", json={"hazards": [{"hazard_id": "H1", "severity": 2.0}]})
    assert r.status_code == 422
    print("[PASS] Security gate -> HTTP 422 rejected invalid severity")

    print("=" * 60)
    print("ALL 6 PHASE 4 COMPOUND LIVE SMOKE SCENARIOS PASSED.")
    print("=" * 60)


if __name__ == "__main__":
    run_live_smoke()
