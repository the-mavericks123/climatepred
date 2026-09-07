"""Prediction data contracts and schemas for Climate Eye View S2.
Defines strict Pydantic models for deterministic hazard forecasting.
"""

from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from intelligence.hazards.types import (
    HazardClassification,
    HazardStatus,
    HazardType,
)
from intelligence.prediction.thresholds import VALID_HORIZONS


class ForecastHorizon(IntEnum):
    """Supported prediction horizons in minutes."""
    MINUTES_30 = 30
    MINUTES_60 = 60
    MINUTES_360 = 360


class PredictionResult(BaseModel):
    """
    Structured, deterministic hazard prediction output for a future horizon.
    Derived from extrapolated environmental physical states evaluated through
    authoritative Phase 2 hazard models.
    """
    prediction_id: str = Field(..., min_length=1, description="Unique prediction identifier")
    hazard: HazardType = Field(..., description="Hazard domain classification (heat, flood, drought)")
    prediction_time: datetime = Field(..., description="Timestamp when prediction was calculated / current telemetry time")
    forecast_time: datetime = Field(..., description="Future target time of the forecast")
    forecast_horizon_minutes: int = Field(..., description="Prediction horizon in minutes: strictly 30, 60, or 360")
    severity: float = Field(..., ge=0.0, le=1.0, description="Predicted hazard severity score in [0.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Forecast confidence score in [0.0, 1.0]")
    classification: Optional[HazardClassification] = Field(default=None, description="Predicted categorical risk tier")
    status: HazardStatus = Field(..., description="Forecast status (DETECTED, NOT_DETECTED, UNAVAILABLE)")
    geometry: Optional[Dict[str, Any]] = Field(default=None, description="Optional geospatial geometry")
    model_version: str = Field(..., min_length=1, description="Immutable prediction model version string")
    source_hazard_id: Optional[str] = Field(default=None, description="Reference to current-state Phase 2 hazard evaluation")
    provenance_hash: str = Field(..., min_length=8, description="Cryptographic SHA-256 fingerprint tracing forecast inputs")
    drivers: List[str] = Field(default_factory=list, description="Deterministic drivers explaining trend and forecast")
    data_quality: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic data quality metrics")
    predicted_features: Dict[str, Any] = Field(default_factory=dict, description="Extrapolated physical sensor quantities")
    simulated: bool = Field(default=False, description="Whether forecast was simulated (strictly False in Phase 3)")
    reason: Optional[str] = Field(default=None, description="Explanation when status is UNAVAILABLE")

    @field_validator("forecast_horizon_minutes")
    @classmethod
    def validate_horizon(cls, v: int) -> int:
        if v not in VALID_HORIZONS:
            raise ValueError(f"forecast_horizon_minutes must be one of {sorted(list(VALID_HORIZONS))}, got {v}")
        return v

    @field_validator("simulated")
    @classmethod
    def validate_simulated_false(cls, v: bool) -> bool:
        if v is True:
            raise ValueError("simulated must be False for Phase 3 production prediction")
        return v


class PredictionEvaluationRequest(BaseModel):
    """API payload schema for hazard prediction evaluation."""
    telemetry: Dict[str, Any] = Field(..., description="Current normalized telemetry dictionary conforming to NormalizedTelemetry")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological historical normalized telemetry list")
    hazards: Optional[List[str]] = Field(default=None, description="Optional subset of hazards to predict: heat, flood, drought")
    horizons_minutes: Optional[List[int]] = Field(default=None, description="Optional subset of horizons to evaluate: 30, 60, 360")


class PredictionEvaluationResponse(BaseModel):
    """API response schema containing independent hazard prediction results."""
    success: bool = Field(default=True)
    predictions: List[PredictionResult] = Field(default_factory=list, description="Array of prediction results")
    request_id: Optional[str] = Field(default=None, description="Unique request tracing ID")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of prediction execution",
    )
