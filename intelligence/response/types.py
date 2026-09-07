"""
Climate Eye View — Phase 9 Response Planner Types and Schemas.

Defines the controlled action vocabulary, alert levels, urgency levels,
action status representations, situation context, and the complete ResponsePlan contract.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AlertLevel(str, Enum):
    """Deterministic regional/situational alert levels."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class UrgencyLevel(str, Enum):
    """Urgency rating for individual response actions."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    """Controlled vocabulary of decision-support emergency response actions."""
    MONITOR = "MONITOR"
    ISSUE_WARNING = "ISSUE_WARNING"
    PREPARE_EVACUATION = "PREPARE_EVACUATION"
    EVACUATE_ZONE = "EVACUATE_ZONE"
    PRIORITIZE_VULNERABLE_POPULATION = "PRIORITIZE_VULNERABLE_POPULATION"
    OPEN_SHELTER = "OPEN_SHELTER"
    REDIRECT_EVACUATION = "REDIRECT_EVACUATION"
    CLOSE_ROAD = "CLOSE_ROAD"
    CLOSE_BRIDGE = "CLOSE_BRIDGE"
    PROTECT_CRITICAL_FACILITY = "PROTECT_CRITICAL_FACILITY"
    PREPOSITION_RESPONSE_RESOURCES = "PREPOSITION_RESPONSE_RESOURCES"
    REQUEST_FIELD_VERIFICATION = "REQUEST_FIELD_VERIFICATION"
    MAINTAIN_MONITORING = "MAINTAIN_MONITORING"
    REASSESS = "REASSESS"


class ActionStatus(str, Enum):
    """Execution recommendation status of an action."""
    RECOMMENDED = "RECOMMENDED"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


class EvidenceType(str, Enum):
    """Epistemic classification of evidence supporting an action."""
    OBSERVED = "OBSERVED"
    PREDICTED = "PREDICTED"
    INFERRED = "INFERRED"
    SIMULATED = "SIMULATED"


class EvidenceReference(BaseModel):
    """A verified pointer to an upstream authoritative evidence item."""
    type: str = Field(description="Evidence category, e.g. hazard, prediction, compound, vulnerability, evacuation, road_edge, shelter")
    id: str = Field(description="Unique upstream identifier, e.g. HAZ-..., PRED-..., COMP-..., ZONE-...")
    evidence_type: EvidenceType = Field(default=EvidenceType.OBSERVED, description="Epistemic status of the evidence")
    severity: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Upstream severity score if applicable")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Upstream confidence score if applicable")
    description: Optional[str] = Field(default=None, description="Human-readable brief summary of the evidence item")


class ActionItem(BaseModel):
    """A prioritized, evidence-backed decision-support emergency response recommendation."""
    action_id: str = Field(description="Unique recommendation identifier, e.g. ACT-001")
    action: ActionType = Field(description="Controlled action category")
    target: str = Field(description="Geographic zone, infrastructure element, or facility target, e.g. ZONE-A, ROAD-1")
    priority: int = Field(ge=1, description="Deterministic 1-indexed priority ranking (1 is highest priority)")
    priority_score: float = Field(ge=0.0, le=1.0, description="Normalized composite priority score [0.0, 1.0]")
    urgency: UrgencyLevel = Field(description="Urgency classification derived from temporal and impact factors")
    urgency_score: float = Field(ge=0.0, le=1.0, description="Numerical urgency score [0.0, 1.0]")
    confidence: float = Field(ge=0.0, le=1.0, description="Aggregated confidence score derived from upstream evidence")
    reason: str = Field(description="Explicit reasoning explaining why this action is recommended")
    evidence: List[EvidenceReference] = Field(default_factory=list, description="Verified upstream evidence items supporting this action")
    status: ActionStatus = Field(default=ActionStatus.RECOMMENDED, description="Action recommendation status")
    requires_human_review: bool = Field(default=False, description="True if mandatory operator authorization is required before execution")
    review_reason: Optional[str] = Field(default=None, description="Explicit rationale when human review is required")
    conflict_ids: List[str] = Field(default_factory=list, description="List of conflicting or superseded action IDs")
    temporal_category: EvidenceType = Field(default=EvidenceType.OBSERVED, description="Temporal ground of the action (OBSERVED, PREDICTED, INFERRED, SIMULATED)")
    forecast_horizon_minutes: Optional[int] = Field(default=None, description="Relevant forecast horizon if action addresses predicted conditions")
    simulated: bool = Field(default=False, description="True if action is derived from a hypothetical simulation scenario")


class SituationContext(BaseModel):
    """Structured synthesis of the current operational and environmental situation."""
    observed_hazards: List[Dict[str, Any]] = Field(default_factory=list, description="List of active observed hazards")
    predicted_hazards: List[Dict[str, Any]] = Field(default_factory=list, description="List of forecasted hazards")
    compound_events: List[Dict[str, Any]] = Field(default_factory=list, description="Detected compound or cascading disaster events")
    affected_zones: List[Dict[str, Any]] = Field(default_factory=list, description="Demographic zones experiencing hazard or vulnerability exposure")
    evacuation_demands: List[Dict[str, Any]] = Field(default_factory=list, description="Evaluated evacuation requirements and population counts")
    shelter_statuses: List[Dict[str, Any]] = Field(default_factory=list, description="Statuses and available capacities of emergency shelters")
    road_network_anomalies: List[Dict[str, Any]] = Field(default_factory=list, description="Impassable, degraded, or closed road segments")
    simulation_context: Optional[Dict[str, Any]] = Field(default=None, description="Hypothetical scenario parameters if running in simulation mode")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation reference timestamp")
    is_stale: bool = Field(default=False, description="True if incoming telemetry exceeds data freshness threshold")
    freshness_age_seconds: float = Field(default=0.0, ge=0.0, description="Age of telemetry in seconds at evaluation time")


class ResponsePlan(BaseModel):
    """The authoritative emergency response plan contract for Climate Eye View Phase 9."""
    plan_id: str = Field(description="Unique response plan identifier, e.g. PLAN-20260907-XXXX")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of plan generation")
    alert_level: AlertLevel = Field(description="Overall regional threat alert level (GREEN, YELLOW, ORANGE, RED)")
    situation: SituationContext = Field(description="Structured situation assessment synthesis")
    actions: List[ActionItem] = Field(default_factory=list, description="Prioritized, evidence-backed list of recommended response actions")
    warnings: List[str] = Field(default_factory=list, description="Operational warnings (e.g. STALE_DATA, LOW_CONFIDENCE, NO_ROUTE)")
    provenance_hash: str = Field(description="Deterministic cryptographic SHA-256 fingerprint of material inputs")
    simulated: bool = Field(default=False, description="True if generated from a what-if scenario rather than live operational data")
    model_version: str = Field(default="response-v1", description="AI Response Planner model architecture version")
    rules_version: str = Field(default="response-rules-v1", description="Deterministic rule set version")
    priority_formula_version: str = Field(default="priority-v1", description="Priority scoring formula version")
    confidence_formula_version: str = Field(default="confidence-v1", description="Confidence aggregation formula version")
    action_count: int = Field(default=0, ge=0, description="Total number of generated actions")
    critical_action_count: int = Field(default=0, ge=0, description="Number of actions with CRITICAL urgency")
    requires_operator_review_count: int = Field(default=0, ge=0, description="Number of actions requiring human operator review")


class ResponseEvaluateRequest(BaseModel):
    """Request payload for POST /api/v1/response/evaluate."""
    telemetry: Optional[Dict[str, Any]] = Field(default=None, description="Optional raw or normalized telemetry dictionary")
    history: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional historical telemetry records")
    population_zones: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional demographic zones overrides")
    road_network: Optional[Dict[str, Any]] = Field(default=None, description="Optional road network graph override")
    shelters: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional emergency shelter list override")
    include_predictions: bool = Field(default=True, description="Whether to include temporal forecasts in evaluation")


class ResponseSimulateRequest(BaseModel):
    """Request payload for POST /api/v1/response/simulate."""
    scenario_id: str = Field(description="Supported scenario ID, e.g. SCN-RAIN-20, SCN-RAIN-40, SCN-FLOOD-HEAT")
    changes: Optional[Dict[str, Any]] = Field(default=None, description="Parameter overrides for the simulation scenario")
    base_state: Optional[str] = Field(default="current", description="Base state identifier ('current' or snapshot ID)")


class ResponsePlanResponse(BaseModel):
    """Standard response envelope for response plan endpoints."""
    success: bool = Field(default=True, description="Success status flag")
    plan: ResponsePlan = Field(description="The generated emergency response plan")
    request_id: Optional[str] = Field(default=None, description="Tracing request identifier")
