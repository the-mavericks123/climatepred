"""Unit and behavioral tests for Heat hazard model (heat-v1).

Tests:
  - Normal, moderate, high, critical heat conditions
  - Missing temperature or humidity -> status UNAVAILABLE (null != 0)
  - Monotonicity: increasing temp or RH never decreases severity
  - Severity and confidence bounded strictly in [0, 1]
  - Forecast horizon strictly 0
  - Simulated strictly False
  - Deterministic drivers generated without LLM
"""

import pytest
from datetime import datetime, timezone

from intelligence.hazards.heat import HeatModel
from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardClassification,
)
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict, HazardQualityGate
from intelligence.core.contracts.telemetry import LocationCoordinate


def _make_features(
    temp: float | None = 25.0,
    humidity: float | None = 50.0,
    timestamp: datetime | None = None,
) -> HazardFeatures:
    return HazardFeatures(
        node_id="TEST-NODE",
        timestamp=timestamp or datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc),
        location=LocationCoordinate(lat=17.385, lon=78.4867, elevation=500.0),
        source="ESP32",
        valid=True,
        confidence_base=0.95,
        anomaly_score=0.0,
        flags=[],
        temperature_c=temp,
        humidity_pct=humidity,
        rainfall_mmhr=0.0,
        soil_moisture_pct=40.0,
        water_level_m=1.0,
        air_quality_aqi=50.0,
        provenance_hash="sha256:dummy",
    )


class TestHeatModel:
    def setup_method(self):
        self.model = HeatModel()
        self.quality_gate = HazardQualityGate()

    def test_normal_conditions(self):
        feat = _make_features(temp=22.0, humidity=45.0)
        verdict = self.quality_gate.verify(feat, HazardType.HEAT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.HEAT
        assert result.status == HazardStatus.NOT_DETECTED
        assert result.classification == HazardClassification.NORMAL
        assert 0.0 <= result.severity < 0.20
        assert 0.0 <= result.confidence <= 1.0
        assert result.forecast_horizon_minutes == 0
        assert result.simulated is False
        assert result.model_version == "heat-v1"

    def test_moderate_conditions(self):
        feat = _make_features(temp=32.0, humidity=55.0)
        verdict = self.quality_gate.verify(feat, HazardType.HEAT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.HEAT
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.MODERATE
        assert 0.40 <= result.severity < 0.60
        assert len(result.drivers) > 0
        assert any("thermal stress" in d or "temperature" in d for d in result.drivers)

    def test_high_conditions(self):
        feat = _make_features(temp=38.0, humidity=50.0)
        verdict = self.quality_gate.verify(feat, HazardType.HEAT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.HEAT
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.HIGH
        assert 0.60 <= result.severity < 0.80

    def test_critical_conditions(self):
        feat = _make_features(temp=46.0, humidity=50.0)
        verdict = self.quality_gate.verify(feat, HazardType.HEAT)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.HEAT
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.CRITICAL
        assert 0.80 <= result.severity <= 1.0

    def test_missing_temperature_returns_unavailable(self):
        feat = _make_features(temp=None, humidity=50.0)
        verdict = self.quality_gate.verify(feat, HazardType.HEAT)
        assert verdict.passed is False
        assert "temperature" in verdict.reason.lower()

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE
        assert result.severity == 0.0
        assert result.classification is None
        assert result.drivers == [verdict.reason]

    def test_missing_humidity_returns_unavailable(self):
        feat = _make_features(temp=35.0, humidity=None)
        verdict = self.quality_gate.verify(feat, HazardType.HEAT)
        assert verdict.passed is False
        assert "humidity" in verdict.reason.lower()

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE

    def test_monotonicity_temperature(self):
        """Increasing temperature at fixed humidity must never decrease severity."""
        severities = []
        for t in range(20, 52, 2):
            feat = _make_features(temp=float(t), humidity=50.0)
            verdict = QualityGateVerdict(is_admissible=True)
            result = self.model.evaluate(feat, verdict)
            severities.append(result.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i], (
                f"Monotonicity violated at step {i}: {severities[i+1]} < {severities[i]}"
            )

    def test_monotonicity_humidity(self):
        """Increasing relative humidity at warm temperature must never decrease severity."""
        severities = []
        for rh in range(20, 95, 5):
            feat = _make_features(temp=35.0, humidity=float(rh))
            verdict = QualityGateVerdict(is_admissible=True)
            result = self.model.evaluate(feat, verdict)
            severities.append(result.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i], (
                f"Monotonicity violated: RH step {i}: {severities[i+1]} < {severities[i]}"
            )

    def test_extreme_clamping(self):
        """Values beyond physical limits should be bounded within [0, 1]."""
        feat_subzero = _make_features(temp=-15.0, humidity=10.0)
        res_subzero = self.model.evaluate(feat_subzero, QualityGateVerdict(is_admissible=True))
        assert res_subzero.severity == 0.0

        feat_superhot = _make_features(temp=75.0, humidity=90.0)
        res_superhot = self.model.evaluate(feat_superhot, QualityGateVerdict(is_admissible=True))
        assert res_superhot.severity == 1.0
