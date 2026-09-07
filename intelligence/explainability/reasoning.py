"""
Structured reasoning and uncertainty analyzer for Phase 10 Explainability.
Generates step-by-step logical rationales and epistemic uncertainty assessments
across predictions, compound disasters, evacuation directives, and response plans.
"""

from typing import Any, Dict, List, Tuple
from intelligence.explainability.types import UncertaintyItem


class ReasoningEngine:
    """
    Generates step-by-step reasoning derivations and uncertainty evaluations.
    """

    @classmethod
    def explain_prediction_reasoning(cls, pred_dict: Dict[str, Any]) -> Tuple[List[str], List[UncertaintyItem]]:
        """Generates reasoning steps and uncertainty bounds for a prediction result."""
        horizon = pred_dict.get("forecast_horizon_minutes", 60)
        sev = float(pred_dict.get("severity", 0.0))
        base_sev = float(pred_dict.get("baseline_severity", 0.0))
        model_type = pred_dict.get("model_type", "deterministic_ols_trend")
        hist_count = int(pred_dict.get("historical_points_count", 6))
        trend = "increasing" if sev > base_sev else ("decreasing" if sev < base_sev else "stable")

        steps = [
            f"1. Telemetry Ingestion: Retrieved historical window with {hist_count} observations.",
            f"2. Trend Analysis: Calculated OLS rate of change; baseline severity was {base_sev:.2f}.",
            f"3. Forecast Extrapolation: Applied {model_type} forward to +{horizon} min horizon.",
            f"4. Physical Bound Clamping: Projected trajectory yields {trend} hazard trend reaching severity {sev:.2f}.",
            f"5. Confidence Discounting: Applied temporal decay factor for {horizon}-minute forecast distance.",
        ]

        uncertainty_level = "LOW" if horizon <= 30 else ("MODERATE" if horizon <= 60 else "HIGH")
        uncertainties = [
            UncertaintyItem(
                source="forecast_horizon_decay",
                level=uncertainty_level,
                description=f"Model confidence diminishes as forecast horizon expands (+{horizon} min).",
                impact_on_decision="Long-range forecasts (+6h) should trigger preparedness rather than immediate evacuation.",
            ),
            UncertaintyItem(
                source="sensor_telemetry_density",
                level="LOW" if hist_count >= 5 else "MODERATE",
                description=f"Derived from {hist_count} historical time-series points.",
                impact_on_decision="Sparser series increase linear regression slope variance.",
            )
        ]
        return steps, uncertainties

    @classmethod
    def explain_compound_reasoning(cls, comp_dict: Dict[str, Any]) -> Tuple[List[str], List[UncertaintyItem]]:
        """Generates reasoning steps for compound and cascading disasters."""
        chain = comp_dict.get("chain") or comp_dict.get("causal_chain") or []
        rule_version = comp_dict.get("rule_version", "compound-rules-v1")
        rule_id = comp_dict.get("rule_id")
        sev = float(comp_dict.get("severity", 0.0))
        drivers = comp_dict.get("drivers", [])

        chain_str = " -> ".join(chain) if chain else "concurrent multi-hazard interaction"
        rule_desc = f"{rule_id} (version: {rule_version})" if rule_id else f"version: {rule_version}"
        steps = [
            f"1. Concurrent Event Detection: Identified overlapping environmental stress states.",
            f"2. Causal Chain Traversal: Traced causal sequence: {chain_str}.",
            f"3. Rule Application: Evaluated deterministic cascade rule {rule_desc}.",
            f"4. Compound Amplification: Applied interaction bonus yielding composite severity {sev:.2f}.",
        ]
        for d in drivers[:3]:
            steps.append(f"• Driver: {d}")

        uncertainties = [
            UncertaintyItem(
                source="multi_hazard_correlation",
                level="MODERATE",
                description="Cross-hazard non-linear feedbacks may amplify local infrastructure failure.",
                impact_on_decision="Demands pre-positioning of multi-hazard emergency equipment along shared access corridors.",
            )
        ]
        return steps, uncertainties

    @classmethod
    def explain_evacuation_reasoning(cls, evac_dict: Dict[str, Any]) -> Tuple[List[str], List[UncertaintyItem]]:
        """Generates reasoning steps for evacuation routing and shelter assignment."""
        status = str(evac_dict.get("status", "RECOMMENDED"))
        zone_id = evac_dict.get("zone_id", "ZONE-UNKNOWN")
        pop_evac = int(evac_dict.get("population_to_evacuate", 0))
        dest = evac_dict.get("destination") or {}
        route = evac_dict.get("route") or {}
        avoid = evac_dict.get("avoid_edges") or []

        if "NO_ROUTE" in status:
            steps = [
                f"1. Evacuation Requirement: Zone {zone_id} population requires extraction.",
                f"2. Network Traversal Failure: Evaluated all topological paths to designated shelters.",
                f"3. Infrastructure Severance: Access corridors impassable or closed due to hazard exposure.",
                f"4. Rejection of Infeasible Paths: Zero safe routes satisfy minimum accessibility threshold.",
                f"5. NO_ROUTE Generation: Routing engine declared isolation. Escalated to incident commander.",
            ]
            uncertainties = [
                UncertaintyItem(
                    source="road_network_isolation",
                    level="CRITICAL",
                    description="Ground route connectivity broken. Real-time physical road conditions unverified.",
                    impact_on_decision="Urgent field reconnaissance required. Synthetic routes strictly prohibited.",
                )
            ]
        else:
            shelter_name = dest.get("shelter_name", dest.get("shelter_id", "Designated Shelter"))
            time_min = float(route.get("estimated_travel_minutes", 0.0))
            steps = [
                f"1. Demand Assessment: Zone {zone_id} has {pop_evac:,} residents requiring relocation.",
                f"2. Shelter Screening: Screened candidate facilities for structural safety and capacity.",
                f"3. Shelter Assignment: Selected {shelter_name} (adequate remaining capacity).",
                f"4. Dijkstra Hazard Routing: Calculated optimal path minimizing hazard exposure and travel time ({time_min:.1f} min).",
                f"5. Infrastructure Avoidance: Excluded {len(avoid)} degraded or impassable road segments.",
            ]
            uncertainties = [
                UncertaintyItem(
                    source="traffic_congestion_assumption",
                    level="MODERATE",
                    description="Travel times assume baseline free-flow velocities with hazard degradation.",
                    impact_on_decision="Surge evacuee volume may cause localized bottlenecks on primary arterial egress.",
                )
            ]

        return steps, uncertainties

    @classmethod
    def explain_response_reasoning(cls, action_dict: Dict[str, Any]) -> Tuple[List[str], List[UncertaintyItem]]:
        """Generates reasoning steps for an AI Response Plan action item."""
        action = action_dict.get("action", "MONITOR")
        target = action_dict.get("target", "REGION")
        prio = action_dict.get("priority", 1)
        urg = action_dict.get("urgency", "MEDIUM")
        review = bool(action_dict.get("requires_human_review") or action_dict.get("human_review_required", False))
        reason = action_dict.get("reason", "")

        steps = [
            f"1. Rule Trigger: Upstream hazard and demographic conditions satisfied criteria for {action}.",
            f"2. Target Identification: Action assigned to {target}.",
            f"3. Priority Scoring: Ranked at priority {prio} with {urg} urgency level.",
            f"4. Conflict Resolution: Evaluated against operational constraints (no blocked route or shelter conflicts).",
            f"5. Operational Directive: {reason}",
        ]
        if review:
            review_reason = action_dict.get("review_reason", "High consequence emergency action.")
            steps.append(f"6. Mandatory Review Gate: HUMAN SUPERVISOR REVIEW REQUIRED ({review_reason}).")

        uncertainties = [
            UncertaintyItem(
                source="decision_support_nature",
                level="LOW",
                description="Recommendation generated by deterministic expert rules for human authorization.",
                impact_on_decision="Human incident commander retains legal and statutory execution responsibility.",
            )
        ]
        return steps, uncertainties
