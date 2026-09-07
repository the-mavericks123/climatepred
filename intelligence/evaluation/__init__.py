"""
Phase 10 Evaluation Package.
Provides dataset management, empirical metrics, domain benchmarks, model comparisons,
and data drift diagnostics.
"""

from intelligence.evaluation.types import (
    ConfusionMatrix,
    DatasetType,
    DriftEvaluateRequest,
    DriftReport,
    EvaluationDataset,
    EvaluationMetrics,
    EvaluationObservation,
    EvaluationReport,
    EvaluationRunRequest,
    GroundTruthRecord,
    GroundTruthStatus,
    ModelCompareRequest,
    ModelComparisonReport,
)
from intelligence.evaluation.engine import EvaluationEngine
from intelligence.evaluation.provenance import EvaluationProvenanceTracker
from intelligence.evaluation.metrics import MetricsCalculator
from intelligence.evaluation.drift import DriftDetector
from intelligence.evaluation.datasets import DatasetRegistry

__all__ = [
    "EvaluationEngine",
    "EvaluationDataset",
    "EvaluationObservation",
    "GroundTruthRecord",
    "EvaluationMetrics",
    "EvaluationReport",
    "ModelComparisonReport",
    "DriftReport",
    "DatasetType",
    "GroundTruthStatus",
    "ConfusionMatrix",
    "EvaluationRunRequest",
    "ModelCompareRequest",
    "DriftEvaluateRequest",
    "EvaluationProvenanceTracker",
    "MetricsCalculator",
    "DriftDetector",
    "DatasetRegistry",
]
