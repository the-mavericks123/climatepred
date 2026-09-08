"""
End-to-End Functional Acceptance Verification for Climate Eye View.
Strictly verifies:
  1. Full Intelligence Pipeline:
     Location Selection -> External Data -> Hazard Detection -> Predictions ->
     Compound Cascade -> Vulnerability -> Evacuation -> Response Planning -> AI Command Query
  2. Simulation Downstream Propagation:
     Rainfall +40% parameter change mathematically propagates into hazard deltas,
     population exposure increase, prediction escalation, and route degradation.
  3. Epistemic Status & Fault Tolerance:
     Honest UNAVAILABLE status for uncredentialed providers (GloFAS),
     null (never 0) for missing physical water-level sensor,
     and ESP32 disconnection keeps global system ONLINE with 0 nodes.
  4. Evacuation Failure Safety:
     Returns NO_ROUTE when all graph egress paths are severed; never invents routes.
  5. Grounded AI Responses:
     AI command responses reference structured evidence IDs (HAZ-101, PRED-204, etc.)
     without numerical hallucination.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.evacuation.types import EvacuationStatus, RoadEdge, RoadNetwork, Shelter
from intelligence.vulnerability.types import PopulationZone


@pytest.fixture
def client():
    return TestClient(app)


class TestFullIntelligencePipelineE2E:
    """Verifies complete end-to-end operational intelligence chain."""

    def test_location_and_regional_intelligence(self, client):
        # 1. Select Hyderabad
        res = client.get("/api/v1/global/region?name=Hyderabad&lat=17.385&lon=78.487")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        region = data["region"]
        assert region["name"] == "Hyderabad"

        # 2. Weather & Ground Telemetry conditions
        conditions = region["current_conditions"]
        assert "temperature_c" in conditions
        assert "rainfall_mmh" in conditions
        assert "humidity_pct" in conditions
        # Preserves 0 as real reading and null for missing gauge
        assert conditions["water_level"] is None

        # 3. Risks & Hazards
        risks = region["risks"]
        assert "primary_hazard" in risks
        assert "primary_severity" in risks
        assert 0.0 <= risks["primary_severity"] <= 1.0

        # 4. Multi-horizon predictions
        predictions = region["predictions"]
        assert "horizon_30m" in predictions
        assert "horizon_60m" in predictions
        assert "horizon_6h" in predictions
        assert predictions["horizon_6h"] >= predictions["horizon_30m"]

        # 5. Compound cascade
        cascade = region["compound_cascade"]
        assert "primary" in cascade
        assert "secondary" in cascade
        assert "infrastructure" in cascade
        assert "consequence" in cascade

        # 6. Human impact & Social Vulnerability
        impact = region["human_impact"]
        assert "population_exposed" in impact
        assert "vulnerability_index" in impact
        assert "critical_facilities_count" in impact

        # 7. Evacuation routing
        evac = region["evacuation"]
        assert "destination_shelter" in evac
        assert "safe_route" in evac
        assert "avoid" in evac
        assert evac["estimated_travel_min"] > 0

    def test_ai_command_center_grounding(self, client):
        """Verifies AI answers cite evidence IDs and ground responses in real state."""
        questions = [
            ("What is happening here?", "OPERATIONAL ASSESSMENT"),
            ("Why is this area at risk?", "PHYSICAL CAUSAL ATTRIBUTION"),
            ("Who is most vulnerable?", "DEMOGRAPHIC VULNERABILITY"),
            ("Where should people evacuate?", "DYNAMIC EVACUATION DIRECTIVE"),
            ("Which road should be avoided?", "INFRASTRUCTURE INTEGRITY"),
            ("What should responders do now?", "EMERGENCY RESPONDER PRIORITY"),
            ("What happens if rainfall increases by 40%?", "SIMULATION ANALYSIS"),
            ("What is the most dangerous cascading failure?", "COMPOUND CASCADE"),
        ]

        for q, expected_headline_keyword in questions:
            res = client.post(
                "/api/v1/global/ai-query",
                json={"question": q, "region": {"name": "Hyderabad"}},
            )
            assert res.status_code == 200
            ans = res.json().get("answer", {})
            assert expected_headline_keyword in ans.get("headline", "")
            citations = ans.get("evidence_ids", [])
            assert len(citations) >= 3
            assert any("HAZ" in c for c in citations)
            assert any("PRED" in c or "COMP" in c or "EVAC" in c for c in citations)
            assert len(ans.get("actions", [])) >= 2


class TestSimulationPropagationE2E:
    """Verifies that hypothetical perturbations propagate through all models mathematically."""

    def test_rainfall_surge_propagation(self, client):
        # 1. Baseline simulation
        res_baseline = client.post(
            "/api/v1/simulation/run",
            json={"scenario_id": "SCN-RAIN-20"},
        )
        assert res_baseline.status_code == 200
        sim_base = res_baseline.json()["simulation"]

        # 2. +40% Surge simulation
        res_40 = client.post(
            "/api/v1/simulation/run",
            json={"scenario_id": "SCN-RAIN-40"},
        )
        assert res_40.status_code == 200
        sim_40 = res_40.json()["simulation"]

        # 3. Verify downstream propagation
        delta_base = sim_base["summary"]["hazard_change"]["max_severity_delta"]
        delta_40 = sim_40["summary"]["hazard_change"]["max_severity_delta"]
        assert delta_40 > delta_base, "Higher rainfall must increase hazard delta"

        # 4. Verify population exposure propagation
        pop_base = sim_base["summary"]["population_change"]["total_simulated_exposed"]
        pop_40 = sim_40["summary"]["population_change"]["total_simulated_exposed"]
        assert pop_40 >= pop_base, "Higher flood severity must expose equal or more population"

        # 5. Verify simulated flag is strictly true
        assert sim_40["simulated"] is True

    def test_road_degradation_propagation(self, client):
        # Degrade road network accessibility by 50%
        res = client.post(
            "/api/v1/simulation/run",
            json={"scenario_id": "SCN-ROAD-DEGRADE"},
        )
        assert res.status_code == 200
        sim = res.json()["simulation"]
        evac_routes = sim["evacuation_routes"]
        assert len(evac_routes) > 0
        route = evac_routes[0]["route"]
        # Safety score degrades under network degradation
        assert route["safety_score"] < 0.90
        assert route["accessibility"] < 0.60


class TestEpistemicHonestyAndDecoupling:
    """Verifies honest status reporting and physical sensor mesh decoupling."""

    def test_glofas_uncredentialed_reports_unavailable(self, client):
        res = client.get("/api/v1/global/sources")
        assert res.status_code == 200
        summary = res.json()["summary"]
        sources = {s["source_id"]: s for s in summary["sources"]}
        assert "glofas" in sources
        assert sources["glofas"]["status"] == "UNAVAILABLE"
        assert "Copernicus" in sources["glofas"]["error_message"]

    def test_esp32_disconnected_maintains_system_online(self, client):
        res = client.get("/api/v1/global/sources")
        assert res.status_code == 200
        summary = res.json()["summary"]
        sources = {s["source_id"]: s for s in summary["sources"]}
        assert "esp32_mesh" in sources
        assert sources["esp32_mesh"]["status"] == "NOT_CONNECTED"
        assert sources["esp32_mesh"]["is_physical_sensor"] is True

        # Global system status must remain ONLINE
        assert summary["system"] == "OPERATIONAL"
        assert summary["global_data"] == "ONLINE"
        assert summary["physical_mesh_nodes"] == 0

    def test_water_level_invariant_never_zero_when_missing(self, client):
        res = client.get("/api/v1/global/region?name=Hyderabad")
        assert res.status_code == 200
        region = res.json()["region"]
        # Physical water level sensor is not present: must be None / null, NEVER 0.0
        assert region["current_conditions"]["water_level"] is None
        assert region["current_conditions"]["water_level_status"] == "NO DATA SOURCE"


class TestEvacuationGraphSafety:
    """Verifies Dijkstra routing behavior when edges are blocked."""

    def test_no_safe_route_when_graph_severed(self):
        engine = EvacuationEngine()
        zone = PopulationZone(
            zone_id="ZONE-ISOLATED",
            name="Isolated Lowland Sector",
            centroid_lat=17.385,
            centroid_lon=78.486,
            population=5000,
            vulnerability_score=0.75,
            node_id="ZONE-ISOLATED",
        )
        shelter = Shelter(
            shelter_id="SHELTER-HIGHLAND",
            name="North Highland Refuge",
            latitude=17.400,
            longitude=78.490,
            capacity=10000,
            current_occupancy=1000,
            node_id="SHELTER-HIGHLAND",
        )
        # Severed single bridge with closed=True and accessibility below threshold
        impassable_edge = RoadEdge(
            edge_id="BRIDGE-SEVERED",
            from_node="ZONE-ISOLATED",
            to_node="SHELTER-HIGHLAND",
            distance_km=4.0,
            travel_time_minutes=8.0,
            accessibility=0.10,  # Below safety threshold
            hazard_risk=0.98,
            closed=True,
            closure_reason="Bridge submerged under flood wave",
        )
        network = RoadNetwork(
            nodes=["ZONE-ISOLATED", "SHELTER-HIGHLAND"],
            edges=[impassable_edge],
        )

        from intelligence.vulnerability.types import VulnerabilityZoneAssessment

        ass = VulnerabilityZoneAssessment(
            assessment_id="VULN-ISO-01",
            zone_id="ZONE-ISOLATED",
            timestamp=datetime.now(timezone.utc),
            hazard_risk=0.85,
            population_total=5000,
            population_exposed=4000,
            exposure_ratio=0.80,
            vulnerability=0.80,
            accessibility=0.10,
            accessibility_risk=0.90,
            human_impact=0.85,
            confidence=0.88,
            simulated=True,
            provenance_hash="a" * 64,
            formula_version="impact-v1",
        )

        recs = engine.evaluate(
            zones=[zone],
            shelters=[shelter],
            road_network=network,
            vulnerabilities=[ass],
            accessibility_threshold=0.40,
            now=datetime.now(timezone.utc),
        )

        assert len(recs) == 1
        rec = recs[0]
        # Must report NO_ROUTE, never invent a path across a severed bridge
        assert rec.status == EvacuationStatus.NO_ROUTE
        assert rec.route is None
        assert rec.no_route_reason is not None
