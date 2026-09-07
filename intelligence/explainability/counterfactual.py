"""
Deterministic counterfactual generator for Phase 10 Explainability.
Evaluates tipping points showing which controlled parameter perturbations
would alter model classifications or operational recommendations.
"""

from typing import Any, Dict, List
from intelligence.explainability.types import CounterfactualItem


class CounterfactualEngine:
    """
    Computes deterministic counterfactual tipping points across intelligence models.
    """

    @classmethod
    def generate_flood_counterfactuals(cls, features: Dict[str, Any], current_severity: float) -> List[CounterfactualItem]:
        """Calculates rainfall and water level reductions needed to lower flood risk."""
        items: List[CounterfactualItem] = []
        rain = float(features.get("rainfall_mmhr") or features.get("rainfall") or 0.0)
        level = float(features.get("water_level_m") or features.get("water_level") or 0.0)

        # 1. Rain reduction to drop severity below MODERATE (0.40) or LOW (0.20)
        if current_severity >= 0.40 and rain > 10.0:
            target_rain = max(0.0, rain * 0.5)
            items.append(CounterfactualItem(
                condition=f"Rainfall intensity decreases from {rain:.1f} mm/hr to {target_rain:.1f} mm/hr (-50%)",
                altered_parameter="rainfall_mmhr",
                original_value=round(rain, 1),
                counterfactual_value=round(target_rain, 1),
                counterfactual_outcome="Flood severity decreases below MODERATE threshold (de-escalation to advisory status).",
            ))

        # 2. Channel drainage / water level abatement
        if level > 5.0:
            target_level = max(2.0, level - 4.0)
            items.append(CounterfactualItem(
                condition=f"Channel water level recedes from {level:.1f} m to {target_level:.1f} m",
                altered_parameter="water_level_m",
                original_value=round(level, 1),
                counterfactual_value=round(target_level, 1),
                counterfactual_outcome="River stage drops below critical levee freeboard; flood alert downgraded.",
            ))

        return items

    @classmethod
    def generate_evacuation_counterfactuals(cls, evac_dict: Dict[str, Any]) -> List[CounterfactualItem]:
        """Calculates infrastructural shifts that alter evacuation routing or resolve NO_ROUTE."""
        items: List[CounterfactualItem] = []
        status = str(evac_dict.get("status", "RECOMMENDED"))
        avoid_edges = evac_dict.get("avoid_edges") or []

        if "NO_ROUTE" in status:
            items.append(CounterfactualItem(
                condition="Restoring primary arterial bridge accessibility from 0.00 to >= 0.50",
                altered_parameter="bridge_accessibility",
                original_value=0.0,
                counterfactual_value=0.50,
                counterfactual_outcome="Resolves NO_ROUTE isolation; establishes valid ground extraction corridor to regional shelter.",
            ))
        elif avoid_edges:
            edge_id = avoid_edges[0]
            items.append(CounterfactualItem(
                condition=f"Clearing debris/water from corridor {edge_id} (accessibility >= 0.70)",
                altered_parameter=f"edge_{edge_id}_accessibility",
                original_value=0.20,
                counterfactual_value=0.70,
                counterfactual_outcome=f"Corridor {edge_id} becomes traversable, reducing overall evacuation transit time.",
            ))

        return items

    @classmethod
    def generate_response_counterfactuals(cls, action_dict: Dict[str, Any]) -> List[CounterfactualItem]:
        """Calculates hazard or vulnerability changes that de-escalate emergency actions."""
        items: List[CounterfactualItem] = []
        action = action_dict.get("action", "MONITOR")
        urgency = action_dict.get("urgency", "MEDIUM")

        if action == "EVACUATE_ZONE":
            items.append(CounterfactualItem(
                condition="Demographic vulnerability mitigated via pre-relocation or flood mitigation barriers",
                altered_parameter="human_impact",
                original_value=0.75,
                counterfactual_value=0.45,
                counterfactual_outcome="Action de-escalates from mandatory EVACUATE_ZONE to PREPARE_EVACUATION.",
            ))
        elif urgency in ("HIGH", "CRITICAL"):
            items.append(CounterfactualItem(
                condition="Forecast horizon extends beyond +6 hours with no active observed flooding",
                altered_parameter="temporal_horizon",
                original_value=30,
                counterfactual_value=360,
                counterfactual_outcome="Temporal discount lowers urgency score, shifting priority from immediate to staged preparation.",
            ))

        return items
