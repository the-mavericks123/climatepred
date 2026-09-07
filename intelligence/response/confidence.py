"""
Climate Eye View — Phase 9 Response Planner Confidence Engine.

Calculates aggregated confidence scores derived from upstream evidence confidences,
data freshness, missing inputs, and model agreement.
"""

from typing import List, Tuple
from intelligence.response.types import EvidenceReference


def calculate_action_confidence(
    evidence_refs: List[EvidenceReference],
    is_stale: bool = False,
    stale_penalty: float = 0.35,
    missing_evidence: bool = False,
    missing_penalty: float = 0.25,
) -> Tuple[float, List[str]]:
    """
    Computes aggregated confidence for a response action based on the confidence
    of its supporting evidence items and operational data quality factors.

    Formula:
        mean_upstream_conf = (1/N) * sum(evidence.confidence)
        if is_stale:
            conf = conf * (1.0 - stale_penalty)
        if missing_evidence:
            conf = conf * (1.0 - missing_penalty)
        conf = clamp(conf, 0.05, 1.0)
    """
    warnings: List[str] = []

    confidences = [ref.confidence for ref in evidence_refs if ref.confidence is not None]

    if confidences:
        base_confidence = sum(confidences) / len(confidences)
    else:
        base_confidence = 0.80  # Default nominal confidence if evidence has no explicit score

    aggregated = base_confidence

    if is_stale:
        aggregated *= (1.0 - stale_penalty)
        warnings.append("STALE_DATA")

    if missing_evidence:
        aggregated *= (1.0 - missing_penalty)
        warnings.append("MISSING_EVIDENCE")

    final_confidence = round(min(1.0, max(0.05, aggregated)), 4)

    if final_confidence < 0.50:
        warnings.append("LOW_CONFIDENCE")

    return final_confidence, warnings


def calculate_plan_overall_confidence(
    hazard_confidences: List[float],
    prediction_confidences: List[float],
    compound_confidences: List[float],
    vulnerability_confidences: List[float],
    evacuation_confidences: List[float],
    is_stale: bool = False,
    stale_penalty: float = 0.35,
) -> Tuple[float, List[str]]:
    """
    Calculates the overall plan-level confidence across all upstream subsystem domains.
    """
    warnings: List[str] = []
    category_means: List[float] = []

    for conf_list in [
        hazard_confidences,
        prediction_confidences,
        compound_confidences,
        vulnerability_confidences,
        evacuation_confidences,
    ]:
        if conf_list:
            category_means.append(sum(conf_list) / len(conf_list))

    if category_means:
        overall = sum(category_means) / len(category_means)
    else:
        overall = 0.85

    if is_stale:
        overall *= (1.0 - stale_penalty)
        warnings.append("STALE_DATA")

    final_plan_conf = round(min(1.0, max(0.05, overall)), 4)
    if final_plan_conf < 0.50:
        warnings.append("LOW_CONFIDENCE")

    return final_plan_conf, warnings
