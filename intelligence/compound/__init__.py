"""
Phase 4: Compound & Cascading Disaster Intelligence Module.
Exports data models, relationship rules, cascade graph, and evaluation engine.
"""

from intelligence.compound.types import (
    RelationshipType,
    StateEvidenceType,
    ContributingState,
    RelationshipEdge,
    CompoundEvent,
    CompoundEvaluationRequest,
    CompoundEvaluationResponse,
)
from intelligence.compound.rules import (
    CompoundRuleConfig,
    DEFAULT_COMPOUND_CONFIG,
    CANONICAL_RULES,
)
from intelligence.compound.graph import CascadeGraph
from intelligence.compound.features import StateFeatureExtractor
from intelligence.compound.confidence import CompoundConfidenceCalculator
from intelligence.compound.engine import CompoundDisasterEngine

__all__ = [
    "RelationshipType",
    "StateEvidenceType",
    "ContributingState",
    "RelationshipEdge",
    "CompoundEvent",
    "CompoundEvaluationRequest",
    "CompoundEvaluationResponse",
    "CompoundRuleConfig",
    "DEFAULT_COMPOUND_CONFIG",
    "CANONICAL_RULES",
    "CascadeGraph",
    "StateFeatureExtractor",
    "CompoundConfidenceCalculator",
    "CompoundDisasterEngine",
]
