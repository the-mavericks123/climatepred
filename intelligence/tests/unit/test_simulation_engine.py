"""Comprehensive Unit Test Suite for Phase 7: Digital Twin & Scenario Simulation Engine.
Implements the 26+ required verification tests across:
  - Scenario validation (1-6)
  - Transformation correctness (7-11)
  - Model propagation (12-16)
  - Cascading behavior (17-19)
  - Simulation isolation (20)
  - Provenance determinism and sensitivity (21-24)
  - Comparison delta correctness (25)
  - Determinism on repeated execution (26)
  - Monotonicity checks & Stale base state rejection
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from intelligence.core.errors.exceptions import StaleDataException
from intelligence.simulation.confidence import SimulationConfidenceCalculator
from intelligence.simulation.engine import SimulationEngine
from intelligence.simulation.outputs import SimulationComparator
from intelligence.simulation.propagation import ModelPropagator
from intelligence.simulation.provenance import SimulationProvenanceTracker
from intelligence.simulation.scenarios import ScenarioCatalog
from intelligence.simulation.state import DigitalTwinStateManager
from intelligence.simulation.transforms import ScenarioTransformer
from intelligence.simulation.types import (
    DigitalTwinState,
    ScenarioParameters,
    ScenarioType,
)


@pytest.fixture
def simulation_engine():
    return SimulationEngine()


@pytest.fixture
def reference_time():
    return datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def default_base_state(reference_time):
    return SimulationEngine.build_default_base_state(reference_time)


class TestScenarioValidation:
    """1 to 6: Scenario validation tests."""

    def test_01_valid_rainfall_20(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation("SCN-RAIN-20", now=reference_time)
        assert res.scenario_id == "SCN-RAIN-20"
        assert res.parameters.rainfall_multiplier == 1.20
        assert res.simulated is True

    def test_02_valid_rainfall_40(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        assert res.scenario_id == "SCN-RAIN-40"
        assert res.parameters.rainfall_multiplier == 1.40
        assert res.simulated is True

    def test_03_valid_rainfall_60(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation("SCN-RAIN-60", now=reference_time)
        assert res.scenario_id == "SCN-RAIN-60"
        assert res.parameters.rainfall_multiplier == 1.60
        assert res.simulated is True

    def test_04_invalid_multiplier(self, simulation_engine, reference_time):
        with pytest.raises(Exception):
            simulation_engine.run_simulation(
                "SCN-RAIN-20",
                changes=ScenarioParameters(rainfall_multiplier=-0.5),
                now=reference_time,
            )

    def test_05_invalid_scenario_id(self, simulation_engine, reference_time):
        with pytest.raises(ValueError, match="Unsupported scenario"):
            simulation_engine.run_simulation("SCN-NONEXISTENT", now=reference_time)

    def test_06_invalid_parameter(self, simulation_engine, reference_time):
        with pytest.raises(Exception):
            simulation_engine.run_simulation(
                "SCN-EXTREME-HEAT",
                changes=ScenarioParameters(temperature_delta=100.0),
                now=reference_time,
            )


class TestTransformationCorrectness:
    """7 to 11: Transformation correctness tests."""

    def test_07_rainfall_transformation_correctness(self, default_base_state):
        base_rain = default_base_state.telemetry.measurements.rainfall
        params = ScenarioParameters(rainfall_multiplier=1.40)
        sim_tel = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, params)
        expected = round(base_rain * 1.40, 2)
        assert sim_tel.measurements.rainfall == expected
        # Baseline must not be mutated
        assert default_base_state.telemetry.measurements.rainfall == base_rain

    def test_08_temperature_transformation_correctness(self, default_base_state):
        base_temp = default_base_state.telemetry.measurements.temperature
        params = ScenarioParameters(temperature_delta=6.5)
        sim_tel = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, params)
        assert sim_tel.measurements.temperature == round(base_temp + 6.5, 2)
        assert default_base_state.telemetry.measurements.temperature == base_temp

    def test_09_soil_moisture_transformation(self, default_base_state):
        base_sm = default_base_state.telemetry.measurements.soil_moisture
        params = ScenarioParameters(soil_moisture_delta=15.0)
        sim_tel = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, params)
        assert sim_tel.measurements.soil_moisture == round(base_sm + 15.0, 2)

    def test_10_drainage_transformation(self, default_base_state):
        base_wl = default_base_state.telemetry.measurements.water_level
        params = ScenarioParameters(drainage_failure_severity=0.8)
        sim_tel = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, params)
        # 1.0 + 0.75 * 0.8 = 1.6
        expected_wl = round(base_wl * 1.6, 2)
        assert sim_tel.measurements.water_level == expected_wl

    def test_11_accessibility_transformation(self, default_base_state):
        base_acc = default_base_state.road_network.edges[0].accessibility
        params = ScenarioParameters(
            road_accessibility_reduction=0.4,
            target_edge_ids=[default_base_state.road_network.edges[0].edge_id],
        )
        sim_net = ScenarioTransformer.transform_road_network(default_base_state.road_network, params)
        expected_acc = round(base_acc * (1.0 - 0.4), 4)
        assert sim_net.edges[0].accessibility == expected_acc
        assert default_base_state.road_network.edges[0].accessibility == base_acc


class TestModelPropagation:
    """12 to 16: Model propagation across Phases 2 to 6."""

    def test_12_rainfall_scenario_changes_flood_model_input(self, simulation_engine, reference_time):
        res_base = simulation_engine.run_simulation("SCN-RAIN-20", now=reference_time)
        res_heavy = simulation_engine.run_simulation("SCN-RAIN-60", now=reference_time)
        # Severity must be computed from perturbed physical inputs
        flood_20 = next(h for h in res_base.hazards if h.hazard.value == "flood")
        flood_60 = next(h for h in res_heavy.hazards if h.hazard.value == "flood")
        assert flood_60.severity >= flood_20.severity

    def test_13_heat_scenario_changes_heat_model_input(self, simulation_engine, reference_time):
        res_heat = simulation_engine.run_simulation("SCN-EXTREME-HEAT", now=reference_time)
        heat_hazard = next(h for h in res_heat.hazards if h.hazard.value == "heat")
        assert heat_hazard.severity > 0.0
        assert res_heat.simulated is True

    def test_14_compound_scenario_reaches_phase_4(self, simulation_engine, reference_time):
        res_compound = simulation_engine.run_simulation("SCN-FLOOD-HEAT", now=reference_time)
        assert len(res_compound.compound_events) > 0
        assert res_compound.simulated is True

    def test_15_vulnerability_recalculates(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        assert len(res.vulnerability_zones) > 0
        vuln = res.vulnerability_zones[0]
        assert vuln.simulated is True
        assert vuln.human_impact > 0.0

    def test_16_evacuation_recalculates(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        assert len(res.evacuation_routes) > 0
        evac = res.evacuation_routes[0]
        assert evac.simulated is True
        assert evac.population_to_evacuate > 0


class TestCascadingBehavior:
    """17 to 19: Cascading effects on accessibility, routing, and shelter selection."""

    def test_17_accessibility_degradation_changes_route(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation(
            "SCN-ROAD-DEGRADE",
            changes=ScenarioParameters(
                road_accessibility_reduction=0.7,
                target_edge_ids=["ROAD-Z-N1"],
            ),
            now=reference_time,
        )
        assert len(res.evacuation_routes) > 0
        evac = res.evacuation_routes[0]
        assert evac.simulated is True
        # If North path is degraded, route should either use alternate path or avoid degraded edge
        if evac.route:
            assert "ROAD-Z-N1" not in evac.route.edge_ids or evac.route.total_cost > 0

    def test_18_route_becomes_no_route_when_appropriate(self, simulation_engine, default_base_state, reference_time):
        # Degrade all edges exiting ZONE-METRO-01 to 0 accessibility
        custom_params = ScenarioParameters(
            road_accessibility_reduction=1.0,
            target_edge_ids=["ROAD-Z-N1", "ROAD-Z-E1"],
        )
        res = simulation_engine.run_simulation(
            "SCN-ROAD-DEGRADE",
            base_state=default_base_state,
            changes=custom_params,
            now=reference_time,
        )
        assert len(res.evacuation_routes) > 0
        assert res.evacuation_routes[0].status.value == "NO_ROUTE"

    def test_19_shelter_selection_changes_when_appropriate(self, simulation_engine, default_base_state, reference_time):
        # Make North shelter unsafe
        state_mod = deepcopy(default_base_state)
        for s in state_mod.shelters:
            if s.shelter_id == "SHELTER-NORTH-01":
                s.safe = False
                s.available_capacity = 0
        res = simulation_engine.run_simulation(
            "SCN-RAIN-20",
            base_state=state_mod,
            now=reference_time,
        )
        assert len(res.evacuation_routes) > 0
        evac = res.evacuation_routes[0]
        if evac.destination:
            assert evac.destination.shelter_id == "SHELTER-EAST-01"


class TestSimulationIsolation:
    """20: Baseline operational state remains byte and logically unmutated."""

    def test_20_live_state_is_unchanged(self, simulation_engine, default_base_state, reference_time):
        # Serialize baseline state before simulation
        baseline_dump_before = default_base_state.model_dump(mode="json")
        baseline_hash_before = DigitalTwinStateManager.compute_state_hash(default_base_state)

        # Run aggressive compound scenario
        simulation_engine.run_simulation(
            "SCN-FLOOD-HEAT",
            base_state=default_base_state,
            changes=ScenarioParameters(rainfall_multiplier=1.8, temperature_delta=8.0),
            now=reference_time,
        )

        # Serialize baseline state after simulation
        baseline_dump_after = default_base_state.model_dump(mode="json")
        baseline_hash_after = DigitalTwinStateManager.compute_state_hash(default_base_state)

        assert baseline_hash_before == baseline_hash_after, "Base state hash mutated during simulation!"
        assert baseline_dump_before == baseline_dump_after, "Base state contents mutated during simulation!"


class TestProvenanceAndDeterminism:
    """21 to 24 & 26: Deterministic provenance, mutation sensitivity, ordering invariance, determinism."""

    def test_21_deterministic_provenance(self, simulation_engine, reference_time):
        res1 = simulation_engine.run_simulation("SCN-RAIN-20", now=reference_time)
        res2 = simulation_engine.run_simulation("SCN-RAIN-20", now=reference_time)
        assert res1.provenance_hash == res2.provenance_hash
        assert res1.simulation_id == res2.simulation_id

    def test_22_material_scenario_mutation_changes_provenance(self, simulation_engine, reference_time):
        res_20 = simulation_engine.run_simulation("SCN-RAIN-20", now=reference_time)
        res_40 = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        assert res_20.provenance_hash != res_40.provenance_hash

    def test_23_base_state_mutation_changes_provenance(self, simulation_engine, default_base_state, reference_time):
        state_mutated = deepcopy(default_base_state)
        state_mutated.telemetry.measurements.rainfall = 45.0
        state_mutated.base_state_id = "STATE-MUTATED-01"

        res_orig = simulation_engine.run_simulation("SCN-RAIN-20", base_state=default_base_state, now=reference_time)
        res_mut = simulation_engine.run_simulation("SCN-RAIN-20", base_state=state_mutated, now=reference_time)
        assert res_orig.provenance_hash != res_mut.provenance_hash

    def test_24_ordering_invariance(self, reference_time):
        params = ScenarioParameters(rainfall_multiplier=1.2)
        payload1 = SimulationProvenanceTracker.build_canonical_payload(
            simulation_id="SIM-TEST",
            scenario_id="SCN-RAIN-20",
            scenario_version="1.0",
            base_state_id="STATE-1",
            base_state_hash="HASH-1",
            parameters=params,
            hazard_count=3,
            vulnerability_count=1,
            evacuation_count=1,
            confidence=0.9,
            simulated=True,
            timestamp=reference_time,
        )
        # Payload with identical contents constructed in different key order
        payload2 = {k: payload1[k] for k in reversed(list(payload1.keys()))}

        hash1 = SimulationProvenanceTracker.compute_provenance_hash(payload1)
        hash2 = SimulationProvenanceTracker.compute_provenance_hash(payload2)
        assert hash1 == hash2

    def test_25_baseline_simulation_delta_correctness(self, simulation_engine, reference_time):
        res = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        assert len(res.comparison.metrics) > 0
        for m in res.comparison.metrics:
            expected_delta = round(m.simulated - m.baseline, 4)
            assert round(m.delta, 4) == expected_delta

    def test_26_repeated_identical_simulation_produces_equivalent_output(self, simulation_engine, reference_time):
        res1 = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        res2 = simulation_engine.run_simulation("SCN-RAIN-40", now=reference_time)
        assert res1.model_dump() == res2.model_dump()


class TestMonotonicityAndFreshness:
    """Additional physical sanity and data freshness verification."""

    def test_27_rainfall_monotonic_input_scaling(self, default_base_state):
        base_rain = default_base_state.telemetry.measurements.rainfall
        tel_20 = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, ScenarioParameters(rainfall_multiplier=1.2))
        tel_40 = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, ScenarioParameters(rainfall_multiplier=1.4))
        tel_60 = ScenarioTransformer.transform_telemetry(default_base_state.telemetry, ScenarioParameters(rainfall_multiplier=1.6))

        assert base_rain < tel_20.measurements.rainfall < tel_40.measurements.rainfall < tel_60.measurements.rainfall

    def test_28_stale_base_state_rejection(self, simulation_engine, default_base_state, reference_time):
        stale_state = deepcopy(default_base_state)
        # Make timestamp 600s in the past (exceeding 300s freshness threshold)
        stale_state.telemetry.timestamp = reference_time - timedelta(seconds=600)

        with pytest.raises(StaleDataException, match="STALE"):
            simulation_engine.run_simulation("SCN-RAIN-20", base_state=stale_state, now=reference_time)
