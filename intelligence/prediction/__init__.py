"""Prediction package for Climate Eye View (S2 Intelligence Subsystem).
Provides deterministic forecasting of Heat, Flood, and Drought hazard states across
30-minute, 1-hour, and 6-hour horizons.
"""

from intelligence.prediction.types import (
    ForecastHorizon,
    PredictionResult,
    PredictionEvaluationRequest,
    PredictionEvaluationResponse,
)
from intelligence.prediction.thresholds import (
    VALID_HORIZONS,
    MIN_HISTORY_OBSERVATIONS,
    MAX_LOOKBACK_HOURS,
    PhysicalSensorBounds,
    PredictionConfig,
    DEFAULT_PHYSICAL_BOUNDS,
    DEFAULT_PREDICTION_CONFIG,
)
from intelligence.prediction.features import (
    SingleVariableSeries,
    TemporalTrendSummary,
    TemporalFeatureExtractor,
)
from intelligence.prediction.models import (
    DeterministicTrendForecaster,
)
from intelligence.prediction.confidence import (
    PredictionConfidenceCalculator,
)
from intelligence.prediction.engine import (
    PredictionEngine,
)

__all__ = [
    "ForecastHorizon",
    "PredictionResult",
    "PredictionEvaluationRequest",
    "PredictionEvaluationResponse",
    "VALID_HORIZONS",
    "MIN_HISTORY_OBSERVATIONS",
    "MAX_LOOKBACK_HOURS",
    "PhysicalSensorBounds",
    "PredictionConfig",
    "DEFAULT_PHYSICAL_BOUNDS",
    "DEFAULT_PREDICTION_CONFIG",
    "SingleVariableSeries",
    "TemporalTrendSummary",
    "TemporalFeatureExtractor",
    "DeterministicTrendForecaster",
    "PredictionConfidenceCalculator",
    "PredictionEngine",
]
