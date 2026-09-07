"""Unit tests for temporal series and feature extraction (Phase 3).

Tests:
  - Chronological sorting of out-of-order packets
  - Irregular sampling time intervals
  - Deduplication of identical timestamps
  - OLS rate of change and trend calculation
  - Missing values handling
  - Insufficient history detection (< 2 observations)
"""

import pytest
from datetime import datetime, timezone, timedelta

from intelligence.prediction.features import (
    TemporalFeatureExtractor,
    SingleVariableSeries,
    TemporalTrendSummary,
)
from intelligence.core.contracts.telemetry import (
    NormalizedTelemetry,
    LocationCoordinate,
    SensorMeasurements,
    QualityMetadata,
)


def _make_packet(ts: datetime, temp: float | None = 25.0, rainfall: float | None = 0.0) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        schema_version="1.0",
        node_id="TEST-NODE-TEMP",
        timestamp=ts,
        location=LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0),
        measurements=SensorMeasurements(temperature=temp, rainfall=rainfall),
        quality=QualityMetadata(valid=True, source="ESP32", received_at=ts),
    )


class TestTemporalFeatureExtractor:
    def setup_method(self):
        self.extractor = TemporalFeatureExtractor(max_lookback_hours=24.0, min_observations=2)
        self.base_time = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    def test_chronological_sorting(self):
        """Out-of-order history must be sorted chronologically."""
        t1 = self.base_time - timedelta(minutes=30)
        t2 = self.base_time - timedelta(minutes=20)
        t3 = self.base_time - timedelta(minutes=10)
        t_curr = self.base_time

        # Provide history in reverse order
        history = [_make_packet(t3, temp=28.0), _make_packet(t1, temp=24.0), _make_packet(t2, temp=26.0)]
        curr = _make_packet(t_curr, temp=30.0)

        series_map = self.extractor.extract_series(curr, history, prediction_time=t_curr)
        temp_series = series_map["temperature"]

        assert temp_series.count == 4
        assert temp_series.values == [24.0, 26.0, 28.0, 30.0]
        assert temp_series.timestamps == [t1, t2, t3, t_curr]

    def test_deduplication_keeps_latest(self):
        """Duplicate timestamps must be deduplicated, preserving the latest entry."""
        t1 = self.base_time - timedelta(minutes=10)
        curr = _make_packet(self.base_time, temp=30.0)
        history = [
            _make_packet(t1, temp=20.0),
            _make_packet(t1, temp=22.0),  # Duplicate timestamp with updated value
        ]

        series_map = self.extractor.extract_series(curr, history, prediction_time=self.base_time)
        temp_series = series_map["temperature"]

        assert temp_series.count == 2
        assert temp_series.values == [22.0, 30.0]

    def test_irregular_sampling_intervals(self):
        """Correct slope calculation when readings arrive at non-uniform intervals (e.g. +5m, +15m, +30m)."""
        t0 = self.base_time - timedelta(minutes=50)
        t1 = t0 + timedelta(minutes=5)   # +5 min, temp=25.0
        t2 = t0 + timedelta(minutes=20)  # +15 min, temp=28.0
        t3 = t0 + timedelta(minutes=50)  # +30 min, temp=34.0 (current)

        curr = _make_packet(t3, temp=34.0)
        history = [_make_packet(t0, temp=24.0), _make_packet(t1, temp=25.0), _make_packet(t2, temp=28.0)]

        series_map = self.extractor.extract_series(curr, history, prediction_time=t3)
        trend = self.extractor.compute_trend(series_map["temperature"])

        assert trend.is_insufficient is False
        assert trend.sample_count == 4
        assert trend.history_span_minutes == 50.0
        # Expected rate of change: (34 - 24) / 50 = 0.20 C/min
        assert pytest.approx(trend.rate_of_change_per_minute, 0.01) == 0.20
        assert trend.direction == "RISING"

    def test_missing_values_preserves_none(self):
        """If a physical variable is missing, it should not be fabricated or zero-coerced."""
        t1 = self.base_time - timedelta(minutes=10)
        curr = _make_packet(self.base_time, temp=None)
        history = [_make_packet(t1, temp=None)]

        series_map = self.extractor.extract_series(curr, history, prediction_time=self.base_time)
        temp_series = series_map["temperature"]
        trend = self.extractor.compute_trend(temp_series)

        assert temp_series.count == 0
        assert trend.current_value is None
        assert trend.is_insufficient is True

    def test_insufficient_history(self):
        """Less than 2 observations must be flagged as insufficient."""
        curr = _make_packet(self.base_time, temp=25.0)
        history = []  # No history

        series_map = self.extractor.extract_series(curr, history, prediction_time=self.base_time)
        trend = self.extractor.compute_trend(series_map["temperature"])

        assert trend.sample_count == 1
        assert trend.is_insufficient is True
        assert trend.rate_of_change_per_minute == 0.0
