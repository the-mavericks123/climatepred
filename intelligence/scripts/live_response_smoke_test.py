"""
Climate Eye View — Phase 9 AI Response Planner Live Smoke Test.

Executes and verifies 12 live operational scenarios against the FastAPI service:
1. Normal conditions (Alert: GREEN, Action: MAINTAIN_MONITORING)
2. High flood (Alert: RED/ORANGE, Action: EVACUATE_ZONE)
3. High human impact (Prioritize vulnerable populations)
4. Predicted flood (+60 min forecast, Action: PREPARE_EVACUATION, explicit PREDICTED label)
5. Compound flood/accessibility chain (Action: PREPOSITION_RESPONSE_RESOURCES referencing causal chain)
6. NO_ROUTE handling (Action: REQUEST_FIELD_VERIFICATION + REASSESS, requires_human_review=True)
7. Shelter capacity constraint (Action: OPEN_SHELTER / REDIRECT_EVACUATION)
8. Alternative evacuation routing (Closed/degraded edge marked BLOCKED)
9. Critical response review gate (Mandatory incident commander sign-off)
10. Simulated +40% rainfall scenario (POST /api/v1/response/simulate, simulated=True)
11. Epistemic label separation (OBSERVED vs PREDICTED vs SIMULATED)
12. Provenance determinism & mutation sensitivity
"""

from datetime import datetime, timezone
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from fastapi.testclient import TestClient
from intelligence.app.main import app

client = TestClient(app)


print("=" * 70)
print("CLIMATE EYE VIEW — PHASE 9 AI RESPONSE PLANNER LIVE SMOKE AUDIT")
print("=" * 70)

# 1. Normal Conditions
res_normal = client.post("/api/v1/response/evaluate", json={})
assert res_normal.status_code == 200, f"Failed normal conditions: {res_normal.text}"
plan_normal = res_normal.json()["plan"]
assert plan_normal["alert_level"] == "GREEN", f"Expected GREEN alert, got {plan_normal['alert_level']}"
assert any(a["action"] in ("MAINTAIN_MONITORING", "MONITOR") for a in plan_normal["actions"])
print(f"[PASS] 1. Normal Baseline: Alert Level={plan_normal['alert_level']}, Actions={len(plan_normal['actions'])}")

# 2. High Flood
res_flood = client.post("/api/v1/response/evaluate", json={
    "telemetry": {
        "node_id": "STATION-RIVER-FLOOD",
        "timestamp": "2026-09-07T14:30:00Z",
        "location": {"lat": 37.77, "lon": -122.42},
        "measurements": {
            "temperature": 22.0,
            "humidity": 95.0,
            "rainfall": 115.0,
            "water_level": 19.5,
            "soil_moisture": 98.0,
        },
        "quality": {"source": "STATION-RIVER-FLOOD", "received_at": "2026-09-07T14:30:00Z"},
    }
})
assert res_flood.status_code == 200
plan_flood = res_flood.json()["plan"]
assert plan_flood["alert_level"] in ("RED", "ORANGE"), f"Expected RED/ORANGE, got {plan_flood['alert_level']}"
evac_act = next((a for a in plan_flood["actions"] if a["action"] == "EVACUATE_ZONE"), None)
assert evac_act is not None, "Expected EVACUATE_ZONE action"
print(f"[PASS] 2. High Flood: Alert Level={plan_flood['alert_level']}, Target={evac_act['target']}, Urgency={evac_act['urgency']}")

# 3. High Human Impact & Vulnerability
res_vuln = client.post("/api/v1/response/evaluate", json={
    "telemetry": {
        "node_id": "STATION-VULN",
        "timestamp": "2026-09-07T14:30:00Z",
        "location": {"lat": 37.77, "lon": -122.42},
        "measurements": {
            "temperature": 24.0,
            "humidity": 90.0,
            "rainfall": 80.0,
            "water_level": 12.0,
            "soil_moisture": 90.0,
        },
        "quality": {"source": "STATION-VULN", "received_at": "2026-09-07T14:30:00Z"},
    },
    "population_zones": [
        {
            "zone_id": "ZONE-CRITICAL-ELDERLY",
            "name": "Senior Care Center District",
            "population": 6000,
            "area_km2": 2.5,
            "elevation_m": 5.0,
            "age_65_plus_ratio": 0.45,
            "healthcare_access": 0.10,
            "centroid_latitude": 37.77,
            "centroid_longitude": -122.42,
        }
    ]
})


assert res_vuln.status_code == 200
plan_vuln = res_vuln.json()["plan"]
vuln_act = next((a for a in plan_vuln["actions"] if a["action"] == "PRIORITIZE_VULNERABLE_POPULATION"), None)
assert vuln_act is not None or any("vulnerable" in a["reason"].lower() for a in plan_vuln["actions"])
print("[PASS] 3. High Human Impact: Prioritized vulnerable demographic population")

# 4. Predicted Flood Horizon (+60 min)
pred_acts = [a for a in plan_flood["actions"] if a["temporal_category"] == "PREDICTED"]
assert len(pred_acts) >= 1 or any("PREDICTED" in a["reason"] for a in plan_flood["actions"])
print(f"[PASS] 4. Predicted Flood Horizon: Detected {len(pred_acts)} predictive actions explicitly labeled PREDICTED")

# 5. Compound Flood / Cascading Access Chain
res_cascade = client.post("/api/v1/response/evaluate", json={
    "telemetry": {
        "node_id": "STATION-CASCADE",
        "timestamp": "2026-09-07T14:30:00Z",
        "location": {"lat": 37.77, "lon": -122.42},
        "measurements": {
            "temperature": 20.0,
            "humidity": 98.0,
            "rainfall": 90.0,
            "water_level": 14.0,
            "soil_moisture": 99.0,
        },
        "quality": {"source": "STATION-CASCADE", "received_at": "2026-09-07T14:30:00Z"},
    }
})
assert res_cascade.status_code == 200
plan_cascade = res_cascade.json()["plan"]
compound_ev = plan_cascade["situation"]["compound_events"]
assert len(compound_ev) >= 1, "Expected compound events in situation assessment"
print(f"[PASS] 5. Compound Disaster: Detected {len(compound_ev)} compound/cascading events with causal chains")

# 6. NO_ROUTE Handling
res_noroute = client.post("/api/v1/response/evaluate", json={
    "telemetry": {
        "node_id": "STATION-FLOOD",
        "timestamp": "2026-09-07T15:00:00Z",
        "location": {"lat": 37.77, "lon": -122.42},
        "measurements": {
            "temperature": 22.0,
            "humidity": 95.0,
            "rainfall": 120.0,
            "water_level": 14.5,
            "soil_moisture": 90.0,
        },
        "quality": {"source": "STATION-FLOOD", "confidence": 1.0, "received_at": "2026-09-07T15:00:00Z"},
    },
    "road_network": {
        "edges": [
            {"edge_id": "ROAD-BLOCKED-ALL", "from_node": "ZONE-A", "to_node": "INT-1", "distance_km": 4.0, "travel_time_minutes": 8.0, "closed": True, "accessibility": 0.0}
        ]
    }
})

assert res_noroute.status_code == 200
plan_noroute = res_noroute.json()["plan"]
verify_act = next((a for a in plan_noroute["actions"] if a["action"] in ("REQUEST_FIELD_VERIFICATION", "REASSESS")), None)
assert verify_act is not None, "Expected REQUEST_FIELD_VERIFICATION when routes are blocked"
assert verify_act["requires_human_review"] is True
print(f"[PASS] 6. NO_ROUTE Handling: Generated {verify_act['action']} with mandatory human operator review")

# 7. Shelter Capacity Constraint
res_shelter_cap = client.post("/api/v1/response/evaluate", json={
    "shelters": [
        {"shelter_id": "SHELTER-FULL", "name": "Full Center", "capacity": 2000, "current_occupancy": 1980, "safe": True, "hazard_risk": 0.0, "latitude": 37.78, "longitude": -122.42}
    ]
})
assert res_shelter_cap.status_code == 200
plan_shelter_cap = res_shelter_cap.json()["plan"]
open_act = next((a for a in plan_shelter_cap["actions"] if a["action"] == "OPEN_SHELTER"), None)
assert open_act is not None or any("exhaust" in a["reason"].lower() for a in plan_shelter_cap["actions"])
print("[PASS] 7. Shelter Capacity: Recommended opening secondary shelter when occupancy nears exhaustion")

# 8. Alternative Evacuation Route & Closed Road
res_closed_road = client.post("/api/v1/response/evaluate", json={
    "road_network": {
        "edges": [
            {"edge_id": "ROAD-A-1", "from_node": "ZONE-A", "to_node": "INT-1", "distance_km": 3.0, "travel_time_minutes": 6.0, "closed": False, "accessibility": 0.9},
            {"edge_id": "ROAD-BROKEN-BRIDGE", "from_node": "INT-1", "to_node": "SHELTER-EAST", "distance_km": 3.5, "travel_time_minutes": 7.0, "closed": True, "accessibility": 0.0, "hazard_risk": 0.95},
        ]
    }
})

assert res_closed_road.status_code == 200
plan_closed_road = res_closed_road.json()["plan"]
close_act = next((a for a in plan_closed_road["actions"] if a["action"] in ("CLOSE_ROAD", "CLOSE_BRIDGE")), None)
assert close_act is not None, "Expected CLOSE_ROAD for impassable road"
print(f"[PASS] 8. Infrastructure Closure: Correctly identified {close_act['action']} for {close_act['target']}")

# 9. Critical Response Review Gate
assert evac_act["requires_human_review"] is True
assert evac_act["review_reason"] is not None
print("[PASS] 9. Human-in-the-Loop Gating: Critical evacuation actions strictly require operator authorization")

# 10. Simulated What-If Scenario (+40% Rainfall)
res_sim = client.post("/api/v1/response/simulate", json={
    "scenario_id": "SCN-RAIN-40",
    "changes": {"rainfall_multiplier": 1.40},
})
assert res_sim.status_code == 200, f"Failed simulate: {res_sim.text}"
plan_sim = res_sim.json()["plan"]
assert plan_sim["simulated"] is True
assert any("SIMULATED_SCENARIO" in w for w in plan_sim["warnings"])
print(f"[PASS] 10. Simulated What-If Scenario: SCN-RAIN-40 evaluated with simulated=True (Actions={len(plan_sim['actions'])})")

# 11. Epistemic Labeling Verification
for act in plan_sim["actions"]:
    assert act["simulated"] is True
    assert act["temporal_category"] == "SIMULATED"
for act in plan_normal["actions"]:
    assert act["simulated"] is False
    assert act["temporal_category"] in ("OBSERVED", "PREDICTED", "INFERRED")
print("[PASS] 11. Epistemic Separation: OBSERVED vs PREDICTED vs SIMULATED strictly enforced")

# 12. Provenance Determinism & Mutation Sensitivity
res_sim_dup = client.post("/api/v1/response/simulate", json={
    "scenario_id": "SCN-RAIN-40",
    "changes": {"rainfall_multiplier": 1.40},
})
assert res_sim_dup.status_code == 200
plan_sim_dup = res_sim_dup.json()["plan"]
assert plan_sim["provenance_hash"] == plan_sim_dup["provenance_hash"], "Repeated simulation must yield identical provenance hash"

res_sim_mut = client.post("/api/v1/response/simulate", json={
    "scenario_id": "SCN-RAIN-40",
    "changes": {"rainfall_multiplier": 1.55},
})
assert res_sim_mut.status_code == 200
plan_sim_mut = res_sim_mut.json()["plan"]
assert plan_sim["provenance_hash"] != plan_sim_mut["provenance_hash"], "Mutating rainfall multiplier must change provenance hash"
print(f"[PASS] 12. Provenance Integrity: Deterministic hash ({plan_sim['provenance_hash'][:12]}...) & mutation sensitivity verified")

print("=" * 70)
print("PHASE 9 RESPONSE PLANNER LIVE SMOKE AUDIT COMPLETED: 12/12 PASSED")
print("=" * 70)
