"""Live Forensic Smoke Test for Climate Eye View Phase 3 Prediction Engine.

Tests:
  - POST /api/v1/predictions/evaluate with:
      1. Stable conditions fixture (all 3 hazards across all 3 horizons: 30m, 60m, 360m)
      2. Heat prediction 30m fixture
      3. Heat prediction 1h fixture
      4. Heat prediction 6h fixture
      5. Flood prediction 30m fixture
      6. Flood prediction 1h fixture
      7. Flood prediction 6h fixture
      8. Drought prediction 30m fixture
      9. Drought prediction 1h fixture
     10. Drought prediction 6h fixture
     11. Insufficient history fixture (persistence fallback & penalty check)
     12. Future leakage fixture (checks that future data is completely ignored)
     13. Unsupported horizon rejection (HTTP 422 VALIDATION_ERROR)
     14. Missing telemetry payload rejection (HTTP 422 VALIDATION_ERROR)
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


def run_prediction_smoke_tests():
    print("============================================================")
    print("CLIMATE EYE VIEW — PHASE 3 PREDICTION FORENSIC VERIFICATION")
    print("============================================================")

    # 1. Stable Conditions (9 predictions: 3 hazards * 3 horizons)
    stable_data = load_fixture("prediction_stable.json")
    resp = client.post("/api/v1/predictions/evaluate", json=stable_data)
    assert resp.status_code == 200, f"Stable eval failed: {resp.text}"
    res = resp.json()
    assert res["success"] is True
    assert len(res["predictions"]) == 9
    for p in res["predictions"]:
        assert p["forecast_horizon_minutes"] in [30, 60, 360]
        assert p["simulated"] is False
        assert 0.0 <= p["severity"] <= 1.0
        assert 0.0 <= p["confidence"] <= 1.0
        assert p["model_version"].endswith("-pred-v1")
        assert len(p["provenance_hash"]) >= 8
    print(f"[PASS] POST /api/v1/predictions/evaluate (stable) -> 9 predictions evaluated")

    # 2-4. Heat Horizons (30m, 1h, 6h)
    for fname, horizon in [("prediction_heat_30m.json", 30), ("prediction_heat_1h.json", 60), ("prediction_heat_6h.json", 360)]:
        data = load_fixture(fname)
        resp = client.post("/api/v1/predictions/evaluate", json=data)
        assert resp.status_code == 200
        p = resp.json()["predictions"][0]
        assert p["hazard"] == "heat"
        assert p["forecast_horizon_minutes"] == horizon
        assert p["model_version"] == "heat-pred-v1"
        assert p["severity"] >= 0.50
        print(f"[PASS] POST /api/v1/predictions/evaluate ({fname}) -> horizon={horizon}m severity={p['severity']} conf={p['confidence']}")

    # 5-7. Flood Horizons (30m, 1h, 6h)
    for fname, horizon in [("prediction_flood_30m.json", 30), ("prediction_flood_1h.json", 60), ("prediction_flood_6h.json", 360)]:
        data = load_fixture(fname)
        resp = client.post("/api/v1/predictions/evaluate", json=data)
        assert resp.status_code == 200
        p = resp.json()["predictions"][0]
        assert p["hazard"] == "flood"
        assert p["forecast_horizon_minutes"] == horizon
        assert p["model_version"] == "flood-pred-v1"
        assert p["severity"] >= 0.50
        print(f"[PASS] POST /api/v1/predictions/evaluate ({fname}) -> horizon={horizon}m severity={p['severity']} conf={p['confidence']}")

    # 8-10. Drought Horizons (30m, 1h, 6h)
    for fname, horizon in [("prediction_drought_30m.json", 30), ("prediction_drought_1h.json", 60), ("prediction_drought_6h.json", 360)]:
        data = load_fixture(fname)
        resp = client.post("/api/v1/predictions/evaluate", json=data)
        assert resp.status_code == 200
        p = resp.json()["predictions"][0]
        assert p["hazard"] == "drought"
        assert p["forecast_horizon_minutes"] == horizon
        assert p["model_version"] == "drought-pred-v1"
        assert p["severity"] >= 0.60
        print(f"[PASS] POST /api/v1/predictions/evaluate ({fname}) -> horizon={horizon}m severity={p['severity']} conf={p['confidence']}")

    # 11. Insufficient History Fallback
    insuf_data = load_fixture("prediction_insufficient_history.json")
    resp = client.post("/api/v1/predictions/evaluate", json=insuf_data)
    assert resp.status_code == 200
    res = resp.json()
    for p in res["predictions"]:
        assert p["confidence"] <= 0.60
        assert p["data_quality"]["has_insufficient_history"] is True
    print(f"[PASS] POST /api/v1/predictions/evaluate (insufficient history) -> persistence fallback and confidence penalized")

    # 12. Future Leakage Filter
    leak_data = load_fixture("prediction_future_leakage.json")
    resp = client.post("/api/v1/predictions/evaluate", json=leak_data)
    assert resp.status_code == 200
    p_leak = resp.json()["predictions"][0]
    # Injected future readings had 60C and 65C. If leakage occurred, severity would be 1.0.
    # Without leakage, temperature at T is 40C, projected +30m is ~44.5C.
    assert p_leak["predicted_features"]["temperature"] < 50.0
    print(f"[PASS] POST /api/v1/predictions/evaluate (future leakage) -> future observations discarded, temp={p_leak['predicted_features']['temperature']}C")

    # 13. Unsupported Horizon Rejected
    unsupp_data = dict(stable_data)
    unsupp_data["horizons_minutes"] = [15, 60]
    resp = client.post("/api/v1/predictions/evaluate", json=unsupp_data)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    print(f"[PASS] POST /api/v1/predictions/evaluate (unsupported horizon 15m) -> HTTP 422 VALIDATION_ERROR")

    # 14. Missing Telemetry Rejected
    resp = client.post("/api/v1/predictions/evaluate", json={})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    print(f"[PASS] POST /api/v1/predictions/evaluate (empty payload) -> HTTP 422 VALIDATION_ERROR")

    print("============================================================")
    print("ALL 14 PHASE 3 PREDICTION SMOKE SCENARIOS PASSED.")
    print("============================================================")


if __name__ == "__main__":
    run_prediction_smoke_tests()
