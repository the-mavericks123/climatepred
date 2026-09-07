"""
Phase 10 Calibration Package.
Provides probability calibration algorithms (Platt scaling & Isotonic regression),
sample-size gating, reliability diagrams, and non-destructive calibrated inference.
"""

from intelligence.calibration.types import (
    CalibratedOutput,
    CalibrationMethod,
    CalibrationReport,
    CalibrationRunRequest,
    ReliabilityBin,
)
from intelligence.calibration.engine import CalibrationEngine
from intelligence.calibration.methods import IsotonicCalibrator, PlattScaler
from intelligence.calibration.provenance import CalibrationProvenanceTracker
from intelligence.calibration.reliability import ReliabilityAnalyzer

__all__ = [
    "CalibrationEngine",
    "CalibrationMethod",
    "CalibrationReport",
    "CalibratedOutput",
    "CalibrationRunRequest",
    "ReliabilityBin",
    "PlattScaler",
    "IsotonicCalibrator",
    "CalibrationProvenanceTracker",
    "ReliabilityAnalyzer",
]
