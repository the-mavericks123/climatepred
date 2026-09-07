"""
Climate Eye View — Phase 9 Response Planner Priority and Urgency Engine.

Provides deterministic priority scoring, multi-factor urgency classification,
temporal horizon discounting, and rank assignment.
"""

from typing import List, Tuple
from intelligence.response.types import (
    ActionItem,
    EvidenceType,
    UrgencyLevel,
)


def calculate_temporal_urgency_factor(
    temporal_category: EvidenceType,
    forecast_horizon_minutes: int | None = None,
) -> float:
    """
    Computes a deterministic temporal urgency factor [0.0, 1.0] based on whether
    the threat is observed live or forecasted for future arrival.
    
    Temporal weights:
    - OBSERVED: 1.00 (immediate current hazard)
    - PREDICTED (+30 min): 0.85 (rapid onset forecast requiring rapid preparation)
    - PREDICTED (+60 min): 0.70 (intermediate forecast)
    - PREDICTED (+360 min / 6 hr): 0.50 (extended horizon forecast)
    - INFERRED: 0.60 (cascade/indirect causal inference)
    - SIMULATED: discounted by 0.75 relative to baseline to reflect hypothetical nature
    """
    if temporal_category == EvidenceType.OBSERVED:
        return 1.00

    if temporal_category == EvidenceType.PREDICTED:
        if forecast_horizon_minutes is None or forecast_horizon_minutes <= 30:
            return 0.85
        elif forecast_horizon_minutes <= 60:
            return 0.70
        else:
            return 0.50

    if temporal_category == EvidenceType.INFERRED:
        return 0.60

    if temporal_category == EvidenceType.SIMULATED:
        if forecast_horizon_minutes is None or forecast_horizon_minutes <= 30:
            return 0.85 * 0.75
        elif forecast_horizon_minutes <= 60:
            return 0.70 * 0.75
        else:
            return 0.50 * 0.75

    return 0.50


def calculate_urgency(
    hazard_severity: float,
    human_impact: float,
    accessibility_risk: float,
    temporal_category: EvidenceType,
    forecast_horizon_minutes: int | None = None,
) -> Tuple[float, UrgencyLevel]:
    """
    Calculates numerical urgency score [0.0, 1.0] and categorizes into UrgencyLevel.

    Formula:
        urgency = clamp(
            0.35 * hazard_urgency +
            0.30 * human_impact_urgency +
            0.15 * accessibility_urgency +
            0.20 * temporal_urgency,
            0.0,
            1.0
        )
    """
    h_urg = min(1.0, max(0.0, float(hazard_severity)))
    i_urg = min(1.0, max(0.0, float(human_impact)))
    a_urg = min(1.0, max(0.0, float(accessibility_risk)))
    t_urg = calculate_temporal_urgency_factor(temporal_category, forecast_horizon_minutes)

    urgency_score = round(
        min(1.0, max(0.0, 0.35 * h_urg + 0.30 * i_urg + 0.15 * a_urg + 0.20 * t_urg)),
        4,
    )

    if urgency_score >= 0.80:
        level = UrgencyLevel.CRITICAL
    elif urgency_score >= 0.60:
        level = UrgencyLevel.HIGH
    elif urgency_score >= 0.40:
        level = UrgencyLevel.MEDIUM
    else:
        level = UrgencyLevel.LOW

    return urgency_score, level


def calculate_priority_score(
    urgency_score: float,
    vulnerability: float,
    cascade_severity: float,
    confidence: float,
) -> float:
    """
    Calculates deterministic composite priority score [0.0, 1.0].

    Formula:
        priority_score = clamp(
            0.40 * urgency_score +
            0.25 * vulnerability +
            0.20 * cascade_severity +
            0.15 * confidence,
            0.0,
            1.0
        )
    """
    u = min(1.0, max(0.0, float(urgency_score)))
    v = min(1.0, max(0.0, float(vulnerability)))
    c = min(1.0, max(0.0, float(cascade_severity)))
    conf = min(1.0, max(0.0, float(confidence)))

    priority_score = round(
        min(1.0, max(0.0, 0.40 * u + 0.25 * v + 0.20 * c + 0.15 * conf)),
        4,
    )
    return priority_score


def rank_actions(actions: List[ActionItem]) -> List[ActionItem]:
    """
    Sorts actions in descending order of priority_score, breaking ties deterministically
    by urgency_score descending and action_id ascending, then assigns 1-indexed priority ranks.
    """
    # Deterministic sorting key: (-priority_score, -urgency_score, action_id)
    sorted_actions = sorted(
        actions,
        key=lambda act: (-act.priority_score, -act.urgency_score, act.action_id),
    )

    ranked: List[ActionItem] = []
    for rank_idx, act in enumerate(sorted_actions, start=1):
        act_dict = act.model_dump()
        act_dict["priority"] = rank_idx
        ranked.append(ActionItem(**act_dict))

    return ranked
