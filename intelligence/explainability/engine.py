"""
ExplainabilityEngine orchestrator for Phase 10.
Coordinates evidence resolution, factor attribution, structured reasoning,
uncertainty quantification, counterfactual reasoning, and provenance hashing.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from intelligence.explainability.attribution import FactorAttributionEngine
from intelligence.explainability.counterfactual import CounterfactualEngine
from intelligence.explainability.evidence import EvidenceResolver
from intelligence.explainability.formatter import ExplanationFormatter
from intelligence.explainability.provenance import ExplanationProvenanceTracker
from intelligence.explainability.reasoning import ReasoningEngine
from intelligence.explainability.types import (
    EpistemicClassification,
    ExplanationContract,
    ExplanationLevel,
    ExplanationRequest,
    FactorAttribution,
    TargetType,
    UncertaintyItem,
)


class ExplainabilityEngine:
    """
    Central service for synthesizing audit-ready explanations across Phase 2-9 outputs.
    """

    def __init__(self, enable_cache: bool = True):
        self.enable_cache = enable_cache
        self._cache: Dict[str, ExplanationContract] = {}

    def explain(
        self,
        target_type: Union[TargetType, ExplanationRequest],
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
        target_object: Optional[Dict[str, Any]] = None,
        upstream_context: Optional[Dict[str, Any]] = None,
    ) -> ExplanationContract:
        """Unified dispatch to explain any target intelligence output."""
        if isinstance(target_type, ExplanationRequest):
            req = target_type
            target_type = req.target_type
            target_id = req.target_id
            level = req.level
            target_object = req.target_object
            upstream_context = req.upstream_context

        if target_id is None:
            target_id = "UNKNOWN-TARGET"

        cache_key = f"{target_type.value}:{target_id}:{level.value}"
        if self.enable_cache and target_object is None and cache_key in self._cache:
            return self._cache[cache_key]

        obj = target_object or {}

        if target_type == TargetType.HAZARD:
            exp = self.explain_hazard(obj, target_id=target_id, level=level)
        elif target_type == TargetType.PREDICTION:
            exp = self.explain_prediction(obj, target_id=target_id, level=level)
        elif target_type == TargetType.COMPOUND:
            exp = self.explain_compound(obj, target_id=target_id, level=level)
        elif target_type == TargetType.VULNERABILITY:
            exp = self.explain_vulnerability(obj, target_id=target_id, level=level)
        elif target_type == TargetType.EVACUATION:
            exp = self.explain_evacuation(obj, target_id=target_id, level=level)
        elif target_type == TargetType.RESPONSE:
            exp = self.explain_response_action(obj, target_id=target_id, level=level)
        elif target_type == TargetType.SIMULATION:
            exp = self.explain_simulation(obj, target_id=target_id, level=level)
        else:
            raise ValueError(f"Unsupported target_type: {target_type}")

        self._cache[cache_key] = exp
        return exp

    def explain_hazard(
        self,
        hazard_dict: Dict[str, Any],
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 3 hazard result (heat, flood, or drought)."""
        h_id = target_id or hazard_dict.get("hazard_id", "HAZ-UNKNOWN")
        h_type = str(hazard_dict.get("hazard") or hazard_dict.get("hazard_type") or "flood").lower()
        model_ver = hazard_dict.get("model_version", f"{h_type}-v1")
        is_sim = bool(hazard_dict.get("simulated", False))
        classification = EpistemicClassification.SIMULATED if is_sim else EpistemicClassification.OBSERVED

        features = hazard_dict.get("features") or hazard_dict

        if "heat" in h_type:
            fname, fexpr, factors = FactorAttributionEngine.attribute_heat(features)
            cf = []
        elif "drought" in h_type:
            fname, fexpr, factors = FactorAttributionEngine.attribute_drought(features)
            cf = []
        else:
            # Default flood
            fname, fexpr, factors = FactorAttributionEngine.attribute_flood(features)
            sev = float(hazard_dict.get("severity", 0.0))
            cf = CounterfactualEngine.generate_flood_counterfactuals(features, sev)

        evidence = EvidenceResolver.resolve_hazard_evidence(hazard_dict)
        summary = ExplanationFormatter.generate_summary_text("hazard", h_id, classification.value, factors)

        # Provenance
        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.HAZARD.value,
            target_id=h_id,
            model_version=model_ver,
            classification=classification.value,
            formula_name=fname,
            formula_expression=fexpr,
            factors=factors,
            evidence=evidence,
            counterfactuals=cf,
            simulated=is_sim,
        )

        return ExplanationContract(
            explanation_id=f"EXP-HAZ-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.HAZARD,
            target_id=h_id,
            model_version=model_ver,
            classification=classification,
            summary=summary,
            explanation_level=level,
            formula_name=fname,
            formula_expression=fexpr,
            factors=factors,
            reasoning_steps=[f"Deterministic evaluation using {fname}.", f"Evaluated raw inputs against baseline bounds."],
            evidence=evidence,
            uncertainty=[],
            counterfactuals=cf,
            provenance_hash=prov_hash,
            simulated=is_sim,
        )

    def explain_prediction(
        self,
        pred_dict: Dict[str, Any],
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 4 deterministic trend prediction."""
        p_id = target_id or pred_dict.get("prediction_id", "PRED-UNKNOWN")
        horizon = pred_dict.get("forecast_horizon_minutes", 60)
        model_ver = pred_dict.get("model_version", "prediction-v1")
        is_sim = bool(pred_dict.get("simulated", False))
        classification = EpistemicClassification.SIMULATED if is_sim else EpistemicClassification.PREDICTED

        steps, uncertainties = ReasoningEngine.explain_prediction_reasoning(pred_dict)
        evidence = EvidenceResolver.resolve_prediction_evidence(pred_dict)
        sev = float(pred_dict.get("severity", pred_dict.get("predicted_severity", 0.0)))
        h_name = pred_dict.get("hazard", "hazard")
        summary = f"{classification.value} +{horizon}m forecast projects {h_name} escalation to severity {sev:.2f} based on historical trajectory."

        base_val = float(pred_dict.get("baseline_severity", pred_dict.get("baseline_component", 0.0)))
        delta_val = float(pred_dict.get("trend_delta", max(0.0, sev - base_val)))

        factors = [
            FactorAttribution(
                factor_name="forecast_horizon",
                display_name="Prediction Horizon",
                input_value=float(horizon),
                normalized_value=round(min(1.0, float(horizon) / 360.0), 4),
                weight=0.30,
                contribution=round(0.30 * min(1.0, float(horizon) / 360.0), 4),
                unit="minutes",
                description=f"Temporal projection distance of +{horizon} minutes.",
            ),
            FactorAttribution(
                factor_name="baseline_persistence",
                display_name="Historical Baseline Persistence",
                input_value=base_val,
                normalized_value=round(min(1.0, max(0.0, base_val)), 4),
                weight=0.40,
                contribution=round(0.40 * min(1.0, max(0.0, base_val)), 4),
                description="Observed persistence baseline prior to trend extrapolation.",
            ),
            FactorAttribution(
                factor_name="trend_extrapolation",
                display_name="Extrapolated Rate of Change",
                input_value=delta_val,
                normalized_value=round(min(1.0, max(0.0, abs(delta_val))), 4),
                weight=0.30,
                contribution=round(0.30 * min(1.0, max(0.0, abs(delta_val))), 4),
                description="Extrapolated slope component driving forward trend.",
            ),
        ]

        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.PREDICTION.value,
            target_id=p_id,
            model_version=model_ver,
            classification=classification.value,
            formula_name="OLS Temporal Trend Extrapolation",
            factors=factors,
            evidence=evidence,
            simulated=is_sim,
        )

        return ExplanationContract(
            explanation_id=f"EXP-PRED-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.PREDICTION,
            target_id=p_id,
            model_version=model_ver,
            classification=classification,
            summary=summary,
            explanation_level=level,
            formula_name="OLS Temporal Trend Extrapolation with Physical Clamping",
            formula_expression=f"y_forecast = clamp(y_baseline + slope * horizon_delta, 0.0, 1.0)",
            factors=factors,
            reasoning_steps=steps,
            evidence=evidence,
            uncertainty=uncertainties,
            counterfactuals=[],
            provenance_hash=prov_hash,
            simulated=is_sim,
        )

    def explain_compound(
        self,
        comp_dict: Dict[str, Any],
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 5 compound or cascading disaster event."""
        c_id = target_id or comp_dict.get("event_id", "COMP-UNKNOWN")
        model_ver = comp_dict.get("rule_version", "compound-rules-v1")
        is_sim = bool(comp_dict.get("simulated", False))
        classification = EpistemicClassification.SIMULATED if is_sim else EpistemicClassification.INFERRED

        steps, uncertainties = ReasoningEngine.explain_compound_reasoning(comp_dict)
        evidence = EvidenceResolver.resolve_compound_evidence(comp_dict)
        chain = comp_dict.get("chain") or comp_dict.get("causal_chain") or []
        chain_str = " -> ".join(chain) if chain else "compound multi-hazard"
        summary = f"{classification.value} cascading disaster detected across chain: {chain_str}."

        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.COMPOUND.value,
            target_id=c_id,
            model_version=model_ver,
            classification=classification.value,
            formula_name="Deterministic Causal DAG Traversal",
            evidence=evidence,
            simulated=is_sim,
        )

        return ExplanationContract(
            explanation_id=f"EXP-COMP-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.COMPOUND,
            target_id=c_id,
            model_version=model_ver,
            classification=classification,
            summary=summary,
            explanation_level=level,
            formula_name="Deterministic Causal DAG Traversal & Non-Linear Amplification",
            reasoning_steps=steps,
            evidence=evidence,
            uncertainty=uncertainties,
            counterfactuals=[],
            provenance_hash=prov_hash,
            simulated=is_sim,
        )

    def explain_vulnerability(
        self,
        vuln_dict: Dict[str, Any],
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 6 human vulnerability and exposure assessment."""
        z_id = target_id or vuln_dict.get("zone_id", "ZONE-UNKNOWN")
        model_ver = vuln_dict.get("formula_version", "vulnerability-v1")
        is_sim = bool(vuln_dict.get("simulated", False))
        classification = EpistemicClassification.SIMULATED if is_sim else EpistemicClassification.INFERRED

        fname, fexpr, factors = FactorAttributionEngine.attribute_human_impact(vuln_dict)
        evidence = EvidenceResolver.resolve_vulnerability_evidence(vuln_dict)
        impact = float(vuln_dict.get("human_impact", 0.0))
        summary = f"{classification.value} human impact for {z_id} is {impact:.2f}, driven primarily by {factors[0].display_name.lower()}."

        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.VULNERABILITY.value,
            target_id=z_id,
            model_version=model_ver,
            classification=classification.value,
            formula_name=fname,
            formula_expression=fexpr,
            factors=factors,
            evidence=evidence,
            simulated=is_sim,
        )

        return ExplanationContract(
            explanation_id=f"EXP-VULN-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.VULNERABILITY,
            target_id=z_id,
            model_version=model_ver,
            classification=classification,
            summary=summary,
            explanation_level=level,
            formula_name=fname,
            formula_expression=fexpr,
            factors=factors,
            reasoning_steps=[f"Synthesized spatial exposure with demographic vulnerability.", f"Calculated healthcare access penalty."],
            evidence=evidence,
            uncertainty=[],
            counterfactuals=[],
            provenance_hash=prov_hash,
            simulated=is_sim,
        )

    def explain_evacuation(
        self,
        evac_dict: Dict[str, Any],
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 7 evacuation routing and shelter directive."""
        e_id = target_id or evac_dict.get("evacuation_id", "EVAC-UNKNOWN")
        model_ver = evac_dict.get("routing_version", "dijkstra-hazard-v1")
        is_sim = bool(evac_dict.get("simulated", False))
        classification = EpistemicClassification.SIMULATED if is_sim else EpistemicClassification.OBSERVED

        steps, uncertainties = ReasoningEngine.explain_evacuation_reasoning(evac_dict)
        evidence = EvidenceResolver.resolve_evacuation_evidence(evac_dict)
        cf = CounterfactualEngine.generate_evacuation_counterfactuals(evac_dict)
        status = evac_dict.get("status", "RECOMMENDED")
        summary = f"{classification.value} evacuation recommendation for {evac_dict.get('zone_id', 'zone')}: {status}."

        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.EVACUATION.value,
            target_id=e_id,
            model_version=model_ver,
            classification=classification.value,
            formula_name="Hazard-Aware Dijkstra Routing",
            evidence=evidence,
            counterfactuals=cf,
            simulated=is_sim,
        )

        return ExplanationContract(
            explanation_id=f"EXP-EVAC-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.EVACUATION,
            target_id=e_id,
            model_version=model_ver,
            classification=classification,
            summary=summary,
            explanation_level=level,
            formula_name="Hazard-Aware Dijkstra Routing with Exponential Penalty",
            formula_expression="cost(edge) = travel_time * (1 + 10 * hazard^2) * (1 + 5 * (1 - accessibility))",
            reasoning_steps=steps,
            evidence=evidence,
            uncertainty=uncertainties,
            counterfactuals=cf,
            provenance_hash=prov_hash,
            simulated=is_sim,
        )

    def explain_response_action(
        self,
        action_dict: Any,
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 9 AI emergency response plan recommendation."""
        if hasattr(action_dict, "model_dump"):
            action_dict = action_dict.model_dump()

        # Validate controlled action vocabulary
        from intelligence.response.types import ActionType
        raw_act = action_dict.get("action", "MONITOR")
        if isinstance(raw_act, ActionType):
            act_name = raw_act.value
        else:
            act_name = str(raw_act).upper()

        valid_action_values = {a.value for a in ActionType}
        if act_name not in valid_action_values:
            raise ValueError(f"Invalid response action '{act_name}': not in Phase 9 controlled vocabulary ActionType")

        a_id = target_id or action_dict.get("action_id", "ACT-UNKNOWN")
        model_ver = action_dict.get("rules_version", "response-rules-v1")
        is_sim = bool(action_dict.get("simulated", False))
        classification = EpistemicClassification.SIMULATED if is_sim else EpistemicClassification.OBSERVED

        fname, fexpr, factors = FactorAttributionEngine.attribute_response_priority(action_dict)
        steps, uncertainties = ReasoningEngine.explain_response_reasoning(action_dict)
        cf = CounterfactualEngine.generate_response_counterfactuals(action_dict)
        evidence = EvidenceResolver.resolve_response_evidence(action_dict)
        target = action_dict.get("target") or action_dict.get("target_zone") or "TARGET"
        summary = f"{classification.value} emergency action {act_name} recommended for {target}."

        # Enforce mandatory human review for critical actions or low confidence
        critical_actions = {"EVACUATE_ZONE", "REDIRECT_EVACUATION", "REQUEST_FIELD_VERIFICATION", "REASSESS"}
        conf = float(action_dict.get("confidence", 0.85))
        is_critical = (act_name in critical_actions) or (conf < 0.50)
        user_req_review = bool(action_dict.get("requires_human_review") or action_dict.get("human_review_required"))
        requires_review = user_req_review or is_critical

        if requires_review and not any("HUMAN SUPERVISOR REVIEW REQUIRED" in s for s in steps):
            steps.append("HUMAN SUPERVISOR REVIEW REQUIRED: Safety-critical emergency directive or low-confidence evidence.")

        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.RESPONSE.value,
            target_id=a_id,
            model_version=model_ver,
            classification=classification.value,
            formula_name=fname,
            formula_expression=fexpr,
            factors=factors,
            evidence=evidence,
            counterfactuals=cf,
            simulated=is_sim,
        )

        return ExplanationContract(
            explanation_id=f"EXP-ACT-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.RESPONSE,
            target_id=a_id,
            model_version=model_ver,
            classification=classification,
            summary=summary,
            explanation_level=level,
            formula_name=fname,
            formula_expression=fexpr,
            factors=factors,
            reasoning_steps=steps,
            evidence=evidence,
            uncertainty=uncertainties,
            counterfactuals=cf,
            provenance_hash=prov_hash,
            simulated=is_sim,
        )

    def explain_simulation(
        self,
        sim_dict: Any,
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 8 digital twin what-if simulation run."""
        if hasattr(sim_dict, "model_dump"):
            sim_dict = sim_dict.model_dump()

        s_id = target_id or sim_dict.get("simulation_id") or sim_dict.get("scenario_id", "SIM-UNKNOWN")
        params = sim_dict.get("parameters", {})
        if hasattr(params, "model_dump"):
            params = params.model_dump()

        param_items = sorted(params.items()) if isinstance(params, dict) else []
        param_str = ", ".join(f"{k}={v}" for k, v in param_items if v is not None) if param_items else "standard perturbation"
        summary = f"SIMULATED WHAT-IF scenario '{sim_dict.get('scenario_id', 'SCENARIO')}' applying perturbations: {param_str}."

        prov_hash = ExplanationProvenanceTracker.compute_provenance_hash(
            target_type=TargetType.SIMULATION.value,
            target_id=s_id,
            model_version="simulation-v1",
            classification=EpistemicClassification.SIMULATED.value,
            formula_name="Controlled Digital Twin Perturbation",
            formula_expression=param_str,
            simulated=True,
        )

        return ExplanationContract(
            explanation_id=f"EXP-SIM-{uuid.uuid4().hex[:8].upper()}",
            target_type=TargetType.SIMULATION,
            target_id=s_id,
            model_version="simulation-v1",
            classification=EpistemicClassification.SIMULATED,
            summary=summary,
            explanation_level=level,
            formula_name="Controlled Digital Twin Perturbation & Multi-Phase Propagation",
            reasoning_steps=[
                f"Applied hypothetical parameter shifts to baseline digital twin state: {param_str}.",
                "Propagated perturbations sequentially through Phase 2-6 models.",
                "Computed delta against live baseline observations.",
            ],
            evidence=[],
            uncertainty=[
                UncertaintyItem(
                    source="hypothetical_simulation",
                    level="HIGH",
                    description="Simulation represents counterfactual modeling, NOT real-world observations.",
                    impact_on_decision="Outputs are strictly for emergency planning and stress-testing.",
                )
            ],
            counterfactuals=[],
            provenance_hash=prov_hash,
            simulated=True,
        )

    def explain_simulation_delta(
        self,
        sim_result: Any,
        target_id: Optional[str] = None,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> ExplanationContract:
        """Explains a Phase 8 simulation delta against live baseline."""
        return self.explain_simulation(sim_result, target_id=target_id, level=level)

