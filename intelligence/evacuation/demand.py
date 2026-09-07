"""
Evacuation demand calculation and zone prioritization for Phase 6.
Translates Phase 5 Human Vulnerability & Impact assessments into deterministic evacuation need,
prioritization ranking, and exact population numbers to relocate.
"""

from typing import Dict, List, Optional
from intelligence.evacuation.types import EvacuationDemand
from intelligence.vulnerability.types import VulnerabilityZoneAssessment


class EvacuationDemandCalculator:
    """
    Computes deterministic evacuation demand and priority from Phase 5 vulnerability assessments.
    Guarantees:
      - Never invents population (population_to_evacuate <= population_exposed).
      - Applies transparent priority weights based on physical danger, vulnerability, and urgency.
      - Never fabricates subgroup census data.
    """

    DEFAULT_HUMAN_IMPACT_THRESHOLD = 0.50
    DEFAULT_HAZARD_RISK_THRESHOLD = 0.70

    # Canonical priority weights (sum = 1.0)
    PRIORITY_WEIGHTS = {
        "human_impact": 0.35,
        "vulnerability": 0.25,
        "hazard_risk": 0.20,
        "accessibility_risk": 0.10,
        "urgency": 0.10,
    }

    @classmethod
    def calculate_urgency(cls, forecast_horizon_minutes: int) -> float:
        """Derives urgency factor based on forecast horizon."""
        if forecast_horizon_minutes <= 0:
            return 1.00  # Imminent / current observed hazard
        elif forecast_horizon_minutes <= 30:
            return 0.85
        elif forecast_horizon_minutes <= 60:
            return 0.70
        else:
            return 0.50

    @classmethod
    def calculate_demand(
        cls,
        assessment: VulnerabilityZoneAssessment,
        human_impact_threshold: float = DEFAULT_HUMAN_IMPACT_THRESHOLD,
        hazard_risk_threshold: float = DEFAULT_HAZARD_RISK_THRESHOLD,
    ) -> EvacuationDemand:
        """
        Calculates whether evacuation is required and determines target population count and priority.
        """
        drivers: List[str] = []

        # 1. Determine necessity
        is_required = (
            assessment.human_impact >= human_impact_threshold
            or assessment.hazard_risk >= hazard_risk_threshold
        )

        if not is_required:
            drivers.append(
                f"Zone risk below evacuation threshold (human impact: {assessment.human_impact:.2f}, hazard: {assessment.hazard_risk:.2f})"
            )
            return EvacuationDemand(
                zone_id=assessment.zone_id,
                evacuation_required=False,
                population_exposed=assessment.population_exposed,
                population_to_evacuate=0,
                priority=0.0,
                human_impact=assessment.human_impact,
                vulnerability=assessment.vulnerability,
                hazard_risk=assessment.hazard_risk,
                accessibility_risk=assessment.accessibility_risk,
                urgency=0.0,
                drivers=drivers,
            )

        # 2. Compute urgency
        urgency = cls.calculate_urgency(assessment.forecast_horizon_minutes)

        # 3. Compute deterministic priority score
        w = cls.PRIORITY_WEIGHTS
        raw_priority = (
            w["human_impact"] * assessment.human_impact
            + w["vulnerability"] * assessment.vulnerability
            + w["hazard_risk"] * assessment.hazard_risk
            + w["accessibility_risk"] * assessment.accessibility_risk
            + w["urgency"] * urgency
        )
        priority = round(max(0.0, min(1.0, raw_priority)), 4)

        # 4. Determine population to evacuate
        # High priority evacuates 100% of exposed population; lower priority scales down from 60%
        scaling = min(1.0, 0.60 + (0.40 * priority))
        pop_to_evacuate = int(round(assessment.population_exposed * scaling))
        # Ensure hard bounds
        pop_to_evacuate = max(0, min(assessment.population_exposed, pop_to_evacuate))

        drivers.append(
            f"Evacuation required: {pop_to_evacuate:,} of {assessment.population_exposed:,} exposed residents"
        )
        drivers.append(f"Evacuation priority: {priority:.2f} (Urgency: {urgency:.2f})")
        if assessment.vulnerability >= 0.60:
            drivers.append(f"Prioritizing vulnerable population segment (vulnerability index: {assessment.vulnerability:.2f})")

        return EvacuationDemand(
            zone_id=assessment.zone_id,
            evacuation_required=True,
            population_exposed=assessment.population_exposed,
            population_to_evacuate=pop_to_evacuate,
            priority=priority,
            human_impact=assessment.human_impact,
            vulnerability=assessment.vulnerability,
            hazard_risk=assessment.hazard_risk,
            accessibility_risk=assessment.accessibility_risk,
            urgency=round(urgency, 4),
            drivers=drivers,
        )
