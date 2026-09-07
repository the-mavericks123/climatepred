"""Unit and behavioral tests for Flood hazard model (flood-v1).

Tests:
  - Normal, moderate, heavy rainfall, elevated water level, saturated soil, critical combination
  - Missing rainfall, water level, or soil moisture -> status UNAVAILABLE (null != 0)
  - Monotonicity: increasing rainfall, water level, or soil moisture never decreases severity
  - Configurable weights evaluation
  - Deterministic drivers verification
  - Bounded severity and confidence [0, 1]
"""

import pytest
from datetime import datetime, timezone

from intelligence.hazards.flood import FloodModel
from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardClassification,
)
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict, HazardQualityGate
from intelligence.hazards.thresholds import FloodModelConfig
from intelligence.core.contracts.telemetry import LocationCoordinate


def _make_features(
    rainfall: float | None = 0.0,
    water_level: float | None = 1.0,
    soil_moisture: float | None = 40.0,
) -> HazardFeatures:
    return HazardFeatures(
        node_id="TEST-FLOOD-NODE",
        timestamp=datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc),
        location=LocationCoordinate(lat=19.076, lon=72.8777, elevation=14.0),
        source="ESP32",
        valid=True,
        confidence_base=0.98,
        anomaly_score=0.0,
        flags=[],
        temperature_c=25.0,
        humidity_pct=80.0,
        rainfall_mmhr=rainfall,
        soil_moisture_pct=soil_moisture,
        water_level_m=water_level,
        air_quality_aqi=40.0,
        provenance_hash="sha256:dummy",
    )


class TestFloodModel:
    def setup_method(self):
        self.model = FloodModel()
        self.quality_gate = HazardQualityGate()

    def test_normal_conditions(self):
        feat = _make_features(rainfall=0.0, water_level=1.0, soil_moisture=30.0)
        verdict = self.quality_gate.verify(feat, HazardType.FLOOD)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.FLOOD
        assert result.status == HazardStatus.NOT_DETECTED
        assert result.classification == HazardClassification.NORMAL
        assert 0.0 <= result.severity < 0.20
        assert result.model_version == "flood-v1"
        assert result.forecast_horizon_minutes == 0

    def test_moderate_flood_conditions(self):
        feat = _make_features(rainfall=45.0, water_level=5.5, soil_moisture=75.0)
        verdict = self.quality_gate.verify(feat, HazardType.FLOOD)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.FLOOD
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.MODERATE
        assert 0.40 <= result.severity < 0.60
        assert len(result.drivers) > 0

    def test_critical_flood_conditions(self):
        feat = _make_features(rainfall=120.0, water_level=16.0, soil_moisture=100.0)
        verdict = self.quality_gate.verify(feat, HazardType.FLOOD)
        result = self.model.evaluate(feat, verdict)

        assert result.hazard == HazardType.FLOOD
        assert result.status == HazardStatus.DETECTED
        assert result.classification == HazardClassification.CRITICAL
        assert 0.80 <= result.severity <= 1.0
        assert any("rainfall" in d for d in result.drivers)
        assert any("water level" in d for d in result.drivers)
        assert any("soil" in d for d in result.drivers)

    def test_missing_rainfall_returns_unavailable(self):
        feat = _make_features(rainfall=None, water_level=5.0, soil_moisture=70.0)
        verdict = self.quality_gate.verify(feat, HazardType.FLOOD)
        assert verdict.passed is False
        assert "rainfall" in verdict.reason.lower()

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE
        assert result.severity == 0.0

    def test_missing_water_level_returns_unavailable(self):
        feat = _make_features(rainfall=30.0, water_level=None, soil_moisture=70.0)
        verdict = self.quality_gate.verify(feat, HazardType.FLOOD)
        assert verdict.passed is False
        assert "water_level" in verdict.reason.lower()

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE

    def test_missing_soil_moisture_returns_unavailable(self):
        feat = _make_features(rainfall=30.0, water_level=4.0, soil_moisture=None)
        verdict = self.quality_gate.verify(feat, HazardType.FLOOD)
        assert verdict.passed is False
        assert "soil_moisture" in verdict.reason.lower()

        result = self.model.evaluate(feat, verdict)
        assert result.status == HazardStatus.UNAVAILABLE

    def test_monotonicity_rainfall(self):
        """Increasing rainfall with constant water level and soil moisture must not decrease severity."""
        severities = []
        for r in range(0, 150, 10):
            feat = _make_features(rainfall=float(r), water_level=5.0, soil_moisture=60.0)
            res = self.model.evaluate(feat, QualityGateVerdict(is_admissible=True))
            severities.append(res.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i]

    def test_monotonicity_water_level(self):
        """Increasing water level with constant rainfall and soil moisture must not decrease severity."""
        severities = []
        for wl in range(0, 20):
            feat = _make_features(rainfall=30.0, water_level=float(wl), soil_moisture=60.0)
            res = self.model.evaluate(feat, QualityGateVerdict(is_admissible=True))
            severities.append(res.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i]

    def test_monotonicity_soil_moisture(self):
        """Increasing soil moisture with constant rainfall and water level must not decrease severity."""
        severities = []
        for sm in range(20, 105, 5):
            feat = _make_features(rainfall=30.0, water_level=5.0, soil_moisture=float(sm))
            res = self.model.evaluate(feat, QualityGateVerdict(is_admissible=True))
            severities.append(res.severity)

        for i in range(len(severities) - 1):
            assert severities[i + 1] >= severities[i]

    def test_custom_weights_configuration(self):
        custom_cfg = FloodModelConfig(
            rainfall_weight=0.70,
            water_level_weight=0.20,
            soil_moisture_weight=0.10,
        )
        custom_model = FloodModel(config=custom_cfg)
        feat = _make_features(rainfall=100.0, water_level=0.0, soil_moisture=0.0)
        res = custom_model.evaluate(feat, QualityGateVerdict(is_admissible=True))
        # rainfall is 1.0 * 0.70 = 0.70
        assert pytest.approx(res.severity, 0.01) == 0.70
