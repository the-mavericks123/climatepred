"""Contract tests for PredictionResult schema and boundaries (Phase 3).

Verifies:
  - Supported forecast horizons strictly in {30, 60, 360}
  - Severity and confidence in [0.0, 1.0]
  - Simulated flag strictly False
  - Model versions and classification enums
  - Provenance hash presence
"""

import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from intelligence.prediction.types import PredictionResult
from intelligence.hazards.types import HazardType, HazardClassification, HazardStatus


def _valid_prediction_dict(**overrides):
    t_now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    base = {
        "prediction_id": "PRED-HEAT-STATION-01-30M-1788780000",
        "hazard": "heat",
        "prediction_time": t_now,
        "forecast_time": t_now + timedelta(minutes=30),
        "forecast_horizon_minutes": 30,
        "severity": 0.72,
        "confidence": 0.85,
        "classification": "HIGH",
        "status": "DETECTED",
        "model_version": "heat-pred-v1",
        "source_hazard_id": "HAZ-HEAT-STATION-01-1788780000",
        "provenance_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "drivers": ["temperature rising +2.1C over +30m"],
        "data_quality": {"sample_count": 5},
        "predicted_features": {"temperature": 41.5, "humidity": 55.0},
        "simulated": False,
    }
    base.update(overrides)
    return base


class TestPredictionContract:
    def test_valid_prediction_result(self):
        payload = _valid_prediction_dict()
        res = PredictionResult(**payload)
        assert res.hazard == HazardType.HEAT
        assert res.forecast_horizon_minutes == 30
        assert res.severity == 0.72
        assert res.confidence == 0.85
        assert res.classification == HazardClassification.HIGH
        assert res.status == HazardStatus.DETECTED
        assert res.simulated is False
        assert res.model_version == "heat-pred-v1"

    @pytest.mark.parametrize("h", [30, 60, 360])
    def test_valid_horizons_accepted(self, h):
        payload = _valid_prediction_dict(forecast_horizon_minutes=h)
        res = PredictionResult(**payload)
        assert res.forecast_horizon_minutes == h

    @pytest.mark.parametrize("invalid_h", [0, 15, 45, 120, 240, 720, 1440])
    def test_invalid_horizons_rejected(self, invalid_h):
        payload = _valid_prediction_dict(forecast_horizon_minutes=invalid_h)
        with pytest.raises(ValidationError):
            PredictionResult(**payload)

    def test_simulated_true_rejected(self):
        payload = _valid_prediction_dict(simulated=True)
        with pytest.raises(ValidationError):
            PredictionResult(**payload)

    def test_severity_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            PredictionResult(**_valid_prediction_dict(severity=-0.01))
        with pytest.raises(ValidationError):
            PredictionResult(**_valid_prediction_dict(severity=1.01))

    def test_confidence_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            PredictionResult(**_valid_prediction_dict(confidence=-0.05))
        with pytest.raises(ValidationError):
            PredictionResult(**_valid_prediction_dict(confidence=1.05))

    def test_provenance_differentiates_distinct_historical_values(self):
        """
        Forensic requirement:
        Two histories with identical timestamps, current telemetry, hazard, and horizon,
        but different historical values, must produce distinct provenance hashes.
        """
        from intelligence.core.contracts.telemetry import (
            NormalizedTelemetry,
            SensorMeasurements,
            LocationCoordinate,
            QualityMetadata,
        )
        from intelligence.prediction.engine import PredictionEngine

        engine = PredictionEngine()
        t0 = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
        curr = NormalizedTelemetry(
            node_id="STATION-01",
            timestamp=t0,
            location=LocationCoordinate(lat=10.0, lon=20.0),
            measurements=SensorMeasurements(temperature=30.0, humidity=50.0),
            quality=QualityMetadata(source="ESP32", valid=True),
        )

        # History A: 20C -> 25C
        h_a = [
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(hours=2),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=20.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(hours=1),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=25.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
        ]

        # History B: 10C -> 15C
        h_b = [
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(hours=2),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=10.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(hours=1),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=15.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
        ]

        res_a = engine.evaluate_predictions(curr, h_a, requested_hazards=[HazardType.HEAT], requested_horizons=[30])
        res_b = engine.evaluate_predictions(curr, h_b, requested_hazards=[HazardType.HEAT], requested_horizons=[30])

        assert res_a[0].provenance_hash != res_b[0].provenance_hash
        assert res_a[0].severity != res_b[0].severity

    def test_provenance_longer_history_sensitivity(self):
        """
        Longer history test (4 observations):
        Modifying just one historical observation in a multi-step sequence must change provenance.
        """
        from intelligence.core.contracts.telemetry import (
            NormalizedTelemetry,
            SensorMeasurements,
            LocationCoordinate,
            QualityMetadata,
        )
        from intelligence.prediction.engine import PredictionEngine

        engine = PredictionEngine()
        t0 = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
        curr = NormalizedTelemetry(
            node_id="STATION-01",
            timestamp=t0,
            location=LocationCoordinate(lat=10.0, lon=20.0),
            measurements=SensorMeasurements(temperature=30.0, humidity=50.0),
            quality=QualityMetadata(source="ESP32", valid=True),
        )

        # History A: 20, 21, 23, 25
        h_a = [
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=40),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=20.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=30),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=21.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=20),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=23.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=10),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=25.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
        ]

        # History B: 20, 21, 24, 25 (one observation modified)
        h_b = [
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=40),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=20.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=30),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=21.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=20),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=24.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
            NormalizedTelemetry(
                node_id="STATION-01",
                timestamp=t0 - timedelta(minutes=10),
                location=LocationCoordinate(lat=10.0, lon=20.0),
                measurements=SensorMeasurements(temperature=25.0, humidity=50.0),
                quality=QualityMetadata(source="ESP32", valid=True),
            ),
        ]

        res_a = engine.evaluate_predictions(curr, h_a, requested_hazards=[HazardType.HEAT], requested_horizons=[60])
        res_b = engine.evaluate_predictions(curr, h_b, requested_hazards=[HazardType.HEAT], requested_horizons=[60])

        assert res_a[0].provenance_hash != res_b[0].provenance_hash

    def test_provenance_ordering_invariance(self):
        """
        Ordering test:
        Supplying identical historical observations in non-chronological order must produce
        the exact same prediction and provenance as supplying them sorted.
        """
        from intelligence.core.contracts.telemetry import (
            NormalizedTelemetry,
            SensorMeasurements,
            LocationCoordinate,
            QualityMetadata,
        )
        from intelligence.prediction.engine import PredictionEngine

        engine = PredictionEngine()
        t0 = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
        curr = NormalizedTelemetry(
            node_id="STATION-01",
            timestamp=t0,
            location=LocationCoordinate(lat=10.0, lon=20.0),
            measurements=SensorMeasurements(temperature=30.0, humidity=50.0),
            quality=QualityMetadata(source="ESP32", valid=True),
        )

        p1 = NormalizedTelemetry(
            node_id="STATION-01",
            timestamp=t0 - timedelta(minutes=30),
            location=LocationCoordinate(lat=10.0, lon=20.0),
            measurements=SensorMeasurements(temperature=22.0, humidity=50.0),
            quality=QualityMetadata(source="ESP32", valid=True),
        )
        p2 = NormalizedTelemetry(
            node_id="STATION-01",
            timestamp=t0 - timedelta(minutes=20),
            location=LocationCoordinate(lat=10.0, lon=20.0),
            measurements=SensorMeasurements(temperature=25.0, humidity=50.0),
            quality=QualityMetadata(source="ESP32", valid=True),
        )
        p3 = NormalizedTelemetry(
            node_id="STATION-01",
            timestamp=t0 - timedelta(minutes=10),
            location=LocationCoordinate(lat=10.0, lon=20.0),
            measurements=SensorMeasurements(temperature=28.0, humidity=50.0),
            quality=QualityMetadata(source="ESP32", valid=True),
        )

        h_sorted = [p1, p2, p3]
        h_shuffled = [p3, p1, p2]

        res_sorted = engine.evaluate_predictions(curr, h_sorted, requested_hazards=[HazardType.HEAT], requested_horizons=[30])
        res_shuffled = engine.evaluate_predictions(curr, h_shuffled, requested_hazards=[HazardType.HEAT], requested_horizons=[30])

        assert res_sorted[0].provenance_hash == res_shuffled[0].provenance_hash
        assert res_sorted[0].severity == res_shuffled[0].severity
        assert res_sorted[0].confidence == res_shuffled[0].confidence
