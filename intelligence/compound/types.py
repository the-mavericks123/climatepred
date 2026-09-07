"""
Data contracts and schemas for Phase 4: Compound & Cascading Disaster Engine.
Defines strict Pydantic models for compound events, cascade chains, relationship edges,
and evaluation requests/responses.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class RelationshipType(str, Enum):
    """Classification of the physical or functional link between hazard states."""
    COMPOUND = "COMPOUND"          # Co-existing or mutually interacting hazards
    CASCADE = "CASCADE"            # Temporal/causal propagation from parent to child state
    AMPLIFICATION = "AMPLIFICATION"  # One condition non-linearly worsens another hazard's severity


class StateEvidenceType(str, Enum):
    """Categorical source nature of an input state or hazard."""
    OBSERVED = "OBSERVED"    # Directly evaluated from contemporaneous telemetry (Phase 2)
    PREDICTED = "PREDICTED"  # Extrapolated for future horizon (Phase 3)
    INFERRED = "INFERRED"    # Derived physical or functional state (e.g. road access degradation)


class ContributingState(BaseModel):
    """An individual hazard or environmental/infrastructure condition feeding into an event."""
    state_id: str = Field(..., min_length=1, description="Identifier of the state (e.g. 'flood', 'road_failure_risk')")
    evidence_type: StateEvidenceType = Field(..., description="Whether observed, predicted, or inferred")
    severity: float = Field(..., ge=0.0, le=1.0, description="Normalized severity score [0.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    timestamp: datetime = Field(..., description="Timestamp of the observation or forecast")
    forecast_horizon_minutes: int = Field(default=0, ge=0, description="0 for observed, 30/60/360 for predicted")
    source_ref_id: Optional[str] = Field(default=None, description="Original hazard_id or prediction_id if applicable")
    provenance_hash: Optional[str] = Field(default=None, description="Cryptographic fingerprint of the contributor")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic state features or parameters")


class RelationshipEdge(BaseModel):
    """Directed relationship link between two contributing states in a cascade graph."""
    from_state: str = Field(..., min_length=1, description="Source state ID")
    to_state: str = Field(..., min_length=1, description="Target state ID")
    relationship_type: RelationshipType = Field(..., description="Type: COMPOUND, CASCADE, AMPLIFICATION")
    rule_id: str = Field(..., min_length=1, description="Identifier of the deterministic rule that triggered this link")
    explanation: str = Field(..., min_length=1, description="Deterministic physical rationale for the link")
    weight: float = Field(default=1.0, ge=0.0, le=2.0, description="Coupling weight / amplification factor")


class CompoundEvent(BaseModel):
    """
    Structured, deterministic compound or cascading disaster event.
    Produced by the Phase 4 engine from observed and predicted hazard states.
    """
    event_id: str = Field(..., min_length=1, description="Unique compound event identifier")
    event_type: RelationshipType = Field(..., description="Dominant event classification: COMPOUND, CASCADE, AMPLIFICATION")
    severity: float = Field(..., ge=0.0, le=1.0, description="Composite bounded severity score [0.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Honest, deterministic event confidence [0.0, 1.0]")
    timestamp: datetime = Field(..., description="Event evaluation timestamp (UTC)")
    chain: List[str] = Field(default_factory=list, description="Ordered sequence of states forming the cascade path")
    contributing_states: List[ContributingState] = Field(default_factory=list, description="Detailed contributor records")
    relationships: List[RelationshipEdge] = Field(default_factory=list, description="Explicit graph edges between states")
    evidence_ids: List[str] = Field(default_factory=list, description="List of source hazard and prediction IDs")
    rule_version: str = Field(..., min_length=1, description="Immutable engine/rule version string (e.g. 'compound-v1')")
    provenance_hash: str = Field(..., min_length=8, description="Deterministic SHA-256 fingerprint tracing all inputs and rules")
    drivers: List[str] = Field(default_factory=list, description="Human-readable explainability driver strings")
    simulated: bool = Field(default=False, description="Strictly False for live production evaluation")

    @field_validator("simulated")
    @classmethod
    def validate_simulated_false(cls, v: bool) -> bool:
        if v is True:
            raise ValueError("simulated must be False for Phase 4 production events")
        return v


class CompoundEvaluationRequest(BaseModel):
    """API payload for compound & cascading disaster evaluation."""
    timestamp: Optional[datetime] = Field(default=None, description="Evaluation baseline timestamp")
    hazards: List[Dict[str, Any]] = Field(default_factory=list, description="Phase 2 HazardResult dictionaries")
    predictions: List[Dict[str, Any]] = Field(default_factory=list, description="Phase 3 PredictionResult dictionaries")
    environmental_states: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Optional extra observed/inferred states (e.g. heavy_rain, soil_saturation)"
    )


class CompoundEvaluationResponse(BaseModel):
    """API response schema containing detected compound & cascading disaster events."""
    success: bool = Field(default=True)
    events: List[CompoundEvent] = Field(default_factory=list, description="Array of detected compound/cascade events")
    event_count: int = Field(default=0, description="Total number of distinct events detected")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of engine execution",
    )
    request_id: Optional[str] = Field(default=None, description="Unique request tracing ID")
