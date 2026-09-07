"""
Unit tests for telemetry validation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.validation.validator import TelemetryValidator
from intelligence.core.errors.exceptions import ValidationException


def test_valid_telemetry_passes_validation(normal_telemetry_dict):
    is_valid, telemetry, error = TelemetryValidator.validate_dict(normal_telemetry_dict)
    assert is_valid is True
    assert telemetry is not None
    assert error is None
    assert telemetry.node_id == "STATION-HYD-001"
    assert telemetry.measurements.rainfall == 0.0  # Legitimate zero rainfall


def test_missing_values_distinguishable_from_zero(missing_sensor_telemetry_dict):
    is_valid, telemetry, error = TelemetryValidator.validate_dict(missing_sensor_telemetry_dict)
    assert is_valid is True
    assert telemetry is not None
    # Crucial rule: missing values are None, NOT zero
    assert telemetry.measurements.water_level is None
    assert telemetry.measurements.air_quality is None
    # And legitimate zero is preserved as 0.0, NOT None
    assert telemetry.measurements.rainfall == 0.0


def test_invalid_latitude_rejected(normal_telemetry_dict):
    invalid_data = dict(normal_telemetry_dict)
    invalid_data["location"] = {"lat": 95.0, "lon": 78.48}
    is_valid, telemetry, error = TelemetryValidator.validate_dict(invalid_data)
    assert is_valid is False
    assert telemetry is None
    assert error is not None
    assert any("lat" in e["field"] for e in error.details.get("errors", []))


def test_invalid_longitude_rejected(normal_telemetry_dict):
    invalid_data = dict(normal_telemetry_dict)
    invalid_data["location"] = {"lat": 17.38, "lon": 195.0}
    is_valid, telemetry, error = TelemetryValidator.validate_dict(invalid_data)
    assert is_valid is False
    assert telemetry is None
    assert any("lon" in e["field"] for e in error.details.get("errors", []))


def test_invalid_humidity_rejected(normal_telemetry_dict):
    invalid_data = dict(normal_telemetry_dict)
    invalid_data["measurements"]["humidity"] = 120.0
    is_valid, telemetry, error = TelemetryValidator.validate_dict(invalid_data)
    assert is_valid is False
    assert any("humidity" in e["field"] for e in error.details.get("errors", []))


def test_negative_rainfall_rejected(normal_telemetry_dict):
    invalid_data = dict(normal_telemetry_dict)
    invalid_data["measurements"]["rainfall"] = -5.0
    is_valid, telemetry, error = TelemetryValidator.validate_dict(invalid_data)
    assert is_valid is False
    assert any("rainfall" in e["field"] for e in error.details.get("errors", []))


def test_future_timestamp_rejected(normal_telemetry_dict):
    invalid_data = dict(normal_telemetry_dict)
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    invalid_data["timestamp"] = future_time.isoformat()
    invalid_data["quality"]["received_at"] = datetime.now(timezone.utc).isoformat()
    is_valid, telemetry, error = TelemetryValidator.validate_dict(invalid_data)
    assert is_valid is False
    assert error is not None


def test_require_valid_raises_exception(invalid_telemetry_dict):
    with pytest.raises(ValidationException) as exc_info:
        TelemetryValidator.require_valid(invalid_telemetry_dict)
    assert exc_info.value.code.value == "VALIDATION_ERROR"
