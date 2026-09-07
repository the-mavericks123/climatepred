"""
Unit tests for Phase 9 Response Rules.
Verifies candidate action generation across all hazard types, predictions,
cascades, demographic vulnerabilities, infrastructure anomalies, and baseline states.
"""

from intelligence.response.evidence import build_evidence_registry_from_upstream
from intelligence.response.rules import ResponseRuleEngine
from intelligence.response.types import (
    ActionStatus,
    ActionType,
    EvidenceType,
    UrgencyLevel,
)


def test_baseline_normal_generates_monitoring():
    engine = ResponseRuleEngine()
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )
    assert len(actions) == 1
    assert actions[0].action == ActionType.MAINTAIN_MONITORING
    assert actions[0].urgency == UrgencyLevel.LOW
    assert actions[0].status == ActionStatus.RECOMMENDED


def test_critical_flood_generates_evacuate_zone():
    engine = ResponseRuleEngine()
    hazards = [{"hazard_id": "HAZ-FLOOD-1", "hazard_type": "flood", "severity": 0.90, "confidence": 0.95}]
    vuln_zones = [{"zone_id": "ZONE-A", "human_impact": 0.85, "vulnerability": 0.75, "population_exposed": 10000}]
    evac_recs = [{"evacuation_id": "EVAC-A-1", "zone_id": "ZONE-A", "status": "RECOMMENDED", "priority": 0.9}]

    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vuln_zones,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
    )

    actions = engine.generate_candidate_actions(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vuln_zones,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    evac_action = next((a for a in actions if a.action == ActionType.EVACUATE_ZONE), None)
    assert evac_action is not None
    assert evac_action.target == "ZONE-A"
    assert evac_action.urgency == UrgencyLevel.CRITICAL
    assert evac_action.requires_human_review is True
    assert "commander sign-off" in evac_action.review_reason.lower()


def test_predicted_flood_generates_prepare_evacuation_with_predicted_label():
    engine = ResponseRuleEngine()
    preds = [{
        "prediction_id": "PRED-FLOOD-60M",
        "hazard": "flood",
        "severity": 0.85,
        "forecast_horizon_minutes": 60,
        "confidence": 0.88,
    }]
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=preds,
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=preds,
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    pred_action = next((a for a in actions if a.action == ActionType.PREPARE_EVACUATION), None)
    assert pred_action is not None
    assert pred_action.temporal_category == EvidenceType.PREDICTED
    assert pred_action.forecast_horizon_minutes == 60
    assert "PREDICTED:" in pred_action.reason
    assert "+60 min" in pred_action.reason


def test_no_route_generates_field_verification_and_reassess():
    engine = ResponseRuleEngine()
    hazards = [{"hazard_id": "HAZ-F1", "hazard_type": "flood", "severity": 0.95}]
    vuln_zones = [{"zone_id": "ZONE-ISOLATED", "human_impact": 0.90, "vulnerability": 0.80, "population_exposed": 5000}]
    evac_recs = [{"evacuation_id": "EVAC-ISO-1", "zone_id": "ZONE-ISOLATED", "status": "NO_ROUTE"}]

    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vuln_zones,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vuln_zones,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    verify_action = next((a for a in actions if a.action == ActionType.REQUEST_FIELD_VERIFICATION), None)
    reassess_action = next((a for a in actions if a.action == ActionType.REASSESS), None)

    assert verify_action is not None
    assert reassess_action is not None
    assert verify_action.target == "ZONE-ISOLATED"
    assert verify_action.requires_human_review is True
    assert "no feasible ground evacuation route exists" in verify_action.review_reason.lower()


def test_vulnerable_population_prioritization():
    engine = ResponseRuleEngine()
    vuln_zones = [{
        "zone_id": "ZONE-ELDERLY",
        "human_impact": 0.70,
        "vulnerability": 0.85,
        "population_exposed": 3000,
    }]
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=vuln_zones,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=vuln_zones,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    vuln_act = next((a for a in actions if a.action == ActionType.PRIORITIZE_VULNERABLE_POPULATION), None)
    assert vuln_act is not None
    assert vuln_act.target == "ZONE-ELDERLY"
    assert "medical support" in vuln_act.reason.lower()


def test_closed_road_and_bridge_closure():
    engine = ResponseRuleEngine(edge_accessibility_threshold=0.40)
    edges = [
        {"edge_id": "ROAD-FLOODED", "closed": True, "accessibility": 0.0, "hazard_risk": 0.9},
        {"edge_id": "BRIDGE-SUSPECT", "closed": False, "accessibility": 0.30, "hazard_risk": 0.6},
    ]
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=edges,
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=edges,
        shelters=[],
        evidence_registry=registry,
    )

    road_act = next((a for a in actions if a.target == "ROAD-FLOODED"), None)
    bridge_act = next((a for a in actions if a.target == "BRIDGE-SUSPECT"), None)

    assert road_act is not None
    assert road_act.action == ActionType.CLOSE_ROAD
    assert bridge_act is not None
    assert bridge_act.action == ActionType.CLOSE_BRIDGE


def test_unsafe_shelter_redirects_evacuation():
    engine = ResponseRuleEngine()
    shelters = [
        {"shelter_id": "SHELTER-HAZARD", "safe": False, "hazard_risk": 0.75, "capacity": 5000, "current_occupancy": 0}
    ]
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=shelters,
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=shelters,
        evidence_registry=registry,
    )

    shelter_act = next((a for a in actions if a.target == "SHELTER-HAZARD"), None)
    assert shelter_act is not None
    assert shelter_act.action == ActionType.REDIRECT_EVACUATION
    assert shelter_act.requires_human_review is True
    assert "DO NOT allocate" in shelter_act.reason


def test_exhausted_shelter_generates_open_shelter():
    engine = ResponseRuleEngine()
    shelters = [
        {"shelter_id": "SHELTER-FULL", "safe": True, "hazard_risk": 0.05, "capacity": 5000, "current_occupancy": 4950}
    ]
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=shelters,
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=shelters,
        evidence_registry=registry,
    )

    open_act = next((a for a in actions if a.target == "SHELTER-FULL"), None)
    assert open_act is not None
    assert open_act.action == ActionType.OPEN_SHELTER


def test_compound_cascade_references_causal_chain():
    engine = ResponseRuleEngine()
    compounds = [{
        "event_id": "COMP-CASCADE-01",
        "severity": 0.88,
        "causal_chain": ["heavy_rain", "soil_saturation", "flood", "road_failure", "access_loss"],
        "confidence": 0.85,
    }]
    registry = build_evidence_registry_from_upstream(
        hazards=[],
        predictions=[],
        compound_events=compounds,
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=[],
        predictions=[],
        compound_events=compounds,
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    cascade_act = next((a for a in actions if a.action == ActionType.PREPOSITION_RESPONSE_RESOURCES), None)
    assert cascade_act is not None
    assert "heavy_rain -> soil_saturation -> flood" in cascade_act.reason


def test_heat_and_drought_response_rules():
    engine = ResponseRuleEngine()
    hazards = [
        {"hazard_id": "HAZ-HEAT-CRIT", "hazard_type": "heat", "severity": 0.88},
        {"hazard_id": "HAZ-DROUGHT-CRIT", "hazard_type": "drought", "severity": 0.82},
    ]
    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )
    actions = engine.generate_candidate_actions(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    heat_act = next((a for a in actions if a.action == ActionType.PROTECT_CRITICAL_FACILITY), None)
    drought_act = next((a for a in actions if a.target == "WATER-RESERVES"), None)

    assert heat_act is not None
    assert drought_act is not None
    assert "cooling centers" in heat_act.reason.lower()
    assert "water tankers" in drought_act.reason.lower()
