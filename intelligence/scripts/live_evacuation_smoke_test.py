"""
Phase 6 Live Smoke Test: Dynamic Evacuation & Adaptive Route Intelligence.
Exercises POST /api/v1/evacuation/evaluate, GET /api/v1/evacuation/routes, and GET /api/v1/evacuation/current.
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
FIXTURES_DIR = WORKSPACE_ROOT / "intelligence" / "tests" / "fixtures"


def _load_fixture(filename: str):
    path = FIXTURES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def run_live_smoke():
    print("=" * 60)
    print("CLIMATE EYE VIEW — PHASE 6 EVACUATION & ROUTING LIVE SMOKE")
    print("=" * 60)

    # 1. Normal baseline zone (stand-by recommendation, 0 evacuees)
    payload_norm = _load_fixture("evacuation_normal.json")
    r = client.post("/api/v1/evacuation/evaluate", json=payload_norm)
    assert r.status_code == 200, f"Normal failed: {r.text}"
    body = r.json()
    assert body["success"] is True
    assert body["recommendation_count"] == 1
    assert body["total_evacuated_population"] == 0
    rec = body["recommendations"][0]
    assert rec["status"] == "RECOMMENDED"
    assert rec["population_to_evacuate"] == 0
    print("[PASS] Normal baseline -> Standby directive, 0 evacuees")

    # 2. Critical Flood in Zone A -> Full evacuation route to North Shelter
    payload_flood = _load_fixture("evacuation_flood.json")
    r = client.post("/api/v1/evacuation/evaluate", json=payload_flood)
    assert r.status_code == 200, f"Flood failed: {r.text}"
    body = r.json()
    assert body["success"] is True
    assert body["recommendation_count"] == 1
    assert body["total_evacuated_population"] > 0
    rec = body["recommendations"][0]
    assert rec["status"] == "RECOMMENDED"
    assert rec["destination"]["shelter_id"] == "SHELTER-NORTH"
    assert rec["route"]["destination_node"] == "SHELTER-NORTH"
    assert rec["route"]["safety_score"] >= 0.80
    print(f"[PASS] Critical Flood -> Dest: {rec['destination']['shelter_name']}, Evacuees: {rec['destination']['assigned_population']:,}, Safety: {rec['route']['safety_score']}")

    # 3. Hazard-Aware Route Selection (Avoids short hazardous road, chooses safe path)
    payload_hazard = _load_fixture("evacuation_hazard_vs_short.json")
    r = client.post("/api/v1/evacuation/evaluate", json=payload_hazard)
    assert r.status_code == 200
    rec = r.json()["recommendations"][0]
    assert "INT-SAFE" in rec["route"]["nodes"]
    assert "INT-DANGER" not in rec["route"]["nodes"]
    assert rec["route"]["safety_score"] >= 0.85
    print(f"[PASS] Hazard-Aware Routing -> Chose safe corridor via {rec['route']['nodes']}, Safety: {rec['route']['safety_score']}")

    # 4. Road Closure Dynamic Reroute (Primary bridge closed -> routes to East complex)
    payload_closure = _load_fixture("evacuation_road_closure.json")
    r = client.post("/api/v1/evacuation/evaluate", json=payload_closure)
    assert r.status_code == 200
    rec = r.json()["recommendations"][0]
    assert rec["destination"]["shelter_id"] == "SHELTER-EAST"
    assert "ROAD-1-NORTH" in rec["avoid_edges"]
    print(f"[PASS] Dynamic Reroute -> Closed bridge avoided: {rec['avoid_edges']}, New dest: {rec['destination']['shelter_name']}")

    # 5. GET /api/v1/evacuation/routes & /api/v1/evacuation/current
    r = client.get("/api/v1/evacuation/routes")
    assert r.status_code == 200
    assert r.json()["recommendation_count"] >= 1
    r_curr = client.get("/api/v1/evacuation/current")
    assert r_curr.status_code == 200
    assert r_curr.json()["recommendation_count"] == r.json()["recommendation_count"]
    print(f"[PASS] GET routes endpoints -> {r.json()['recommendation_count']} cached recommendations retrieved")

    # 6. Negative test: Empty shelters rejected with HTTP 422
    payload_bad = dict(payload_flood)
    payload_bad["shelters"] = []
    r = client.post("/api/v1/evacuation/evaluate", json=payload_bad)
    assert r.status_code == 422
    print("[PASS] Negative test: Empty shelters rejected with HTTP 422")

    # 7. Negative test: Negative capacity rejected with HTTP 422
    payload_bad_cap = dict(payload_flood)
    payload_bad_cap["shelters"] = [dict(payload_flood["shelters"][0], capacity=-500)]
    r = client.post("/api/v1/evacuation/evaluate", json=payload_bad_cap)
    assert r.status_code == 422
    print("[PASS] Negative test: Negative shelter capacity rejected with HTTP 422")

    # 8. Forensic Remediation Scenario: Dynamic Accessibility Degradation & Invalidation
    payload_remediation = _load_fixture("evacuation_multiple_shelters.json")
    # Step 1: Initial evaluation yields valid route to SHELTER-NORTH
    r1 = client.post("/api/v1/evacuation/evaluate", json=payload_remediation)
    assert r1.status_code == 200
    rec1 = r1.json()["recommendations"][0]
    assert rec1["status"] == "RECOMMENDED"
    assert rec1["destination"]["shelter_id"] == "SHELTER-NORTH"
    initial_route_nodes = rec1["route"]["nodes"]
    prov1 = rec1["provenance_hash"]

    # Step 2: Accessibility degradation on primary corridor (ROAD-A-1: 0.90 -> 0.20 < threshold 0.40)
    payload_degraded = json.loads(json.dumps(payload_remediation))
    for edge in payload_degraded["road_network"]["edges"]:
        if edge["edge_id"] == "ROAD-A-1":
            edge["accessibility"] = 0.20  # Below 0.40 threshold, closed remains False

    r2 = client.post("/api/v1/evacuation/evaluate", json=payload_degraded)
    assert r2.status_code == 200
    rec2 = r2.json()["recommendations"][0]
    prov2 = rec2["provenance_hash"]
    # Provenance hash must change due to material input degradation
    assert prov1 != prov2
    # Old route is invalidated; alternative route to SHELTER-EAST selected
    assert rec2["status"] == "RECOMMENDED"
    assert rec2["destination"]["shelter_id"] == "SHELTER-EAST"
    assert "ROAD-A-1" in rec2["avoid_edges"]
    print(f"[PASS] Dynamic Accessibility Invalidation -> Degraded edge ROAD-A-1 avoided, Route adapted to: {rec2['destination']['shelter_name']}")

    # Step 3: Complete network accessibility degradation causes NO_ROUTE
    payload_severed = json.loads(json.dumps(payload_degraded))
    for edge in payload_severed["road_network"]["edges"]:
        edge["accessibility"] = 0.15  # All edges below threshold 0.40
    r3 = client.post("/api/v1/evacuation/evaluate", json=payload_severed)
    assert r3.status_code == 200
    rec3 = r3.json()["recommendations"][0]
    assert rec3["status"] == "NO_ROUTE"
    assert rec3["destination"] is None
    assert rec3["route"] is None
    print(f"[PASS] Total Accessibility Degradation -> Deterministically returned NO_ROUTE ({rec3['no_route_reason']})")

    print("=" * 60)
    print("ALL 8 PHASE 6 EVACUATION LIVE SMOKE SCENARIOS PASSED.")
    print("=" * 60)


if __name__ == "__main__":
    run_live_smoke()
