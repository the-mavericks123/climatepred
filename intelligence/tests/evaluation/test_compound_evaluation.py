"""
Deterministic evaluation benchmark scenarios for Phase 4: Compound & Cascading Disaster Engine.
Runs 10 explicit scenarios and checks expected behavior, chain structure, and severity/confidence bounds.
"""

from datetime import datetime, timezone, timedelta
import pytest

from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.hazards.types import HazardClassification, HazardResult, HazardStatus, HazardType
from intelligence.prediction.types import PredictionResult
from intelligence.core.contracts.telemetry import LocationCoordinate

T_BASE = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
LOC = LocationCoordinate(lat=25.5941, lon=85.1376)


def _h(hazard: HazardType, severity: float, conf: float = 0.90, dt_min: int = 0, feats: dict = None) -> HazardResult:
    return HazardResult(
        hazard_id=f"HAZ-{hazard.value.upper()}",
        hazard=hazard,
        severity=severity,
        confidence=conf,
        classification=HazardClassification.HIGH if severity >= 0.70 else HazardClassification.NORMAL,
        status=HazardStatus.DETECTED if severity >= 0.35 else HazardStatus.NOT_DETECTED,
        timestamp=T_BASE + timedelta(minutes=dt_min),
        forecast_horizon_minutes=0,
        location=LOC,
        features=feats or {},
        drivers=[f"{hazard.value} active"],
        model_version=f"{hazard.value}-v1",
        simulated=False,
    )


def _p(hazard: HazardType, severity: float, horizon: int = 60, conf: float = 0.85, feats: dict = None) -> PredictionResult:
    return PredictionResult(
        prediction_id=f"PRED-{hazard.value.upper()}-{horizon}M",
        hazard=hazard,
        prediction_time=T_BASE,
        forecast_time=T_BASE + timedelta(minutes=horizon),
        forecast_horizon_minutes=horizon,
        severity=severity,
        confidence=conf,
        classification=HazardClassification.HIGH if severity >= 0.70 else HazardClassification.MODERATE,
        status=HazardStatus.DETECTED,
        model_version=f"{hazard.value}-pred-v1",
        provenance_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        drivers=[f"Predicted {hazard.value}"],
        predicted_features=feats or {},
        simulated=False,
    )


class TestCompoundBenchmarks:
    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = CompoundDisasterEngine()

    def test_scenario_1_normal_environment(self):
        """Scenario 1: Mild / normal conditions -> No compound or cascade events."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.HEAT, 0.15), _h(HazardType.FLOOD, 0.10)],
            predictions=[],
        )
        assert len(events) == 0

    def test_scenario_2_heat_only(self):
        """Scenario 2: Single heat hazard without drought -> No compound event."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.HEAT, 0.75)],
            predictions=[],
        )
        assert len(events) == 0

    def test_scenario_3_drought_only(self):
        """Scenario 3: Single drought hazard -> No compound event."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.DROUGHT, 0.80)],
            predictions=[],
        )
        assert len(events) == 0

    def test_scenario_4_flood_only_without_access_damage(self):
        """Scenario 4: Moderate flood alone -> Triggers cascade to inferred road failure."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.FLOOD, 0.75)],
            predictions=[],
        )
        assert len(events) >= 1
        cascade = next(e for e in events if e.event_type == "CASCADE")
        assert "flood" in cascade.chain

    def test_scenario_5_heat_and_drought_compound(self):
        """Scenario 5: Concurrent severe heat and drought -> Compound multihazard event."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.HEAT, 0.78), _h(HazardType.DROUGHT, 0.82)],
            predictions=[],
        )
        compound = next(e for e in events if e.event_type == "COMPOUND")
        assert "heat" in compound.chain
        assert "drought" in compound.chain
        assert compound.severity >= 0.85

    def test_scenario_6_heavy_rain_soil_flood_cascade(self):
        """Scenario 6: High rainfall with saturated soil -> Rapid surface flood cascade."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.FLOOD, 0.80, feats={"rainfall": 80.0, "soil_moisture": 90.0})],
            predictions=[],
        )
        chains = [e.chain for e in events if e.event_type == "CASCADE"]
        assert any("soil_saturation" in c for c in chains)

    def test_scenario_7_flood_to_access_degradation(self):
        """Scenario 7: Critical flood -> Inundation -> Inferred Access Loss."""
        events = self.engine.evaluate(
            hazards=[_h(HazardType.FLOOD, 0.90, feats={"water_level": 15.0})],
            predictions=[],
        )
        cascade = next(e for e in events if e.event_type == "CASCADE")
        assert "inferred_road_failure_risk" in cascade.chain
        assert "inferred_access_loss" in cascade.chain

    def test_scenario_8_predicted_flood_cascade(self):
        """Scenario 8: Future predicted flood at +60m -> Future predicted access loss."""
        events = self.engine.evaluate(
            hazards=[],
            predictions=[_p(HazardType.FLOOD, 0.85, horizon=60, feats={"water_level": 11.0})],
        )
        cascade = next(e for e in events if e.event_type == "CASCADE")
        assert cascade.chain[0] == "flood"
        assert "predicted_access_loss" in cascade.chain or "inferred_road_failure_risk" in cascade.chain

    def test_scenario_9_multiple_simultaneous_hazards(self):
        """Scenario 9: Co-occurring heat, drought, and flood -> Multi-event discovery."""
        events = self.engine.evaluate(
            hazards=[
                _h(HazardType.HEAT, 0.76),
                _h(HazardType.DROUGHT, 0.80),
                _h(HazardType.FLOOD, 0.75),
            ],
            predictions=[],
        )
        assert len(events) >= 2

    def test_scenario_10_missing_and_unrelated_data(self):
        """Scenario 10: Missing data or temporally disconnected events -> Safe handling, 0 false events."""
        events = self.engine.evaluate(
            hazards=[
                _h(HazardType.HEAT, 0.80, dt_min=0),
                _h(HazardType.DROUGHT, 0.80, dt_min=300),  # 5 hours apart
            ],
            predictions=[],
        )
        compound_events = [e for e in events if "heat" in e.chain and "drought" in e.chain]
        assert len(compound_events) == 0
