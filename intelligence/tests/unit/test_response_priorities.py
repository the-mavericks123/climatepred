"""
Unit tests for Phase 9 Priority and Urgency Engine.
Verifies temporal discounting, multi-factor urgency scoring, priority scoring,
and rank ordering determinism.
"""

from intelligence.response.priorities import (
    calculate_priority_score,
    calculate_temporal_urgency_factor,
    calculate_urgency,
    rank_actions,
)
from intelligence.response.types import (
    ActionItem,
    ActionStatus,
    ActionType,
    EvidenceType,
    UrgencyLevel,
)


def test_temporal_urgency_discounting():
    # Observed should outrank predicted
    obs_factor = calculate_temporal_urgency_factor(EvidenceType.OBSERVED)
    pred_30 = calculate_temporal_urgency_factor(EvidenceType.PREDICTED, 30)
    pred_60 = calculate_temporal_urgency_factor(EvidenceType.PREDICTED, 60)
    pred_360 = calculate_temporal_urgency_factor(EvidenceType.PREDICTED, 360)
    sim_factor = calculate_temporal_urgency_factor(EvidenceType.SIMULATED, 30)

    assert obs_factor == 1.00
    assert pred_30 == 0.85
    assert pred_60 == 0.70
    assert pred_360 == 0.50
    assert sim_factor < pred_30
    assert obs_factor > pred_30 > pred_60 > pred_360


def test_urgency_calculation_critical():
    score, level = calculate_urgency(
        hazard_severity=0.95,
        human_impact=0.90,
        accessibility_risk=0.80,
        temporal_category=EvidenceType.OBSERVED,
    )
    assert score >= 0.80
    assert level == UrgencyLevel.CRITICAL


def test_urgency_calculation_levels():
    # Test level mapping boundaries
    # High: 0.60 - 0.79
    score_high, level_high = calculate_urgency(
        hazard_severity=0.70,
        human_impact=0.60,
        accessibility_risk=0.50,
        temporal_category=EvidenceType.OBSERVED,
    )
    assert 0.60 <= score_high < 0.80
    assert level_high == UrgencyLevel.HIGH

    # Low: < 0.40
    score_low, level_low = calculate_urgency(
        hazard_severity=0.20,
        human_impact=0.10,
        accessibility_risk=0.10,
        temporal_category=EvidenceType.OBSERVED,
    )
    assert score_low < 0.40
    assert level_low == UrgencyLevel.LOW


def test_priority_score_weighting():
    prio_high = calculate_priority_score(
        urgency_score=0.90,
        vulnerability=0.85,
        cascade_severity=0.80,
        confidence=0.95,
    )
    prio_low = calculate_priority_score(
        urgency_score=0.20,
        vulnerability=0.20,
        cascade_severity=0.10,
        confidence=0.90,
    )
    assert 0.0 <= prio_high <= 1.0
    assert 0.0 <= prio_low <= 1.0
    assert prio_high > prio_low


def test_rank_actions_ordering():
    act1 = ActionItem(
        action_id="ACT-001",
        action=ActionType.MONITOR,
        target="ZONE-A",
        priority=1,
        priority_score=0.30,
        urgency=UrgencyLevel.LOW,
        urgency_score=0.25,
        confidence=0.9,
        reason="Low priority",
    )
    act2 = ActionItem(
        action_id="ACT-002",
        action=ActionType.EVACUATE_ZONE,
        target="ZONE-B",
        priority=1,
        priority_score=0.95,
        urgency=UrgencyLevel.CRITICAL,
        urgency_score=0.90,
        confidence=0.9,
        reason="High priority",
    )
    act3 = ActionItem(
        action_id="ACT-003",
        action=ActionType.PREPARE_EVACUATION,
        target="ZONE-C",
        priority=1,
        priority_score=0.70,
        urgency=UrgencyLevel.HIGH,
        urgency_score=0.65,
        confidence=0.9,
        reason="Medium priority",
    )

    ranked = rank_actions([act1, act2, act3])

    assert ranked[0].action_id == "ACT-002"
    assert ranked[0].priority == 1
    assert ranked[1].action_id == "ACT-003"
    assert ranked[1].priority == 2
    assert ranked[2].action_id == "ACT-001"
    assert ranked[2].priority == 3


def test_rank_actions_deterministic_tiebreaking():
    # Identical priority_score and urgency_score -> sorted by action_id ascending
    act_b = ActionItem(
        action_id="ACT-BBB",
        action=ActionType.ISSUE_WARNING,
        target="ZONE-B",
        priority=1,
        priority_score=0.60,
        urgency=UrgencyLevel.MEDIUM,
        urgency_score=0.55,
        confidence=0.9,
        reason="Tie B",
    )
    act_a = ActionItem(
        action_id="ACT-AAA",
        action=ActionType.ISSUE_WARNING,
        target="ZONE-A",
        priority=1,
        priority_score=0.60,
        urgency=UrgencyLevel.MEDIUM,
        urgency_score=0.55,
        confidence=0.9,
        reason="Tie A",
    )

    ranked1 = rank_actions([act_b, act_a])
    ranked2 = rank_actions([act_a, act_b])

    assert ranked1[0].action_id == "ACT-AAA"
    assert ranked1[1].action_id == "ACT-BBB"
    assert ranked2[0].action_id == "ACT-AAA"
    assert ranked2[1].action_id == "ACT-BBB"


def test_priority_score_monotonicity():
    # Increasing vulnerability strictly increases priority_score
    p1 = calculate_priority_score(0.7, 0.4, 0.5, 0.9)
    p2 = calculate_priority_score(0.7, 0.8, 0.5, 0.9)
    assert p2 > p1


def test_urgency_score_monotonicity():
    # Increasing hazard strictly increases urgency_score
    u1, _ = calculate_urgency(0.3, 0.5, 0.2, EvidenceType.OBSERVED)
    u2, _ = calculate_urgency(0.9, 0.5, 0.2, EvidenceType.OBSERVED)
    assert u2 > u1
