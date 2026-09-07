"""
Phase 10 Explainability Package.
Provides deterministic explanation contracts, factor attribution, structured reasoning,
and counterfactual analysis across all Climate Eye View models.
"""

from intelligence.explainability.types import (
    CounterfactualItem,
    EpistemicClassification,
    EvidenceReference,
    ExplanationContract,
    ExplanationLevel,
    ExplanationRequest,
    FactorAttribution,
    TargetType,
    UncertaintyItem,
)
from intelligence.explainability.engine import ExplainabilityEngine
from intelligence.explainability.provenance import ExplanationProvenanceTracker

__all__ = [
    "ExplainabilityEngine",
    "ExplanationContract",
    "ExplanationRequest",
    "ExplanationLevel",
    "TargetType",
    "EpistemicClassification",
    "FactorAttribution",
    "EvidenceReference",
    "UncertaintyItem",
    "CounterfactualItem",
    "ExplanationProvenanceTracker",
]
