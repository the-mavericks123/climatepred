"""Comprehensive Provenance and Determinism Verification for Phase 7 Simulation Engine.
Implements:
  1. Blocker 1: Determinism & Volatile Execution Metadata Decoupling
     - Identical simulation produces identical provenance
     - Execution timestamp mutation does NOT change provenance (H1 == H2)
     - Simulation ID mutation does NOT change provenance (H1 == H2)
  2. Blocker 2: Material Evidence Capture & Canonicalization Invariance
     - Unordered collection reordering invariance (H1 == H2)
     - Order-sensitive sequence reordering sensitivity (H1 != H2 for route_nodes, route_edges, causal_chain)
     - Irrelevant data filtering invariance (H1 == H2)
  3. Mandatory 30-Item Mutation Matrix
     - Verifies that mutating any single material decision input changes the provenance hash (H_baseline != H_mutated)
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from intelligence.simulation.engine import SimulationEngine
from intelligence.simulation.provenance import SimulationProvenanceTracker
from intelligence.simulation.types import ScenarioParameters


@pytest.fixture
def base_components():
    """Provides a baseline set of canonical simulation components."""
    params = ScenarioParameters(
        rainfall_multiplier=1.40,
        temperature_delta=3.0,
        soil_moisture_delta=10.0,
        water_level_delta=1.5,
        drainage_failure_severity=0.4,
        road_accessibility_reduction=0.3,
        target_edge_ids=["ROAD-1", "ROAD-2"],
    )
    hazards = [
        {
            "hazard_id": "HAZ-FLOOD-01",
            "hazard": "flood",
            "severity": 0.65,
            "confidence": 0.90,
            "timestamp": "2026-09-07T12:00:00Z",
            "forecast_horizon_minutes": 0,
            "model_version": "flood-v1",
            "source": "model",
            "simulated": False,
        },
        {
            "hazard_id": "HAZ-HEAT-01",
            "hazard": "heat",
            "severity": 0.50,
            "confidence": 0.85,
            "timestamp": "2026-09-07T12:00:00Z",
            "forecast_horizon_minutes": 0,
            "model_version": "heat-v1",
            "source": "model",
            "simulated": False,
        }
    ]
    predictions = [
        {
            "prediction_id": "PRED-FLOOD-60M",
            "hazard": "flood",
            "prediction_time": "2026-09-07T12:00:00Z",
            "forecast_time": "2026-09-07T13:00:00Z",
            "severity": 0.75,
            "confidence": 0.80,
            "model_version": "phase3-v1",
            "simulated": False,
        }
    ]
    compounds = [
        {
            "event_id": "COMP-001",
            "severity": 0.72,
            "confidence": 0.85,
            "chain": ["heavy_rain", "soil_saturation", "flood", "road_failure"],
            "contributing_hazards": ["HAZ-FLOOD-01", "HAZ-RAIN-01"],
            "rule_version": "compound-v1",
            "timestamp": "2026-09-07T12:00:00Z",
            "simulated": False,
        }
    ]
    vulns = [
        {
            "zone_id": "ZONE-A",
            "population_exposed": 5000,
            "exposure_ratio": 0.50,
            "vulnerability": 0.60,
            "accessibility": 0.70,
            "accessibility_risk": 0.30,
            "human_impact": 0.68,
            "evidence_ids": ["HAZ-FLOOD-01", "COMP-001"],
            "confidence": 0.88,
            "formula_version": "impact-v1",
            "simulated": True,
        }
    ]
    edges = [
        {
            "edge_id": "ROAD-1",
            "from_node": "ZONE-A",
            "to_node": "INT-1",
            "distance_km": 3.0,
            "travel_time_minutes": 6.0,
            "hazard_risk": 0.20,
            "accessibility": 0.80,
            "closed": False,
            "inferred_failure_risk": 0.15,
        },
        {
            "edge_id": "ROAD-2",
            "from_node": "INT-1",
            "to_node": "SHELTER-1",
            "distance_km": 2.5,
            "travel_time_minutes": 5.0,
            "hazard_risk": 0.10,
            "accessibility": 0.90,
            "closed": False,
            "inferred_failure_risk": 0.05,
        }
    ]
    shelters = [
        {
            "shelter_id": "SHELTER-1",
            "capacity": 8000,
            "current_occupancy": 2000,
            "available_capacity": 6000,
            "hazard_risk": 0.05,
            "accessibility": 0.95,
            "safe": True,
            "latitude": 37.78,
            "longitude": -122.41,
            "simulated": True,
        }
    ]
    routes = [
        {
            "zone_id": "ZONE-A",
            "destination": {"shelter_id": "SHELTER-1", "assigned_population": 4000},
            "route": {
                "nodes": ["ZONE-A", "INT-1", "SHELTER-1"],
                "edge_ids": ["ROAD-1", "ROAD-2"],
                "distance_km": 5.5,
                "estimated_travel_minutes": 11.0,
                "hazard_exposure": 0.15,
                "accessibility": 0.85,
                "safety_score": 0.90,
            },
            "status": "RECOMMENDED",
            "reason": "Optimal safe path to Shelter 1",
        }
    ]
    return {
        "scenario_id": "SCN-RAIN-40",
        "scenario_version": "1.0",
        "base_state_id": "STATE-001",
        "base_state_hash": "a" * 64,
        "parameters": params,
        "hazards": hazards,
        "predictions": predictions,
        "compound_events": compounds,
        "vulnerability_zones": vulns,
        "road_edges": edges,
        "shelters": shelters,
        "evacuation_routes": routes,
        "confidence": 0.92,
        "accessibility_threshold": 0.30,
        "hazard_threshold": 0.85,
    }


def compute_hash(comp):
    return SimulationProvenanceTracker.compute_provenance_hash(**comp)


# ===========================================================================
# 1. BLOCKER 1: DETERMINISM & EXECUTION METADATA DECOUPLING
# ===========================================================================

class TestBlocker1DeterminismAndDecoupling:
    """Proves that volatile execution metadata does NOT contaminate provenance."""

    def test_identical_simulation_produces_identical_hash(self, base_components):
        h1 = compute_hash(base_components)
        h2 = compute_hash(base_components)
        assert h1 == h2

    def test_timestamp_only_mutation_invariance(self, base_components):
        """Execution timestamp change MUST NOT alter the provenance hash."""
        h1 = SimulationProvenanceTracker.compute_provenance_hash(
            **base_components,
            timestamp=datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc),
        )
        h2 = SimulationProvenanceTracker.compute_provenance_hash(
            **base_components,
            timestamp=datetime(2026, 9, 7, 18, 45, 12, tzinfo=timezone.utc),
        )
        assert h1 == h2, "Execution timestamp contaminated provenance hash!"

    def test_simulation_id_only_mutation_invariance(self, base_components):
        """Generated simulation execution ID change MUST NOT alter the provenance hash."""
        h1 = SimulationProvenanceTracker.compute_provenance_hash(
            **base_components,
            simulation_id="SIM-EXECUTION-RUN-001",
        )
        h2 = SimulationProvenanceTracker.compute_provenance_hash(
            **base_components,
            simulation_id="SIM-EXECUTION-RUN-999-DIFFERENT",
        )
        assert h1 == h2, "Generated simulation ID contaminated provenance hash!"

    def test_request_id_only_mutation_invariance(self, base_components):
        """Request ID change MUST NOT alter the provenance hash."""
        h1 = SimulationProvenanceTracker.compute_provenance_hash(
            **base_components,
            request_id="REQ-FIRST-1111",
        )
        h2 = SimulationProvenanceTracker.compute_provenance_hash(
            **base_components,
            request_id="REQ-SECOND-2222",
        )
        assert h1 == h2, "Request ID contaminated provenance hash!"

    def test_end_to_end_engine_determinism_across_time(self):
        """Two engine runs with identical base inputs executed seconds apart yield identical provenance."""
        engine = SimulationEngine()
        t1 = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 7, 12, 0, 30, tzinfo=timezone.utc)
        base = SimulationEngine.build_default_base_state(t1)

        res1 = engine.run_simulation("SCN-RAIN-20", base_state=base, now=t1)
        res2 = engine.run_simulation("SCN-RAIN-20", base_state=base, now=t2)
        assert res1.provenance_hash == res2.provenance_hash


# ===========================================================================
# 2. BLOCKER 2: MATERIAL EVIDENCE INVARIANCE & SENSITIVITY
# ===========================================================================

class TestBlocker2InvarianceAndCanonicalization:
    """Proves canonicalization rules (order-sensitive vs. order-insensitive) and relevance filtering."""

    def test_unordered_hazards_reorder_invariance(self, base_components):
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)
        comp2["hazards"] = list(reversed(comp1["hazards"]))

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 == h2, "Unordered hazard list reordering must remain invariant"

    def test_unordered_shelters_reorder_invariance(self, base_components):
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)
        # Add second shelter and reverse
        extra_shelter = {
            "shelter_id": "SHELTER-2",
            "capacity": 5000,
            "current_occupancy": 1000,
            "available_capacity": 4000,
            "hazard_risk": 0.08,
            "accessibility": 0.90,
            "safe": True,
            "latitude": 37.76,
            "longitude": -122.39,
            "simulated": True,
        }
        comp1["shelters"].append(extra_shelter)
        comp2["shelters"].append(extra_shelter)
        comp2["shelters"] = list(reversed(comp1["shelters"]))

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 == h2, "Unordered shelter list reordering must remain invariant"

    def test_unordered_candidate_edges_reorder_invariance(self, base_components):
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)
        comp2["road_edges"] = list(reversed(comp1["road_edges"]))

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 == h2, "Unordered road edges reordering must remain invariant"

    def test_order_sensitive_route_nodes_reorder_changes_hash(self, base_components):
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)
        # Reorder nodes sequence: ["ZONE-A", "INT-1", "SHELTER-1"] -> ["ZONE-A", "SHELTER-1", "INT-1"]
        comp2["evacuation_routes"][0]["route"]["nodes"] = ["ZONE-A", "SHELTER-1", "INT-1"]

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 != h2, "Order-sensitive route_nodes sequence MUST alter provenance hash!"

    def test_order_sensitive_route_edges_reorder_changes_hash(self, base_components):
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)
        # Reorder edge sequence: ["ROAD-1", "ROAD-2"] -> ["ROAD-2", "ROAD-1"]
        comp2["evacuation_routes"][0]["route"]["edge_ids"] = ["ROAD-2", "ROAD-1"]

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 != h2, "Order-sensitive route_edges sequence MUST alter provenance hash!"

    def test_order_sensitive_causal_chain_reorder_changes_hash(self, base_components):
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)
        # Reorder causal chain: ["heavy_rain", "soil_saturation", "flood", "road_failure"] -> reversed
        comp2["compound_events"][0]["chain"] = list(reversed(comp1["compound_events"][0]["chain"]))

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 != h2, "Order-sensitive compound causal_chain sequence MUST alter provenance hash!"

    def test_irrelevant_data_filtering_invariance(self, base_components):
        """An irrelevant hazard not part of simulation decision is filtered out (H1 == H2)."""
        comp1 = deepcopy(base_components)
        comp2 = deepcopy(base_components)

        irrelevant_hazard = {
            "hazard_id": "IRRELEVANT-HAZ-UNRELATED-999",
            "hazard": "drought",
            "severity": 0.10,
            "confidence": 0.50,
            "timestamp": "2026-09-07T12:00:00Z",
            "forecast_horizon_minutes": 0,
            "model_version": "drought-v1",
            "source": "unrelated_sensor",
            "simulated": False,
            "is_relevant": False,
        }
        comp2["hazards"].append(irrelevant_hazard)

        h1 = compute_hash(comp1)
        h2 = compute_hash(comp2)
        assert h1 == h2, "Irrelevant data must be filtered out and not contaminate provenance!"


# ===========================================================================
# 3. MANDATORY 30-ITEM PROVENANCE MUTATION MATRIX
# ===========================================================================

class TestProvenanceMutationMatrix30:
    """Verifies that mutating each of the 30 material simulation inputs changes the hash."""

    @pytest.fixture(autouse=True)
    def setup_baseline(self, base_components):
        self.base = base_components
        self.baseline_hash = compute_hash(self.base)

    def test_mut_01_rainfall_multiplier(self):
        comp = deepcopy(self.base)
        comp["parameters"] = ScenarioParameters(rainfall_multiplier=1.80)
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_02_temperature_delta(self):
        comp = deepcopy(self.base)
        comp["parameters"] = ScenarioParameters(temperature_delta=8.5)
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_03_base_state_input(self):
        comp = deepcopy(self.base)
        comp["base_state_hash"] = "b" * 64
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_04_hazard_severity(self):
        comp = deepcopy(self.base)
        comp["hazards"][0]["severity"] = 0.99
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_05_hazard_confidence(self):
        comp = deepcopy(self.base)
        comp["hazards"][0]["confidence"] = 0.55
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_06_hazard_evidence_id(self):
        comp = deepcopy(self.base)
        comp["hazards"][0]["hazard_id"] = "HAZ-FLOOD-MUTATED-ID"
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_07_prediction_severity(self):
        comp = deepcopy(self.base)
        comp["predictions"][0]["severity"] = 0.95
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_08_prediction_confidence(self):
        comp = deepcopy(self.base)
        comp["predictions"][0]["confidence"] = 0.60
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_09_prediction_evidence_id(self):
        comp = deepcopy(self.base)
        comp["predictions"][0]["prediction_id"] = "PRED-MUTATED-ID"
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_10_compound_severity(self):
        comp = deepcopy(self.base)
        comp["compound_events"][0]["severity"] = 0.99
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_11_compound_causal_chain(self):
        comp = deepcopy(self.base)
        comp["compound_events"][0]["chain"] = ["heavy_rain", "direct_washout", "road_failure"]
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_12_vulnerability(self):
        comp = deepcopy(self.base)
        comp["vulnerability_zones"][0]["vulnerability"] = 0.92
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_13_human_impact(self):
        comp = deepcopy(self.base)
        comp["vulnerability_zones"][0]["human_impact"] = 0.99
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_14_population_exposed(self):
        comp = deepcopy(self.base)
        comp["vulnerability_zones"][0]["population_exposed"] = 9500
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_15_road_hazard(self):
        comp = deepcopy(self.base)
        comp["road_edges"][0]["hazard_risk"] = 0.85
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_16_road_accessibility(self):
        comp = deepcopy(self.base)
        comp["road_edges"][0]["accessibility"] = 0.35
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_17_road_travel_time(self):
        comp = deepcopy(self.base)
        comp["road_edges"][0]["travel_time_minutes"] = 25.0
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_18_road_closure(self):
        comp = deepcopy(self.base)
        comp["road_edges"][0]["closed"] = True
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_19_inferred_failure_risk(self):
        comp = deepcopy(self.base)
        comp["road_edges"][0]["inferred_failure_risk"] = 0.88
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_20_shelter_capacity(self):
        comp = deepcopy(self.base)
        comp["shelters"][0]["capacity"] = 15000
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_21_shelter_occupancy(self):
        comp = deepcopy(self.base)
        comp["shelters"][0]["current_occupancy"] = 7500
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_22_shelter_hazard(self):
        comp = deepcopy(self.base)
        comp["shelters"][0]["hazard_risk"] = 0.55
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_23_shelter_accessibility(self):
        comp = deepcopy(self.base)
        comp["shelters"][0]["accessibility"] = 0.50
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_24_shelter_safety(self):
        comp = deepcopy(self.base)
        comp["shelters"][0]["safe"] = False
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_25_evacuation_route(self):
        comp = deepcopy(self.base)
        comp["evacuation_routes"][0]["route"]["nodes"] = ["ZONE-A", "INT-ALT", "SHELTER-1"]
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_26_route_safety(self):
        comp = deepcopy(self.base)
        comp["evacuation_routes"][0]["route"]["safety_score"] = 0.45
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_27_routing_threshold(self):
        comp = deepcopy(self.base)
        comp["accessibility_threshold"] = 0.55
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_28_model_version(self):
        comp = deepcopy(self.base)
        comp["model_versions"] = {"hazard_models": "phase2-v2-experimental"}
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_29_transformation_version(self):
        comp = deepcopy(self.base)
        comp["transform_version"] = "sim-trans-v2"
        assert compute_hash(comp) != self.baseline_hash

    def test_mut_30_scenario_version(self):
        comp = deepcopy(self.base)
        comp["scenario_version"] = "2.0"
        assert compute_hash(comp) != self.baseline_hash
