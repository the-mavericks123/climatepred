"""
Unit tests validating the deterministic fixture dataset.
"""

from datetime import datetime, timezone
from intelligence.core.validation.validator import TelemetryValidator


def test_normal_fixture(normal_telemetry_dict):
    is_valid, telemetry, _ = TelemetryValidator.validate_dict(normal_telemetry_dict)
    assert is_valid is True
    assert telemetry.node_id == "STATION-HYD-001"
    assert telemetry.measurements.temperature == 24.5


def test_hot_fixture(hot_telemetry_dict):
    is_valid, telemetry, _ = TelemetryValidator.validate_dict(hot_telemetry_dict)
    assert is_valid is True
    assert telemetry.measurements.temperature == 46.2
    assert "HEAT_STRESS_WARNING" in telemetry.quality.flags


def test_heavy_rain_fixture(heavy_rain_telemetry_dict):
    is_valid, telemetry, _ = TelemetryValidator.validate_dict(heavy_rain_telemetry_dict)
    assert is_valid is True
    assert telemetry.measurements.rainfall == 68.5


def test_critical_flood_fixture(critical_flood_telemetry_dict):
    is_valid, telemetry, _ = TelemetryValidator.validate_dict(critical_flood_telemetry_dict)
    assert is_valid is True
    assert telemetry.measurements.water_level == 18.9
    assert "CRITICAL_FLOOD_STAGE" in telemetry.quality.flags


def test_invalid_fixture(invalid_telemetry_dict):
    is_valid, _, error = TelemetryValidator.validate_dict(invalid_telemetry_dict)
    assert is_valid is False
    assert error is not None
    assert len(error.details["errors"]) >= 4  # multiple physical range violations


def test_missing_sensor_fixture(missing_sensor_telemetry_dict):
    is_valid, telemetry, _ = TelemetryValidator.validate_dict(missing_sensor_telemetry_dict)
    assert is_valid is True
    assert telemetry.measurements.water_level is None
    assert telemetry.measurements.air_quality is None
    assert telemetry.measurements.temperature == 28.0


def test_stale_fixture(stale_telemetry_dict):
    is_valid, telemetry, _ = TelemetryValidator.validate_dict(stale_telemetry_dict)
    assert is_valid is True
    age_seconds = (telemetry.quality.received_at - telemetry.timestamp).total_seconds()
    assert age_seconds > 300  # Older than 5-minute freshness threshold
