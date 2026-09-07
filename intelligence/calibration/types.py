"""
Climate Eye View — Phase 10 Calibration Data Contracts.
Defines schemas for calibration methods, reliability bins, calibration diagnostics,
and calibrated output envelopes while strictly preserving original raw model values.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CalibrationMethod(str, Enum):
    """Supported probability calibration methods."""
    PLATT_SCALING = "platt_scaling"      # Parametric logistic sigmoid fitting
    ISOTONIC = "isotonic"                # Non-parametric Pool Adjacent Violators Algorithm (PAVA)


class ReliabilityBin(BaseModel):
    """Single bin partition for a reliability diagram."""
    bin_index: int = Field(..., ge=0)
    lower_bound: float = Field(..., ge=0.0, le=1.0)
    upper_bound: float = Field(..., ge=0.0, le=1.0)
    mean_predicted_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    empirical_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    sample_count: int = Field(default=0, ge=0)
    calibration_gap: float = Field(default=0.0, ge=0.0, le=1.0)


class CalibrationReport(BaseModel):
    """
    Summary report of a calibration model fitting run, including before/after metrics.
    """
    calibration_id: str = Field(..., description="Unique calibration run identifier")
    model_version: str = Field(..., description="Target model version being calibrated")
    method: CalibrationMethod = Field(...)
    dataset_id: str = Field(..., description="Dataset used to fit the calibrator")
    sample_count: int = Field(..., ge=0)
    status: str = Field(default="CALIBRATED", description="'CALIBRATED' or 'CALIBRATION_UNAVAILABLE'")
    reason: Optional[str] = Field(default=None, description="Explanation if calibration was rejected")

    # Diagnostic metrics before vs after
    brier_score_before: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    brier_score_after: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ece_before: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ece_after: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    mce_before: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    mce_after: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    reliability_bins: List[ReliabilityBin] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance_hash: str = Field(..., description="Deterministic SHA-256 fingerprint of calibration fitting")


class CalibratedOutput(BaseModel):
    """
    Calibrated probabilistic output envelope.
    CRITICAL: Never replaces raw_value with calibrated_value; preserves both.
    """
    calibration_id: str = Field(...)
    model_version: str = Field(...)
    method: CalibrationMethod = Field(...)
    raw_value: float = Field(..., description="Authoritative uncalibrated model output score")
    calibrated_value: float = Field(..., ge=0.0, le=1.0, description="Calibrated event probability")
    calibration_dataset: str = Field(...)
    calibration_version: str = Field(default="1.0")
    provenance_hash: str = Field(...)


class CalibrationRunRequest(BaseModel):
    """Request payload for POST /api/v1/calibration/run."""
    model_version: str = Field(...)
    dataset_id: str = Field(...)
    method: Optional[CalibrationMethod] = Field(default=CalibrationMethod.ISOTONIC)
