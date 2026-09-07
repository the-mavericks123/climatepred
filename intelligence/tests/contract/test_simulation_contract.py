"""Contract tests for Phase 7: Digital Twin & Scenario Simulation Engine.
Verifies Pydantic schema compliance, strict boundary validation, rejection of invalid inputs,
and structural integrity of benchmark fixtures.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from intelligence.simulation.types import (
    DigitalTwinState,
    ScenarioDefinition,
    ScenarioParameters,
    ScenarioType,
    SimulationCatalogResponse,
    SimulationComparison,
    SimulationResult,
    SimulationRunRequest,
    SimulationRunResponse,
    SimulationSummary,
)


class TestScenarioContract:
    """Validates contract boundaries and parameter rejection."""

    def test_valid_scenario_parameters(self):
        params = ScenarioParameters(
            rainfall_multiplier=1.4,
            temperature_delta=5.0,
            soil_moisture_delta=10.0,
            water_level_delta=1.5,
            drainage_failure_severity=0.5,
            road_accessibility_reduction=0.3,
            target_edge_ids=["ROAD-1", "ROAD-2"],
        )
        assert params.rainfall_multiplier == 1.4
        assert params.temperature_delta == 5.0
        assert params.target_edge_ids == ["ROAD-1", "ROAD-2"]

    def test_invalid_rainfall_multiplier_negative(self):
        with pytest.raises(ValidationError):
            ScenarioParameters(rainfall_multiplier=-0.1)

    def test_invalid_rainfall_multiplier_excessive(self):
        with pytest.raises(ValidationError):
            ScenarioParameters(rainfall_multiplier=10.5)

    def test_invalid_temperature_delta(self):
        with pytest.raises(ValidationError):
            ScenarioParameters(temperature_delta=60.0)

        with pytest.raises(ValidationError):
            ScenarioParameters(temperature_delta=-55.0)

    def test_invalid_soil_moisture_delta(self):
        with pytest.raises(ValidationError):
            ScenarioParameters(soil_moisture_delta=150.0)

    def test_invalid_drainage_failure_severity(self):
        with pytest.raises(ValidationError):
            ScenarioParameters(drainage_failure_severity=1.5)

        with pytest.raises(ValidationError):
            ScenarioParameters(drainage_failure_severity=-0.1)

    def test_invalid_road_accessibility_reduction(self):
        with pytest.raises(ValidationError):
            ScenarioParameters(road_accessibility_reduction=1.2)

    def test_simulation_run_request_validation(self):
        req = SimulationRunRequest(
            scenario_id="SCN-RAIN-20",
            base_state="current",
            changes=ScenarioParameters(rainfall_multiplier=1.2),
        )
        assert req.scenario_id == "SCN-RAIN-20"
        assert req.base_state == "current"
        assert req.changes.rainfall_multiplier == 1.2

    def test_simulation_run_request_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            SimulationRunRequest(scenario_id="")


class TestSimulationFixtures:
    """Verifies that all 7 required simulation benchmark fixtures conform to contracts."""

    FIXTURE_NAMES = [
        "simulation_rain_20.json",
        "simulation_rain_40.json",
        "simulation_rain_60.json",
        "simulation_extreme_heat.json",
        "simulation_drainage_failure.json",
        "simulation_accessibility_degradation.json",
        "simulation_flood_heat.json",
    ]

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_fixture_deserialization_and_simulated_flag(self, fixture_name: str):
        fixture_path = Path("intelligence/tests/fixtures") / fixture_name
        assert fixture_path.exists(), f"Missing required fixture: {fixture_path}"

        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        result = SimulationResult(**raw_data)
        assert result.simulated is True, f"Fixture {fixture_name} must have simulated=True"
        assert result.simulation_id.startswith("SIM-")
        assert len(result.provenance_hash) == 64
        assert len(result.hazards) > 0
        for v in result.vulnerability_zones:
            assert v.simulated is True
        for e in result.evacuation_routes:
            assert e.simulated is True
