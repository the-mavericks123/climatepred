"""
Deterministic confidence scoring for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Synthesizes hazard confidence, vulnerability certainty, road network reliability,
shelter metadata veracity, and forecast horizon discounting.
"""

from typing import Optional
from intelligence.evacuation.types import EvacuationRoute, Shelter
from intelligence.vulnerability.types import VulnerabilityZoneAssessment


class EvacuationConfidenceCalculator:
    """
    Computes an honest, data-grounded confidence score in [0.0, 1.0] for an evacuation recommendation.
    """

    @classmethod
    def calculate_confidence(
        cls,
        assessment: Optional[VulnerabilityZoneAssessment] = None,
        shelter: Optional[Shelter] = None,
        route: Optional[EvacuationRoute] = None,
        is_predicted: bool = False,
        has_cascade_disruption: bool = False,
    ) -> float:
        """
        Calculates composite evacuation directive confidence.
        """
        # 1. Base vulnerability / demand confidence
        vuln_conf = assessment.confidence if assessment else 0.85

        # 2. Shelter veracity factor
        if shelter is None:
            shelter_conf = 0.50
        elif shelter.simulated:
            shelter_conf = 0.80  # Synthetic / demo facility
        else:
            shelter_conf = 0.95  # Officially validated municipal emergency refuge

        # 3. Route network reliability
        if route is None:
            route_conf = 0.50
        else:
            # High accessibility and lower hazard along route yield higher confidence
            route_conf = 0.70 + (0.15 * route.accessibility) + (0.15 * (1.0 - route.hazard_exposure))

        # 4. Inferred cascade penalty
        cascade_penalty = 0.08 if has_cascade_disruption else 0.0

        # 5. Forecast horizon discounting (predictive evacuations carry higher epistemic uncertainty)
        horizon_discount = 0.90 if is_predicted else 1.00

        # Weighted geometric blending
        base = (vuln_conf ** 0.35) * (shelter_conf ** 0.30) * (route_conf ** 0.35)
        final_conf = (base - cascade_penalty) * horizon_discount

        return round(max(0.10, min(1.0, final_conf)), 4)
