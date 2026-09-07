"""Unit tests for deterministic prediction models (Phase 3).

Tests:
  - Heat prediction under rising and falling temperatures
  - Flood prediction under rising rainfall and water level
  - Drought prediction under depleting soil moisture
  - Physical clamping boundaries (humidity in [0, 100], rainfall >= 0, etc.)
  - Supported horizons: 30, 60, 360 minutes
  - Extreme trend bounding
"""

import pytest
from datetime import datetime, timezone, timedelta

from intelligence.prediction.models import DeterministicTrendForecaster
from intelligence.prediction.features import TemporalTrendSummary
from intelligence.prediction.engine import PredictionEngine
from intelligence.hazards.types import HazardType, HazardClassification
from intelligence.core.contracts.telemetry import (
    NormalizedTelemetry,
    LocationCoordinate,
    SensorMeasurements,
    QualityMetadata,
)


def _make_telemetry(
    ts: datetime,
    temp: float = 25.0,
    humidity: float = 50.0,
    rainfall: float = 0.0,
    water_level: float = 1.0,
    soil_moisture: float = 40.0,
) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        schema_version="1.0",
        node_id="STATION-TEST-PRED",
        timestamp=ts,
        location=LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0),
        measurements=SensorMeasurements(
            temperature=temp,
            humidity=humidity,
            rainfall=rainfall,
            water_level=water_level,
            soil_moisture=soil_moisture,
        ),
        quality=QualityMetadata(valid=True, source="ESP32", received_at=ts, confidence=0.98),
    )


class TestPredictionModels:
    def setup_method(self):
        self.forecaster = DeterministicTrendForecaster()
        self.engine = PredictionEngine()
        self.base_time = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    def test_physical_clamping_humidity(self):
        """Extrapolated humidity exceeding 100% must clamp to 100.0%."""
        # Rate: +0.50 % per minute over 60 minutes -> +30% on current 85% = 115%
        summary = TemporalTrendSummary(
            variable_name="humidity",
            current_value=85.0,
            sample_count=5,
            history_span_minutes=40.0,
            rate_of_change_per_minute=0.50,
            trend_variance=0.1,
            is_insufficient=False,
            direction="RISING",
        )
        val, drivers = self.forecaster.forecast_variable(summary, horizon_minutes=60)
        assert val == 100.0
        assert any("clamped to physical ceiling" in d for d in drivers)

    def test_physical_clamping_rainfall_floor(self):
        """Decreasing rainfall extrapolation below zero must clamp to 0.0."""
        summary = TemporalTrendSummary(
            variable_name="rainfall",
            current_value=10.0,
            sample_count=5,
            history_span_minutes=40.0,
            rate_of_change_per_minute=-0.40,  # 10 - 24 = -14
            is_insufficient=False,
            direction="FALLING",
        )
        val, drivers = self.forecaster.forecast_variable(summary, horizon_minutes=60)
        assert val == 0.0
        assert any("clamped to physical floor" in d for d in drivers)

    def test_heat_prediction_horizons(self):
        """Predicting heat across 30m, 60m, 360m under rising temperature."""
        history = [
            _make_telemetry(self.base_time - timedelta(minutes=10 * i), temp=30.0 + (5 - i) * 1.5, humidity=60.0)
            for i in range(5, 0, -1)
        ]
        curr = _make_telemetry(self.base_time, temp=38.0, humidity=60.0)

        results = self.engine.evaluate_predictions(
            current_telemetry=curr,
            history=history,
            requested_hazards=[HazardType.HEAT],
            requested_horizons=[30, 60, 360],
        )

        assert len(results) == 3
        r30 = next(r for r in results if r.forecast_horizon_minutes == 30)
        r60 = next(r for r in results if r.forecast_horizon_minutes == 60)
        r360 = next(r for r in results if r.forecast_horizon_minutes == 360)

        # Temperature is rising rapidly -> severity should increase with horizon until ceiling
        assert r30.severity >= 0.60
        assert r60.severity >= r30.severity
        assert r360.severity >= r60.severity
        assert r360.severity <= 1.0

        # Model version contract
        assert r30.model_version == "heat-pred-v1"
        assert r30.simulated is False

    def test_flood_prediction_rising_water(self):
        """Predicting flood under rapidly rising water level and rainfall."""
        history = [
            _make_telemetry(
                self.base_time - timedelta(minutes=10 * i),
                rainfall=10.0 + (5 - i) * 10.0,
                water_level=2.0 + (5 - i) * 1.0,
                soil_moisture=60.0 + (5 - i) * 5.0,
            )
            for i in range(5, 0, -1)
        ]
        curr = _make_telemetry(self.base_time, rainfall=60.0, water_level=7.0, soil_moisture=85.0)

        results = self.engine.evaluate_predictions(
            current_telemetry=curr,
            history=history,
            requested_hazards=[HazardType.FLOOD],
            requested_horizons=[30, 60],
        )

        assert len(results) == 2
        f30 = next(r for r in results if r.forecast_horizon_minutes == 30)
        f60 = next(r for r in results if r.forecast_horizon_minutes == 60)

        assert f30.hazard == HazardType.FLOOD
        assert f30.classification in [HazardClassification.HIGH, HazardClassification.CRITICAL]
        assert f60.severity >= f30.severity
        assert f60.model_version == "flood-pred-v1"

    def test_drought_prediction_drying_soil(self):
        """Predicting drought under depleting soil moisture and rising ambient heat."""
        history = [
            _make_telemetry(
                self.base_time - timedelta(minutes=10 * i),
                temp=32.0 + (5 - i) * 1.5,
                humidity=45.0 - (5 - i) * 4.0,
                soil_moisture=30.0 - (5 - i) * 3.0,
            )
            for i in range(5, 0, -1)
        ]
        curr = _make_telemetry(self.base_time, temp=40.0, humidity=25.0, soil_moisture=14.0)

        results = self.engine.evaluate_predictions(
            current_telemetry=curr,
            history=history,
            requested_hazards=[HazardType.DROUGHT],
            requested_horizons=[60],
        )

        assert len(results) == 1
        d60 = results[0]
        assert d60.hazard == HazardType.DROUGHT
        assert d60.severity >= 0.70
        assert d60.classification in [HazardClassification.HIGH, HazardClassification.CRITICAL]
        assert d60.model_version == "drought-pred-v1"
