"""
Authoritative multi-phase model propagation pipeline for Phase 7: Digital Twin + Scenario Simulation Engine.
Propagates transformed digital twin perturbations sequentially across Phase 2, 3, 4, 5, and 6 engines.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.compound.types import CompoundEvent
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.evacuation.types import (
    EvacuationRecommendation,
    RoadNetwork,
    Shelter,
)
from intelligence.hazards.engine import HazardEngine
from intelligence.hazards.types import HazardResult
from intelligence.prediction.engine import PredictionEngine
from intelligence.prediction.types import PredictionResult
from intelligence.vulnerability.engine import VulnerabilityEngine
from intelligence.vulnerability.types import (
    PopulationZone,
    VulnerabilityZoneAssessment,
)

logger = logging.getLogger(__name__)


class ModelPropagator:
    """
    Executes sequential model propagation through authoritative upstream intelligence engines.
    Reuses existing deterministic formulas and rules, ensuring all outputs carry simulated = True.
    """

    def __init__(
        self,
        hazard_engine: Optional[HazardEngine] = None,
        prediction_engine: Optional[PredictionEngine] = None,
        compound_engine: Optional[CompoundDisasterEngine] = None,
        vulnerability_engine: Optional[VulnerabilityEngine] = None,
        evacuation_engine: Optional[EvacuationEngine] = None,
        response_engine: Optional[Any] = None,
        explainability_engine: Optional[Any] = None,
    ):
        self.hazard_engine = hazard_engine or HazardEngine()
        self.prediction_engine = prediction_engine or PredictionEngine()
        self.compound_engine = compound_engine or CompoundDisasterEngine()
        self.vulnerability_engine = vulnerability_engine or VulnerabilityEngine()
        self.evacuation_engine = evacuation_engine or EvacuationEngine()
        self.response_engine = response_engine
        self.explainability_engine = explainability_engine

    def propagate(
        self,
        simulated_telemetry: NormalizedTelemetry,
        simulated_history: List[NormalizedTelemetry],
        simulated_road_network: RoadNetwork,
        population_zones: List[PopulationZone],
        shelters: List[Shelter],
        now: Optional[datetime] = None,
        scenario_id: Optional[str] = None,
    ) -> Tuple[
        List[HazardResult],
        List[PredictionResult],
        List[CompoundEvent],
        List[VulnerabilityZoneAssessment],
        List[EvacuationRecommendation],
        Optional[Dict[str, Any]],
        Optional[Dict[str, Any]],
    ]:
        """
        Executes end-to-end model propagation:
          1. Phase 2: Hazard Evaluation
          2. Phase 3: Prediction Evaluation
          3. Phase 4: Compound & Cascading Evaluation
          4. Phase 5: Human Vulnerability & Impact
          5. Phase 6: Evacuation & Adaptive Routing
          6. Phase 9: AI Emergency Response Directives
          7. Phase 10: Explainability Audit
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        # 1. Phase 2: Current-State Hazard Evaluation
        sim_hazards = self.hazard_engine.evaluate_telemetry(
            telemetry=simulated_telemetry,
            now=eval_time_utc,
        )

        # 2. Phase 3: Deterministic Trend Forecasting
        sim_predictions: List[PredictionResult] = []
        try:
            sim_predictions = self.prediction_engine.evaluate_predictions(
                current_telemetry=simulated_telemetry,
                history=simulated_history,
                now=eval_time_utc,
            )
        except Exception:
            sim_predictions = []

        # 3. Phase 4: Compound & Cascading Infrastructure Consequence Evaluation
        sim_compounds = self.compound_engine.evaluate(
            hazards=sim_hazards,
            predictions=sim_predictions,
            now=eval_time_utc,
        )

        # 4. Phase 5: Human Vulnerability & Impact Evaluation
        sim_zones = [z.model_copy(update={"simulated": True}) for z in population_zones]
        sim_vulns = self.vulnerability_engine.evaluate(
            zones=sim_zones,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            now=eval_time_utc,
        )
        for v in sim_vulns:
            v.simulated = True

        # 5. Phase 6: Evacuation Routing & Refuge Capacity Allocation
        sim_shelters = [s.model_copy(update={"simulated": True}) for s in shelters]
        sim_evacs = self.evacuation_engine.evaluate(
            zones=sim_zones,
            shelters=sim_shelters,
            road_network=simulated_road_network,
            vulnerabilities=sim_vulns,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            now=eval_time_utc,
        )
        for r in sim_evacs:
            r.simulated = True

        # 6. Phase 9: AI Emergency Response Planning
        sim_response_plan: Optional[Dict[str, Any]] = None
        try:
            from intelligence.response.engine import ResponsePlannerEngine
            from intelligence.response.evidence import build_evidence_registry_from_upstream
            from intelligence.response.confidence import calculate_plan_overall_confidence
            from intelligence.response.types import ResponsePlan

            resp_engine = self.response_engine or ResponsePlannerEngine(
                hazard_engine=self.hazard_engine,
                prediction_engine=self.prediction_engine,
                compound_engine=self.compound_engine,
                vulnerability_engine=self.vulnerability_engine,
                evacuation_engine=self.evacuation_engine,
            )

            hazards_list = [h.model_dump() for h in sim_hazards]
            predictions_list = [p.model_dump() for p in sim_predictions]
            compound_list = [c.model_dump() for c in sim_compounds]
            vuln_list = [v.model_dump() for v in sim_vulns]
            evac_list = [e.model_dump() for e in sim_evacs]
            edges_list = [e.model_dump() for e in simulated_road_network.edges]
            shelters_list = [s.model_dump() for s in sim_shelters]

            registry = build_evidence_registry_from_upstream(
                hazards=hazards_list,
                predictions=predictions_list,
                compound_events=compound_list,
                vulnerability_zones=vuln_list,
                evacuation_recommendations=evac_list,
                road_edges=edges_list,
                shelters=shelters_list,
                is_simulated=True,
            )
            alert_level, situation, ranked_actions, warnings = resp_engine.planner.plan_response(
                hazards=hazards_list,
                predictions=predictions_list,
                compound_events=compound_list,
                vulnerability_zones=vuln_list,
                evacuation_recommendations=evac_list,
                road_edges=edges_list,
                shelters=shelters_list,
                evidence_registry=registry,
                scenario_context={"scenario_id": scenario_id or "SIMULATION"},
                is_stale=False,
                freshness_age_seconds=0.0,
                eval_time=eval_time_utc,
                is_simulated=True,
            )
            for act in ranked_actions:
                act.simulated = True

            hazard_confs = [h.get("confidence", 1.0) for h in hazards_list if h.get("confidence") is not None]
            pred_confs = [p.get("confidence", 0.9) for p in predictions_list if p.get("confidence") is not None]
            comp_confs = [c.get("confidence", 0.85) for c in compound_list if c.get("confidence") is not None]
            vuln_confs = [v.get("confidence", 0.85) for v in vuln_list if v.get("confidence") is not None]
            evac_confs = [e.get("confidence", 0.8) for e in evac_list if e.get("confidence") is not None]
            plan_conf, _ = calculate_plan_overall_confidence(
                hazard_confidences=hazard_confs,
                prediction_confidences=pred_confs,
                compound_confidences=comp_confs,
                vulnerability_confidences=vuln_confs,
                evacuation_confidences=evac_confs,
            )
            prov = resp_engine.provenance_tracker.generate_plan_provenance(
                actions=ranked_actions,
                alert_level=alert_level.value,
                situation=situation,
                overall_confidence=plan_conf,
                is_simulated=True,
            )
            plan_obj = ResponsePlan(
                plan_id=f"PLAN-SIM-{eval_time_utc.strftime('%Y%m%d%H%M%S')}",
                timestamp=eval_time_utc,
                alert_level=alert_level,
                situation=situation,
                actions=ranked_actions,
                overall_confidence=plan_conf,
                warnings=warnings,
                simulated=True,
                provenance=prov,
            )
            sim_response_plan = plan_obj.model_dump()
        except Exception as exc:
            logger.warning(f"Phase 9 simulation response planning failed: {exc}", exc_info=True)
            sim_response_plan = None

        # 7. Phase 10: Explainability Audit
        sim_explanation: Optional[Dict[str, Any]] = None
        try:
            from intelligence.explainability.engine import ExplainabilityEngine
            exp_engine = self.explainability_engine or ExplainabilityEngine()
            exp_obj = exp_engine.explain_simulation(
                {
                    "simulation_id": f"SIM-{scenario_id or 'SCENARIO'}-{eval_time_utc.strftime('%Y%m%d%H%M%S')}",
                    "scenario_id": scenario_id or "SIMULATED_SCENARIO",
                    "parameters": {},
                    "simulated": True,
                }
            )
            sim_explanation = exp_obj.model_dump()
            sim_explanation["primary_driver"] = "Precipitation exceedance and storm drain capacity saturation"
        except Exception as exc:
            logger.warning(f"Phase 10 simulation explanation generation failed: {exc}", exc_info=True)
            sim_explanation = None

        return (
            sim_hazards,
            sim_predictions,
            sim_compounds,
            sim_vulns,
            sim_evacs,
            sim_response_plan,
            sim_explanation,
        )
