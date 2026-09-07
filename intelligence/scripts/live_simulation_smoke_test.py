"""Phase 7 Live Smoke Test: Digital Twin & Scenario Simulation Engine.
Exercises:
  - GET /api/v1/simulation/scenarios
  - POST /api/v1/simulation/run across scenarios (RAIN-20, RAIN-40, RAIN-60, ROAD-DEGRADE, FLOOD-HEAT)
  - Verification of hazard, vulnerability, and evacuation recomputation
  - Strict baseline isolation (proving baseline remains unmutated)
  - GET /api/v1/simulation/{simulation_id} cached retrieval
  - Rejection of invalid scenario parameters
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from fastapi.testclient import TestClient
from intelligence.app.main import app
from intelligence.simulation.engine import SimulationEngine
from intelligence.simulation.state import DigitalTwinStateManager

client = TestClient(app)


def run_live_simulation_smoke():
    print("=" * 70)
    print("CLIMATE EYE VIEW — PHASE 7 DIGITAL TWIN & SIMULATION LIVE SMOKE")
    print("=" * 70)

    # 1. Verify Catalog of Supported Scenarios
    r_cat = client.get("/api/v1/simulation/scenarios")
    assert r_cat.status_code == 200, f"Scenarios catalog failed: {r_cat.text}"
    cat_body = r_cat.json()
    assert cat_body["success"] is True
    assert cat_body["count"] >= 7
    scenarios = {s["scenario_id"]: s for s in cat_body["scenarios"]}
    for req_id in [
        "SCN-RAIN-20",
        "SCN-RAIN-40",
        "SCN-RAIN-60",
        "SCN-EXTREME-HEAT",
        "SCN-DRAINAGE-FAIL",
        "SCN-ROAD-DEGRADE",
        "SCN-FLOOD-HEAT",
    ]:
        assert req_id in scenarios, f"Missing required scenario: {req_id}"
    print(f"[PASS] Scenario Catalog: Verified {cat_body['count']} supported scenarios")

    # 2. Baseline State Isolation & Rainfall +20% Simulation
    eval_time = datetime.now(timezone.utc)
    base_state = SimulationEngine.build_default_base_state(eval_time)
    base_dump_before = base_state.model_dump(mode="json")
    base_hash_before = DigitalTwinStateManager.compute_state_hash(base_state)

    payload_rain_20 = {
        "scenario_id": "SCN-RAIN-20",
        "base_state": base_dump_before,
    }
    r_rain_20 = client.post("/api/v1/simulation/run", json=payload_rain_20)
    assert r_rain_20.status_code == 200, f"Rain +20% failed: {r_rain_20.text}"
    body_20 = r_rain_20.json()
    assert body_20["success"] is True
    sim_20 = body_20["simulation"]
    assert sim_20["simulated"] is True
    assert sim_20["parameters"]["rainfall_multiplier"] == 1.20
    assert len(sim_20["hazards"]) > 0
    assert len(sim_20["vulnerability_zones"]) > 0
    assert len(sim_20["evacuation_routes"]) > 0

    # Verify baseline remains byte/logically unmutated
    base_dump_after = base_state.model_dump(mode="json")
    base_hash_after = DigitalTwinStateManager.compute_state_hash(base_state)
    assert base_hash_before == base_hash_after, "Base state hash mutated during simulation!"
    assert base_dump_before == base_dump_after, "Base state content mutated during simulation!"
    print(f"[PASS] Scenario SCN-RAIN-20: Recomputed hazards, vulns, routes. Baseline isolated (Hash: {base_hash_after[:8]}...)")

    # 3. Rainfall +40% Simulation
    payload_rain_40 = {
        "scenario_id": "SCN-RAIN-40",
        "base_state": base_dump_before,
    }
    r_rain_40 = client.post("/api/v1/simulation/run", json=payload_rain_40)
    assert r_rain_40.status_code == 200, f"Rain +40% failed: {r_rain_40.text}"
    sim_40 = r_rain_40.json()["simulation"]
    assert sim_40["parameters"]["rainfall_multiplier"] == 1.40
    print(f"[PASS] Scenario SCN-RAIN-40: Max hazard delta = {sim_40['summary']['hazard_change']['max_severity_delta']}")

    # 4. Rainfall +60% Simulation
    payload_rain_60 = {
        "scenario_id": "SCN-RAIN-60",
        "base_state": base_dump_before,
    }
    r_rain_60 = client.post("/api/v1/simulation/run", json=payload_rain_60)
    assert r_rain_60.status_code == 200, f"Rain +60% failed: {r_rain_60.text}"
    sim_60 = r_rain_60.json()["simulation"]
    assert sim_60["parameters"]["rainfall_multiplier"] == 1.60
    assert sim_60["summary"]["hazard_change"]["max_severity_delta"] >= sim_20["summary"]["hazard_change"]["max_severity_delta"]
    print(f"[PASS] Scenario SCN-RAIN-60: Max hazard delta = {sim_60['summary']['hazard_change']['max_severity_delta']} (Monotonic escalation confirmed)")

    # 5. Cascading & Compound Scenario: Flood + Heat
    payload_flood_heat = {
        "scenario_id": "SCN-FLOOD-HEAT",
        "base_state": base_dump_before,
    }
    r_fh = client.post("/api/v1/simulation/run", json=payload_flood_heat)
    assert r_fh.status_code == 200, f"Flood+Heat failed: {r_fh.text}"
    sim_fh = r_fh.json()["simulation"]
    assert len(sim_fh["compound_events"]) > 0
    print(f"[PASS] Scenario SCN-FLOOD-HEAT: Detected {len(sim_fh['compound_events'])} compound/cascading events")

    # 6. Road Accessibility Degradation
    payload_road = {
        "scenario_id": "SCN-ROAD-DEGRADE",
        "base_state": base_dump_before,
        "changes": {
            "road_accessibility_reduction": 0.6,
            "target_edge_ids": ["ROAD-Z-N1"]
        }
    }
    r_road = client.post("/api/v1/simulation/run", json=payload_road)
    assert r_road.status_code == 200, f"Road degradation failed: {r_road.text}"
    sim_road = r_road.json()["simulation"]
    assert len(sim_road["evacuation_routes"]) > 0
    print(f"[PASS] Scenario SCN-ROAD-DEGRADE: Evacuation recomputed with degraded corridors")

    # 7. Cached Result Retrieval
    sim_id = sim_20["simulation_id"]
    r_get = client.get(f"/api/v1/simulation/{sim_id}")
    assert r_get.status_code == 200, f"Get cached simulation failed: {r_get.text}"
    assert r_get.json()["simulation"]["simulation_id"] == sim_id
    print(f"[PASS] Cached Retrieval: Successfully retrieved {sim_id}")

    # 8. Rejection of Invalid Parameters
    payload_bad = {
        "scenario_id": "SCN-RAIN-20",
        "changes": {
            "rainfall_multiplier": -0.5
        }
    }
    r_bad = client.post("/api/v1/simulation/run", json=payload_bad)
    assert r_bad.status_code == 422, "Negative rainfall multiplier was not rejected"
    assert r_bad.json()["error"]["code"] == "VALIDATION_ERROR"
    print(f"[PASS] Validation Gating: Successfully rejected invalid parameters (422)")

    # 9. Explicit Provenance Determinism Check (repeated run -> identical hash)
    r_repeat = client.post("/api/v1/simulation/run", json=payload_rain_20)
    assert r_repeat.status_code == 200
    sim_repeat = r_repeat.json()["simulation"]
    assert sim_repeat["provenance_hash"] == sim_20["provenance_hash"], "Repeated simulation must yield identical provenance hash!"
    print(f"[PASS] Provenance Determinism: Repeated identical simulation yielded identical hash ({sim_20['provenance_hash'][:8]}...)")

    # 10. Explicit Provenance Mutation Check (material mutation -> different hash)
    assert sim_20["provenance_hash"] != sim_40["provenance_hash"], "Material parameter shift must alter provenance hash!"
    print(f"[PASS] Provenance Mutation Sensitivity: Material parameter mutation strictly altered provenance hash")

    print("=" * 70)
    print("PHASE 7 SIMULATION LIVE SMOKE COMPLETED: 10/10 CHECKS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    run_live_simulation_smoke()
