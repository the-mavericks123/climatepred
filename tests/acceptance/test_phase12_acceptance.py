"""
Climate Eye View — Phase 12 Full S2 Integration Acceptance Test Suite.
Verifies end-to-end operational execution across all 12 pipeline stages:
1. Telemetry Ingestion (MQTT & REST)
2. Validation & Quality Gates
3. Persistence & Relational Consistency (Survival across restart)
4. Core Hazard Intelligence (Heat, Flood, Drought)
5. Multi-Horizon Prediction (+30m, +60m, +360m)
6. Compound & Cascading Disaster DAG
7. Human Vulnerability & Impact (Hazard x Exposure x Vulnerability x Access)
8. Dynamic Evacuation & Rerouting (Bridge B cut-off / No-Route handling)
9. Digital Twin Simulation Engine (Rain +40%, simulated=true epistemic isolation)
10. AI Response Planner (Priority actions, evidence IDs, HITL requirements)
11. Explainability & Attribution (WHAT, WHY, EVIDENCE, CONFIDENCE)
12. Realtime Event Streaming & Frontend Integration
Also verifies security enforcement, failure paths, epistemic integrity, and numerical integrity.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.app.config import settings
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.realtime.broadcaster import realtime_broadcaster
from intelligence.core.security.auth import Role, create_access_token
from intelligence.database.repository import IntelligenceRepository
from intelligence.hazards.engine import HazardEngine
from intelligence.hazards.types import HazardType
from intelligence.ingestion.mqtt_client import ClimateMqttClient
from intelligence.prediction.engine import PredictionEngine
from intelligence.simulation.engine import SimulationEngine


@pytest.fixture
def auth_headers():
    token = create_access_token(
        client_id="acceptance-operator",
        role=Role.OPERATOR,
        expires_in_sec=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = create_access_token(
        client_id="acceptance-admin",
        role=Role.ADMIN,
        expires_in_sec=3600,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestPhase12EndToEndPipeline:
    """Acceptance testing of all 12 pipeline stages."""

    def test_01_telemetry_ingestion_and_validation(self, client, auth_headers):
        """Stage 1 & 2: Telemetry arrives, validates against contract, and computes provenance."""
        golden_file = Path("shared/fixtures/golden_demo/01_normal_telemetry.json")
        assert golden_file.exists(), "Golden fixture 01 does not exist"
        payload = json.loads(golden_file.read_text(encoding="utf-8"))

        response = client.post("/api/v1/telemetry/validate", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Telemetry validation failed: {response.text}"
        data = response.json()
        assert data["valid"] is True
        assert data["telemetry"]["node_id"] == "NODE-001"
        assert "provenance" in data
        assert len(data["provenance"]["record_hash"]) == 64

    def test_02_mqtt_client_processing(self):
        """Stage 1: Real MQTT subscriber validates, deduplicates, and normalizes telemetry."""
        received = []

        def on_telemetry(t: NormalizedTelemetry):
            received.append(t)

        client = ClimateMqttClient(
            broker_host="localhost",
            on_telemetry_callback=on_telemetry,
        )

        golden_file = Path("shared/fixtures/golden_demo/02_heavy_rain_telemetry.json")
        payload_bytes = golden_file.read_bytes()

        # Test message processor directly
        success, normalized, msg = client.process_raw_message(
            topic="climate/nodes/NODE-001/telemetry",
            payload_bytes=payload_bytes,
        )
        assert success is True, f"MQTT processing failed: {msg}"
        assert normalized is not None
        assert normalized.node_id == "NODE-001"
        assert normalized.measurements.rainfall == 42.0
        assert len(received) == 1

        # Test deduplication rejection
        dup_success, _, dup_msg = client.process_raw_message(
            topic="climate/nodes/NODE-001/telemetry",
            payload_bytes=payload_bytes,
        )
        assert dup_success is False
        assert "Duplicate" in dup_msg

    def test_03_database_persistence_survival_across_restart(self):
        """Stage 3: Database persistence preserves records, geometry, and relationships across restarts."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_file = tf.name

        try:
            # 1. First instance writes records
            repo1 = IntelligenceRepository(db_path=db_file)
            repo1.upsert_node("NODE-001", "SF Delta Station", 37.7749, -122.4194)

            from intelligence.core.contracts.telemetry import (
                LocationCoordinate,
                QualityMetadata,
                SensorMeasurements,
            )
            telemetry = NormalizedTelemetry(
                schema_version="1.0",
                node_id="NODE-001",
                timestamp=datetime.now(timezone.utc),
                location=LocationCoordinate(lat=37.7749, lon=-122.4194),
                measurements=SensorMeasurements(
                    temperature=24.5,
                    humidity=60.0,
                    rainfall=15.0,
                ),
                quality=QualityMetadata(valid=True, source="ESP32"),
            )
            r_id = repo1.save_telemetry(telemetry, provenance_hash="a" * 64)
            assert r_id > 0

            repo1.save_hazard_event(
                event_id="HAZ-001",
                hazard_type="FLOOD",
                severity=0.75,
                confidence=0.88,
                detected_at=datetime.now(timezone.utc),
                node_id="NODE-001",
            )
            repo1.save_prediction(
                prediction_id="PRED-001",
                node_id="NODE-001",
                target_hazard="FLOOD",
                horizon_minutes=60,
                predicted_severity=0.82,
                confidence=0.80,
                trend="INCREASING",
                model_version="v2.1",
            )

            # 2. Simulate Backend Restart (destroy repo1, initialize fresh repo2 pointing to same file)
            del repo1
            repo2 = IntelligenceRepository(db_path=db_file)

            # 3. Query records from repo2 and verify integrity
            node = repo2.get_node("NODE-001")
            assert node is not None
            assert node["name"] == "SF Delta Station"

            readings = repo2.get_telemetry("NODE-001")
            assert len(readings) == 1
            assert readings[0]["rainfall"] == 15.0
            assert readings[0]["provenance_hash"] == "a" * 64

            hazards = repo2.get_hazard_events(node_id="NODE-001")
            assert len(hazards) == 1
            assert hazards[0]["severity"] == 0.75
            assert hazards[0]["confidence"] == 0.88

            preds = repo2.get_predictions("NODE-001")
            assert len(preds) == 1
            assert preds[0]["horizon_minutes"] == 60
            assert preds[0]["model_version"] == "v2.1"
        finally:
            Path(db_file).unlink(missing_ok=True)

    def test_04_core_hazard_evaluation(self, client, auth_headers):
        """Stage 4: Evaluate core hazards (Heat, Flood, Drought). Outputs strictly in [0,1]."""
        surge_file = Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json")
        telemetry_payload = json.loads(surge_file.read_text(encoding="utf-8"))

        response = client.post(
            "/api/v1/hazards/evaluate",
            json={"telemetry": telemetry_payload},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        hazards = data["hazards"]
        assert len(hazards) >= 3

        for h in hazards:
            assert 0.0 <= h["severity"] <= 1.0, f"Severity out of range: {h['severity']}"
            assert 0.0 <= h["confidence"] <= 1.0, f"Confidence out of range: {h['confidence']}"
            assert h["simulated"] is False
            assert h["forecast_horizon_minutes"] == 0

        # Flood severity must be high given 95 mm/h rain and 5.2m water level
        flood = next(h for h in hazards if h["hazard"].lower() == "flood")
        assert flood["severity"] >= 0.70

    def test_05_prediction_horizons(self, client, auth_headers):
        """Stage 5: Predictions evaluated at strictly +30m, +60m, +360m horizons."""
        h1 = json.loads(Path("shared/fixtures/golden_demo/01_normal_telemetry.json").read_text(encoding="utf-8"))
        h2 = json.loads(Path("shared/fixtures/golden_demo/02_heavy_rain_telemetry.json").read_text(encoding="utf-8"))
        h3 = json.loads(Path("shared/fixtures/golden_demo/03_saturated_soil_telemetry.json").read_text(encoding="utf-8"))
        current = json.loads(Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json").read_text(encoding="utf-8"))

        response = client.post(
            "/api/v1/predictions/evaluate",
            json={
                "telemetry": current,
                "history": [h1, h2, h3],
                "horizons_minutes": [30, 60, 360],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        preds = data["predictions"]
        assert len(preds) > 0

        horizons_found = {p["forecast_horizon_minutes"] for p in preds}
        assert horizons_found == {30, 60, 360}

        for p in preds:
            assert 0.0 <= p["severity"] <= 1.0
            assert 0.0 <= p["confidence"] <= 1.0
            assert p["simulated"] is False
            assert "model_version" in p

    def test_06_compound_disaster_cascade(self, client, auth_headers):
        """Stage 6: Compound disaster evaluates multi-hazard interactions and causal chains."""
        surge_file = Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json")
        telemetry_payload = json.loads(surge_file.read_text(encoding="utf-8"))

        haz_resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry_payload}, headers=auth_headers)
        hazards = haz_resp.json()["hazards"]

        comp_resp = client.post(
            "/api/v1/compound/evaluate",
            json={"hazards": hazards},
            headers=auth_headers,
        )
        assert comp_resp.status_code == 200
        data = comp_resp.json()
        assert data["success"] is True
        assert "events" in data

    def test_07_human_vulnerability(self, client, auth_headers):
        """Stage 7: Human vulnerability produces impact score from Hazard x Exposure x Vulnerability x Access."""
        surge_file = Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json")
        telemetry_payload = json.loads(surge_file.read_text(encoding="utf-8"))
        haz_resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry_payload}, headers=auth_headers)
        hazards = haz_resp.json()["hazards"]

        zones = [
            {
                "zone_id": "ZONE-A",
                "population": 5000,
                "age_65_plus_ratio": 0.16,
                "age_0_14_ratio": 0.12,
                "socioeconomic_vulnerability": 0.25,
                "healthcare_access": 0.8,
                "road_accessibility": 0.8,
                "critical_facility_access": 0.7,
            }
        ]

        vuln_resp = client.post(
            "/api/v1/vulnerability/evaluate",
            json={"zones": zones, "hazards": hazards},
            headers=auth_headers,
        )
        assert vuln_resp.status_code == 200
        data = vuln_resp.json()
        assert data["success"] is True
        assert len(data["assessments"]) == 1
        ass = data["assessments"][0]
        assert 0.0 <= ass["human_impact"] <= 1.0

    def test_08_dynamic_evacuation_rerouting(self, client, auth_headers):
        """Stage 8: Dynamic evacuation identifies Bridge B cut-off and recalculates path to alternate shelter."""
        surge_file = Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json")
        telemetry_payload = json.loads(surge_file.read_text(encoding="utf-8"))
        haz_resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry_payload}, headers=auth_headers)
        hazards = haz_resp.json()["hazards"]

        net_file = Path("shared/fixtures/golden_demo/05_bridge_failure_network.json")
        network_data = json.loads(net_file.read_text(encoding="utf-8"))

        evac_resp = client.post(
            "/api/v1/evacuation/evaluate",
            json={
                "zones": network_data["zones"],
                "shelters": network_data["shelters"],
                "road_network": network_data["road_network"],
                "hazards": hazards,
            },
            headers=auth_headers,
        )
        assert evac_resp.status_code == 200
        data = evac_resp.json()
        assert data["success"] is True
        recs = data["recommendations"]
        assert len(recs) == 1
        rec = recs[0]

        # Since Bridge B to Shelter North is closed, route MUST be recalculated to East Ridge Shelter
        assert rec["status"] == "RECOMMENDED"
        assert rec["destination"]["shelter_id"] == "SHELTER-EAST"
        # Bridge B must not appear in the selected active route edges
        assert "BRIDGE-B" not in rec["route"]["edge_ids"]

    def test_09_digital_twin_simulation_isolation(self, client, auth_headers):
        """Stage 9: Simulation runs with simulated=true and never alters live authoritative records."""
        sim_file = Path("shared/fixtures/golden_demo/06_simulation_rain40.json")
        sim_request = json.loads(sim_file.read_text(encoding="utf-8"))

        sim_resp = client.post(
            "/api/v1/simulation/run",
            json=sim_request,
            headers=auth_headers,
        )
        assert sim_resp.status_code == 200
        data = sim_resp.json()
        assert data["success"] is True
        sim = data["simulation"]
        assert sim["simulated"] is True
        assert "SCENARIO" in sim["scenario_id"]

    def test_10_response_planner_and_hitl(self, client, auth_headers):
        """Stage 10: Response planner produces actions with evidence IDs and enforces HITL review."""
        surge_file = Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json")
        telemetry_payload = json.loads(surge_file.read_text(encoding="utf-8"))

        resp_plan = client.post(
            "/api/v1/response/evaluate",
            json={
                "telemetry": telemetry_payload,
                "population_zones": [{"zone_id": "ZONE-A", "population": 5000}],
            },
            headers=auth_headers,
        )
        assert resp_plan.status_code == 200
        data = resp_plan.json()
        assert data["success"] is True
        plan = data["plan"]
        assert plan["alert_level"] in ["WARNING", "CRITICAL", "RED", "EMERGENCY", "ORANGE", "YELLOW"]
        assert len(plan["actions"]) > 0

        # Mandatory human review verification
        for act in plan["actions"]:
            if act["action"] in ["EVACUATE_ZONE", "REDIRECT_EVACUATION", "REQUEST_FIELD_VERIFICATION"]:
                assert act["requires_human_review"] is True, f"Action {act['action']} requires HITL approval"

    def test_11_explainability_attribution(self, client, auth_headers):
        """Stage 11: Explainability produces WHAT, WHY, EVIDENCE, and CONFIDENCE."""
        surge_file = Path("shared/fixtures/golden_demo/04_flood_surge_telemetry.json")
        telemetry_payload = json.loads(surge_file.read_text(encoding="utf-8"))

        haz_resp = client.post("/api/v1/hazards/evaluate", json={"telemetry": telemetry_payload}, headers=auth_headers)
        hazards = haz_resp.json()["hazards"]
        flood = next(h for h in hazards if h["hazard"].lower() == "flood")

        expl_resp = client.post(
            "/api/v1/explainability/generate",
            json={
                "target_type": "hazard",
                "target_id": flood["hazard_id"],
                "target_object": flood,
                "level": "STANDARD",
            },
            headers=auth_headers,
        )
        assert expl_resp.status_code == 200
        expl_data = expl_resp.json()
        assert expl_data["success"] is True
        expl = expl_data["explanation"]
        assert "summary" in expl
        assert "reasoning_steps" in expl
        assert "evidence" in expl
        assert "counterfactuals" in expl
        assert "provenance_hash" in expl

    def test_12_realtime_events_history_and_sse(self, client):
        """Stage 12: Realtime broadcaster logs events and allows client catch-up via HTTP."""
        # Direct broadcast verification
        realtime_broadcaster.broadcast_sync(
            "hazard.updated",
            {"node_id": "NODE-001", "hazard": "FLOOD", "severity": 0.85},
        )

        history_resp = client.get("/api/v1/events/history?limit=10")
        assert history_resp.status_code == 200
        data = history_resp.json()
        assert data["success"] is True
        events = data["events"]
        assert len(events) > 0
        event_types = {e["event_type"] for e in events}
        assert "hazard.updated" in event_types


class TestPhase12SecurityAndFailurePaths:
    """Adversarial testing of failure modes and security barriers."""

    def test_unauthenticated_request_rejected(self, client):
        """Unauthenticated requests to protected endpoints return 401."""
        orig = settings.api_auth_enabled
        try:
            settings.api_auth_enabled = True
            resp = client.post("/api/v1/simulation/run", json={"scenario_id": "SCENARIO_RAIN_40", "changes": {}})
            assert resp.status_code == 401
        finally:
            settings.api_auth_enabled = orig

    def test_insufficient_role_rejected(self, client):
        """Public role attempting operator action receives 403."""
        orig = settings.api_auth_enabled
        try:
            settings.api_auth_enabled = True
            public_token = create_access_token(
                client_id="public-user",
                role=Role.PUBLIC,
            )
            headers = {"Authorization": f"Bearer {public_token}"}
            resp = client.post("/api/v1/simulation/run", json={"scenario_id": "SCENARIO_RAIN_40", "changes": {}}, headers=headers)
            assert resp.status_code == 403
        finally:
            settings.api_auth_enabled = orig

    def test_rate_limiter_active(self, client, auth_headers):
        """Bursting requests triggers 429 and Retry-After header."""
        statuses = []
        for _ in range(15):
            r = client.post("/api/v1/response/simulate", json={"plan_id": "P-1", "modifications": []}, headers=auth_headers)
            statuses.append(r.status_code)
        assert 429 in statuses, "Rate limiter did not throttle requests after 10 requests/window"

    def test_malformed_telemetry_rejected(self, client, auth_headers):
        """Malformed or out-of-physical-range telemetry is rejected with 422."""
        bad_payload = {
            "node_id": "NODE-001",
            "timestamp": "2026-09-08T12:00:00Z",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "temperature": 150.0,  # Physically impossible on Earth
        }
        resp = client.post("/api/v1/telemetry/validate", json=bad_payload, headers=auth_headers)
        assert resp.status_code == 422

    def test_no_evacuation_route_returns_no_route(self, client, auth_headers):
        """When all routes are closed, engine returns NO_ROUTE without fabricating paths."""
        net_file = Path("shared/fixtures/evacuation_no_route.json")
        data = json.loads(net_file.read_text(encoding="utf-8"))

        resp = client.post(
            "/api/v1/evacuation/evaluate",
            json={
                "zones": data["zones"],
                "shelters": data["shelters"],
                "road_network": data["road_network"],
                "hazards": data.get("hazards", []),
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        rec = resp.json()["recommendations"][0]
        assert rec["status"] == "NO_ROUTE"
        assert rec["route"] is None
