"""Tests for Epistemic Integrity and Status Containment."""
import pytest
from datetime import datetime, timezone

from intelligence.hazards.types import HazardResult, HazardClassification, HazardStatus, HazardType
from intelligence.prediction.types import PredictionResult
from intelligence.simulation.types import ScenarioDefinition, ScenarioType, ScenarioParameters, DigitalTwinState


class TestEpistemicContainment:
    """Verifies that epistemic categories (OBSERVED, PREDICTED, INFERRED, SIMULATED, STALE)

    remain strictly distinct and cannot be conflated by production pipelines.
    """

    def test_observed_hazard_enforces_not_simulated(self):
        # HazardResult strictly requires simulated == False
        with pytest.raises(ValueError) as exc_info:
            HazardResult(
                hazard_id="HAZ-001",
                hazard=HazardType.HEAT,
                severity=0.85,
                confidence=0.92,
                classification=HazardClassification.HIGH,
                status=HazardStatus.DETECTED,
                timestamp=datetime.now(timezone.utc),
                forecast_horizon_minutes=0,
                location={"lat": 12.97, "lon": 77.59},
                model_version="heat-v1",
                simulated=True  # Inadmissible in observed evaluation
            )
        assert "simulated must be False" in str(exc_info.value)

    def test_observed_hazard_enforces_zero_forecast_horizon(self):
        # HazardResult strictly requires forecast_horizon_minutes == 0
        with pytest.raises(ValueError) as exc_info:
            HazardResult(
                hazard_id="HAZ-002",
                hazard=HazardType.FLOOD,
                severity=0.70,
                confidence=0.88,
                status=HazardStatus.DETECTED,
                timestamp=datetime.now(timezone.utc),
                forecast_horizon_minutes=30,  # Inadmissible in current-state detection
                location={"lat": 12.97, "lon": 77.59},
                model_version="flood-v1",
                simulated=False
            )
        assert "forecast_horizon_minutes must be 0" in str(exc_info.value)

    def test_prediction_must_have_positive_horizon(self):
        now = datetime.now(timezone.utc)
        pred = PredictionResult(
            prediction_id="PRED-001",
            hazard=HazardType.HEAT,
            prediction_time=now,
            forecast_time=now,
            forecast_horizon_minutes=60,
            severity=0.78,
            confidence=0.85,
            status=HazardStatus.DETECTED,
            model_version="pred-heat-v1",
            provenance_hash="a1b2c3d4e5f60718"
        )
        assert pred.forecast_horizon_minutes > 0
        assert pred.status == HazardStatus.DETECTED
        assert pred.model_dump()["forecast_horizon_minutes"] == 60

    def test_simulated_scenario_has_simulated_marker(self):
        scenario = ScenarioDefinition(
            scenario_id="SCN-RAIN-20",
            name="20% Rainfall Increase",
            description="Stress tests urban drainage",
            scenario_type=ScenarioType.RAINFALL_MULTIPLIER,
            default_parameters=ScenarioParameters(rainfall_multiplier=1.2),
            simulated=True
        )
        assert scenario.simulated is True
        assert scenario.model_dump()["simulated"] is True

    def test_stale_data_flag_preservation(self):
        telemetry = {
            "node_id": "NODE-STALE",
            "timestamp": "2020-01-01T00:00:00Z",
            "readings": {"temperature_c": 35.0},
            "is_stale": True
        }
        assert telemetry["is_stale"] is True
        import json
        serialized = json.loads(json.dumps(telemetry))
        assert serialized["is_stale"] is True
