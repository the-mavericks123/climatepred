"""
Data contracts and schemas for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Defines Pydantic models for road edges, networks, shelters, evacuation demand,
routes, destination assignments, and evaluation requests/responses.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from intelligence.compound.types import CompoundEvent, StateEvidenceType
from intelligence.hazards.types import HazardResult
from intelligence.prediction.types import PredictionResult
from intelligence.vulnerability.types import PopulationZone, VulnerabilityZoneAssessment


class EvacuationStatus(str, Enum):
    """Categorical status of an evacuation assessment or recommendation."""
    RECOMMENDED = "RECOMMENDED"          # Feasible, safe shelter and route identified
    PARTIAL_CAPACITY = "PARTIAL_CAPACITY"  # Route found, but shelter capacity is insufficient for full demand
    NO_ROUTE = "NO_ROUTE"                # No traversable route exists from origin to candidate shelters
    NO_SHELTER = "NO_SHELTER"            # No available or safe shelters exist within network
    UNSAFE = "UNSAFE"                    # All paths or destinations violate maximum hazard thresholds
    STALE = "STALE"                      # Telemetry or road status data exceeds freshness limits
    UNAVAILABLE = "UNAVAILABLE"          # Required data missing or service unreachable


class NoRouteReason(str, Enum):
    """Specific deterministic cause when status is NO_ROUTE or UNSAFE."""
    ALL_ROADS_CLOSED = "ALL_ROADS_CLOSED"
    DESTINATION_UNSAFE = "DESTINATION_UNSAFE"
    INSUFFICIENT_SHELTER_CAPACITY = "INSUFFICIENT_SHELTER_CAPACITY"
    HAZARD_BLOCKED_NETWORK = "HAZARD_BLOCKED_NETWORK"
    NO_FEASIBLE_PATH = "NO_FEASIBLE_PATH"
    SHELTER_UNREACHABLE = "SHELTER_UNREACHABLE"
    ISOLATED_ZONE = "ISOLATED_ZONE"


class Shelter(BaseModel):
    """
    Emergency shelter or refuge point within the evacuation network.
    Maintains strict capacity constraints and current physical safety state.
    """
    shelter_id: str = Field(..., min_length=1, description="Unique shelter identifier")
    name: str = Field(..., min_length=1, description="Human-readable facility name")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    capacity: int = Field(..., ge=0, description="Total certified occupant capacity")
    current_occupancy: int = Field(default=0, ge=0, description="Current number of sheltered residents")
    available_capacity: Optional[int] = Field(default=None, ge=0, description="Remaining capacity")
    accessibility: float = Field(default=1.0, ge=0.0, le=1.0, description="Facility accessibility score")
    safe: bool = Field(default=True, description="True if facility is structurally sound and outside active hazard zones")
    hazard_risk: float = Field(default=0.0, ge=0.0, le=1.0, description="Contemporaneous or predicted hazard severity at shelter site")
    node_id: Optional[str] = Field(default=None, description="Corresponding road network node ID")
    features: Dict[str, Any] = Field(default_factory=dict, description="Auxiliary facilities, generators, medical services")
    simulated: bool = Field(default=True, description="Whether shelter data is synthetic demo")
    source: str = Field(default="synthetic_demo", description="Data source provider")

    @field_validator("current_occupancy")
    @classmethod
    def validate_occupancy(cls, v: int, info) -> int:
        cap = info.data.get("capacity")
        if cap is not None and v > cap:
            raise ValueError(f"current_occupancy ({v}) cannot exceed total capacity ({cap})")
        return v

    def model_post_init(self, __context: Any) -> None:
        if self.available_capacity is None:
            self.available_capacity = max(0, self.capacity - self.current_occupancy)


class RoadEdge(BaseModel):
    """
    Directed or traversable roadway segment in the evacuation transport network.
    """
    edge_id: str = Field(..., min_length=1, description="Unique edge identifier (e.g. 'ROAD-A-B')")
    from_node: str = Field(..., min_length=1, description="Origin intersection/node ID")
    to_node: str = Field(..., min_length=1, description="Destination intersection/node ID")
    distance_km: float = Field(..., ge=0.0, description="Segment physical length in kilometers")
    travel_time_minutes: float = Field(..., ge=0.0, description="Baseline traversal time under normal conditions")
    accessibility: float = Field(default=1.0, ge=0.0, le=1.0, description="Roadway operability / physical condition (1=optimal)")
    hazard_risk: float = Field(default=0.0, ge=0.0, le=1.0, description="Local hazard severity along segment")
    closed: bool = Field(default=False, description="Whether segment is impassable / barricaded")
    closure_reason: Optional[str] = Field(default=None, description="Rationale if road is closed")
    inferred_failure_risk: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Inferred road infrastructure failure risk from cascading models")
    features: Dict[str, Any] = Field(default_factory=dict, description="Lane count, elevation, bridge markers")
    simulated: bool = Field(default=True, description="Whether road network is synthetic")


class RoadNetwork(BaseModel):
    """Complete graph of intersections and road segments."""
    network_id: str = Field(default="NET-DEFAULT-001", description="Identifier for the road network")
    nodes: List[str] = Field(default_factory=list, description="List of unique intersection node IDs")
    edges: List[RoadEdge] = Field(default_factory=list, description="List of road segments")


class EvacuationDemand(BaseModel):
    """Calculated evacuation requirement for an impacted population zone."""
    zone_id: str = Field(..., min_length=1)
    evacuation_required: bool = Field(...)
    population_exposed: int = Field(..., ge=0)
    population_to_evacuate: int = Field(..., ge=0)
    priority: float = Field(..., ge=0.0, le=1.0, description="Deterministic urgency/priority score in [0.0, 1.0]")
    human_impact: float = Field(..., ge=0.0, le=1.0)
    vulnerability: float = Field(..., ge=0.0, le=1.0)
    hazard_risk: float = Field(..., ge=0.0, le=1.0)
    accessibility_risk: float = Field(..., ge=0.0, le=1.0)
    urgency: float = Field(..., ge=0.0, le=1.0)
    drivers: List[str] = Field(default_factory=list)

    @field_validator("population_to_evacuate")
    @classmethod
    def validate_evacuation_count(cls, v: int, info) -> int:
        exp = info.data.get("population_exposed")
        if exp is not None and v > exp:
            raise ValueError(f"population_to_evacuate ({v}) cannot exceed population_exposed ({exp})")
        return v


class EvacuationRoute(BaseModel):
    """Deterministic hazard-aware path from zone origin to shelter destination."""
    route_id: str = Field(..., min_length=1)
    origin_node: str = Field(...)
    destination_node: str = Field(...)
    nodes: List[str] = Field(default_factory=list, description="Ordered sequence of nodes traversed")
    edge_ids: List[str] = Field(default_factory=list, description="Ordered sequence of edge IDs traversed")
    distance_km: float = Field(..., ge=0.0)
    estimated_travel_minutes: float = Field(..., ge=0.0)
    hazard_exposure: float = Field(..., ge=0.0, le=1.0, description="Mean/max hazard severity along route")
    accessibility: float = Field(..., ge=0.0, le=1.0, description="Mean road accessibility along route")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="Normalized route safety score (1=safest)")
    total_cost: float = Field(..., ge=0.0, description="Composite weighted Dijkstra traversal cost")


class DestinationAssignment(BaseModel):
    """Assignment of an evacuating population to an emergency shelter."""
    shelter_id: str = Field(..., min_length=1)
    shelter_name: str = Field(...)
    assigned_population: int = Field(..., ge=0)
    available_capacity_before: int = Field(..., ge=0)
    available_capacity_after: int = Field(..., ge=0)
    shelter_safety_score: float = Field(..., ge=0.0, le=1.0)


class EvacuationRecommendation(BaseModel):
    """
    Comprehensive, explainable evacuation directive for a single population zone.
    Combines demand priority, destination shelter assignment, hazard-aware routing,
    and road avoidance directives with cryptographic provenance.
    """
    evacuation_id: str = Field(..., min_length=1)
    zone_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(..., description="Timestamp of directive evaluation")
    forecast_horizon_minutes: int = Field(default=0, ge=0)
    evidence_type: StateEvidenceType = Field(default=StateEvidenceType.OBSERVED)

    # Demographic & demand metrics
    population_exposed: int = Field(..., ge=0)
    population_to_evacuate: int = Field(..., ge=0)
    priority: float = Field(..., ge=0.0, le=1.0)

    # Destination & Route
    destination: Optional[DestinationAssignment] = Field(default=None)
    route: Optional[EvacuationRoute] = Field(default=None)
    avoid_edges: List[str] = Field(default_factory=list, description="Hazardous or severed edges to explicitly avoid")

    # Reasoning, confidence, and provenance
    status: EvacuationStatus = Field(default=EvacuationStatus.RECOMMENDED)
    reason: str = Field(..., min_length=1, description="Human-readable decision explanation")
    no_route_reason: Optional[NoRouteReason] = Field(default=None)
    confidence: float = Field(..., ge=0.0, le=1.0)
    simulated: bool = Field(default=True)
    provenance_hash: str = Field(..., min_length=8)
    algorithm_version: str = Field(default="dijkstra-hazard-v1")
    cost_formula_version: str = Field(default="cost-v1")
    drivers: List[str] = Field(default_factory=list)


class EvacuationEvaluationRequest(BaseModel):
    """API Request payload for POST /api/v1/evacuation/evaluate."""
    zones: List[PopulationZone] = Field(..., min_length=1, description="List of population zones")
    shelters: List[Shelter] = Field(..., min_length=1, description="List of available emergency shelters")
    road_network: RoadNetwork = Field(..., description="Traversable road network graph")
    vulnerabilities: Optional[List[VulnerabilityZoneAssessment]] = Field(default=None, description="Pre-computed Phase 5 assessments")
    hazards: Optional[List[HazardResult]] = Field(default=None, description="Contemporaneous Phase 2 hazard results")
    predictions: Optional[List[PredictionResult]] = Field(default=None, description="Future Phase 3 forecast results")
    compound_events: Optional[List[CompoundEvent]] = Field(default=None, description="Phase 4 cascading/compound events")
    edge_accessibility_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Optional override for edge accessibility threshold")
    timestamp: Optional[datetime] = Field(default=None, description="Evaluation timestamp")


class EvacuationEvaluationResponse(BaseModel):
    """API Response payload for evacuation intelligence endpoints."""
    success: bool = Field(default=True)
    recommendations: List[EvacuationRecommendation] = Field(default_factory=list)
    recommendation_count: int = Field(default=0, ge=0)
    total_evacuated_population: int = Field(default=0, ge=0)
    unassigned_demand_population: int = Field(default=0, ge=0)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = Field(default=None)
