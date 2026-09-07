"""Live Forensic Smoke Test for Climate Eye View Phase 2 Intelligence Service.

Tests:
  - GET /health
  - GET /ready
  - POST /api/v1/hazards/evaluate with:
      1. Normal telemetry
      2. Heat critical telemetry
      3. Flood critical telemetry
      4. Drought critical telemetry
      5. Missing sensor telemetry (verifies status=UNAVAILABLE, null != 0)
      6. Stale telemetry (verifies confidence penalty)
      7. Anomalous telemetry (verifies confidence penalty)
      8. Invalid telemetry (verifies structured error response)
      9. Missing telemetry field (verifies structured error response)
     10. Filtered hazards (verifies subset evaluation)
"""

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
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def run_smoke_tests():
    print("============================================================")
    print("CLIMATE EYE VIEW — PHASE 2 LIVE FORENSIC VERIFICATION")
    print("============================================================")

    # 1. Health Probe
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health failed: {resp.text}"
    print(f"[PASS] GET /health -> {resp.json()}")

    # 2. Readiness Probe
    resp = client.get("/ready")
    assert resp.status_code == 200, f"Ready failed: {resp.text}"
    print(f"[PASS] GET /ready -> {resp.json()}")

    # 3. Normal Telemetry
    norm_data = load_fixture("normal_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": norm_data})
    assert resp.status_code == 200, f"Normal eval failed: {resp.text}"
    res = resp.json()
    assert res["success"] is True
    assert len(res["hazards"]) == 3
    for h in res["hazards"]:
        assert h["forecast_horizon_minutes"] == 0
        assert h["simulated"] is False
        assert 0.0 <= h["severity"] <= 1.0
        assert 0.0 <= h["confidence"] <= 1.0
        assert h["status"] in ["NOT_DETECTED", "DETECTED"]
    print(f"[PASS] POST /api/v1/hazards/evaluate (normal) -> {[h['hazard'] + '=' + h['classification'] for h in res['hazards']]}")

    # 4. Critical Heat Telemetry
    heat_data = load_fixture("heat_critical_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": heat_data})
    assert resp.status_code == 200
    res = resp.json()
    heat = next(h for h in res["hazards"] if h["hazard"] == "heat")
    assert heat["classification"] == "CRITICAL"
    assert heat["status"] == "DETECTED"
    assert heat["severity"] >= 0.80
    assert heat["model_version"] == "heat-v1"
    assert heat["forecast_horizon_minutes"] == 0
    print(f"[PASS] POST /api/v1/hazards/evaluate (critical heat) -> severity={heat['severity']}, drivers={heat['drivers']}")

    # 5. Critical Flood Telemetry
    flood_data = load_fixture("critical_flood_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": flood_data})
    assert resp.status_code == 200
    res = resp.json()
    flood = next(h for h in res["hazards"] if h["hazard"] == "flood")
    assert flood["classification"] == "CRITICAL"
    assert flood["status"] == "DETECTED"
    assert flood["severity"] >= 0.80
    assert flood["model_version"] == "flood-v1"
    print(f"[PASS] POST /api/v1/hazards/evaluate (critical flood) -> severity={flood['severity']}, drivers={flood['drivers']}")

    # 6. Critical Drought Telemetry
    drought_data = load_fixture("drought_critical_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": drought_data})
    assert resp.status_code == 200
    res = resp.json()
    drought = next(h for h in res["hazards"] if h["hazard"] == "drought")
    assert drought["classification"] == "CRITICAL"
    assert drought["status"] == "DETECTED"
    assert drought["severity"] >= 0.80
    assert drought["model_version"] == "drought-v1"
    print(f"[PASS] POST /api/v1/hazards/evaluate (critical drought) -> severity={drought['severity']}, drivers={drought['drivers']}")

    # 7. Missing Sensor Telemetry (null != zero check)
    missing_data = load_fixture("missing_sensor_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": missing_data})
    assert resp.status_code == 200
    res = resp.json()
    missing_flood = next(h for h in res["hazards"] if h["hazard"] == "flood")
    assert missing_flood["status"] == "UNAVAILABLE"
    assert missing_flood["severity"] == 0.0
    assert missing_flood["classification"] is None
    print(f"[PASS] POST /api/v1/hazards/evaluate (missing water_level) -> status=UNAVAILABLE (null != 0 verified)")

    # 8. Stale Telemetry (confidence degradation)
    stale_data = load_fixture("stale_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": stale_data})
    assert resp.status_code == 200
    res = resp.json()
    # Telemetry is from 2026-09-06, which is > 5 minutes stale compared to now
    for h in res["hazards"]:
        assert h["confidence"] < 0.90
    print(f"[PASS] POST /api/v1/hazards/evaluate (stale telemetry) -> confidence penalized to {[h['confidence'] for h in res['hazards']]}")

    # 9. Anomalous Telemetry (confidence degradation)
    anom_data = load_fixture("anomalous_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": anom_data})
    assert resp.status_code == 200
    res = resp.json()
    for h in res["hazards"]:
        assert h["confidence"] <= 0.80
    print(f"[PASS] POST /api/v1/hazards/evaluate (anomalous telemetry) -> confidence reduced to {[h['confidence'] for h in res['hazards']]}")

    # 10. Invalid Telemetry (schema violation)
    invalid_data = load_fixture("invalid_telemetry.json")
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": invalid_data})
    assert resp.status_code == 422
    res = resp.json()
    assert res["success"] is False
    assert res["error"]["code"] == "VALIDATION_ERROR"
    print(f"[PASS] POST /api/v1/hazards/evaluate (invalid telemetry) -> HTTP 422 {res['error']['code']}")

    # 11. Missing 'telemetry' field
    resp = client.post("/api/v1/hazards/evaluate", json={"wrong_key": 123})
    assert resp.status_code == 422
    res = resp.json()
    assert res["success"] is False
    assert res["error"]["code"] == "VALIDATION_ERROR"
    print(f"[PASS] POST /api/v1/hazards/evaluate (missing field) -> HTTP 422 {res['error']['message']}")

    # 12. Hazard Filtering
    resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": norm_data, "hazards": ["flood"]})
    assert resp.status_code == 200
    res = resp.json()
    assert len(res["hazards"]) == 1
    assert res["hazards"][0]["hazard"] == "flood"
    print(f"[PASS] POST /api/v1/hazards/evaluate (filtered hazards=['flood']) -> evaluated only flood")

    print("============================================================")
    print("ALL 12 LIVE SCENARIO AUDITS PASSED WITH ZERO ERRORS.")
    print("============================================================")


if __name__ == "__main__":
    run_smoke_tests()
