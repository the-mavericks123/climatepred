"""Evaluation Framework: Synthetic & Deterministic Prediction Benchmarks.

STATUS: SYNTHETIC/DETERMINISTIC EVALUATION
Evaluates deterministic prediction model outputs across 10 benchmark scenarios:
  1. Stable conditions
  2. Rising heat
  3. Falling heat
  4. Rising rainfall
  5. Rising water level
  6. Increasing soil saturation
  7. Worsening drought
  8. Improving drought
  9. Noisy measurements
  10. Insufficient history

NOTE: These tests do NOT represent real-world empirical validation or operational disaster forecasts.
They verify deterministic consistency against engineering scenario specifications.
"""

from datetime import datetime, timezone, timedelta
from typing import NamedTuple, List, Optional
import pytest

from intelligence.prediction.engine import PredictionEngine
from intelligence.prediction.features import TemporalFeatureExtractor
from intelligence.hazards.types import HazardType, HazardClassification, HazardStatus
from intelligence.core.contracts.telemetry import (
    NormalizedTelemetry,
    LocationCoordinate,
    SensorMeasurements,
    QualityMetadata,
)


def _pkt(
    ts: datetime,
    temp: float = 25.0,
    humidity: float = 50.0,
    rainfall: float = 0.0,
    water_level: float = 1.0,
    soil_moisture: float = 40.0,
    variance_noise: float = 0.0,
) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        schema_version="1.0",
        node_id="BENCH-NODE",
        timestamp=ts,
        location=LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0),
        measurements=SensorMeasurements(
            temperature=round(temp + variance_noise, 2),
            humidity=round(humidity, 2),
            rainfall=round(rainfall, 2),
            water_level=round(water_level, 2),
            soil_moisture=round(soil_moisture, 2),
        ),
        quality=QualityMetadata(valid=True, source="ESP32", received_at=ts, confidence=0.98),
    )


class PredictionBenchmarkScenario(NamedTuple):
    scenario_id: str
    description: str
    target_hazard: HazardType
    target_horizon: int
    expected_direction: str  # "HIGHER", "LOWER", "STABLE"
    min_expected_severity: float
    max_expected_severity: float
    expected_status: HazardStatus
    expected_min_confidence: float


class TestPredictionEvaluationBenchmarks:
    def setup_method(self):
        self.engine = PredictionEngine()
        self.T = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    def test_1_stable_conditions(self):
        """Scenario 1: Stable conditions across all parameters."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), temp=28.0, water_level=1.5, soil_moisture=45.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, temp=28.1, water_level=1.51, soil_moisture=45.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.HEAT], requested_horizons=[60], now=self.T)
        res = preds[0]
        assert res.classification in [HazardClassification.NORMAL, HazardClassification.LOW]
        assert res.severity < 0.35
        assert res.confidence > 0.80

    def test_2_rising_heat(self):
        """Scenario 2: Rapidly rising temperature."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), temp=30.0 + (5 - i) * 2.0, humidity=55.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, temp=40.0, humidity=55.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.HEAT], requested_horizons=[60], now=self.T)
        res = preds[0]
        assert res.severity >= 0.70
        assert res.classification in [HazardClassification.HIGH, HazardClassification.CRITICAL]

    def test_3_falling_heat(self):
        """Scenario 3: Falling temperature from hot conditions."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), temp=44.0 - (5 - i) * 2.5, humidity=40.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, temp=31.5, humidity=40.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.HEAT], requested_horizons=[60], now=self.T)
        res = preds[0]
        # Temperature is dropping back into lower risk
        assert res.severity < 0.45

    def test_4_rising_rainfall(self):
        """Scenario 4: Sharp rise in rainfall intensity."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), rainfall=5.0 + (5 - i) * 12.0, water_level=2.0, soil_moisture=50.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, rainfall=65.0, water_level=2.5, soil_moisture=55.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.FLOOD], requested_horizons=[30], now=self.T)
        res = preds[0]
        assert res.severity > 0.40
        assert any("rainfall" in d for d in res.drivers)

    def test_5_rising_water_level(self):
        """Scenario 5: Rising river water stage level."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), rainfall=20.0, water_level=2.0 + (5 - i) * 1.5, soil_moisture=60.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, rainfall=25.0, water_level=9.5, soil_moisture=65.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.FLOOD], requested_horizons=[60], now=self.T)
        res = preds[0]
        assert res.severity >= 0.60
        assert res.classification in [HazardClassification.HIGH, HazardClassification.CRITICAL]

    def test_6_increasing_soil_saturation(self):
        """Scenario 6: Rising soil moisture approaching saturation."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), water_level=3.0, soil_moisture=50.0 + (5 - i) * 8.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, water_level=3.5, soil_moisture=90.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.FLOOD], requested_horizons=[30], now=self.T)
        res = preds[0]
        assert res.severity >= 0.30

    def test_7_worsening_drought(self):
        """Scenario 7: Depleting soil moisture combined with high ambient temperature."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), temp=35.0 + (5 - i) * 1.5, humidity=30.0 - (5 - i) * 3.0, soil_moisture=30.0 - (5 - i) * 4.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, temp=42.5, humidity=15.0, soil_moisture=10.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.DROUGHT], requested_horizons=[60], now=self.T)
        res = preds[0]
        assert res.severity >= 0.75
        assert res.classification in [HazardClassification.HIGH, HazardClassification.CRITICAL]

    def test_8_improving_drought(self):
        """Scenario 8: Rehydrating soil and dropping temperature."""
        history = [_pkt(self.T - timedelta(minutes=10 * i), temp=38.0 - (5 - i) * 2.0, humidity=25.0 + (5 - i) * 5.0, soil_moisture=15.0 + (5 - i) * 6.0) for i in range(5, 0, -1)]
        curr = _pkt(self.T, temp=28.0, humidity=50.0, soil_moisture=45.0)

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.DROUGHT], requested_horizons=[60], now=self.T)
        res = preds[0]
        assert res.severity < 0.30

    def test_9_noisy_measurements(self):
        """Scenario 9: Highly noisy history degrades forecast confidence."""
        clean_history = [_pkt(self.T - timedelta(minutes=10 * i), temp=30.0 + (5 - i) * 1.0) for i in range(5, 0, -1)]
        noisy_history = [
            _pkt(self.T - timedelta(minutes=10 * i), temp=30.0 + (5 - i) * 1.0, variance_noise=5.0 if i % 2 == 0 else -5.0)
            for i in range(5, 0, -1)
        ]
        curr = _pkt(self.T, temp=35.0)

        p_clean = self.engine.evaluate_predictions(curr, clean_history, requested_hazards=[HazardType.HEAT], requested_horizons=[60], now=self.T)[0]
        p_noisy = self.engine.evaluate_predictions(curr, noisy_history, requested_hazards=[HazardType.HEAT], requested_horizons=[60], now=self.T)[0]

        assert p_noisy.confidence < p_clean.confidence

    def test_10_insufficient_history(self):
        """Scenario 10: Only 1 observation available falls back to persistence and penalizes confidence."""
        curr = _pkt(self.T, temp=32.0, water_level=1.2, soil_moisture=40.0)
        history = []  # No historical packets

        preds = self.engine.evaluate_predictions(curr, history, requested_hazards=[HazardType.HEAT], requested_horizons=[30], now=self.T)
        res = preds[0]
        assert res.confidence < 0.60
        assert res.data_quality["has_insufficient_history"] is True
        assert any("persistence fallback" in d for d in res.drivers)
