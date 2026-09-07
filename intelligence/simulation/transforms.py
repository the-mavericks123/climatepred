"""
Deterministic scenario transformations for Phase 7: Digital Twin + Scenario Simulation Engine.
Implements bounded, pure mathematical transforms on telemetry and network topology without
mutating baseline state.
"""

from copy import deepcopy
from typing import List, Tuple
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.evacuation.types import RoadNetwork
from intelligence.simulation.types import ScenarioParameters


class ScenarioTransformer:
    """
    Applies deterministic mathematical transformations to telemetry and road network graphs.
    All transformations are pure functions returning new, deeply-copied instances.
    """

    TRANSFORM_VERSION = "sim-trans-v1"

    # Physical clamping bounds
    MAX_RAINFALL_MM_HR = 300.0
    MIN_TEMP_C = -40.0
    MAX_TEMP_C = 65.0
    MIN_SOIL_PCT = 0.0
    MAX_SOIL_PCT = 100.0
    MIN_WATER_M = 0.0
    MAX_WATER_M = 30.0

    @classmethod
    def transform_telemetry(
        cls,
        telemetry: NormalizedTelemetry,
        parameters: ScenarioParameters,
    ) -> NormalizedTelemetry:
        """
        Creates a modified, simulated NormalizedTelemetry copy by applying parameter shifts.
        Does NOT mutate the original telemetry instance.
        """
        t_copy = telemetry.model_copy(deep=True)

        # 1. Rainfall Multiplier
        if parameters.rainfall_multiplier is not None:
            mult = parameters.rainfall_multiplier
            if t_copy.measurements.rainfall is not None:
                new_rain = round(min(cls.MAX_RAINFALL_MM_HR, t_copy.measurements.rainfall * mult), 2)
                t_copy.measurements.rainfall = new_rain

        # 2. Temperature Delta
        if parameters.temperature_delta is not None:
            delta = parameters.temperature_delta
            if t_copy.measurements.temperature is not None:
                new_temp = round(max(cls.MIN_TEMP_C, min(cls.MAX_TEMP_C, t_copy.measurements.temperature + delta)), 2)
                t_copy.measurements.temperature = new_temp

        # 3. Soil Moisture Delta
        if parameters.soil_moisture_delta is not None:
            delta = parameters.soil_moisture_delta
            if t_copy.measurements.soil_moisture is not None:
                new_sm = round(max(cls.MIN_SOIL_PCT, min(cls.MAX_SOIL_PCT, t_copy.measurements.soil_moisture + delta)), 2)
                t_copy.measurements.soil_moisture = new_sm

        # 4. Water Level Delta
        if parameters.water_level_delta is not None:
            delta = parameters.water_level_delta
            if t_copy.measurements.water_level is not None:
                new_wl = round(max(cls.MIN_WATER_M, min(cls.MAX_WATER_M, t_copy.measurements.water_level + delta)), 2)
                t_copy.measurements.water_level = new_wl

        # 5. Drainage Failure Severity
        # Elevates effective water level and runoff saturation based on drainage failure severity
        if parameters.drainage_failure_severity is not None:
            sev = parameters.drainage_failure_severity
            if t_copy.measurements.water_level is not None:
                elevation_factor = 1.0 + (0.75 * sev)
                new_wl = round(min(cls.MAX_WATER_M, t_copy.measurements.water_level * elevation_factor), 2)
                t_copy.measurements.water_level = new_wl
            if t_copy.measurements.soil_moisture is not None:
                new_sm = round(min(cls.MAX_SOIL_PCT, t_copy.measurements.soil_moisture + (25.0 * sev)), 2)
                t_copy.measurements.soil_moisture = new_sm

        return t_copy

    @classmethod
    def transform_history(
        cls,
        history: List[NormalizedTelemetry],
        parameters: ScenarioParameters,
    ) -> List[NormalizedTelemetry]:
        """
        Applies scenario parameters across historical telemetry observations.
        """
        return [cls.transform_telemetry(t, parameters) for t in history]

    @classmethod
    def transform_road_network(
        cls,
        road_network: RoadNetwork,
        parameters: ScenarioParameters,
    ) -> RoadNetwork:
        """
        Applies road accessibility degradations to candidate or network edges.
        Does NOT mutate the original RoadNetwork instance.
        """
        net_copy = road_network.model_copy(deep=True)

        if parameters.road_accessibility_reduction is not None:
            reduction = parameters.road_accessibility_reduction
            target_ids = set(parameters.target_edge_ids) if parameters.target_edge_ids else None

            for edge in net_copy.edges:
                if target_ids is None or edge.edge_id in target_ids:
                    # Multiplicative degradation: new_access = access * (1.0 - reduction)
                    new_acc = round(max(0.0, min(1.0, edge.accessibility * (1.0 - reduction))), 4)
                    edge.accessibility = new_acc
                    if edge.inferred_failure_risk is None:
                        edge.inferred_failure_risk = round(reduction, 4)
                    else:
                        edge.inferred_failure_risk = max(edge.inferred_failure_risk, round(reduction, 4))

        return net_copy
