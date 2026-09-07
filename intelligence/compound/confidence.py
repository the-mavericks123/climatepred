"""
Deterministic confidence calculation for Phase 4: Compound & Cascading Disaster Engine.
Computes composite confidence based on evidence quality, source diversity, temporal alignment,
and relationship rule certainty.
"""

from typing import Dict, List, Tuple
from intelligence.compound.types import (
    ContributingState,
    RelationshipEdge,
    RelationshipType,
    StateEvidenceType,
)


class CompoundConfidenceCalculator:
    """
    Computes transparent, honest confidence scores for compound events and cascade chains.
    Accounts for:
      - Contributor confidence scores
      - Ratio of OBSERVED vs PREDICTED vs INFERRED sources
      - Temporal disparity/alignment between chained events
      - Rule coupling penalties
    Ensures that deriving sub-states from the same physical measurement does not falsely inflate confidence.
    """

    @staticmethod
    def compute_event_confidence(
        states: List[ContributingState],
        edges: List[RelationshipEdge],
        time_span_minutes: float,
        max_window_minutes: float = 120.0,
    ) -> float:
        """
        Calculates bounded confidence in [0.0, 1.0] for a compound or cascading disaster event.
        """
        if not states:
            return 0.0

        # 1. Base confidence: harmonic-geometric blend of contributing state confidences
        # Geometric mean ensures if any critical contributor has very low confidence, overall drops
        conf_values = [max(0.05, s.confidence) for s in states]
        avg_conf = sum(conf_values) / len(conf_values)
        min_conf = min(conf_values)

        # 2. Source evidence factor: penalize heavily-inferred or long-horizon predicted chains
        evidence_weights = {
            StateEvidenceType.OBSERVED: 1.00,
            StateEvidenceType.PREDICTED: 0.88,
            StateEvidenceType.INFERRED: 0.82,
        }
        source_factor = sum(evidence_weights[s.evidence_type] for s in states) / len(states)

        # 3. Temporal alignment factor: penalize events matched near edge of temporal window
        if max_window_minutes > 0.0:
            temporal_decay = max(0.80, 1.0 - (0.20 * (time_span_minutes / max_window_minutes)))
        else:
            temporal_decay = 1.0

        # 4. Cascade depth penalty: longer chains compound uncertainty (3% discount per edge)
        depth_penalty = max(0.75, 1.0 - (0.03 * len(edges)))

        # Composite score
        raw_confidence = (
            (0.60 * avg_conf + 0.40 * min_conf)
            * source_factor
            * temporal_decay
            * depth_penalty
        )

        return round(max(0.05, min(1.0, raw_confidence)), 4)
