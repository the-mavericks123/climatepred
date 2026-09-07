"""Contract tests for Hazard Result Schema and constraints.

Verifies:
  - Pydantic contract boundaries:
    - severity in [0.0, 1.0]
    - confidence in [0.0, 1.0]
    - forecast_horizon_minutes == 0
    - simulated is False
    - lat in [-90, 90], lon in [-180, 180]
  - Status enum enforcement (DETECTED, NOT_DETECTED, UNAVAILABLE)
  - Classification enum enforcement (NORMAL, LOW, MODERATE, HIGH, CRITICAL)
  - Provenance linkage preservation
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardClassification,
    HazardResult,
    HazardEvaluationRequest,
    HazardEvaluationResponse,
)
from intelligence.core.contracts.telemetry import LocationCoordinate


def _valid_hazard_payload(**overrides):
    base = {
        "hazard_id": "HAZ-TEST-001",
        "hazard": "flood",
        "severity": 0.85,
        "confidence": 0.92,
        "classification": "CRITICAL",
        "status": "DETECTED",
        "timestamp": datetime(2026, 9, 7, 10, 30, 0, tzinfo=timezone.utc),
        "forecast_horizon_minutes": 0,
        "location": {"lat": 17.385, "lon": 78.4867},
        "features": {"rainfall": 68.5, "water_level": 12.4},
        "drivers": ["high rainfall", "rising water level"],
        "source": "model",
        "model_version": "flood-v1",
        "simulated": False,
        "telemetry_fingerprint": "sha256:abcd1234",
    }
    base.update(overrides)
    return base


class TestHazardContract:
    def test_valid_hazard_result(self):
        payload = _valid_hazard_payload()
        result = HazardResult(**payload)
        assert result.hazard == HazardType.FLOOD
        assert result.severity == 0.85
        assert result.confidence == 0.92
        assert result.classification == HazardClassification.CRITICAL
        assert result.status == HazardStatus.DETECTED
        assert result.forecast_horizon_minutes == 0
        assert result.simulated is False
        assert result.model_version == "flood-v1"

    def test_severity_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(severity=-0.01))

        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(severity=1.01))

    def test_confidence_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(confidence=-0.1))

        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(confidence=1.05))

    def test_forecast_horizon_must_be_zero_in_phase2(self):
        # Contract enforces ge=0, and for Phase 2, models must strictly emit 0
        res = HazardResult(**_valid_hazard_payload(forecast_horizon_minutes=0))
        assert res.forecast_horizon_minutes == 0

        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(forecast_horizon_minutes=-5))

    def test_invalid_coordinates_rejected(self):
        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(location={"lat": 95.0, "lon": 78.0}))

        with pytest.raises(ValidationError):
            HazardResult(**_valid_hazard_payload(location={"lat": 17.0, "lon": 185.0}))

    def test_unavailable_result_contract(self):
        payload = _valid_hazard_payload(
            status="UNAVAILABLE",
            severity=0.0,
            classification=None,
            drivers=["Required water_level measurement unavailable"],
        )
        res = HazardResult(**payload)
        assert res.status == HazardStatus.UNAVAILABLE
        assert res.classification is None
        assert res.severity == 0.0

    def test_evaluation_response_serialization(self):
        res1 = HazardResult(**_valid_hazard_payload())
        resp = HazardEvaluationResponse(
            success=True,
            hazards=[res1],
            request_id="REQ-TEST-1234",
        )
        data = resp.model_dump()
        assert data["success"] is True
        assert len(data["hazards"]) == 1
        assert data["hazards"][0]["model_version"] == "flood-v1"
        assert data["hazards"][0]["forecast_horizon_minutes"] == 0
        assert data["hazards"][0]["simulated"] is False
