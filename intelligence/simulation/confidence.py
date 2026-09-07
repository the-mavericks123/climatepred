"""
Simulation confidence assessment for Phase 7: Digital Twin + Scenario Simulation Engine.
Computes model-informed simulation confidence while strictly distinguishing hypothetical
perturbation confidence from real-world probability forecasts.
"""

from intelligence.simulation.types import DigitalTwinState, ScenarioParameters


class SimulationConfidenceCalculator:
    """
    Evaluates simulation modeling confidence based on base state telemetry validity,
    magnitude of parameter perturbation, and underlying model calibrations.
    """

    CONFIDENCE_FORMULA_VERSION = "sim-conf-v1"

    @classmethod
    def calculate_confidence(
        cls,
        base_state: DigitalTwinState,
        parameters: ScenarioParameters,
    ) -> float:
        """
        Calculates bounded simulation confidence in [0.10, 1.0].
        Penalizes severe perturbations that push conditions far beyond nominal training bounds.
        """
        # Base telemetry confidence
        base_conf = 0.90
        if base_state.hazards:
            base_conf = sum(h.confidence for h in base_state.hazards) / len(base_state.hazards)

        penalty = 0.0

        # Perturbation scale penalties: extreme multipliers introduce greater modeling uncertainty
        if parameters.rainfall_multiplier is not None:
            if parameters.rainfall_multiplier > 2.0:
                penalty += 0.10
            elif parameters.rainfall_multiplier > 1.5:
                penalty += 0.05

        if parameters.temperature_delta is not None:
            if abs(parameters.temperature_delta) > 10.0:
                penalty += 0.10
            elif abs(parameters.temperature_delta) > 5.0:
                penalty += 0.05

        if parameters.drainage_failure_severity is not None:
            penalty += 0.05 * parameters.drainage_failure_severity

        if parameters.road_accessibility_reduction is not None:
            penalty += 0.05 * parameters.road_accessibility_reduction

        if base_state.simulated:
            penalty += 0.05

        final_conf = max(0.10, min(1.0, base_conf - penalty))
        return round(final_conf, 4)
