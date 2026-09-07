"""
Unit tests for Phase 9 Response Conflict Resolution.
Verifies that conflicting actions are detected, resolved using authoritative upstream state,
and explicitly marked BLOCKED, SUPERSEDED, or CONDITIONAL without silent drops.
"""

from intelligence.response.planner import ResponsePlanner
from intelligence.response.types import (
    ActionItem,
    ActionStatus,
    ActionType,
    UrgencyLevel,
)


def test_conflict_routing_over_closed_edge_is_blocked():
    planner = ResponsePlanner(edge_accessibility_threshold=0.40)
    edges = [{"edge_id": "ROAD-COLLAPSED", "closed": True, "accessibility": 0.0}]
    shelters = []

    action = ActionItem(
        action_id="ACT-001",
        action=ActionType.EVACUATE_ZONE,
        target="ROAD-COLLAPSED",
        priority=1,
        priority_score=0.85,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.85,
        confidence=0.90,
        reason="Route passes through collapsed road",
        status=ActionStatus.RECOMMENDED,
    )

    resolved = planner.resolve_conflicts([action], road_edges=edges, shelters=shelters)
    assert len(resolved) == 1
    assert resolved[0].status == ActionStatus.BLOCKED
    assert "CONFLICT-CLOSED-EDGE-ROAD-COLLAPSED" in resolved[0].conflict_ids
    assert resolved[0].requires_human_review is True


def test_conflict_evacuation_to_unsafe_shelter_is_blocked():
    planner = ResponsePlanner()
    edges = []
    shelters = [{"shelter_id": "SHELTER-FLOODED", "safe": False, "hazard_risk": 0.85}]

    action = ActionItem(
        action_id="ACT-002",
        action=ActionType.EVACUATE_ZONE,
        target="SHELTER-FLOODED",
        priority=1,
        priority_score=0.80,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.80,
        confidence=0.90,
        reason="Evacuate to flooded shelter",
        status=ActionStatus.RECOMMENDED,
    )

    resolved = planner.resolve_conflicts([action], road_edges=edges, shelters=shelters)
    assert len(resolved) == 1
    assert resolved[0].status == ActionStatus.BLOCKED
    assert "CONFLICT-UNSAFE-SHELTER-SHELTER-FLOODED" in resolved[0].conflict_ids
    assert resolved[0].requires_human_review is True


def test_conflict_evacuation_to_exhausted_shelter_is_conditional():
    planner = ResponsePlanner()
    edges = []
    shelters = [{"shelter_id": "SHELTER-FULL", "safe": True, "capacity": 1000, "current_occupancy": 1000}]

    action = ActionItem(
        action_id="ACT-003",
        action=ActionType.EVACUATE_ZONE,
        target="SHELTER-FULL",
        priority=1,
        priority_score=0.75,
        urgency=UrgencyLevel.HIGH,
        urgency_score=0.70,
        confidence=0.90,
        reason="Evacuate to full shelter",
        status=ActionStatus.RECOMMENDED,
    )

    resolved = planner.resolve_conflicts([action], road_edges=edges, shelters=shelters)
    assert len(resolved) == 1
    assert resolved[0].status == ActionStatus.CONDITIONAL
    assert "CONFLICT-EXHAUSTED-SHELTER-SHELTER-FULL" in resolved[0].conflict_ids


def test_conflict_evacuate_zone_supersedes_monitoring_for_same_target():
    planner = ResponsePlanner()
    act_monitor = ActionItem(
        action_id="ACT-MON-1",
        action=ActionType.MAINTAIN_MONITORING,
        target="ZONE-A",
        priority=2,
        priority_score=0.20,
        urgency=UrgencyLevel.LOW,
        urgency_score=0.20,
        confidence=0.90,
        reason="Routine monitoring",
        status=ActionStatus.RECOMMENDED,
    )
    act_evac = ActionItem(
        action_id="ACT-EVAC-1",
        action=ActionType.EVACUATE_ZONE,
        target="ZONE-A",
        priority=1,
        priority_score=0.95,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.90,
        confidence=0.95,
        reason="Critical flood evacuation",
        status=ActionStatus.RECOMMENDED,
    )

    resolved = planner.resolve_conflicts([act_monitor, act_evac], road_edges=[], shelters=[])

    evac_item = next(a for a in resolved if a.action_id == "ACT-EVAC-1")
    mon_item = next(a for a in resolved if a.action_id == "ACT-MON-1")

    assert evac_item.status == ActionStatus.RECOMMENDED
    assert mon_item.status == ActionStatus.SUPERSEDED
    assert "SUPERSEDED-BY-EVAC-ZONE-A" in mon_item.conflict_ids


def test_conflict_close_road_action_itself_not_blocked():
    planner = ResponsePlanner(edge_accessibility_threshold=0.40)
    edges = [{"edge_id": "ROAD-BAD", "closed": True, "accessibility": 0.0}]

    close_action = ActionItem(
        action_id="ACT-CLOSE-1",
        action=ActionType.CLOSE_ROAD,
        target="ROAD-BAD",
        priority=1,
        priority_score=0.85,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.85,
        confidence=0.95,
        reason="Close degraded road",
        status=ActionStatus.RECOMMENDED,
    )

    resolved = planner.resolve_conflicts([close_action], road_edges=edges, shelters=[])
    assert len(resolved) == 1
    # CLOSE_ROAD targeting the closed road should be RECOMMENDED, not BLOCKED!
    assert resolved[0].status == ActionStatus.RECOMMENDED


def test_conflict_redirect_evacuation_from_unsafe_shelter_not_blocked():
    planner = ResponsePlanner()
    shelters = [{"shelter_id": "SHELTER-UNSAFE", "safe": False, "hazard_risk": 0.9}]

    redirect_action = ActionItem(
        action_id="ACT-REDIR-1",
        action=ActionType.REDIRECT_EVACUATION,
        target="SHELTER-UNSAFE",
        priority=1,
        priority_score=0.85,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.85,
        confidence=0.95,
        reason="Redirect evacuees away from unsafe shelter",
        status=ActionStatus.RECOMMENDED,
    )

    resolved = planner.resolve_conflicts([redirect_action], road_edges=[], shelters=shelters)
    assert len(resolved) == 1
    assert resolved[0].status == ActionStatus.RECOMMENDED
