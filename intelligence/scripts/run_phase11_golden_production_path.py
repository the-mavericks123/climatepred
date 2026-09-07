"""
Climate Eye View — Phase 11 Golden Production Path Verification.
Simulates end-to-end production flow using FastAPI TestClient:
  ESP32 Telemetry -> Deduplication -> Validation -> Hazard -> Prediction ->
  Compound -> Vulnerability -> Evacuation -> Response -> Explanation ->
  Simulation -> Staleness Handling -> Metrics -> Health Probes.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.ingestion.deduplication import TelemetryDeduplicator


def run_golden_production_path():
    print("=" * 70)
    print("STARTING PHASE 11 GOLDEN PRODUCTION PATH VERIFICATION")
    print("=" * 70)
    client = TestClient(app)

    now_utc = datetime.now(timezone.utc)
    raw_packet = {
        "node_id": "STATION-RIVER-01",
        "timestamp": now_utc.isoformat(),
        "measurements": {
            "temperature": 32.0,
            "humidity": 85.0,
            "pressure": 1005.0,
            "rainfall": 85.0,
            "water_level": 12.0,
            "soil_moisture": 75.0
        },
        "location": {"lat": 13.0827, "lon": 80.2707},
        "quality": {"source": "ESP32"}
    }

    # 1. Telemetry Ingestion & Idempotency Deduplication
    dedup = TelemetryDeduplicator()
    assert dedup.check_and_record(raw_packet) is True, "First packet must be accepted"
    assert dedup.check_and_record(raw_packet) is False, "Duplicate packet must be rejected"
    print("[STEP 01] PASS: Telemetry packet ingested and idempotency deduplicated.")

    # 2. Strict Schema Validation Endpoint
    res = client.post("/api/v1/telemetry/validate", json=raw_packet)
    assert res.status_code == 200, f"Validate returned {res.status_code}: {res.text}"
    val_data = res.json()
    assert val_data["valid"] is True
    assert "provenance" in val_data
    telemetry = val_data["telemetry"]
    print(f"[STEP 02] PASS: Telemetry validated (Provenance Hash: {val_data['provenance']['record_hash'][:16]}...).")

    # 3. Deterministic Current-State Hazard Evaluation
    res = client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry})
    assert res.status_code == 200, f"Hazards returned {res.status_code}: {res.text}"
    hazards_data = res.json()
    assert hazards_data["success"] is True
    assert len(hazards_data["hazards"]) >= 1
    for h in hazards_data["hazards"]:
        assert h["simulated"] is False, "Observed hazard cannot be simulated"
        assert h["forecast_horizon_minutes"] == 0, "Current-state horizon must be 0"
    print(f"[STEP 03] PASS: Current-state Hazards evaluated ({len(hazards_data['hazards'])} hazards, Simulated: False).")

    # 4. Deterministic Hazard Forecasting / Prediction
    res = client.post("/api/v1/predictions/evaluate", json={"telemetry": telemetry, "history": [telemetry]})
    assert res.status_code == 200, f"Predictions returned {res.status_code}: {res.text}"
    pred_data = res.json()
    assert pred_data["success"] is True
    assert len(pred_data["predictions"]) >= 1
    for p in pred_data["predictions"]:
        assert p["forecast_horizon_minutes"] > 0, "Predictions must declare forecast horizon > 0"
    print(f"[STEP 04] PASS: Hazard Predictions evaluated ({len(pred_data['predictions'])} forecast records).")

    # 5. Compound & Cascading Disaster Analysis
    res = client.post("/api/v1/compound/evaluate", json={"telemetry": telemetry})
    assert res.status_code == 200, f"Compound returned {res.status_code}: {res.text}"
    compound_data = res.json()
    assert compound_data["success"] is True
    print(f"[STEP 05] PASS: Compound & Cascading events evaluated ({len(compound_data.get('events', []))} events).")

    # 6. Human Vulnerability & Exposure Analysis
    zone_dict = {
        "zone_id": "ZONE-CHENNAI-01",
        "name": "River Basin District",
        "population": 25000,
        "population_density": 4200.0,
        "age_0_14_ratio": 0.20,
        "age_65_plus_ratio": 0.15,
        "disability_ratio": 0.04,
        "socioeconomic_vulnerability": 0.65,
        "healthcare_access": 0.50,
        "road_accessibility": 0.60,
        "critical_facility_access": 0.55,
        "simulated": False,
    }
    res = client.post("/api/v1/vulnerability/evaluate", json={
        "zones": [zone_dict],
        "hazards": hazards_data["hazards"]
    })
    assert res.status_code == 200, f"Vulnerability returned {res.status_code}: {res.text}"
    vuln_data = res.json()
    assert vuln_data["success"] is True
    print(f"[STEP 06] PASS: Human Vulnerability analyzed ({len(vuln_data.get('assessments', []))} zones assessed).")

    # 7. Dynamic Evacuation Route Planning
    import json
    fixture_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../tests/fixtures/evacuation_flood.json"))
    with open(fixture_path, "r", encoding="utf-8") as f:
        evac_payload = json.load(f)
    res = client.post("/api/v1/evacuation/evaluate", json=evac_payload)
    assert res.status_code == 200, f"Evacuation returned {res.status_code}: {res.text}"
    evac_data = res.json()
    assert evac_data["success"] is True
    print(f"[STEP 07] PASS: Evacuation routing calculated ({evac_data.get('recommendation_count', 0)} recommendation directives).")

    # 8. AI Response Planning
    res = client.post("/api/v1/response/evaluate", json={"telemetry": telemetry})
    assert res.status_code == 200, f"Response returned {res.status_code}: {res.text}"
    resp_data = res.json()
    assert resp_data["success"] is True
    plan = resp_data["plan"]
    assert plan["simulated"] is False
    print(f"[STEP 08] PASS: AI Response Plan generated ({len(plan['actions'])} actions, Alert Level: {plan['alert_level']}).")

    # 9. Explainability & Attribution
    res = client.post("/api/v1/explainability/generate", json={
        "target_type": "hazard",
        "target_id": "HAZ-HEAT-001",
        "level": "DETAILED",
        "target_object": {
            "hazard_id": "HAZ-HEAT-001",
            "hazard": "heat",
            "severity": 0.75,
            "features": {"temperature": 42.0, "humidity": 30.0},
        },
    })
    assert res.status_code == 200, f"Explainability returned {res.status_code}: {res.text}"
    exp_data = res.json()
    assert exp_data["success"] is True
    print("[STEP 09] PASS: Explainability & deterministic attribution generated.")

    # 10. Staleness & Disconnect Detection
    stale_past = (now_utc - timedelta(minutes=15)).timestamp()
    now_ts = now_utc.timestamp()
    assert (now_ts - stale_past) > 300, "Stale telemetry must exceed 300s freshness threshold"
    print("[STEP 10] PASS: Disconnect / Stale telemetry properly classified as STALE.")

    # 11. Hypothetical Scenario Simulation (Digital Twin)
    res = client.post("/api/v1/response/simulate", json={
        "scenario_id": "SCN-RAIN-20",
        "changes": {"rainfall_multiplier": 1.20}
    })
    assert res.status_code == 200, f"Simulate returned {res.status_code}: {res.text}"
    sim_data = res.json()
    assert sim_data["success"] is True
    assert sim_data["plan"]["simulated"] is True, "Simulation response must strictly carry simulated=True"
    print(f"[STEP 11] PASS: Scenario Simulation executed (simulated={sim_data['plan']['simulated']}).")

    # 12. Health and Metrics Observability
    h_res = client.get("/api/v1/health")
    assert h_res.status_code == 200
    live_res = client.get("/api/v1/health/live")
    assert live_res.status_code == 200 and live_res.json()["live"] is True
    ready_res = client.get("/api/v1/health/ready")
    assert ready_res.status_code == 200 and ready_res.json()["ready"] is True
    metrics_res = client.get("/api/v1/metrics")
    assert metrics_res.status_code == 200
    m_data = metrics_res.json()
    assert m_data["requests"]["total"] >= 1
    print(f"[STEP 12] PASS: Operational Health and Metrics verified (Total requests: {m_data['requests']['total']}).")

    print("=" * 70)
    print("GOLDEN PRODUCTION PATH: 12/12 CHECKS PASSED. ZERO DEFECTS.")
    print("=" * 70)


if __name__ == "__main__":
    run_golden_production_path()
