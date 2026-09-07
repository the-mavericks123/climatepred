"""
Climate Eye View — Phase 9 Response Planner Core Engine.

Coordinates situation assessment, threat alert level classification,
candidate action generation, conflict resolution, prioritization ranking,
and human-in-the-loop review gating.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from intelligence.response.confidence import (
    calculate_plan_overall_confidence,
)
from intelligence.response.evidence import EvidenceRegistry
from intelligence.response.priorities import rank_actions
from intelligence.response.rules import ResponseRuleEngine
from intelligence.response.types import (
    ActionItem,
    ActionStatus,
    ActionType,
    AlertLevel,
    SituationContext,
)


class ResponsePlanner:
    """
    Core decision-support planner that transforms Phase 2–8 intelligence
    into a synthesized, conflict-resolved emergency response plan.
    """

    def __init__(
        self,
        rule_engine: Optional[ResponseRuleEngine] = None,
        edge_accessibility_threshold: float = 0.40,
        alert_level_green_max_hazard: float = 0.40,
        alert_level_yellow_max_hazard: float = 0.70,
        alert_level_orange_hazard_threshold: float = 0.70,
        alert_level_orange_impact_threshold: float = 0.50,
        alert_level_red_hazard_threshold: float = 0.85,
        alert_level_red_impact_threshold: float = 0.70,
    ):
        self.rule_engine = rule_engine or ResponseRuleEngine(
            edge_accessibility_threshold=edge_accessibility_threshold,
        )
        self.edge_accessibility_threshold = edge_accessibility_threshold
        self.alert_level_green_max_hazard = alert_level_green_max_hazard
        self.alert_level_yellow_max_hazard = alert_level_yellow_max_hazard
        self.alert_level_orange_hazard_threshold = alert_level_orange_hazard_threshold
        self.alert_level_orange_impact_threshold = alert_level_orange_impact_threshold
        self.alert_level_red_hazard_threshold = alert_level_red_hazard_threshold
        self.alert_level_red_impact_threshold = alert_level_red_impact_threshold

    def assess_situation(
        self,
        hazards: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        compound_events: List[Dict[str, Any]],
        vulnerability_zones: List[Dict[str, Any]],
        evacuation_recommendations: List[Dict[str, Any]],
        road_edges: List[Dict[str, Any]],
        shelters: List[Dict[str, Any]],
        scenario_context: Optional[Dict[str, Any]] = None,
        is_stale: bool = False,
        freshness_age_seconds: float = 0.0,
        eval_time: Optional[datetime] = None,
    ) -> SituationContext:
        """
        Builds the structured situation context representation.
        """
        now = eval_time or datetime.now(timezone.utc)
        road_anomalies = [
            e for e in road_edges
            if e.get("closed") or float(e.get("accessibility", 1.0)) < self.edge_accessibility_threshold or float(e.get("hazard_risk", 0.0)) >= 0.70
        ]
        return SituationContext(
            observed_hazards=hazards,
            predicted_hazards=predictions,
            compound_events=compound_events,
            affected_zones=vulnerability_zones,
            evacuation_demands=evacuation_recommendations,
            shelter_statuses=shelters,
            road_network_anomalies=road_anomalies,
            simulation_context=scenario_context,
            timestamp=now,
            is_stale=is_stale,
            freshness_age_seconds=freshness_age_seconds,
        )

    def determine_alert_level(
        self,
        hazards: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        compound_events: List[Dict[str, Any]],
        vulnerability_zones: List[Dict[str, Any]],
        evacuation_recommendations: List[Dict[str, Any]],
    ) -> AlertLevel:
        """
        Determines the overall regional alert level deterministically.
        Rules:
        - RED: Max hazard >= 0.85 AND human impact >= 0.70, OR any zone with NO_ROUTE and population exposed > 0,
               OR compound severity >= 0.85.
        - ORANGE: Max hazard >= 0.70 OR human impact >= 0.50 OR compound severity >= 0.70.
        - YELLOW: Max hazard >= 0.40 OR any prediction >= 0.50.
        - GREEN: All hazards < 0.40 and no significant threats.
        """
        max_hazard = max([float(h.get("severity", 0.0)) for h in hazards], default=0.0)
        max_impact = max([float(v.get("human_impact", 0.0)) for v in vulnerability_zones], default=0.0)
        max_compound = max([float(c.get("severity", 0.0)) for c in compound_events], default=0.0)
        max_pred = max([float(p.get("severity", 0.0)) for p in predictions], default=0.0)

        has_no_route = any(e.get("status") == "NO_ROUTE" for e in evacuation_recommendations)

        # 1. Check RED criteria
        if (max_hazard >= self.alert_level_red_hazard_threshold and max_impact >= self.alert_level_red_impact_threshold) or (has_no_route and max_impact > 0.3) or max_compound >= 0.85:
            return AlertLevel.RED

        # 2. Check ORANGE criteria
        if (max_hazard >= self.alert_level_orange_hazard_threshold) or (max_impact >= self.alert_level_orange_impact_threshold) or (max_compound >= 0.70):
            return AlertLevel.ORANGE

        # 3. Check YELLOW criteria
        if (max_hazard >= self.alert_level_green_max_hazard) or (max_pred >= 0.50):
            return AlertLevel.YELLOW

        return AlertLevel.GREEN

    def resolve_conflicts(
        self,
        candidate_actions: List[ActionItem],
        road_edges: List[Dict[str, Any]],
        shelters: List[Dict[str, Any]],
    ) -> List[ActionItem]:
        """
        Resolves conflicts among candidate recommendations using authoritative upstream state.

        Conflict Scenarios:
        1. Routing over unsafe edges: If an evacuation action relies on a road/bridge marked closed
           or impassable, that path is marked BLOCKED and redirected.
        2. Compromised shelter allocation: If an evacuation route directs people to a shelter
           that is unsafe (safe=False or hazard_risk >= 0.60) or at 0 capacity, that recommendation
           is marked BLOCKED and superseded by REDIRECT_EVACUATION.
        3. Contradictory zone directives: If a zone has both EVACUATE_ZONE and MONITOR,
           the higher-urgency action marks the lower-urgency action SUPERSEDED.
        """
        closed_edge_ids = {
            e.get("edge_id") for e in road_edges
            if e.get("closed") or float(e.get("accessibility", 1.0)) < self.edge_accessibility_threshold
        }
        unsafe_shelter_ids = {
            s.get("shelter_id") for s in shelters
            if not bool(s.get("safe", True)) or float(s.get("hazard_risk", 0.0)) >= 0.60
        }
        exhausted_shelter_ids = {
            s.get("shelter_id") for s in shelters
            if int(s.get("capacity", 0)) - int(s.get("current_occupancy", 0)) <= 0
        }

        resolved: List[ActionItem] = []

        for action in candidate_actions:
            act_dict = action.model_dump()

            # Conflict 1: Action references a closed/impassable road segment
            if action.target in closed_edge_ids and action.action not in (ActionType.CLOSE_ROAD, ActionType.CLOSE_BRIDGE, ActionType.REQUEST_FIELD_VERIFICATION):
                act_dict["status"] = ActionStatus.BLOCKED
                act_dict["conflict_ids"].append(f"CONFLICT-CLOSED-EDGE-{action.target}")
                act_dict["requires_human_review"] = True
                act_dict["review_reason"] = f"Corridor {action.target} is impassable or closed. Action blocked."

            # Conflict 2: Evacuation or allocation to an unsafe or exhausted shelter
            elif action.target in unsafe_shelter_ids and action.action != ActionType.REDIRECT_EVACUATION:
                act_dict["status"] = ActionStatus.BLOCKED
                act_dict["conflict_ids"].append(f"CONFLICT-UNSAFE-SHELTER-{action.target}")
                act_dict["requires_human_review"] = True
                act_dict["review_reason"] = f"Destination shelter {action.target} is compromised by hazards. Action blocked."

            elif action.target in exhausted_shelter_ids and action.action not in (ActionType.OPEN_SHELTER, ActionType.REDIRECT_EVACUATION):
                act_dict["status"] = ActionStatus.CONDITIONAL
                act_dict["conflict_ids"].append(f"CONFLICT-EXHAUSTED-SHELTER-{action.target}")
                act_dict["requires_human_review"] = True
                act_dict["review_reason"] = f"Destination shelter {action.target} capacity is exhausted. Awaiting secondary site."

            resolved.append(ActionItem(**act_dict))

        # Conflict 3: Deduplicate contradictory zone directives
        # If zone has EVACUATE_ZONE, any MONITOR or ISSUE_WARNING for that same zone is superseded
        evac_zones = {a.target for a in resolved if a.action == ActionType.EVACUATE_ZONE and a.status == ActionStatus.RECOMMENDED}
        final_list: List[ActionItem] = []
        for a in resolved:
            if a.target in evac_zones and a.action in (ActionType.MAINTAIN_MONITORING, ActionType.MONITOR):
                a_dict = a.model_dump()
                a_dict["status"] = ActionStatus.SUPERSEDED
                a_dict["conflict_ids"].append(f"SUPERSEDED-BY-EVAC-{a.target}")
                final_list.append(ActionItem(**a_dict))
            else:
                final_list.append(a)

        return final_list

    def plan_response(
        self,
        hazards: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        compound_events: List[Dict[str, Any]],
        vulnerability_zones: List[Dict[str, Any]],
        evacuation_recommendations: List[Dict[str, Any]],
        road_edges: List[Dict[str, Any]],
        shelters: List[Dict[str, Any]],
        evidence_registry: EvidenceRegistry,
        scenario_context: Optional[Dict[str, Any]] = None,
        is_stale: bool = False,
        freshness_age_seconds: float = 0.0,
        eval_time: Optional[datetime] = None,
        is_simulated: bool = False,
    ) -> Tuple[AlertLevel, SituationContext, List[ActionItem], List[str]]:
        """
        Executes the end-to-end deterministic planning pipeline.
        Returns: (alert_level, situation_context, ranked_actions, warnings).
        """
        warnings: List[str] = []

        # 1. Situation Assessment
        situation = self.assess_situation(
            hazards=hazards,
            predictions=predictions,
            compound_events=compound_events,
            vulnerability_zones=vulnerability_zones,
            evacuation_recommendations=evacuation_recommendations,
            road_edges=road_edges,
            shelters=shelters,
            scenario_context=scenario_context,
            is_stale=is_stale,
            freshness_age_seconds=freshness_age_seconds,
            eval_time=eval_time,
        )

        # 2. Threat Classification (Alert Level)
        alert_level = self.determine_alert_level(
            hazards=hazards,
            predictions=predictions,
            compound_events=compound_events,
            vulnerability_zones=vulnerability_zones,
            evacuation_recommendations=evacuation_recommendations,
        )

        # 3. Action Generation
        candidate_actions = self.rule_engine.generate_candidate_actions(
            hazards=hazards,
            predictions=predictions,
            compound_events=compound_events,
            vulnerability_zones=vulnerability_zones,
            evacuation_recommendations=evacuation_recommendations,
            road_edges=road_edges,
            shelters=shelters,
            evidence_registry=evidence_registry,
            is_stale=is_stale,
            is_simulated=is_simulated,
        )

        # 4. Conflict Resolution
        resolved_actions = self.resolve_conflicts(
            candidate_actions=candidate_actions,
            road_edges=road_edges,
            shelters=shelters,
        )

        # 5. Prioritization & Rank Assignment
        ranked_actions = rank_actions(resolved_actions)

        # 6. Check for Plan-level Warnings
        if is_stale:
            warnings.append("STALE_DATA: Input telemetry exceeds freshness threshold; confidence scores discounted.")
        if any(e.get("status") == "NO_ROUTE" for e in evacuation_recommendations):
            warnings.append("NO_ROUTE: One or more demographic zones have no feasible ground evacuation path.")
        if any(a.confidence < 0.50 for a in ranked_actions):
            warnings.append("LOW_CONFIDENCE: Multiple recommendations carry low model confidence.")

        return alert_level, situation, ranked_actions, warnings
