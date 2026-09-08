"""
Data contracts and schemas for Phase 7: Digital Twin + Scenario Simulation Engine.
Defines Pydantic models for digital twin baseline state, scenario definitions, parameter validation,
model propagation outputs, numerical comparison deltas, and simulation provenance.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from intelligence.compound.types import CompoundEvent
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.evacuation.types import (
    EvacuationRecommendation,
    RoadNetwork,
    Shelter,
)
from intelligence.hazards.types import HazardResult
from intelligence.prediction.types import PredictionResult
from intelligence.vulnerability.types import (
    PopulationZone,
    VulnerabilityZoneAssessment,
)


class ScenarioType(str, Enum):
    """Supported scenario perturbation categories."""
    RAINFALL_MULTIPLIER = "RAINFALL_MULTIPLIER"
    TEMPERATURE_DELTA = "TEMPERATURE_DELTA"
    SOIL_MOISTURE_DELTA = "SOIL_MOISTURE_DELTA"
    WATER_LEVEL_DELTA = "WATER_LEVEL_DELTA"
    DRAINAGE_FAILURE = "DRAINAGE_FAILURE"
    ROAD_ACCESSIBILITY_REDUCTION = "ROAD_ACCESSIBILITY_REDUCTION"
    FLOOD_HEAT_COMPOUND = "FLOOD_HEAT_COMPOUND"
    CUSTOM = "CUSTOM"


class ScenarioParameters(BaseModel):
    """
    Explicit, bounded parameters for a scenario simulation.
    Rejects out-of-range perturbations to guarantee numerical and physical sanity.
    """
    rainfall_multiplier: Optional[float] = Field(
        default=None,
        ge=0.10,
        le=5.00,
        description="Multiplicative scaling factor for rainfall telemetry (0.10 to 5.00)",
    )
    temperature_delta: Optional[float] = Field(
        default=None,
        ge=-20.0,
        le=30.0,
        description="Additive temperature shift in degrees Celsius (-20.0 to +30.0 °C)",
    )
    soil_moisture_delta: Optional[float] = Field(
        default=None,
        ge=-50.0,
        le=50.0,
        description="Additive volumetric soil moisture percentage shift (-50.0% to +50.0%)",
    )
    water_level_delta: Optional[float] = Field(
        default=None,
        ge=-10.0,
        le=20.0,
        description="Additive water level shift in meters (-10.0 to +20.0 m)",
    )
    drainage_failure_severity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Drainage capacity failure severity factor (0.0 = nominal, 1.0 = total block)",
    )
    road_accessibility_reduction: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Road segment accessibility degradation penalty (0.0 = unchanged, 1.0 = total loss)",
    )
    target_edge_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific edge IDs targeted for road degradation; if empty, applies network-wide",
    )

    @model_validator(mode="after")
    def validate_has_at_least_one_change(self) -> "ScenarioParameters":
        """Ensures at least one actionable parameter is specified."""
        values = [
            self.rainfall_multiplier,
            self.temperature_delta,
            self.soil_moisture_delta,
            self.water_level_delta,
            self.drainage_failure_severity,
            self.road_accessibility_reduction,
        ]
        if all(v is None for v in values):
            raise ValueError("ScenarioParameters must specify at least one valid parameter change")
        return self


class ScenarioDefinition(BaseModel):
    """
    Catalog entry describing an authorized simulation scenario.
    """
    scenario_id: str = Field(..., min_length=1, description="Unique scenario identifier (e.g. 'SCN-RAIN-20')")
    name: str = Field(..., min_length=1, description="Human-readable scenario title")
    description: str = Field(..., min_length=1, description="Scenario description and rationale")
    scenario_type: ScenarioType = Field(..., description="Category of physical or infrastructural change")
    default_parameters: ScenarioParameters = Field(..., description="Canonical default parameters for scenario")
    version: str = Field(default="1.0", description="Scenario specification version")
    simulated: bool = Field(default=True, description="Always true for hypothetical scenarios")


class DigitalTwinState(BaseModel):
    """
    Structured representation of the baseline or simulated digital twin state.
    Preserves all decision-relevant inputs across Phases 1 through 6.
    """
    base_state_id: str = Field(..., min_length=1, description="Unique identifier for the base state snapshot")
    timestamp: datetime = Field(..., description="Timestamp of snapshot evaluation")
    telemetry: NormalizedTelemetry = Field(..., description="Primary telemetry readings")
    history: List[NormalizedTelemetry] = Field(default_factory=list, description="Historical observations for trend analysis")
    hazards: List[HazardResult] = Field(default_factory=list, description="Phase 2 hazard evaluation outputs")
    predictions: List[PredictionResult] = Field(default_factory=list, description="Phase 3 forecasting outputs")
    compound_events: List[CompoundEvent] = Field(default_factory=list, description="Phase 4 cascading events")
    vulnerability_zones: List[VulnerabilityZoneAssessment] = Field(default_factory=list, description="Phase 5 human vulnerability zones")
    population_zones: List[PopulationZone] = Field(default_factory=list, description="Population demographic zones")
    road_network: RoadNetwork = Field(..., description="Road transport network graph")
    shelters: List[Shelter] = Field(default_factory=list, description="Emergency shelters and current occupancies")
    evacuation_routes: List[EvacuationRecommendation] = Field(default_factory=list, description="Phase 6 evacuation directives")
    simulated: bool = Field(default=False, description="True if state represents hypothetical scenario")
    provenance_hash: Optional[str] = Field(default=None, description="Cryptographic fingerprint of the digital twin state")


class ComponentDelta(BaseModel):
    """
    Numerical comparison of a specific metric between baseline and simulated state.
    """
    name: str = Field(..., description="Metric name (e.g. 'flood_severity')")
    baseline: float = Field(..., description="Value in baseline state")
    simulated: float = Field(..., description="Value under simulation")
    delta: float = Field(..., description="Numerical difference: simulated - baseline")
    relative_delta: Optional[float] = Field(default=None, description="Percentage/fractional change where baseline != 0")
    units: str = Field(default="", description="Measurement units")


class SimulationSummary(BaseModel):
    """
    Structured executive summary of scenario impacts across hazard, demographic, and routing dimensions.
    """
    hazard_change: Dict[str, Any] = Field(default_factory=dict, description="Summary of hazard severity shifts")
    population_change: Dict[str, Any] = Field(default_factory=dict, description="Summary of newly exposed populations")
    route_change: Dict[str, Any] = Field(default_factory=dict, description="Summary of altered or severed evacuation routes")
    infrastructure_change: Dict[str, Any] = Field(default_factory=dict, description="Summary of degraded road or shelter capacities")


class SimulationComparison(BaseModel):
    """
    Detailed baseline vs. simulated delta comparison.
    """
    metrics: List[ComponentDelta] = Field(default_factory=list, description="Specific numerical metric deltas")
    route_status_transitions: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Zone-level routing status shifts (e.g. {'ZONE-A': {'baseline': 'RECOMMENDED', 'simulated': 'NO_ROUTE'}})",
    )
    new_avoid_edges: List[str] = Field(default_factory=list, description="Road edges that became newly impassable")
    shelter_occupancy_deltas: Dict[str, int] = Field(default_factory=dict, description="Change in required shelter occupants")


class SimulationResult(BaseModel):
    """
    Comprehensive output structure for a Phase 7 scenario simulation.
    All simulated model outputs carry explicit simulated = True flags.
    """
    simulation_id: str = Field(..., min_length=1, description="Unique simulation execution identifier")
    scenario_id: str = Field(..., min_length=1, description="ID of simulated scenario")
    scenario_version: str = Field(default="1.0", description="Version of scenario definition")
    timestamp: datetime = Field(..., description="Simulation timestamp")
    simulated: bool = Field(default=True, description="Strictly true: hypothetical scenario results")
    base_state_id: str = Field(..., description="Source digital twin base state identifier")
    base_state_hash: str = Field(..., description="Cryptographic fingerprint of the base state")
    parameters: ScenarioParameters = Field(..., description="Applied scenario perturbation parameters")
    summary: SimulationSummary = Field(..., description="Executive delta summary")
    comparison: SimulationComparison = Field(..., description="Exhaustive metric deltas")
    hazards: List[HazardResult] = Field(default_factory=list, description="Simulated Phase 2 hazard results")
    predictions: List[PredictionResult] = Field(default_factory=list, description="Simulated Phase 3 predictions")
    compound_events: List[CompoundEvent] = Field(default_factory=list, description="Simulated Phase 4 cascading events")
    vulnerability_zones: List[VulnerabilityZoneAssessment] = Field(default_factory=list, description="Simulated Phase 5 human impact")
    evacuation_routes: List[EvacuationRecommendation] = Field(default_factory=list, description="Simulated Phase 6 evacuation routes")
    response_plan: Optional[Dict[str, Any]] = Field(default=None, description="Simulated Phase 9 response directives")
    explanation: Optional[Dict[str, Any]] = Field(default=None, description="Simulated Phase 10 explainability audit")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in simulation modeling pipeline")
    provenance_hash: str = Field(..., min_length=8, description="Cryptographic SHA-256 simulation fingerprint")


class SimulationRunRequest(BaseModel):
    """
    API payload for POST /api/v1/simulation/run.
    """
    scenario_id: str = Field(..., min_length=1, description="Identifier of cataloged scenario to execute")
    base_state: Optional[Union[DigitalTwinState, str]] = Field(default="current", description="Optional explicit base state or 'current' for live snapshot")
    changes: Optional[ScenarioParameters] = Field(default=None, description="Optional parameter overrides for the scenario")
    region: Optional[str] = Field(default=None, description="Target region name or coordinates for baseline binding")
    current_telemetry: Optional[Dict[str, Any]] = Field(default=None, description="Optional live telemetry overrides from client")



class SimulationRunResponse(BaseModel):
    """
    API response for POST /api/v1/simulation/run.
    """
    success: bool = Field(default=True)
    simulation: SimulationResult
    request_id: Optional[str] = Field(default=None)


class SimulationCatalogResponse(BaseModel):
    """
    API response for GET /api/v1/simulation/scenarios.
    """
    success: bool = Field(default=True)
    count: int = Field(default=0, ge=0)
    scenarios: List[ScenarioDefinition] = Field(default_factory=list)
