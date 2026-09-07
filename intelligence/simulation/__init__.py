"""Phase 7: Digital Twin & Scenario Simulation Engine.

Provides deterministic, explainable scenario simulation for Climate Eye View.
Perturbs physical and environmental states in strict isolation and recalculates
hazard, prediction, compound, vulnerability, and dynamic evacuation downstream effects.
"""

from intelligence.simulation.types import (
    ScenarioType,
    ScenarioParameters,
    ScenarioDefinition,
    DigitalTwinState,
    ComponentDelta,
    SimulationSummary,
    SimulationComparison,
    SimulationResult,
    SimulationRunRequest,
    SimulationRunResponse,
    SimulationCatalogResponse,
)
from intelligence.simulation.transforms import ScenarioTransformer
from intelligence.simulation.scenarios import ScenarioCatalog
from intelligence.simulation.state import DigitalTwinStateManager
from intelligence.simulation.propagation import ModelPropagator
from intelligence.simulation.outputs import SimulationComparator
from intelligence.simulation.confidence import SimulationConfidenceCalculator
from intelligence.simulation.provenance import SimulationProvenanceTracker
from intelligence.simulation.engine import SimulationEngine

__all__ = [
    "ScenarioType",
    "ScenarioParameters",
    "ScenarioDefinition",
    "DigitalTwinState",
    "ComponentDelta",
    "SimulationSummary",
    "SimulationComparison",
    "SimulationResult",
    "SimulationRunRequest",
    "SimulationRunResponse",
    "SimulationCatalogResponse",
    "ScenarioTransformer",
    "ScenarioCatalog",
    "DigitalTwinStateManager",
    "ModelPropagator",
    "SimulationComparator",
    "SimulationConfidenceCalculator",
    "SimulationProvenanceTracker",
    "SimulationEngine",
]
