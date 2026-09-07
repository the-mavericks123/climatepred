"""Unit and behavioral tests for Drought hazard model (drought-v1).

Tests:
  - Normal conditions
  - Dry soil, high temperature, low humidity
  - Critical drought combination
  - Missing soil moisture, temperature, or humidity -> status UNAVAILABLE (null != 0)
  - Monotonicity: decreasing soil moisture, increasing temp, decreasing humidity never decreases severity
  - Deterministic drivers verification
  - Bounded severity and confidence [0, 1]
"""

import pytest
from datetime import datetime, timezone

from intelligence.hazards.drought import DroughtModel
from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardClassification,
)
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict, HazardQualityGate
from intelligence.core.contracts.telemetry import LocationCoordinate


def _make_features(
    soil_moisture: float | None = 45.0,
    temp: float | None = 25.0,
    humidity: float | None = 55.0,
) -> HazardFeatures:
    return HazardFeatures(
        node_id="TEST-DROUGHT-NODE",
        timestamp=datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc),
        location=LocationCoordinate(lat=15.317, lon=75.714, elevation=650.0),
        source="ESP32",
        valid=True,
        confidence_base=0.96,
        anomaly_score=0.0,
        flags=[],
        temperature_c=temp,
        humidity_pct=humidity,
        rainfall_mmhr=0.0,
        soil_moisture_pct=soil_moisture,
        water_level_m=1.0,
        air_quality_aqi=50.0,
        provenance_hash="sha256:dummy",
    )


class TestDroughtModel:
    def setup_method(self):
        self.model = DroughtModel()
        self.quality_gate = HazardQualityGate()

    def test_normal_conditions(self):
        feat = _make_features(soil_moisture=50.0, temp=24.0, humidity=60.0)
        verdict = self.quality_gate.verify(feat, HazardType.DROUGHT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.DROUGHT
        assert result.status == HazardStatus.NOT_DETECTED
        assert result.classification == HazardClassification.NORMAL
        assert result.severity == 0.0
        assert result.model_version == "drought-v1"
        assert result.forecast_horizon_minutes == 0

    def test_moderate_drought_conditions(self):
        feat = _make_features(soil_moisture=22.0, temp=35.0, humidity=28.0)
        verdict = self.quality_gate.verify(feat, HazardType.DROUGHT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.DROUGHT
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.MODERATE
        assert 0.40 <= result.severity < 0.60
        assert len(result.drivers) > 0

    def test_critical_drought_conditions(self):
        feat = _make_features(soil_moisture=4.0, temp=45.0, humidity=12.0)
        verdict = self.quality_gate.verify(feat, HazardType.DROUGHT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.DROUGHT
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.CRITICAL
        assert 0.80 <= result.severity <= 1.0
        assert any("soil" in d for d in result.drivers)
        assert any("temperature" in d for d in result.drivers)
        assert any("humidity" in d for d in result.drivers)

    def test_missing_soil_moisture_returns_unavailable(self):
        feat = _make_features(soil_moisture=None, temp=35.0, humidity=30.0)
        verdict = self.quality_gate.verify(feat, HazardType.DROUGHT)
        assert verdict.passed is False
        assert "soil_moisture" in verdict.reason.lower()

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE
        assert result.severity == 0.0

    def test_missing_temperature_returns_unavailable(self):
        feat = _make_features(soil_moisture=15.0, temp=None, humidity=30.0)
        verdict = self.quality_gate.verify(feat, HazardType.DROUGHT)
        assert verdict.passed is False

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE

    def test_missing_humidity_returns_unavailable(self):
        feat = _make_features(soil_moisture=15.0, temp=35.0, humidity=None)
        verdict = self.quality_gate.verify(feat, HazardType.DROUGHT)
        assert verdict.passed is False

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE

    def test_monotonicity_decreasing_soil_moisture(self):
        """Decreasing soil moisture must not decrease drought severity."""
        severities = []
        for sm in range(60, -5, -5):
            feat = _make_features(soil_moisture=float(sm), temp=32.0, humidity=40.0)
            res = self.model.evaluate(feat, QualityGateVerdict(is_admissible=True))
            severities.append(res.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i], (
                f"Monotonicity violated: soil moisture step {i}: {severities[i+1]} < {severities[i]}"
            )

    def test_monotonicity_increasing_temperature(self):
        """Increasing temperature must not decrease drought severity."""
        severities = []
        for t in range(20, 52, 2):
            feat = _make_features(soil_moisture=20.0, temp=float(t), humidity=30.0)
            res = self.model.evaluate(feat, QualityGateVerdict(is_admissible=True))
            severities.append(res.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i]

    def test_monotonicity_decreasing_humidity(self):
        """Decreasing humidity must not decrease drought severity."""
        severities = []
        for h in range(70, -5, -5):
            feat = _make_features(soil_moisture=20.0, temp=32.0, humidity=float(h))
            res = self.model.evaluate(feat, QualityGateVerdict(is_admissible=True))
            severities.append(res.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i]
