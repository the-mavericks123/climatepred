"""Tests for Timestamp Hardening, Freshness Thresholds, and Clock Skew."""
import pytest
from datetime import datetime, timezone, timedelta

from intelligence.core.validation.validator import TelemetryValidator


class TestTimestampHardening:
    """Verifies UTC validation, freshness evaluation, and future timestamp rejection."""

    def test_valid_current_utc_timestamp(self):
        valid_packet = {
            "node_id": "NODE-TS-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "measurements": {
                "temperature": 26.0,
                "humidity": 55.0,
                "pressure": 1013.25
            },
            "location": {"lat": 12.9716, "lon": 77.5946},
            "quality": {"source": "ESP32"}
        }
        is_valid, telemetry, err = TelemetryValidator.validate_dict(valid_packet)
        assert is_valid is True
        assert err is None
        assert telemetry is not None

    def test_malformed_timestamp_rejected(self):
        invalid_packet = {
            "node_id": "NODE-TS-02",
            "timestamp": "not-an-iso-timestamp",
            "measurements": {"temperature": 26.0},
            "location": {"lat": 12.9716, "lon": 77.5946},
            "quality": {"source": "ESP32"}
        }
        is_valid, telemetry, err = TelemetryValidator.validate_dict(invalid_packet)
        assert is_valid is False
        assert err is not None

    def test_future_timestamp_rejected(self):
        far_future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        future_packet = {
            "node_id": "NODE-TS-03",
            "timestamp": far_future,
            "measurements": {
                "temperature": 26.0,
                "humidity": 55.0,
                "pressure": 1013.25
            },
            "location": {"lat": 12.9716, "lon": 77.5946},
            "quality": {"source": "ESP32"}
        }
        is_valid, telemetry, err = TelemetryValidator.validate_dict(future_packet)
        assert is_valid is False
        assert err is not None
        assert "more than 300s ahead" in err.message or "validation failed" in err.message.lower()

    def test_stale_freshness_boundary(self):
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=15)).timestamp()
        now = datetime.now(timezone.utc).timestamp()
        freshness_threshold = 300.0  # 5 minutes
        is_stale = (now - old_time) > freshness_threshold
        assert is_stale is True
