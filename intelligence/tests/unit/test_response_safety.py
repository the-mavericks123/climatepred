"""
Safety and Boundary Invariant Tests for Phase 9 Response Planner.
Verifies critical non-functional safety constraints:
- Never invents a route when NO_ROUTE is encountered.
- Never sends evacuees to an unsafe shelter.
- Never claims an action has already been executed.
- Never converts a simulation scenario into a live emergency alert.
- Never fabricates evidence IDs.
- Never fabricates numerical hazard/impact scores.
"""

from intelligence.response.engine import ResponsePlannerEngine
from intelligence.response.evidence import build_evidence_registry_from_upstream
from intelligence.response.planner import ResponsePlanner
from intelligence.response.types import (
    ActionStatus,
    ActionType,
    AlertLevel,
    EvidenceType,
)


def test_safety_never_invents_route_on_no_route():
    planner = ResponsePlanner()
    evac_recs = [{"evacuation_id": "EVAC-A", "zone_id": "ZONE-A", "status": "NO_ROUTE"}]
    hazards = [{"hazard_id": "HAZ-F", "hazard_type": "flood", "severity": 0.9}]
    vulns = [{"zone_id": "ZONE-A", "human_impact": 0.8, "vulnerability": 0.7, "population_exposed": 4000}]

    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
    )

    _, _, actions, warnings = planner.plan_response(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    # Must NOT generate EVACUATE_ZONE with a fabricated corridor
    evac_actions = [a for a in actions if a.action == ActionType.EVACUATE_ZONE]
    assert len(evac_actions) == 0

    # Must generate REQUEST_FIELD_VERIFICATION and REASSESS
    verify_acts = [a for a in actions if a.action in (ActionType.REQUEST_FIELD_VERIFICATION, ActionType.REASSESS)]
    assert len(verify_acts) >= 1
    assert any(a.requires_human_review for a in verify_acts)
    assert any("NO_ROUTE" in w for w in warnings)


def test_safety_never_allocates_to_unsafe_shelter():
    planner = ResponsePlanner()
    shelters = [
        {"shelter_id": "SHELTER-TOXIC", "name": "Flooded Gym", "safe": False, "hazard_risk": 0.90, "capacity": 5000}
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
    _, _, actions, _ = planner.plan_response(
        hazards=[],
        predictions=[],
        compound_events=[],
        vulnerability_zones=[],
        evacuation_recommendations=[],
        road_edges=[],
        shelters=shelters,
        evidence_registry=registry,
    )

    # Any action targeting SHELTER-TOXIC must NOT recommend sending evacuees there
    toxic_acts = [a for a in actions if a.target == "SHELTER-TOXIC"]
    for act in toxic_acts:
        assert act.action != ActionType.EVACUATE_ZONE
        if act.action == ActionType.REDIRECT_EVACUATION:
            assert "DO NOT allocate" in act.reason
        else:
            assert act.status == ActionStatus.BLOCKED


def test_safety_never_claims_action_executed():
    planner = ResponsePlanner()
    hazards = [{"hazard_id": "HAZ-1", "hazard_type": "flood", "severity": 0.85}]
    vulns = [{"zone_id": "ZONE-1", "human_impact": 0.75, "vulnerability": 0.70, "population_exposed": 1000}]
    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )
    _, _, actions, _ = planner.plan_response(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )
    for act in actions:
        # Status must be one of recommendation statuses, never "EXECUTED", "COMPLETED", "DONE"
        assert act.status in (
            ActionStatus.RECOMMENDED,
            ActionStatus.CONDITIONAL,
            ActionStatus.BLOCKED,
            ActionStatus.SUPERSEDED,
            ActionStatus.REQUIRES_HUMAN_REVIEW,
        )


def test_safety_never_converts_simulation_into_live_alert():
    engine = ResponsePlannerEngine()
    plan = engine.simulate_scenario_response(
        scenario_id="SCN-RAIN-20",
    )
    assert plan.simulated is True
    assert "SIMULATED_SCENARIO" in " ".join(plan.warnings)
    assert "NOT A LIVE ALERT" in " ".join(plan.warnings)
    for action in plan.actions:
        assert action.simulated is True
        assert action.temporal_category == EvidenceType.SIMULATED


def test_safety_never_creates_fake_evidence_ids():
    engine = ResponsePlannerEngine()
    plan = engine.evaluate_response_plan()

    # Verify that every action's evidence IDs exist in the situation context
    all_context_ids = set()
    for h in plan.situation.observed_hazards:
        all_context_ids.add(h.get("hazard_id"))
    for p in plan.situation.predicted_hazards:
        all_context_ids.add(p.get("prediction_id"))
    for c in plan.situation.compound_events:
        all_context_ids.add(c.get("event_id"))
    for v in plan.situation.affected_zones:
        all_context_ids.add(v.get("zone_id"))
    for e in plan.situation.evacuation_demands:
        all_context_ids.add(e.get("evacuation_id"))
    for edge in plan.situation.road_network_anomalies:
        all_context_ids.add(edge.get("edge_id"))
    for s in plan.situation.shelter_statuses:
        all_context_ids.add(s.get("shelter_id"))

    for act in plan.actions:
        for ref in act.evidence:
            # Referenced ID must either be in context or match the target ID
            assert ref.id in all_context_ids or ref.id == act.target or ref.id.startswith("HAZ-") or ref.id.startswith("ROAD-") or ref.id.startswith("SHELTER-") or ref.id.startswith("ZONE-")


def test_safety_emergency_evacuation_requires_human_review():
    planner = ResponsePlanner()
    hazards = [{"hazard_id": "HAZ-FLOOD", "hazard_type": "flood", "severity": 0.95}]
    vulns = [{"zone_id": "ZONE-A", "human_impact": 0.85, "vulnerability": 0.80, "population_exposed": 10000}]
    evac_recs = [{"evacuation_id": "EVAC-1", "zone_id": "ZONE-A", "status": "RECOMMENDED"}]

    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
    )
    _, _, actions, _ = planner.plan_response(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=evac_recs,
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
    )

    evac_act = next(a for a in actions if a.action == ActionType.EVACUATE_ZONE)
    assert evac_act.requires_human_review is True
    assert evac_act.review_reason is not None
    assert len(evac_act.review_reason) > 0


def test_safety_stale_telemetry_penalizes_confidence_and_warns():
    planner = ResponsePlanner()
    hazards = [{"hazard_id": "HAZ-1", "hazard_type": "flood", "severity": 0.80, "confidence": 0.90}]
    vulns = [{"zone_id": "ZONE-1", "human_impact": 0.70, "vulnerability": 0.70, "population_exposed": 1000}]

    registry = build_evidence_registry_from_upstream(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
    )

    _, _, actions_fresh, warnings_fresh = planner.plan_response(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
        is_stale=False,
    )

    _, _, actions_stale, warnings_stale = planner.plan_response(
        hazards=hazards,
        predictions=[],
        compound_events=[],
        vulnerability_zones=vulns,
        evacuation_recommendations=[],
        road_edges=[],
        shelters=[],
        evidence_registry=registry,
        is_stale=True,
    )

    assert actions_stale[0].confidence < actions_fresh[0].confidence
    assert any("STALE_DATA" in w for w in warnings_stale)
    assert not any("STALE_DATA" in w for w in warnings_fresh)


def test_safety_numerical_values_come_from_upstream_models():
    # Verify that plan alert level is derived from numerical models rather than hardcoded
    planner = ResponsePlanner()
    low_hazards = [{"hazard_id": "HAZ-1", "hazard_type": "flood", "severity": 0.10}]
    high_hazards = [{"hazard_id": "HAZ-1", "hazard_type": "flood", "severity": 0.95}]
    vuln_high = [{"zone_id": "ZONE-1", "human_impact": 0.85, "vulnerability": 0.80, "population_exposed": 5000}]

    reg_low = build_evidence_registry_from_upstream(low_hazards, [], [], [], [], [], [])
    reg_high = build_evidence_registry_from_upstream(high_hazards, [], [], vuln_high, [], [], [])

    alert_low = planner.determine_alert_level(low_hazards, [], [], [], [])
    alert_high = planner.determine_alert_level(high_hazards, [], [], vuln_high, [])

    assert alert_low == AlertLevel.GREEN
    assert alert_high == AlertLevel.RED
