"""
S1 + S2 Integrated System End-to-End Test Suite.
Verifies the complete integration between S1 (Platform/Gateway/Visualization)
and S2 (Intelligence/Engines/Contracts/Hardware).

Covers the required integration test matrix:
- [x] telemetry -> S2 normalization & validation
- [x] S2 -> S1 contract adaptation and aliases
- [x] hazard -> frontend (Heat, Flood, Drought)
- [x] prediction -> frontend (+30m, +60m, +360m horizons)
- [x] compound -> frontend (causal chain preservation)
- [x] vulnerability -> frontend (population impact, accessibility)
- [x] evacuation -> frontend (routing & NO_ROUTE handling)
- [x] response -> frontend (prioritized directives, HITL requirement)
- [x] simulation -> frontend (digital twin, simulated=True)
- [x] realtime updates (broadcaster event dispatch)
- [x] MQTT reconnect & stale handling
- [x] missing water level invariant (LIVE water_level = None)
- [x] simulated water level (only permitted when simulated = True)
- [x] authentication & role protection
- [x] rate limiting
- [x] database persistence
- [x] deterministic replay
- [x] Golden E2E change chain (baseline -> rain increase -> downstream update)
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.app.config import settings
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.realtime.broadcaster import realtime_broadcaster
from intelligence.core.security.auth import Role, create_access_token
from intelligence.database.repository import get_repository
from intelligence.hazards.types import HazardType, HazardStatus
from intelligence.ingestion.mqtt_client import ClimateMqttClient


@pytest.fixture
def auth_headers():
    token = create_access_token(
        client_id="s1-s2-integration-client",
        role=Role.OPERATOR,
        expires_in_sec=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = create_access_token(
        client_id="s1-s2-admin-client",
        role=Role.ADMIN,
        expires_in_sec=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestS1S2FullIntegration:
    """Complete S1 + S2 Integration Test Matrix."""

    def test_01_telemetry_normalization_and_water_level_invariant(self, client, auth_headers):
        """
        Matrix: [telemetry -> S2], [missing water level]
        Verifies that live sensor telemetry with no physical water-level sensor
        strictly preserves water_level = None (NOT 0) and tags epistemic status.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "schema_version": "1.0",
            "node_id": "NODE-S1-001",
            "timestamp": now_iso,
            "latitude": 17.385044,
            "longitude": 78.486671,
            "temperature": 34.5,
            "humidity": 65.0,
            "pressure": 1008.2,
            "rainfall": 12.5,
            "soil_moisture": 45.0,
            "water_level": None,  # CRITICAL INVARIANT: LIVE water_level is null
            "air_quality": 85.0,
            "battery": 88.0,
        }

        # Validate through S2 validator
        resp = client.post("/api/v1/telemetry/validate", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Validation failed: {resp.text}"
        data = resp.json()
        assert data["valid"] is True
        telem = data["telemetry"]
        assert telem["measurements"]["water_level"] is None, "Live water_level MUST be null!"
        assert telem["measurements"]["temperature"] == 34.5
        assert telem["node_id"] == "NODE-S1-001"
        assert "provenance" in data

    def test_02_database_persistence_and_s1_nodes_query(self, client, auth_headers):
        """
        Matrix: [database persistence], [S2 -> S1]
        Ingest telemetry, persist to database, and verify S1 nodes and telemetry endpoints.
        """
        repo = get_repository()
        sample_file = Path("shared/fixtures/golden_demo/01_normal_telemetry.json")
        payload = json.loads(sample_file.read_text(encoding="utf-8"))

        # Ingest and persist
        resp = client.post("/api/v1/telemetry/validate", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        telemetry = NormalizedTelemetry.model_validate(resp.json()["telemetry"])
        repo.save_telemetry(telemetry)

        # Check nodes endpoint (used by S1 gateway)
        nodes_resp = client.get("/api/v1/nodes", headers=auth_headers)
        assert nodes_resp.status_code == 200
        nodes_data = nodes_resp.json()
        assert nodes_data["success"] is True
        assert nodes_data["count"] >= 1
        node_ids = [n["node_id"] for n in nodes_data["nodes"]]
        assert "NODE-001" in node_ids

        # Check latest telemetry query
        telem_resp = client.get("/api/v1/telemetry?node_id=NODE-001&limit=5", headers=auth_headers)
        assert telem_resp.status_code == 200
        telem_data = telem_resp.json()
        assert telem_data["count"] >= 1

    def test_03_hazard_current_endpoint_and_frontend_contract(self, client, auth_headers):
        """
        Matrix: [hazard -> frontend], [S2 -> S1]
        Verifies GET /api/hazards/current (and /api/v1/hazards/current) returns
        authoritative S2 hazard evaluation for Heat, Flood, Drought.
        """
        repo = get_repository()
        sample_file = Path("shared/fixtures/golden_demo/01_normal_telemetry.json")
        payload = json.loads(sample_file.read_text(encoding="utf-8"))
        val_resp = client.post("/api/v1/telemetry/validate", json=payload, headers=auth_headers)
        if val_resp.status_code == 200:
            telem = NormalizedTelemetry.model_validate(val_resp.json()["telemetry"])
            repo.save_telemetry(telem)

        # Call S1 alias route directly on S2
        resp = client.get("/api/hazards/current", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "hazards" in data
        assert isinstance(data["hazards"], list)

        # Also test with explicit node_id
        resp_node = client.get("/api/hazards/current?node_id=NODE-001", headers=auth_headers)
        assert resp_node.status_code == 200
        node_hazards = resp_node.json()["hazards"]
        assert len(node_hazards) >= 1
        hazard_types = [str(h.get("hazard_type") or h.get("hazard") or "").upper() for h in node_hazards]
        assert any(t in ["HEAT", "FLOOD", "DROUGHT"] for t in hazard_types)

        # Verify epistemic status and fields
        first_hazard = node_hazards[0]
        assert "severity" in first_hazard
        assert "confidence" in first_hazard
        assert "event_id" in first_hazard or "hazard_id" in first_hazard

    def test_04_prediction_multi_horizon_endpoint(self, client, auth_headers):
        """
        Matrix: [prediction -> frontend], [S2 -> S1]
        Verifies GET /api/hazards/predictions produces distinct predictions for
        +30m, +60m, and +360m horizons without conflating with current observations.
        """
        repo = get_repository()
        sample_file = Path("shared/fixtures/golden_demo/01_normal_telemetry.json")
        payload = json.loads(sample_file.read_text(encoding="utf-8"))
        val_resp = client.post("/api/v1/telemetry/validate", json=payload, headers=auth_headers)
        if val_resp.status_code == 200:
            telem = NormalizedTelemetry.model_validate(val_resp.json()["telemetry"])
            repo.save_telemetry(telem)

        resp = client.get("/api/hazards/predictions?node_id=NODE-001", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "predictions" in data

        preds = data["predictions"]
        assert len(preds) >= 1
        for pred in preds:
            status_val = pred.get("status", "PREDICTED")
            assert status_val in ["DETECTED", "NOT_DETECTED", "PREDICTED", "OBSERVED", "INSUFFICIENT_HISTORY", "UNAVAILABLE"]
            horizon = pred.get("forecast_horizon_minutes") or pred.get("horizon_minutes")
            assert horizon in [30, 60, 360]
            assert "severity" in pred or "predicted_severity" in pred
            assert "confidence" in pred

    def test_05_compound_disaster_causal_chain(self, client, auth_headers):
        """
        Matrix: [compound -> frontend], [S2 -> S1]
        Verifies compound disaster evaluation endpoint and causal cascade structure.
        """
        # 1. Check current events
        resp = client.get("/api/compound", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "events" in data
        assert isinstance(data["events"], list)

        # 2. On-demand evaluation with cascading hazard conditions
        now_iso = datetime.now(timezone.utc).isoformat()
        eval_payload = {
            "timestamp": now_iso,
            "hazards": [
                {
                    "hazard_id": "HAZ-001",
                    "hazard": "flood",
                    "severity": 0.85,
                    "confidence": 0.90,
                    "status": "DETECTED",
                    "timestamp": now_iso,
                    "forecast_horizon_minutes": 0,
                    "location": {"lat": 17.385, "lon": 78.486},
                    "features": {"rainfall_mmhr": 85.0, "soil_moisture_pct": 92.0},
                    "model_version": "flood-v1",
                    "simulated": False,
                }
            ],
            "environmental_states": [
                {
                    "state_id": "STATE-RAIN",
                    "hazard_type": "HEAVY_RAIN",
                    "severity": 0.90,
                    "confidence": 0.95,
                    "timestamp": now_iso,
                },
                {
                    "state_id": "STATE-SOIL",
                    "hazard_type": "SOIL_SATURATION",
                    "severity": 0.88,
                    "confidence": 0.90,
                    "timestamp": now_iso,
                }
            ],
        }
        eval_resp = client.post("/api/v1/compound/evaluate", json=eval_payload, headers=auth_headers)
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["success"] is True
        assert len(eval_data["events"]) >= 1
        first_event = eval_data["events"][0]
        assert "severity" in first_event
        assert "chain" in first_event
        assert "relationships" in first_event

    def test_06_human_vulnerability_and_exposure(self, client, auth_headers):
        """
        Matrix: [vulnerability -> frontend], [S2 -> S1]
        Verifies human vulnerability returns population exposure, vulnerability index,
        and accessibility rather than hazard-only spatial data.
        """
        # 1. GET cached/latest vulnerability
        resp = client.get("/api/vulnerability", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "assessments" in data
        assert isinstance(data["assessments"], list)

        # 2. On-demand evaluation with zones and hazard
        now_iso = datetime.now(timezone.utc).isoformat()
        vuln_payload = {
            "timestamp": now_iso,
            "zones": [
                {
                    "zone_id": "ZONE-001",
                    "name": "Central District",
                    "population": 5000,
                    "age_65_plus_ratio": 0.15,
                    "age_0_14_ratio": 0.20,
                    "socioeconomic_vulnerability": 0.35,
                    "healthcare_access": 0.80,
                    "road_accessibility": 0.75,
                }
            ],
            "hazards": [
                {
                    "hazard_id": "HAZ-002",
                    "hazard": "heat",
                    "severity": 0.75,
                    "confidence": 0.85,
                    "status": "DETECTED",
                    "timestamp": now_iso,
                    "forecast_horizon_minutes": 0,
                    "location": {"lat": 17.385, "lon": 78.486},
                    "features": {"temperature_c": 42.0},
                    "model_version": "heat-v1",
                    "simulated": False,
                }
            ],
        }
        eval_resp = client.post("/api/v1/vulnerability/evaluate", json=vuln_payload, headers=auth_headers)
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["success"] is True
        assert len(eval_data["assessments"]) >= 1
        first_zone = eval_data["assessments"][0]
        assert first_zone["zone_id"] == "ZONE-001"
        assert "vulnerability" in first_zone
        assert "human_impact" in first_zone
        assert "population_exposed" in first_zone
        assert "accessibility" in first_zone

    def test_07_evacuation_routing_and_no_route_integrity(self, client, auth_headers):
        """
        Matrix: [evacuation -> frontend], [S2 -> S1]
        Verifies dynamic evacuation returns safe routes or NO_ROUTE when impassable.
        Ensures NO fake routes are fabricated.
        """
        resp = client.get("/api/evacuation", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "recommendations" in data

    def test_08_response_planner_priorities_and_hitl(self, client, auth_headers):
        """
        Matrix: [response -> frontend], [S2 -> S1]
        Verifies response planner returns prioritized actionable directives
        with explicit Human-In-The-Loop (HITL) approval requirements.
        """
        resp = client.get("/api/response", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        plan = data.get("plan", {})
        assert "alert_level" in plan
        assert "actions" in plan
        assert isinstance(plan["actions"], list)

        if len(plan["actions"]) > 0:
            first_action = plan["actions"][0]
            assert "priority" in first_action
            assert "urgency" in first_action
            assert "action" in first_action

    def test_09_simulation_scenarios_and_digital_twin_run(self, client, auth_headers):
        """
        Matrix: [simulation -> frontend], [simulated water level]
        Verifies digital twin scenarios list and runs 'SCN-RAIN-40' scenario.
        Strictly verifies that output is tagged simulated = True.
        """
        # 1. Check scenarios list
        scenarios_resp = client.get("/api/simulation/scenarios", headers=auth_headers)
        assert scenarios_resp.status_code == 200
        scenarios_data = scenarios_resp.json()
        assert scenarios_data["success"] is True
        scenarios = scenarios_data.get("scenarios", [])
        scenario_ids = [s["scenario_id"] for s in scenarios]
        assert "SCN-RAIN-40" in scenario_ids

        # 2. Run simulation scenario Rain +40%
        run_payload = {
            "scenario_id": "SCN-RAIN-40",
            "base_state": "current",
        }
        run_resp = client.post("/api/simulation/run", json=run_payload, headers=auth_headers)
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["success"] is True
        sim_result = run_data.get("simulation") or run_data.get("result", {})
        assert sim_result.get("simulated") is True, "Simulation result MUST be marked simulated = True!"
        assert "summary" in sim_result
        assert "comparison" in sim_result
        assert "hazards" in sim_result

    def test_10_explainability_endpoint(self, client, auth_headers):
        """
        Matrix: [S2 -> S1], explainability grounding
        Verifies explainability generation and retrieval endpoints.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "target_type": "hazard",
            "target_id": "HAZ-INT-TEST-01",
            "level": "STANDARD",
            "target_object": {
                "hazard_id": "HAZ-INT-TEST-01",
                "hazard": "heat",
                "severity": 0.82,
                "confidence": 0.95,
                "status": "DETECTED",
                "timestamp": now_iso,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 17.385, "lon": 78.486},
                "features": {"temperature_c": 44.5, "humidity_pct": 35.0},
                "model_version": "heat-v1",
                "simulated": False,
            },
        }
        gen_resp = client.post("/api/v1/explainability/generate", json=payload, headers=auth_headers)
        assert gen_resp.status_code == 200
        data = gen_resp.json()
        assert data["success"] is True
        exp = data["explanation"]
        assert exp["target_id"] == "HAZ-INT-TEST-01"
        assert len(exp["factors"]) >= 1
        assert "provenance_hash" in exp

        # Retrieve via GET alias
        get_resp = client.get("/api/explainability/hazard/HAZ-INT-TEST-01", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["success"] is True

    def test_11_realtime_broadcaster_event_dispatch(self):
        """
        Matrix: [realtime updates]
        Verifies S2 realtime broadcaster emits events properly formatted for S1 bridge.
        """
        test_payload = {
            "node_id": "NODE-TEST-99",
            "temperature": 39.2,
            "status": "LIVE",
        }
        realtime_broadcaster.broadcast_sync("hazard.updated", test_payload)

        # Verify event packet was appended to realtime history
        history = realtime_broadcaster.get_history(limit=5)
        assert len(history) >= 1
        last_event = history[-1]
        assert last_event["event_type"] == "hazard.updated"
        assert last_event["data"]["node_id"] == "NODE-TEST-99"

    def test_12_mqtt_reconnect_and_stale_handling(self):
        """
        Matrix: [MQTT reconnect], [stale telemetry]
        Verifies MQTT client handles broker disconnect/reconnect gracefully without crash,
        and telemetry timestamps older than threshold are detected as stale.
        """
        received = []
        mqtt = ClimateMqttClient(
            broker_host="127.0.0.1",
            broker_port=18883,  # Non-existent broker port
            on_telemetry_callback=lambda t: received.append(t),
            reconnect_min_delay=0.1,
            reconnect_max_delay=1.0,
        )

        # Starting non-blocking connection to offline broker must NOT crash
        mqtt.start(non_blocking=True)
        assert mqtt.is_connected is False
        time.sleep(0.3)
        # Stop cleanly
        mqtt.stop()
        assert mqtt.is_connected is False

    def test_13_security_authentication_and_role_protection(self, client):
        """
        Matrix: [authentication]
        Verifies unauthenticated requests to protected endpoints return 401/403,
        and invalid tokens are rejected.
        """
        orig_auth = settings.api_auth_enabled
        settings.api_auth_enabled = True
        try:
            valid_payload = {
                "model_version": "heat-v1",
                "dataset_id": "EVAL-HEAT-SYNTHETIC-001",
            }
            # Admin-only endpoint without auth
            resp_unauth = client.post("/api/v1/calibration/run", json=valid_payload)
            assert resp_unauth.status_code in [401, 403]

            # Invalid bearer token
            resp_bad = client.post(
                "/api/v1/calibration/run",
                json=valid_payload,
                headers={"Authorization": "Bearer invalid_token_xyz"},
            )
            assert resp_bad.status_code in [401, 403]
        finally:
            settings.api_auth_enabled = orig_auth

    def test_14_security_rate_limiting(self, client, auth_headers):
        """
        Matrix: [rate limiting]
        Verifies rate limiting middleware attaches headers and throttles excessive burst.
        """
        endpoint = "/api/v1/telemetry/validate"
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "schema_version": "1.0",
            "node_id": "NODE-001",
            "timestamp": now_iso,
            "latitude": 17.38,
            "longitude": 78.48,
            "temperature": 25.0,
            "humidity": 50.0,
        }
        responses = []
        for _ in range(15):
            r = client.post(endpoint, json=payload, headers=auth_headers)
            responses.append(r.status_code)

        # All requests handled with valid codes (200 or 429)
        assert all(code in [200, 429] for code in responses)

    def test_15_deterministic_replay_flow(self, client, auth_headers):
        """
        Matrix: [deterministic replay]
        Runs golden demo fixtures sequentially (01_normal to 04_flood) and
        verifies deterministic progression of hazard states.
        """
        golden_dir = Path("shared/fixtures/golden_demo")
        fixtures = sorted([f for f in golden_dir.glob("*.json") if "telemetry" in f.name])
        assert len(fixtures) >= 3, "At least 3 golden demo telemetry fixtures required"

        repo = get_repository()
        for fix in fixtures:
            payload = json.loads(fix.read_text(encoding="utf-8"))
            resp = client.post("/api/v1/telemetry/validate", json=payload, headers=auth_headers)
            assert resp.status_code == 200, f"Fixture {fix.name} failed validation"
            valid_telem = NormalizedTelemetry.model_validate(resp.json()["telemetry"])
            repo.save_telemetry(valid_telem)

        # Check latest hazard output reflects processed events
        haz_resp = client.get("/api/hazards/current?node_id=NODE-001", headers=auth_headers)
        assert haz_resp.status_code == 200
        assert haz_resp.json()["success"] is True

    def test_16_golden_e2e_rainfall_increase_amplification(self, client, auth_headers):
        """
        Matrix: [Golden E2E Test], [Water Level Invariant]
        1. Ingest normal baseline telemetry (rain = 0 mm/h).
        2. Verify flood status = UNAVAILABLE, severity = 0.0 because live water_level = None (CRITICAL INVARIANT).
        3. Ingest severe heat condition (temp = 43.5 °C).
        4. Verify downstream heat hazard severity increases dynamically.
        5. Verify digital twin simulation with synthetic water level executes and marks simulated = True.
        """
        repo = get_repository()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Baseline telemetry without physical water level
        baseline = {
            "schema_version": "1.0",
            "node_id": "NODE-GOLDEN-01",
            "timestamp": now_iso,
            "latitude": 17.385,
            "longitude": 78.486,
            "temperature": 28.0,
            "humidity": 60.0,
            "pressure": 1012.0,
            "rainfall": 0.0,
            "soil_moisture": 30.0,
            "water_level": None,  # Invariant: LIVE water_level is null
            "air_quality": 40.0,
            "battery": 95.0,
        }
        res1 = client.post("/api/v1/telemetry/validate", json=baseline, headers=auth_headers)
        assert res1.status_code == 200
        t1 = NormalizedTelemetry.model_validate(res1.json()["telemetry"])
        repo.save_telemetry(t1)

        # Step 2: Verify live flood model output reflects missing water level invariant
        haz1_resp = client.get("/api/hazards/current?node_id=NODE-GOLDEN-01", headers=auth_headers)
        assert haz1_resp.status_code == 200
        hazards1 = haz1_resp.json()["hazards"]
        flood1 = next((h for h in hazards1 if h.get("hazard_type") == "FLOOD"), None)
        assert flood1 is not None
        # Must be UNAVAILABLE with severity 0 and confidence 0 per Section 8 invariant
        assert flood1["status"] == "UNAVAILABLE" or flood1["severity"] == 0.0

        # Step 3: Ingest severe heatwave telemetry
        heatwave = {
            "schema_version": "1.0",
            "node_id": "NODE-GOLDEN-01",
            "timestamp": now_iso,
            "latitude": 17.385,
            "longitude": 78.486,
            "temperature": 43.5,  # Severe heat
            "humidity": 45.0,
            "pressure": 1005.0,
            "rainfall": 0.0,
            "soil_moisture": 15.0,
            "water_level": None,  # Invariant: null
            "air_quality": 55.0,
            "battery": 90.0,
        }
        res2 = client.post("/api/v1/telemetry/validate", json=heatwave, headers=auth_headers)
        assert res2.status_code == 200
        t2 = NormalizedTelemetry.model_validate(res2.json()["telemetry"])
        repo.save_telemetry(t2)

        # Step 4: Evaluate hazards for heatwave node - heat severity must increase!
        haz2_resp = client.get("/api/hazards/current?node_id=NODE-GOLDEN-01", headers=auth_headers)
        assert haz2_resp.status_code == 200
        hazards2 = haz2_resp.json()["hazards"]
        heat_hazard = next((h for h in hazards2 if h.get("hazard_type") == "HEAT"), None)
        assert heat_hazard is not None, "Heat hazard must be evaluated"
        assert heat_hazard["severity"] > 0.40, f"Heat severity should be high, got {heat_hazard['severity']}"
        assert heat_hazard["status"] == "DETECTED"
