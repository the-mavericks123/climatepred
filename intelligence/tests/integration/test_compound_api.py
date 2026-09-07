"""
Integration tests for Phase 4: POST /api/v1/compound/evaluate endpoint.
Tests end-to-end API execution from raw Phase 2 HazardResult and Phase 3 PredictionResult payloads.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app

client = TestClient(app)
T_NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc).isoformat()


def _build_hazard_dict(hazard: str, severity: float, conf: float = 0.90, feats: dict = None):
    return {
        "hazard_id": f"HAZ-{hazard.upper()}-TEST",
        "hazard": hazard,
        "severity": severity,
        "confidence": conf,
        "classification": "HIGH" if severity >= 0.70 else "MODERATE",
        "status": "DETECTED",
        "timestamp": T_NOW,
        "forecast_horizon_minutes": 0,
        "location": {"lat": 25.5941, "lon": 85.1376},
        "features": feats or {},
        "drivers": [f"Test {hazard} active"],
        "model_version": f"{hazard}-v1",
        "simulated": False,
        "provenance_hash": f"prov-{hazard}",
    }


def _build_pred_dict(hazard: str, severity: float, horizon: int = 60, conf: float = 0.85):
    return {
        "prediction_id": f"PRED-{hazard.upper()}-{horizon}M",
        "hazard": hazard,
        "prediction_time": T_NOW,
        "forecast_time": (datetime.fromisoformat(T_NOW) + timedelta(minutes=horizon)).isoformat(),
        "forecast_horizon_minutes": horizon,
        "severity": severity,
        "confidence": conf,
        "classification": "HIGH" if severity >= 0.70 else "MODERATE",
        "status": "DETECTED",
        "model_version": f"{hazard}-pred-v1",
        "source_hazard_id": f"HAZ-{hazard.upper()}",
        "provenance_hash": f"prov-pred-{hazard}",
        "drivers": [f"Predicted {hazard}"],
        "data_quality": {"sample_count": 5},
        "predicted_features": {},
        "simulated": False,
    }


class TestCompoundAPI:
    def test_evaluate_compound_heat_drought_success(self):
        payload = {
            "timestamp": T_NOW,
            "hazards": [
                _build_hazard_dict("heat", 0.78),
                _build_hazard_dict("drought", 0.82),
            ],
            "predictions": [],
        }
        res = client.post("/api/v1/compound/evaluate", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["event_count"] >= 1
        event = body["events"][0]
        assert event["event_type"] in ["COMPOUND", "CASCADE"]
        assert 0.0 <= event["severity"] <= 1.0
        assert 0.0 <= event["confidence"] <= 1.0
        assert event["simulated"] is False

    def test_evaluate_cascade_flood_success(self):
        payload = {
            "timestamp": T_NOW,
            "hazards": [
                _build_hazard_dict("flood", 0.85, feats={"water_level": 12.0, "rainfall": 80.0}),
            ],
            "predictions": [],
        }
        res = client.post("/api/v1/compound/evaluate", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["event_count"] >= 1
        cascade = next(e for e in body["events"] if e["event_type"] == "CASCADE")
        assert "flood" in cascade["chain"]
        assert "inferred_road_failure_risk" in cascade["chain"]

    def test_evaluate_empty_payload_returns_zero_events(self):
        payload = {"hazards": [], "predictions": []}
        res = client.post("/api/v1/compound/evaluate", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["event_count"] == 0
        assert body["events"] == []

    def test_evaluate_invalid_hazard_schema_returns_422(self):
        payload = {
            "hazards": [{"hazard_id": "INVALID", "severity": 1.5}],  # Out of range severity
        }
        res = client.post("/api/v1/compound/evaluate", json=payload)
        assert res.status_code == 422
        body = res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_get_current_compound_events(self):
        # 1. Post a valid compound payload
        payload = {
            "timestamp": T_NOW,
            "hazards": [
                _build_hazard_dict("heat", 0.82),
                _build_hazard_dict("drought", 0.78),
            ],
            "predictions": [],
        }
        post_res = client.post("/api/v1/compound/evaluate", json=payload)
        assert post_res.status_code == 200

        # 2. Get current events
        get_res = client.get("/api/v1/compound-events/current")
        assert get_res.status_code == 200
        body = get_res.json()
        assert body["success"] is True
        assert body["event_count"] >= 1
        assert any(e["event_type"] == "COMPOUND" for e in body["events"])
