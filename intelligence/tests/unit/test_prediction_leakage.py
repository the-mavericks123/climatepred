"""Anti-leakage regression test for the Phase 3 Prediction Engine.

Mathematically proves that observations occurring after prediction_time T
are completely excluded and cannot leak into or alter predictions made at time T.
"""

from datetime import datetime, timezone, timedelta
import pytest

from intelligence.prediction.engine import PredictionEngine
from intelligence.hazards.types import HazardType
from intelligence.core.contracts.telemetry import (
    NormalizedTelemetry,
    LocationCoordinate,
    SensorMeasurements,
    QualityMetadata,
)


def _make_packet(ts: datetime, temp: float, humidity: float = 50.0) -> NormalizedTelemetry:
    return NormalizedTelemetry(
        schema_version="1.0",
        node_id="STATION-LEAK-TEST",
        timestamp=ts,
        location=LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0),
        measurements=SensorMeasurements(temperature=temp, humidity=humidity),
        quality=QualityMetadata(valid=True, source="ESP32", received_at=ts),
    )


class TestPredictionLeakage:
    def test_future_data_leakage_prevention(self):
        """
        History A: Observations up to T.
        History B: Same observations + future observations after T (with wild extreme values).
        Prediction(T, History A) must strictly equal Prediction(T, History B).
        """
        engine = PredictionEngine()
        T = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

        # Baseline observations up to T: gradual rise from 25C to 30C
        history_A = [
            _make_packet(T - timedelta(minutes=40), temp=25.0),
            _make_packet(T - timedelta(minutes=30), temp=26.2),
            _make_packet(T - timedelta(minutes=20), temp=27.5),
            _make_packet(T - timedelta(minutes=10), temp=28.8),
        ]
        curr = _make_packet(T, temp=30.0)

        # History B: includes everything in History A + wild future observations at T+10m, T+20m, T+30m
        future_observations = [
            _make_packet(T + timedelta(minutes=10), temp=55.0),  # Wild temperature spike
            _make_packet(T + timedelta(minutes=20), temp=60.0),
            _make_packet(T + timedelta(minutes=30), temp=65.0),
        ]
        history_B = history_A + future_observations

        # Evaluate predictions at time T using History A
        preds_A = engine.evaluate_predictions(
            current_telemetry=curr,
            history=history_A,
            requested_hazards=[HazardType.HEAT],
            requested_horizons=[30, 60, 360],
            now=T,
        )

        # Evaluate predictions at time T using History B (contaminated with future data)
        preds_B = engine.evaluate_predictions(
            current_telemetry=curr,
            history=history_B,
            requested_hazards=[HazardType.HEAT],
            requested_horizons=[30, 60, 360],
            now=T,
        )

        assert len(preds_A) == 3
        assert len(preds_B) == 3

        # Strict mathematical identity verification
        for p_a, p_b in zip(preds_A, preds_B):
            assert p_a.forecast_horizon_minutes == p_b.forecast_horizon_minutes
            assert p_a.severity == p_b.severity, f"Leakage detected! Severity differs: {p_a.severity} != {p_b.severity}"
            assert p_a.confidence == p_b.confidence, f"Leakage detected! Confidence differs: {p_a.confidence} != {p_b.confidence}"
            assert p_a.classification == p_b.classification
            assert p_a.predicted_features == p_b.predicted_features
            assert p_a.provenance_hash == p_b.provenance_hash, f"Leakage detected in provenance! {p_a.provenance_hash} != {p_b.provenance_hash}"
