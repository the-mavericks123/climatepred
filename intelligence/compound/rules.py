"""
Deterministic relationship rules and configuration for Phase 4 Compound & Cascading Disaster Engine.
Defines rule identifiers, activation conditions, relationship types, amplification formulas,
and temporal matching thresholds.
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from intelligence.compound.types import (
    ContributingState,
    RelationshipEdge,
    RelationshipType,
    StateEvidenceType,
)


class CompoundRuleConfig(BaseModel):
    """Configuration parameters for compound & cascading disaster evaluation."""
    rule_version: str = "compound-v1"
    relationship_window_minutes: float = Field(
        default=120.0,
        description="Maximum temporal disparity between contributing states to be considered concurrent or chained",
    )
    max_cascade_depth: int = Field(
        default=6,
        description="Maximum graph traversal depth to prevent infinite loops or excessive recursion",
    )
    # Severity calculation bounds and interaction factors
    compound_interaction_bonus: float = Field(
        default=0.15,
        description="Interaction amplification added to base mean severity for co-occurring compound hazards",
    )
    cascade_amplification_factor: float = Field(
        default=0.10,
        description="Severity addition for each downstream cascade stage",
    )
    # Minimum state severity to be eligible for compound/cascade evaluation
    min_activation_severity: float = Field(
        default=0.35,
        description="Threshold below which mild conditions (NORMAL/LOW) do not trigger compound/cascade alarms",
    )


DEFAULT_COMPOUND_CONFIG = CompoundRuleConfig()


class CascadeRuleDefinition(BaseModel):
    """Specification of a deterministic causal or compound rule."""
    rule_id: str = Field(..., description="Unique stable rule ID (e.g. 'HEAT-DRY-001')")
    name: str = Field(..., description="Human-readable rule name")
    relationship_type: RelationshipType = Field(..., description="COMPOUND, CASCADE, or AMPLIFICATION")
    source_states: List[str] = Field(..., description="Required state identifiers that must be present")
    target_state: str = Field(..., description="Target or resulting state produced/amplified")
    explanation_template: str = Field(..., description="Deterministic explanation template")
    amplification_factor: float = Field(default=0.10, ge=0.0, le=1.0)
    # Functional predicate is evaluated in code via registry


# Canonical Rule Registry Definitions
CANONICAL_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "RAIN-SAT-001",
        "name": "Heavy Rainfall to Soil Saturation Cascade",
        "relationship_type": RelationshipType.CASCADE,
        "source_states": ["heavy_rain"],
        "target_state": "soil_saturation",
        "explanation": "Intense precipitation rate directly saturates topsoil layer, exhausting percolation capacity.",
        "amplification": 0.10,
    },
    {
        "rule_id": "SAT-FLOOD-001",
        "name": "Saturated Soil Runoff to Surface Flood Cascade",
        "relationship_type": RelationshipType.CASCADE,
        "source_states": ["soil_saturation"],
        "target_state": "flood",
        "explanation": "Fully saturated soil eliminates infiltration, converting further precipitation into rapid surface water accumulation.",
        "amplification": 0.15,
    },
    {
        "rule_id": "HEAT-DRY-001",
        "name": "Heatwave and Drought Compound Condition",
        "relationship_type": RelationshipType.COMPOUND,
        "source_states": ["heat", "drought"],
        "target_state": "amplified_environmental_heat_drought_stress",
        "explanation": "Co-occurrence of extreme ambient temperatures and severe moisture deficit compounds thermal stress.",
        "amplification": 0.18,
    },
    {
        "rule_id": "FLOOD-ROAD-001",
        "name": "Surface Flooding to Road Inundation Cascade",
        "relationship_type": RelationshipType.CASCADE,
        "source_states": ["flood"],
        "target_state": "inferred_road_failure_risk",
        "explanation": "Elevated surface water levels inundate roadway network, resulting in high physical failure/washout risk.",
        "amplification": 0.12,
        "required_evidence_type": StateEvidenceType.OBSERVED,
    },
    {
        "rule_id": "ROAD-ACCESS-001",
        "name": "Road Failure Risk to Infrastructure Access Loss",
        "relationship_type": RelationshipType.CASCADE,
        "source_states": ["inferred_road_failure_risk"],
        "target_state": "inferred_access_loss",
        "explanation": "Inundated/failed transportation corridors block transit routes to critical infrastructure and emergency facilities.",
        "amplification": 0.10,
    },
    {
        "rule_id": "DROUGHT-HEAT-AMP-001",
        "name": "Drought Soil Dryness Heat Amplification",
        "relationship_type": RelationshipType.AMPLIFICATION,
        "source_states": ["drought", "heat"],
        "target_state": "heat",
        "explanation": "Severe soil desiccation suppresses evaporative cooling, amplifying sensible heat flux and ambient temperature.",
        "amplification": 0.12,
    },
    {
        "rule_id": "PRED-FLOOD-ACCESS-001",
        "name": "Predicted Flood to Future Access Degradation Cascade",
        "relationship_type": RelationshipType.CASCADE,
        "source_states": ["flood"],
        "target_state": "predicted_access_loss",
        "explanation": "Anticipated future flood peak is projected to sever downstream arterial transit corridors.",
        "amplification": 0.10,
        "required_evidence_type": StateEvidenceType.PREDICTED,
    },
    {
        "rule_id": "HEAT-FLOOD-001",
        "name": "Concurrent Heat and Flood Compound Hazard",
        "relationship_type": RelationshipType.COMPOUND,
        "source_states": ["heat", "flood"],
        "target_state": "heat_flood_multihazard_stress",
        "explanation": "Simultaneous occurrence of localized thermal extremes and hydrological flooding challenges simultaneous response logistics.",
        "amplification": 0.14,
    },
    {
        "rule_id": "FLOOD-DROUGHT-001",
        "name": "Flash Flood Over Desiccated Soil Compound Hazard",
        "relationship_type": RelationshipType.COMPOUND,
        "source_states": ["drought", "flood"],
        "target_state": "drought_flood_flash_runoff_stress",
        "explanation": "Hydrophobic crust from antecedent drought accelerates flash runoff when inundated by sudden floodwaters.",
        "amplification": 0.15,
    },
]
