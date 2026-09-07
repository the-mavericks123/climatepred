"""
Catalog of authorized and pre-configured scenarios for Phase 7: Digital Twin + Scenario Simulation Engine.
Enforces registration of canonical scenarios, strict ID lookups, and parameter defaulting.
"""

from typing import Dict, List, Optional
from intelligence.simulation.types import (
    ScenarioDefinition,
    ScenarioParameters,
    ScenarioType,
)


class ScenarioCatalog:
    """
    Registry of authorized scenario definitions available for simulation.
    """

    _CATALOG: Dict[str, ScenarioDefinition] = {
        "SCN-RAIN-20": ScenarioDefinition(
            scenario_id="SCN-RAIN-20",
            name="Rainfall Increase (+20%)",
            description="Simulates a moderate 20% surge in precipitation intensity across the catchment basin.",
            scenario_type=ScenarioType.RAINFALL_MULTIPLIER,
            default_parameters=ScenarioParameters(rainfall_multiplier=1.20),
            version="1.0",
        ),
        "SCN-RAIN-40": ScenarioDefinition(
            scenario_id="SCN-RAIN-40",
            name="Rainfall Surge (+40%)",
            description="Simulates an elevated 40% surge in rainfall intensity, testing drainage saturation thresholds.",
            scenario_type=ScenarioType.RAINFALL_MULTIPLIER,
            default_parameters=ScenarioParameters(rainfall_multiplier=1.40),
            version="1.0",
        ),
        "SCN-RAIN-60": ScenarioDefinition(
            scenario_id="SCN-RAIN-60",
            name="Extreme Rainfall Deluge (+60%)",
            description="Simulates an extreme 60% deluge triggering flash flood inundation and rapid runoff expansion.",
            scenario_type=ScenarioType.RAINFALL_MULTIPLIER,
            default_parameters=ScenarioParameters(rainfall_multiplier=1.60),
            version="1.0",
        ),
        "SCN-EXTREME-HEAT": ScenarioDefinition(
            scenario_id="SCN-EXTREME-HEAT",
            name="Extreme Heat Wave (+5.0 °C)",
            description="Simulates a severe summer heat dome driving ambient dry-bulb temperature upward by +5.0 °C.",
            scenario_type=ScenarioType.TEMPERATURE_DELTA,
            default_parameters=ScenarioParameters(temperature_delta=5.0),
            version="1.0",
        ),
        "SCN-DRAINAGE-FAIL": ScenarioDefinition(
            scenario_id="SCN-DRAINAGE-FAIL",
            name="Urban Drainage Infrastructure Failure (50%)",
            description="Simulates a 50% loss of stormwater culvert efficiency, causing accelerated surface pooling.",
            scenario_type=ScenarioType.DRAINAGE_FAILURE,
            default_parameters=ScenarioParameters(drainage_failure_severity=0.50),
            version="1.0",
        ),
        "SCN-ROAD-DEGRADE": ScenarioDefinition(
            scenario_id="SCN-ROAD-DEGRADE",
            name="Network Accessibility Degradation (50%)",
            description="Simulates a 50% degradation in road operability and speed limits due to flood inundation.",
            scenario_type=ScenarioType.ROAD_ACCESSIBILITY_REDUCTION,
            default_parameters=ScenarioParameters(road_accessibility_reduction=0.50),
            version="1.0",
        ),
        "SCN-FLOOD-HEAT": ScenarioDefinition(
            scenario_id="SCN-FLOOD-HEAT",
            name="Compound Flood + Heat Escalation",
            description="Simulates concurrent rainfall escalation (+40%) and elevated temperature (+4.0 °C) driving multi-hazard risk.",
            scenario_type=ScenarioType.FLOOD_HEAT_COMPOUND,
            default_parameters=ScenarioParameters(rainfall_multiplier=1.40, temperature_delta=4.0),
            version="1.0",
        ),
    }

    @classmethod
    def list_scenarios(cls) -> List[ScenarioDefinition]:
        """Returns all registered scenario definitions, sorted by scenario_id."""
        return sorted(cls._CATALOG.values(), key=lambda s: s.scenario_id)

    @classmethod
    def get_scenario(cls, scenario_id: str) -> Optional[ScenarioDefinition]:
        """Retrieves a scenario definition by its unique identifier."""
        return cls._CATALOG.get(scenario_id)

    @classmethod
    def resolve_parameters(
        cls,
        scenario_id: str,
        overrides: Optional[ScenarioParameters] = None,
    ) -> ScenarioParameters:
        """
        Resolves effective parameters by combining scenario defaults with optional user overrides.
        """
        definition = cls.get_scenario(scenario_id)
        if not definition:
            if overrides:
                return overrides
            raise ValueError(f"Unsupported scenario ID '{scenario_id}'. Not found in catalog.")

        if not overrides:
            return definition.default_parameters.model_copy(deep=True)

        # Merge overrides over default parameters
        default_dict = definition.default_parameters.model_dump()
        override_dict = overrides.model_dump(exclude_unset=True)
        for k, v in override_dict.items():
            if v is not None:
                default_dict[k] = v

        return ScenarioParameters(**default_dict)
