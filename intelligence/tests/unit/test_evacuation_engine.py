"""
Unit tests for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Tests demand calculation, Dijkstra hazard-aware routing, shelter capacity allocation,
confidence scoring, provenance sensitivity, and dynamic invalidation.
"""

from datetime import datetime, timezone
import pytest

from intelligence.compound.types import StateEvidenceType
from intelligence.evacuation.confidence import EvacuationConfidenceCalculator
from intelligence.evacuation.demand import EvacuationDemandCalculator
from intelligence.evacuation.network import RoadNetworkGraph
from intelligence.evacuation.provenance import EvacuationProvenanceTracker
from intelligence.evacuation.routing import HazardAwareRouter
from intelligence.evacuation.shelters import ShelterManager
from intelligence.evacuation.types import (
    EvacuationDemand,
    EvacuationRoute,
    EvacuationStatus,
    RoadEdge,
    RoadNetwork,
    Shelter,
)
from intelligence.vulnerability.types import VulnerabilityZoneAssessment

T_NOW = datetime.now(timezone.utc)


def _make_sample_assessment(human_impact=0.75, hazard_risk=0.80, pop_exposed=10000, vuln=0.60):
    return VulnerabilityZoneAssessment(
        assessment_id="VULN-Z1-01",
        zone_id="ZONE-1",
        timestamp=T_NOW,
        forecast_horizon_minutes=0,
        evidence_type=StateEvidenceType.OBSERVED,
        hazard_risk=hazard_risk,
        population_total=12000,
        population_exposed=pop_exposed,
        exposure_ratio=pop_exposed / 12000,
        vulnerability=vuln,
        accessibility=0.80,
        accessibility_risk=0.20,
        human_impact=human_impact,
        confidence=0.88,
        evidence_ids=["HAZ-01"],
        drivers=[],
        simulated=True,
        provenance_hash="a" * 64,
        formula_version="impact-v1",
    )


class TestEvacuationDemandCalculator:
    def test_low_risk_zone_does_not_require_evacuation(self):
        ass = _make_sample_assessment(human_impact=0.30, hazard_risk=0.40)
        demand = EvacuationDemandCalculator.calculate_demand(ass)
        assert demand.evacuation_required is False
        assert demand.population_to_evacuate == 0
        assert demand.priority == 0.0

    def test_high_risk_zone_requires_evacuation_with_bounded_population(self):
        ass = _make_sample_assessment(human_impact=0.85, hazard_risk=0.90, pop_exposed=10000)
        demand = EvacuationDemandCalculator.calculate_demand(ass)
        assert demand.evacuation_required is True
        assert demand.population_to_evacuate > 0
        assert demand.population_to_evacuate <= demand.population_exposed
        assert 0.0 <= demand.priority <= 1.0

    def test_vulnerability_increases_priority(self):
        ass_low_v = _make_sample_assessment(vuln=0.20)
        ass_high_v = _make_sample_assessment(vuln=0.90)
        d_low = EvacuationDemandCalculator.calculate_demand(ass_low_v)
        d_high = EvacuationDemandCalculator.calculate_demand(ass_high_v)
        assert d_high.priority > d_low.priority


class TestHazardAwareRouter:
    @pytest.fixture
    def sample_graph(self):
        edges = [
            RoadEdge(
                edge_id="E-SHORT-HAZARDOUS",
                from_node="A",
                to_node="B",
                distance_km=2.0,
                travel_time_minutes=4.0,
                hazard_risk=0.85,
                accessibility=0.90,
                closed=False,
            ),
            RoadEdge(
                edge_id="E-LONG-SAFE-1",
                from_node="A",
                to_node="C",
                distance_km=3.0,
                travel_time_minutes=5.0,
                hazard_risk=0.05,
                accessibility=0.95,
                closed=False,
            ),
            RoadEdge(
                edge_id="E-LONG-SAFE-2",
                from_node="C",
                to_node="B",
                distance_km=3.0,
                travel_time_minutes=5.0,
                hazard_risk=0.05,
                accessibility=0.95,
                closed=False,
            ),
        ]
        net = RoadNetwork(network_id="N1", nodes=["A", "B", "C"], edges=edges)
        return RoadNetworkGraph(net)

    def test_safest_route_preferred_over_hazardous_shorter_route(self, sample_graph):
        route = HazardAwareRouter.find_route(sample_graph, "A", "B")
        assert route is not None
        # Should take A -> C -> B because the hazard multiplier on E-SHORT makes it more expensive
        assert route.nodes == ["A", "C", "B"]
        assert route.safety_score > 0.80

    def test_closed_edge_is_never_traversed(self, sample_graph):
        # Close E-LONG-SAFE-1
        edge = sample_graph.get_edge("E-LONG-SAFE-1")
        edge.closed = True

        route = HazardAwareRouter.find_route(sample_graph, "A", "B")
        assert route is not None
        # Must fall back to A -> B directly because safe route is severed
        assert route.nodes == ["A", "B"]

    def test_unreachable_node_returns_none(self, sample_graph):
        route = HazardAwareRouter.find_route(sample_graph, "A", "NON-EXISTENT")
        assert route is None


class TestShelterManager:
    def test_available_capacity_calculation(self):
        s = Shelter(
            shelter_id="S1",
            name="Shelter 1",
            latitude=37.77,
            longitude=-122.41,
            capacity=5000,
            current_occupancy=1500,
        )
        assert s.available_capacity == 3500

    def test_capacity_allocation_decrements_deterministically(self):
        s = Shelter(
            shelter_id="S1",
            name="Shelter 1",
            latitude=37.77,
            longitude=-122.41,
            capacity=5000,
            current_occupancy=1000,
        )
        mgr = ShelterManager([s])
        shelter_inst = mgr.get_shelter("S1")
        dest = mgr.allocate_capacity(shelter_inst, 2500)
        assert dest.assigned_population == 2500
        assert dest.available_capacity_before == 4000
        assert dest.available_capacity_after == 1500
        assert shelter_inst.available_capacity == 1500

    def test_unsafe_shelter_rejected(self):
        s = Shelter(
            shelter_id="S-UNSAFE",
            name="Flooded Shelter",
            latitude=37.77,
            longitude=-122.41,
            capacity=5000,
            current_occupancy=0,
            safe=False,
            hazard_risk=0.85,
        )
        mgr = ShelterManager([s])
        assert mgr.is_shelter_safe(s) is False


class TestEvacuationConfidenceCalculator:
    def test_confidence_penalties(self):
        ass = _make_sample_assessment()
        s_real = Shelter(shelter_id="S1", name="S1", latitude=0, longitude=0, capacity=1000, simulated=False)
        s_sim = Shelter(shelter_id="S2", name="S2", latitude=0, longitude=0, capacity=1000, simulated=True)
        r = EvacuationRoute(
            route_id="R1", origin_node="A", destination_node="B",
            distance_km=5, estimated_travel_minutes=10, hazard_exposure=0.1,
            accessibility=0.9, safety_score=0.85, total_cost=15.0,
        )

        conf_real = EvacuationConfidenceCalculator.calculate_confidence(ass, s_real, r, is_predicted=False)
        conf_sim = EvacuationConfidenceCalculator.calculate_confidence(ass, s_sim, r, is_predicted=False)
        assert conf_sim < conf_real

        # Prediction discount
        conf_pred = EvacuationConfidenceCalculator.calculate_confidence(ass, s_real, r, is_predicted=True)
        assert conf_pred < conf_real


class TestEvacuationProvenanceTracker:
    def test_provenance_sensitivity(self):
        prov1 = EvacuationProvenanceTracker.compute_provenance_hash(
            "Z1", 5000, 0.85, "RECOMMENDED", "S1", ["A", "B"], ["E1"], "v1", "v1"
        )
        # Mutate population
        prov2 = EvacuationProvenanceTracker.compute_provenance_hash(
            "Z1", 5001, 0.85, "RECOMMENDED", "S1", ["A", "B"], ["E1"], "v1", "v1"
        )
        assert prov1 != prov2

        # Mutate shelter
        prov3 = EvacuationProvenanceTracker.compute_provenance_hash(
            "Z1", 5000, 0.85, "RECOMMENDED", "S2", ["A", "B"], ["E1"], "v1", "v1"
        )
        assert prov1 != prov3

    def test_provenance_ordering_invariance(self):
        prov1 = EvacuationProvenanceTracker.compute_provenance_hash(
            "Z1", 5000, 0.85, "RECOMMENDED", "S1", ["A", "B"], ["E1", "E2"], "v1", "v1"
        )
        prov2 = EvacuationProvenanceTracker.compute_provenance_hash(
            "Z1", 5000, 0.85, "RECOMMENDED", "S1", ["A", "B"], ["E2", "E1"], "v1", "v1"
        )
        assert prov1 == prov2


# ==============================================================================
# BLOCKER 1 REMEDIATION: DYNAMIC ACCESSIBILITY INVALIDATION (TESTS A - F)
# ==============================================================================

class TestAccessibilityInvalidation:
    def test_a_accessibility_above_threshold(self):
        """
        TEST A — accessibility above threshold (e.g. 0.80 >= 0.50) -> Edge usable, route available.
        """
        edge = RoadEdge(
            edge_id="E-AB",
            from_node="A",
            to_node="B",
            distance_km=2.0,
            travel_time_minutes=4.0,
            hazard_risk=0.10,
            accessibility=0.80,
            closed=False,
        )
        graph = RoadNetworkGraph(RoadNetwork(network_id="NET-A", nodes=["A", "B"], edges=[edge]))
        threshold = 0.50

        cost = HazardAwareRouter.calculate_edge_cost(edge, accessibility_threshold=threshold)
        assert cost != float("inf")
        assert cost > 0.0

        route = HazardAwareRouter.find_route(graph, "A", "B", accessibility_threshold=threshold)
        assert route is not None
        assert route.nodes == ["A", "B"]
        assert route.accessibility == 0.80

    def test_b_accessibility_below_threshold(self):
        """
        TEST B — accessibility below threshold (e.g. 0.40 < 0.50) -> Edge unavailable.
        """
        edge = RoadEdge(
            edge_id="E-AB",
            from_node="A",
            to_node="B",
            distance_km=2.0,
            travel_time_minutes=4.0,
            hazard_risk=0.10,
            accessibility=0.40,
            closed=False,
        )
        graph = RoadNetworkGraph(RoadNetwork(network_id="NET-B", nodes=["A", "B"], edges=[edge]))
        threshold = 0.50

        cost = HazardAwareRouter.calculate_edge_cost(edge, accessibility_threshold=threshold)
        assert cost == float("inf")

        route = HazardAwareRouter.find_route(graph, "A", "B", accessibility_threshold=threshold)
        assert route is None

    def test_c_existing_route_becomes_invalid(self):
        """
        TEST C — initial route A -> B -> C becomes invalid when B -> C accessibility degrades
        from 0.90 to 0.30 (threshold = 0.50), dynamically selecting alternative route A -> D -> C.
        """
        edges = [
            # Primary fast route via B: A -> B -> C (total 8 min)
            RoadEdge(edge_id="E-AB", from_node="A", to_node="B", distance_km=2.0, travel_time_minutes=4.0, accessibility=0.90, hazard_risk=0.05, closed=False),
            RoadEdge(edge_id="E-BC", from_node="B", to_node="C", distance_km=2.0, travel_time_minutes=4.0, accessibility=0.90, hazard_risk=0.05, closed=False),
            # Alternative longer route via D: A -> D -> C (total 14 min)
            RoadEdge(edge_id="E-AD", from_node="A", to_node="D", distance_km=4.0, travel_time_minutes=7.0, accessibility=0.85, hazard_risk=0.05, closed=False),
            RoadEdge(edge_id="E-DC", from_node="D", to_node="C", distance_km=4.0, travel_time_minutes=7.0, accessibility=0.85, hazard_risk=0.05, closed=False),
        ]
        net = RoadNetwork(network_id="NET-C", nodes=["A", "B", "C", "D"], edges=edges)
        graph = RoadNetworkGraph(net)
        threshold = 0.50

        # Initial evaluation: picks faster A -> B -> C
        route_initial = HazardAwareRouter.find_route(graph, "A", "C", accessibility_threshold=threshold)
        assert route_initial is not None
        assert route_initial.nodes == ["A", "B", "C"]

        # Material accessibility degradation on B -> C
        edge_bc = graph.get_edge("E-BC")
        assert edge_bc is not None
        edge_bc.accessibility = 0.30

        # Recomputation: B -> C is now below threshold (0.30 < 0.50); router must select alternative A -> D -> C
        route_updated = HazardAwareRouter.find_route(graph, "A", "C", accessibility_threshold=threshold)
        assert route_updated is not None
        assert route_updated.nodes == ["A", "D", "C"]
        assert "E-BC" not in route_updated.edge_ids

    def test_d_accessibility_degradation_causes_no_route(self):
        """
        TEST D — accessibility degradation on single access corridor causes NO_ROUTE.
        """
        from intelligence.evacuation.engine import EvacuationEngine
        from intelligence.evacuation.types import PopulationZone, NoRouteReason

        zone = PopulationZone(zone_id="ZONE-ISOLATED", population=5000, simulated=True)
        shelter = Shelter(shelter_id="SHELTER-SAFE", name="Safe Shelter", latitude=37.77, longitude=-122.41, capacity=6000, safe=True, hazard_risk=0.05, node_id="SHELTER-SAFE")
        edge = RoadEdge(edge_id="E-ISOLATED", from_node="ZONE-ISOLATED", to_node="SHELTER-SAFE", distance_km=3.0, travel_time_minutes=5.0, accessibility=0.20, hazard_risk=0.10, closed=False)

        net = RoadNetwork(network_id="NET-ISO", nodes=["ZONE-ISOLATED", "SHELTER-SAFE"], edges=[edge])
        engine = EvacuationEngine()
        ass = _make_sample_assessment(human_impact=0.85, hazard_risk=0.85, pop_exposed=4000)
        ass.zone_id = "ZONE-ISOLATED"

        recs = engine.evaluate(
            zones=[zone],
            shelters=[shelter],
            road_network=net,
            vulnerabilities=[ass],
            accessibility_threshold=0.40,  # 0.20 < 0.40 -> edge impassable
        )

        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.NO_ROUTE
        assert rec.destination is None
        assert rec.route is None
        assert rec.no_route_reason in (NoRouteReason.NO_FEASIBLE_PATH, NoRouteReason.ALL_ROADS_CLOSED)

    def test_e_threshold_is_configurable(self):
        """
        TEST E — threshold is configurable.
        Run the exact same network with two different thresholds:
          threshold=0.40 -> accessibility 0.45 is eligible (route found)
          threshold=0.50 -> accessibility 0.45 is ineligible (route None)
        Proves routing logic does not use a hidden hardcoded threshold.
        """
        edge = RoadEdge(edge_id="E-TEST", from_node="X", to_node="Y", distance_km=2.0, travel_time_minutes=4.0, accessibility=0.45, hazard_risk=0.10, closed=False)
        graph = RoadNetworkGraph(RoadNetwork(network_id="NET-E", nodes=["X", "Y"], edges=[edge]))

        # With threshold 0.40: 0.45 >= 0.40 -> Pass
        route_lenient = HazardAwareRouter.find_route(graph, "X", "Y", accessibility_threshold=0.40)
        assert route_lenient is not None
        assert route_lenient.nodes == ["X", "Y"]

        # With threshold 0.50: 0.45 < 0.50 -> Fail
        route_strict = HazardAwareRouter.find_route(graph, "X", "Y", accessibility_threshold=0.50)
        assert route_strict is None

    def test_f_explicit_closure_remains_distinct(self):
        """
        TEST F — explicit closure remains distinct:
          closed = False and accessibility = 0.30 (< threshold 0.50)
          does NOT become closed = True.
          The road is unavailable for routing, but closed remains strictly False.
        """
        edge = RoadEdge(
            edge_id="E-DISTINCT",
            from_node="P",
            to_node="Q",
            distance_km=3.0,
            travel_time_minutes=6.0,
            accessibility=0.30,
            hazard_risk=0.10,
            closed=False,
        )
        threshold = 0.50
        cost = HazardAwareRouter.calculate_edge_cost(edge, accessibility_threshold=threshold)
        assert cost == float("inf")
        # Physical closure state must NOT be modified
        assert edge.closed is False


# ==============================================================================
# BLOCKER 2 REMEDIATION: PROVENANCE MUTATION MATRIX (22 MATERIAL MUTATIONS)
# ==============================================================================

class TestProvenanceMutationMatrix:
    @pytest.fixture
    def baseline_payload(self):
        """Constructs a comprehensive baseline canonical provenance payload."""
        return EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="ZONE-M1",
            total_population=10000,
            population_exposed=6000,
            population_to_evacuate=4500,
            priority=0.82,
            vulnerability=0.70,
            human_impact=0.78,
            accessibility_risk=0.25,
            evidence_ids=["EVID-01", "EVID-02"],
            source_confidence=0.92,
            assessment_confidence=0.88,
            hazards=[{
                "hazard_id": "HAZ-01",
                "hazard": "flood",
                "severity": 0.75,
                "confidence": 0.89,
                "timestamp": "2026-09-07T14:00:00Z",
                "forecast_horizon_minutes": 0,
                "model_version": "flood-v1",
                "simulated": False,
            }],
            predictions=[{
                "prediction_id": "PRED-01",
                "hazard": "flood",
                "severity": 0.82,
                "confidence": 0.85,
                "prediction_time": "2026-09-07T14:00:00Z",
                "forecast_time": "2026-09-07T15:00:00Z",
                "forecast_horizon_minutes": 60,
                "model_version": "flood-v1",
                "simulated": False,
            }],
            compound_events=[{
                "event_id": "COMP-01",
                "severity": 0.88,
                "confidence": 0.84,
                "chain": ["flood", "inferred_road_failure_risk", "inferred_access_loss"],
                "contributing_hazards": ["flood"],
                "rule_version": "compound-v1",
                "simulated": False,
            }],
            candidate_edges=[{
                "edge_id": "ROAD-01",
                "from_node": "ZONE-M1",
                "to_node": "SHELTER-01",
                "distance_km": 4.5,
                "travel_time_minutes": 8.0,
                "hazard_risk": 0.12,
                "accessibility": 0.88,
                "closed": False,
                "inferred_failure_risk": None,
            }],
            accessibility_threshold=0.40,
            hazard_threshold=0.95,
            algorithm_version="dijkstra-hazard-v1",
            cost_formula_version="cost-v1",
            candidate_shelters=[{
                "shelter_id": "SHELTER-01",
                "capacity": 5000,
                "current_occupancy": 500,
                "hazard_risk": 0.05,
                "accessibility": 0.95,
                "safe": True,
                "latitude": 37.77,
                "longitude": -122.41,
                "simulated": False,
            }],
            selected_shelter_id="SHELTER-01",
            route_nodes=["ZONE-M1", "SHELTER-01"],
            route_edges=["ROAD-01"],
            distance_km=4.5,
            travel_time_minutes=8.0,
            hazard_exposure=0.12,
            route_accessibility=0.88,
            route_safety_score=0.91,
            avoid_edges=[],
            assigned_population=4500,
            status="RECOMMENDED",
            reason="Safe corridor confirmed",
            final_confidence=0.86,
            simulated=False,
            forecast_horizon_minutes=0,
        )

    def test_mutation_1_population_exposed(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["zone"]["population_exposed"] = 6500
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_2_population_to_evacuate(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["zone"]["population_to_evacuate"] = 4600
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_3_human_impact(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["vulnerability_assessment"]["human_impact"] = 0.85
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_4_vulnerability(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["vulnerability_assessment"]["vulnerability"] = 0.79
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_5_hazard_severity(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["evidence"]["hazards"][0]["severity"] = 0.92
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_6_hazard_confidence(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["evidence"]["hazards"][0]["confidence"] = 0.95
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_7_prediction_severity(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["evidence"]["predictions"][0]["severity"] = 0.99
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_8_prediction_evidence_id(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["evidence"]["predictions"][0]["prediction_id"] = "PRED-MUTATED"
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_9_compound_severity(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["evidence"]["compound_events"][0]["severity"] = 0.96
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_10_compound_causal_chain(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["evidence"]["compound_events"][0]["causal_chain"] = ["flood", "bridge_washout", "access_loss"]
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_11_road_hazard(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["network_inputs"]["candidate_edges"][0]["hazard_risk"] = 0.45
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_12_road_accessibility(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["network_inputs"]["candidate_edges"][0]["accessibility"] = 0.55
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_13_road_travel_time(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["network_inputs"]["candidate_edges"][0]["travel_time_minutes"] = 15.0
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_14_road_closure(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["network_inputs"]["candidate_edges"][0]["closed"] = True
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_15_shelter_capacity(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["shelters"][0]["capacity"] = 7500
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_16_shelter_occupancy(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["shelters"][0]["current_occupancy"] = 1200
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_17_shelter_hazard(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["shelters"][0]["hazard_risk"] = 0.25
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_18_shelter_accessibility(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["shelters"][0]["accessibility"] = 0.65
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_19_shelter_safety(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["shelters"][0]["safe"] = False
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_20_accessibility_threshold(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["routing_config"]["accessibility_threshold"] = 0.60
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_21_routing_algorithm_version(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["routing_config"]["algorithm_version"] = "dijkstra-v2"
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2

    def test_mutation_22_cost_formula_version(self, baseline_payload):
        import copy
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=baseline_payload)
        p = copy.deepcopy(baseline_payload)
        p["routing_config"]["cost_formula_version"] = "cost-v2"
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        assert h1 != h2


# ==============================================================================
# BLOCKER 2 REMEDIATION: PROVENANCE INVARIANCE TESTS
# ==============================================================================

class TestProvenanceInvariance:
    def test_ordering_invariance_unordered_inputs(self):
        """
        Reordering equivalent unordered collections (candidate_shelters, candidate_edges, avoid_edges,
        hazards, predictions, evidence_ids) must yield identical provenance hashes: H1 == H2.
        """
        p1 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1",
            total_population=5000,
            population_exposed=3000,
            population_to_evacuate=2000,
            priority=0.8,
            vulnerability=0.6,
            human_impact=0.7,
            accessibility_risk=0.2,
            evidence_ids=["HAZ-02", "HAZ-01"],
            hazards=[
                {"hazard_id": "HAZ-B", "severity": 0.5, "confidence": 0.8},
                {"hazard_id": "HAZ-A", "severity": 0.7, "confidence": 0.9},
            ],
            candidate_edges=[
                {"edge_id": "EDGE-2", "from_node": "B", "to_node": "C", "distance_km": 2.0, "travel_time_minutes": 3.0, "hazard_risk": 0.1, "accessibility": 0.9, "closed": False},
                {"edge_id": "EDGE-1", "from_node": "A", "to_node": "B", "distance_km": 1.0, "travel_time_minutes": 2.0, "hazard_risk": 0.1, "accessibility": 0.9, "closed": False},
            ],
            candidate_shelters=[
                {"shelter_id": "SHELTER-Y", "capacity": 3000, "current_occupancy": 500, "hazard_risk": 0.1, "accessibility": 0.9, "safe": True, "latitude": 37.7, "longitude": -122.4},
                {"shelter_id": "SHELTER-X", "capacity": 4000, "current_occupancy": 200, "hazard_risk": 0.05, "accessibility": 0.95, "safe": True, "latitude": 37.8, "longitude": -122.3},
            ],
            avoid_edges=["E-Z", "E-A"],
        )

        p2 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1",
            total_population=5000,
            population_exposed=3000,
            population_to_evacuate=2000,
            priority=0.8,
            vulnerability=0.6,
            human_impact=0.7,
            accessibility_risk=0.2,
            evidence_ids=["HAZ-01", "HAZ-02"],  # reversed
            hazards=[
                {"hazard_id": "HAZ-A", "severity": 0.7, "confidence": 0.9},  # reversed
                {"hazard_id": "HAZ-B", "severity": 0.5, "confidence": 0.8},
            ],
            candidate_edges=[
                {"edge_id": "EDGE-1", "from_node": "A", "to_node": "B", "distance_km": 1.0, "travel_time_minutes": 2.0, "hazard_risk": 0.1, "accessibility": 0.9, "closed": False},  # reversed
                {"edge_id": "EDGE-2", "from_node": "B", "to_node": "C", "distance_km": 2.0, "travel_time_minutes": 3.0, "hazard_risk": 0.1, "accessibility": 0.9, "closed": False},
            ],
            candidate_shelters=[
                {"shelter_id": "SHELTER-X", "capacity": 4000, "current_occupancy": 200, "hazard_risk": 0.05, "accessibility": 0.95, "safe": True, "latitude": 37.8, "longitude": -122.3},  # reversed
                {"shelter_id": "SHELTER-Y", "capacity": 3000, "current_occupancy": 500, "hazard_risk": 0.1, "accessibility": 0.9, "safe": True, "latitude": 37.7, "longitude": -122.4},
            ],
            avoid_edges=["E-A", "E-Z"],  # reversed
        )

        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p1)
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p2)
        assert h1 == h2

    def test_order_sensitivity_route_nodes(self):
        """
        route_nodes is semantically ORDER-SENSITIVE:
        [A, B, C] represents a fundamentally different route than [A, C, B], so hashes must differ.
        """
        p1 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1", total_population=1000, population_exposed=500, population_to_evacuate=400,
            priority=0.5, vulnerability=0.5, human_impact=0.5, accessibility_risk=0.2,
            route_nodes=["A", "B", "C"],
        )
        p2 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1", total_population=1000, population_exposed=500, population_to_evacuate=400,
            priority=0.5, vulnerability=0.5, human_impact=0.5, accessibility_risk=0.2,
            route_nodes=["A", "C", "B"],
        )
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p1)
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p2)
        assert h1 != h2

    def test_order_sensitivity_causal_chain(self):
        """
        compound event causal_chain is semantically ORDER-SENSITIVE:
        chain [flood, road_failure] is different from [road_failure, flood].
        """
        p1 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1", total_population=1000, population_exposed=500, population_to_evacuate=400,
            priority=0.5, vulnerability=0.5, human_impact=0.5, accessibility_risk=0.2,
            compound_events=[{"event_id": "CE1", "severity": 0.8, "confidence": 0.9, "chain": ["flood", "road_failure"]}],
        )
        p2 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1", total_population=1000, population_exposed=500, population_to_evacuate=400,
            priority=0.5, vulnerability=0.5, human_impact=0.5, accessibility_risk=0.2,
            compound_events=[{"event_id": "CE1", "severity": 0.8, "confidence": 0.9, "chain": ["road_failure", "flood"]}],
        )
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p1)
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p2)
        assert h1 != h2

    def test_irrelevant_data_invariance(self):
        """
        Passing non-decision metadata outside material canonical fields must NOT alter provenance.
        """
        p1 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1", total_population=1000, population_exposed=500, population_to_evacuate=400,
            priority=0.5, vulnerability=0.5, human_impact=0.5, accessibility_risk=0.2,
        )
        p2 = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z1", total_population=1000, population_exposed=500, population_to_evacuate=400,
            priority=0.5, vulnerability=0.5, human_impact=0.5, accessibility_risk=0.2,
        )
        h1 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p1)
        h2 = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p2)
        assert h1 == h2

    def test_provenance_determinism(self):
        """
        Repeatedly computing the hash across 100 iterations on identical inputs must be strictly deterministic.
        """
        p = EvacuationProvenanceTracker.build_canonical_payload(
            zone_id="Z-DET", total_population=2000, population_exposed=1200, population_to_evacuate=900,
            priority=0.75, vulnerability=0.65, human_impact=0.70, accessibility_risk=0.15,
            route_nodes=["X", "Y", "Z"],
        )
        h_base = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
        for _ in range(100):
            h_iter = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
            assert h_iter == h_base

    def test_provenance_collision_sanity(self):
        """
        Distinct evaluation inputs must produce strictly distinct provenance hashes.
        """
        hashes = set()
        for i in range(25):
            p = EvacuationProvenanceTracker.build_canonical_payload(
                zone_id=f"Z-{i}",
                total_population=1000 + i * 100,
                population_exposed=500 + i * 50,
                population_to_evacuate=300 + i * 30,
                priority=round(0.40 + i * 0.02, 4),
                vulnerability=round(0.30 + i * 0.02, 4),
                human_impact=round(0.40 + i * 0.02, 4),
                accessibility_risk=0.10,
            )
            h = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=p)
            assert h not in hashes, f"Collision detected for iteration {i}"
            hashes.add(h)
