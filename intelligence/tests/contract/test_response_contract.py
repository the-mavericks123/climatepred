"""
Phase 9 Contract Tests: Schema validation and invariants for Response Planner.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from intelligence.response.types import (
    ActionItem,
    ActionStatus,
    ActionType,
    AlertLevel,
    EvidenceReference,
    EvidenceType,
    ResponsePlan,
    ResponsePlanResponse,
    SituationContext,
    UrgencyLevel,
)


def test_evidence_reference_valid():
    ref = EvidenceReference(
        type="hazard",
        id="HAZ-FLOOD-001",
        evidence_type=EvidenceType.OBSERVED,
        severity=0.85,
        confidence=0.92,
        description="Severe riverine flood",
    )
    assert ref.id == "HAZ-FLOOD-001"
    assert ref.evidence_type == EvidenceType.OBSERVED
    assert ref.severity == 0.85


def test_evidence_reference_invalid_severity():
    with pytest.raises(ValidationError):
        EvidenceReference(type="hazard", id="HAZ-1", severity=1.5)


def test_action_item_valid():
    act = ActionItem(
        action_id="ACT-001",
        action=ActionType.EVACUATE_ZONE,
        target="ZONE-C",
        priority=1,
        priority_score=0.92,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.88,
        confidence=0.90,
        reason="High flood severity threatening residential sector.",
        evidence=[EvidenceReference(type="hazard", id="HAZ-001", severity=0.9)],
        status=ActionStatus.RECOMMENDED,
        requires_human_review=True,
        review_reason="Mandatory incident commander authorization.",
        temporal_category=EvidenceType.OBSERVED,
        simulated=False,
    )
    assert act.action == ActionType.EVACUATE_ZONE
    assert act.priority == 1
    assert act.urgency == UrgencyLevel.CRITICAL


def test_action_item_invalid_priority():
    with pytest.raises(ValidationError):
        ActionItem(
            action_id="ACT-001",
            action=ActionType.MONITOR,
            target="ZONE-A",
            priority=0,  # Invalid: priority must be >= 1
            priority_score=0.1,
            urgency=UrgencyLevel.LOW,
            urgency_score=0.1,
            confidence=0.9,
            reason="Test",
        )


def test_response_plan_schema():
    plan = ResponsePlan(
        plan_id="PLAN-TEST-001",
        generated_at=datetime.now(timezone.utc),
        alert_level=AlertLevel.RED,
        situation=SituationContext(
            observed_hazards=[{"hazard_type": "flood", "severity": 0.9}],
            is_stale=False,
        ),
        actions=[
            ActionItem(
                action_id="ACT-001",
                action=ActionType.EVACUATE_ZONE,
                target="ZONE-A",
                priority=1,
                priority_score=0.95,
                urgency=UrgencyLevel.CRITICAL,
                urgency_score=0.90,
                confidence=0.92,
                reason="Severe flood impact",
                status=ActionStatus.RECOMMENDED,
                requires_human_review=True,
            )
        ],
        warnings=["CRITICAL_ALERT"],
        provenance_hash="abc1234567890",
        simulated=False,
        model_version="response-v1",
        action_count=1,
        critical_action_count=1,
        requires_operator_review_count=1,
    )
    assert plan.alert_level == AlertLevel.RED
    assert len(plan.actions) == 1
    assert plan.simulated is False


def test_response_plan_response_envelope():
    plan = ResponsePlan(
        plan_id="PLAN-TEST-002",
        generated_at=datetime.now(timezone.utc),
        alert_level=AlertLevel.GREEN,
        situation=SituationContext(),
        actions=[],
        warnings=[],
        provenance_hash="hash000",
        simulated=False,
    )
    resp = ResponsePlanResponse(
        success=True,
        plan=plan,
        request_id="REQ-TEST",
    )
    assert resp.success is True
    assert resp.request_id == "REQ-TEST"
    assert resp.plan.alert_level == AlertLevel.GREEN


def test_simulated_contract_labeling():
    plan = ResponsePlan(
        plan_id="PLAN-SIM-001",
        generated_at=datetime.now(timezone.utc),
        alert_level=AlertLevel.ORANGE,
        situation=SituationContext(),
        actions=[
            ActionItem(
                action_id="ACT-SIM-001",
                action=ActionType.PREPARE_EVACUATION,
                target="ZONE-B",
                priority=1,
                priority_score=0.75,
                urgency=UrgencyLevel.HIGH,
                urgency_score=0.70,
                confidence=0.85,
                reason="SIMULATED: Scenario surge",
                temporal_category=EvidenceType.SIMULATED,
                simulated=True,
            )
        ],
        warnings=["SIMULATED_SCENARIO"],
        provenance_hash="simhash123",
        simulated=True,
    )
    assert plan.simulated is True
    assert plan.actions[0].simulated is True
    assert plan.actions[0].temporal_category == EvidenceType.SIMULATED
