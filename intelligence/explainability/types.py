"""
Climate Eye View — Phase 10 Explainability Data Contracts.
Defines strict Pydantic schemas for explanation requests, factor attributions,
uncertainty assessments, counterfactuals, and structured explanation contracts.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TargetType(str, Enum):
    """Supported target intelligence model outputs."""
    HAZARD = "hazard"
    PREDICTION = "prediction"
    COMPOUND = "compound"
    COMPOUND_EVENT = "compound"
    VULNERABILITY = "vulnerability"
    EVACUATION = "evacuation"
    RESPONSE = "response"
    RESPONSE_PLAN = "response"
    SIMULATION = "simulation"


class ExplanationLevel(str, Enum):
    """Granularity of the generated explanation."""
    SUMMARY = "SUMMARY"          # 1-2 sentence executive briefing
    STANDARD = "STANDARD"        # Primary factors, evidence items, and drivers
    DETAILED = "DETAILED"        # Complete formula terms, weights, uncertainty, counterfactuals


class EpistemicClassification(str, Enum):
    """Epistemic status of the explained output."""
    OBSERVED = "OBSERVED"
    PREDICTED = "PREDICTED"
    INFERRED = "INFERRED"
    SIMULATED = "SIMULATED"


class FactorAttribution(BaseModel):
    """Quantitative contribution of an individual factor to an output score."""
    factor_name: str = Field(..., description="Canonical parameter or feature identifier")
    display_name: str = Field(..., description="Human-readable factor title")
    input_value: Any = Field(..., description="Raw observed or simulated input measurement")
    normalized_value: float = Field(..., ge=0.0, le=1.0, description="Normalized score in [0.0, 1.0]")
    weight: float = Field(..., ge=0.0, le=1.0, description="Mathematical model weight applied to factor")
    contribution: float = Field(..., description="Effective score contribution (normalized_value * weight)")
    unit: Optional[str] = Field(default=None, description="Physical unit of measurement (e.g. 'mm/hr', '°C', 'm')")
    description: Optional[str] = Field(default=None, description="Detailed explanatory text for the factor")


class EvidenceReference(BaseModel):
    """Cryptographic link to an authoritative upstream model or telemetry object."""
    type: str = Field(..., description="Type of upstream object (telemetry, hazard, prediction, compound, etc.)")
    id: str = Field(..., description="Unique entity identifier from upstream phase")
    severity: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Upstream severity metric if applicable")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Upstream confidence metric if applicable")
    provenance_hash: Optional[str] = Field(default=None, description="Upstream cryptographic digest")


class UncertaintyItem(BaseModel):
    """Source and magnitude of modeling uncertainty or epistemic limitation."""
    source: str = Field(..., description="Component introducing uncertainty (e.g. 'telemetry_noise', 'forecast_horizon')")
    level: str = Field(..., description="Uncertainty tier: 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'")
    description: str = Field(..., description="Operational explanation of what is uncertain")
    impact_on_decision: str = Field(..., description="How this uncertainty bounds or qualifies the recommendation")


class CounterfactualItem(BaseModel):
    """Deterministic what-if permutation showing tipping points for alternative outcomes."""
    condition: str = Field(..., description="Hypothetical input shift (e.g. 'rainfall decreases by 40%')")
    altered_parameter: str = Field(..., description="Specific parameter modified")
    original_value: Any = Field(..., description="Observed baseline value")
    counterfactual_value: Any = Field(..., description="Perturbed parameter value required for transition")
    counterfactual_outcome: str = Field(..., description="Resulting model output under this shift")
    feasibility: str = Field(default="MODEL_COUNTERFACTUAL", description="Explicit tag noting hypothetical nature")


class ExplanationContract(BaseModel):
    """
    Canonical explainability envelope answering WHY a model produced an output,
    WHICH inputs contributed, and WHAT would change the decision.
    """
    explanation_id: str = Field(..., description="Unique identifier for this explanation")
    target_type: TargetType = Field(..., description="Classification of target intelligence artifact")
    target_id: str = Field(..., description="Unique identifier of target intelligence artifact")
    model_version: str = Field(..., description="Authoritative model version that generated the output")
    classification: EpistemicClassification = Field(..., description="Epistemic status: OBSERVED, PREDICTED, INFERRED, SIMULATED")
    summary: str = Field(..., description="Concise operator briefing explaining the output")
    explanation_level: ExplanationLevel = Field(default=ExplanationLevel.STANDARD)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Factor attribution & formulas
    formula_name: Optional[str] = Field(default=None, description="Name of the deterministic mathematical formula")
    formula_expression: Optional[str] = Field(default=None, description="Human-readable mathematical expression")
    factors: List[FactorAttribution] = Field(default_factory=list, description="Ranked factor attributions")

    # Reasoning and evidence
    reasoning_steps: List[str] = Field(default_factory=list, description="Logical step-by-step reasoning derivation")
    evidence: List[EvidenceReference] = Field(default_factory=list, description="Referenced upstream entities")
    uncertainty: List[UncertaintyItem] = Field(default_factory=list, description="Epistemic limits and data quality flags")
    counterfactuals: List[CounterfactualItem] = Field(default_factory=list, description="Deterministic tipping-point counterfactuals")

    # Cryptographic provenance & metadata
    provenance_hash: str = Field(..., description="Deterministic SHA-256 fingerprint of material explanation inputs")
    simulated: bool = Field(default=False, description="Whether explanation describes a simulated what-if outcome")


class ExplanationRequest(BaseModel):
    """Request payload for POST /api/v1/explainability/generate."""
    target_type: TargetType = Field(..., description="Type of object to explain")
    target_id: str = Field(..., description="Identifier of object to explain")
    level: ExplanationLevel = Field(default=ExplanationLevel.STANDARD, description="Detail level requested")
    target_object: Optional[Dict[str, Any]] = Field(default=None, description="Optional inline target payload if not cached")
    upstream_context: Optional[Dict[str, Any]] = Field(default=None, description="Optional upstream multi-phase context")
