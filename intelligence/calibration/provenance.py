"""
Deterministic cryptographic provenance tracker for Phase 10 Calibration.
Generates reproducible SHA-256 digests over calibration fitting parameters,
methods, and calibrated outputs.
"""

import hashlib
import json
from typing import Any, Dict, Optional
from intelligence.calibration.types import CalibrationMethod


class CalibrationProvenanceTracker:
    """
    Computes deterministic SHA-256 provenance hashes for calibration runs.
    """

    PROVENANCE_VERSION = "calibration-prov-v1"

    @classmethod
    def compute_calibration_hash(
        cls,
        model_version: str,
        method: CalibrationMethod,
        dataset_id: str,
        sample_count: int,
        brier_after: Optional[float] = None,
        ece_after: Optional[float] = None,
    ) -> str:
        """Generates SHA-256 digest from canonical calibration parameters."""
        payload = {
            "model_version": str(model_version),
            "method": method.value,
            "dataset_id": str(dataset_id),
            "sample_count": int(sample_count),
            "brier_after": round(brier_after, 4) if brier_after is not None else None,
            "ece_after": round(ece_after, 4) if ece_after is not None else None,
            "provenance_version": cls.PROVENANCE_VERSION,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def compute_output_hash(
        cls,
        calibration_id: str,
        model_version: str,
        raw_value: float,
        calibrated_value: float,
    ) -> str:
        """Generates SHA-256 digest for an individual calibrated inference output."""
        payload = {
            "calibration_id": str(calibration_id),
            "model_version": str(model_version),
            "raw_value": round(float(raw_value), 4),
            "calibrated_value": round(float(calibrated_value), 4),
            "provenance_version": cls.PROVENANCE_VERSION,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
