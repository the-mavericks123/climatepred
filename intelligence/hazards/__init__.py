"""Hazards package for Climate Eye View (S2 Intelligence Service).

Provides deterministic current-state hazard detection and evaluation.
"""

from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardClassification,
    HazardResult,
    HazardEvaluationRequest,
    HazardEvaluationResponse,
)
from intelligence.hazards.base import BaseHazardModel
from intelligence.hazards.features import HazardFeatures, FeatureExtractor
from intelligence.hazards.quality_gate import HazardQualityGate, QualityGateVerdict
from intelligence.hazards.thresholds import (
    ClassificationThresholds,
    HeatModelConfig,
    FloodModelConfig,
    DroughtModelConfig,
    DEFAULT_CLASSIFICATION_THRESHOLDS,
    DEFAULT_HEAT_CONFIG,
    DEFAULT_FLOOD_CONFIG,
    DEFAULT_DROUGHT_CONFIG,
)
from intelligence.hazards.heat import HeatModel
from intelligence.hazards.flood import FloodModel
from intelligence.hazards.drought import DroughtModel
from intelligence.hazards.engine import HazardEngine

__all__ = [
    "HazardType",
    "HazardStatus",
    "HazardClassification",
    "HazardResult",
    "HazardEvaluationRequest",
    "HazardEvaluationResponse",
    "BaseHazardModel",
    "HazardFeatures",
    "FeatureExtractor",
    "HazardQualityGate",
    "QualityGateVerdict",
    "ClassificationThresholds",
    "HeatModelConfig",
    "FloodModelConfig",
    "DroughtModelConfig",
    "DEFAULT_CLASSIFICATION_THRESHOLDS",
    "DEFAULT_HEAT_CONFIG",
    "DEFAULT_FLOOD_CONFIG",
    "DEFAULT_DROUGHT_CONFIG",
    "HeatModel",
    "FloodModel",
    "DroughtModel",
    "HazardEngine",
]
