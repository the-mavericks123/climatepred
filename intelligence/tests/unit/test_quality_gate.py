"""Unit tests for HazardQualityGate and FeatureExtractor.

Verifies:
  - Missing measurements detection without zero-coercion (null != 0)
  - Freshness and staleness penalty
  - Anomaly penalty and confidence reduction
  - Telemetry validity gating
  - Feature extraction mapping and preservation of provenance
"""

import pytest
from datetime import datetime, timezone, timedelta

from intelligence.hazards.quality_gate import HazardQualityGate
from intelligence.hazards.features import FeatureExtractor, HazardFeatures
from intelligence.hazards.types import HazardType
from intelligence.core.contracts.telemetry import (
    NormalizedTelemetry,
    LocationCoordinate,
    SensorMeasurements,
    QualityMetadata,
)


def _build_telemetry(
    timestamp: datetime | None = None,
    temperature: float | None = 25.0,
    rainfall: float | None = 0.0,
    water_level: float | None = 1.0,
    soil_moisture: float | None = 50.0,
    humidity: float | None = 60.0,
    valid: bool = True,
    confidence: float = 0.95,
    anomaly_score: float = 0.0,
    flags: list | None = None,
) -> NormalizedTelemetry:
    ts = timestamp or datetime.now(timezone.utc)
    return NormalizedTelemetry(
        schema_version="1.0",
        node_id="TEST-STATION-01",
        timestamp=ts,
        location=LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0),
        measurements=SensorMeasurements(
            temperature=temperature,
            humidity=humidity,
            pressure=1013.0,
            rainfall=rainfall,
            soil_moisture=soil_moisture,
            water_level=water_level,
            air_quality=50.0,
        ),
        quality=QualityMetadata(
            valid=valid,
            source="ESP32",
            received_at=ts,
            confidence=confidence,
            anomaly_score=anomaly_score,
            flags=flags or [],
        ),
    )


class TestHazardQualityGate:
    def setup_method(self):
        self.extractor = FeatureExtractor()
        self.gate = HazardQualityGate(stale_threshold_seconds=300)

    def test_feature_extractor_preserves_none(self):
        t = _build_telemetry(temperature=None)
        f = self.extractor.extract(t, provenance_hash="sha256:testfingerprint")
        assert f.temperature_c is None
        assert f.node_id == "TEST-STATION-01"
        assert f.provenance_hash == "sha256:testfingerprint"

    def test_gate_heat_passes_complete_data(self):
        now = datetime.now(timezone.utc)
        t = _build_telemetry(timestamp=now, temperature=30.0, humidity=50.0)
        f = self.extractor.extract(t)
        verdict = self.gate.verify(f, HazardType.HEAT, now=now)
        assert verdict.passed is True
        assert verdict.is_stale is False
        assert verdict.confidence_factor > 0.9

    def test_gate_heat_fails_missing_temperature(self):
        now = datetime.now(timezone.utc)
        t = _build_telemetry(timestamp=now, temperature=None, humidity=50.0)
        f = self.extractor.extract(t)
        verdict = self.gate.verify(f, HazardType.HEAT, now=now)
        assert verdict.passed is False
        assert "temperature_c" in verdict.missing_fields

    def test_gate_flood_fails_missing_water_level(self):
        now = datetime.now(timezone.utc)
        t = _build_telemetry(timestamp=now, rainfall=20.0, water_level=None, soil_moisture=60.0)
        f = self.extractor.extract(t)
        verdict = self.gate.verify(f, HazardType.FLOOD, now=now)
        assert verdict.passed is False
        assert "water_level_m" in verdict.missing_fields

    def test_gate_drought_fails_missing_soil_moisture(self):
        now = datetime.now(timezone.utc)
        t = _build_telemetry(timestamp=now, soil_moisture=None, temperature=35.0, humidity=30.0)
        f = self.extractor.extract(t)
        verdict = self.gate.verify(f, HazardType.DROUGHT, now=now)
        assert verdict.passed is False
        assert "soil_moisture_pct" in verdict.missing_fields

    def test_gate_marks_stale_telemetry(self):
        now = datetime.now(timezone.utc)
        old_ts = now - timedelta(seconds=600)  # 10 mins old > 300s
        t = _build_telemetry(timestamp=old_ts)
        f = self.extractor.extract(t)
        verdict = self.gate.verify(f, HazardType.HEAT, now=now)
        assert verdict.passed is True  # still evaluate, but penalized
        assert verdict.is_stale is True
        # Confidence factor penalized for staleness
        assert verdict.confidence_factor < 0.85

    def test_gate_penalizes_high_anomaly(self):
        now = datetime.now(timezone.utc)
        t = _build_telemetry(timestamp=now, anomaly_score=0.9, flags=["GLITCH_DETECTED"])
        f = self.extractor.extract(t)
        verdict = self.gate.verify(f, HazardType.HEAT, now=now)
        assert verdict.passed is True
        assert verdict.confidence_factor < 0.60
        assert "GLITCH_DETECTED" in verdict.anomaly_flags
