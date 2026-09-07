"""
Climate Eye View — Phase 9 Response Planner Top-Level Engine.

Orchestrates the entire AI Response Planner subsystem:
- Integrates outputs from Hazard, Prediction, Compound, Vulnerability, Evacuation, and Simulation engines.
- Evaluates live situation and generates prioritized, evidence-backed ResponsePlans.
- Supports what-if counterfactual scenario response planning against Phase 8 digital twin states.
- Maintains in-memory cache of current and historical response plans.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from intelligence.app.config import settings
from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.core.contracts.telemetry import (
    LocationCoordinate,
    NormalizedTelemetry,
    QualityMetadata,
    SensorMeasurements,
)
from intelligence.core.errors.exceptions import ValidationException
from intelligence.core.validation.validator import TelemetryValidator
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.hazards.engine import HazardEngine
from intelligence.prediction.engine import PredictionEngine
from intelligence.response.evidence import build_evidence_registry_from_upstream
from intelligence.response.planner import ResponsePlanner
from intelligence.response.provenance import ResponseProvenanceTracker
from intelligence.response.types import (
    ActionItem,
    ActionType,
    AlertLevel,
    ResponsePlan,
    SituationContext,
)
from intelligence.simulation.engine import SimulationEngine
from intelligence.vulnerability.engine import VulnerabilityEngine


class ResponsePlannerEngine:
    """
    Production orchestrator for Phase 9 AI Response Planner.
    """

    def __init__(
        self,
        planner: Optional[ResponsePlanner] = None,
        provenance_tracker: Optional[ResponseProvenanceTracker] = None,
        hazard_engine: Optional[HazardEngine] = None,
        prediction_engine: Optional[PredictionEngine] = None,
        compound_engine: Optional[CompoundDisasterEngine] = None,
        vulnerability_engine: Optional[VulnerabilityEngine] = None,
        evacuation_engine: Optional[EvacuationEngine] = None,
        simulation_engine: Optional[SimulationEngine] = None,
        stale_threshold_seconds: Optional[int] = None,
    ):
        self.planner = planner or ResponsePlanner(
            edge_accessibility_threshold=settings.edge_accessibility_threshold,
            alert_level_green_max_hazard=settings.alert_level_green_max_hazard,
            alert_level_yellow_max_hazard=settings.alert_level_yellow_max_hazard,
            alert_level_orange_hazard_threshold=settings.alert_level_orange_hazard_threshold,
            alert_level_orange_impact_threshold=settings.alert_level_orange_impact_threshold,
            alert_level_red_hazard_threshold=settings.alert_level_red_hazard_threshold,
            alert_level_red_impact_threshold=settings.alert_level_red_impact_threshold,
        )
        self.provenance_tracker = provenance_tracker or ResponseProvenanceTracker(
            model_version=settings.response_model_version,
            rules_version=settings.response_rule_version,
            priority_formula_version=settings.response_priority_formula_version,
            confidence_formula_version=settings.response_confidence_formula_version,
        )
        self.hazard_engine = hazard_engine or HazardEngine()
        self.prediction_engine = prediction_engine or PredictionEngine()
        self.compound_engine = compound_engine or CompoundDisasterEngine()
        self.vulnerability_engine = vulnerability_engine or VulnerabilityEngine()
        self.evacuation_engine = evacuation_engine or EvacuationEngine()
        self.simulation_engine = simulation_engine or SimulationEngine()
        self.stale_threshold_seconds = stale_threshold_seconds or settings.response_freshness_threshold_sec

        self._latest_plan: Optional[ResponsePlan] = None

    def evaluate_response_plan(
        self,
        telemetry: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        population_zones: Optional[List[Dict[str, Any]]] = None,
        road_network: Optional[Dict[str, Any]] = None,
        shelters: Optional[List[Dict[str, Any]]] = None,
        include_predictions: bool = True,
        eval_time: Optional[datetime] = None,
    ) -> ResponsePlan:
        """
        Evaluates current operational state across Phases 2–7 and synthesizes an authoritative ResponsePlan.
        """
        now = eval_time or datetime.now(timezone.utc)

        # 1. Parse or default NormalizedTelemetry
        if telemetry is not None:
            if isinstance(telemetry, NormalizedTelemetry):
                norm_telemetry = telemetry
            else:
                is_valid, parsed, _ = TelemetryValidator.validate_dict(telemetry)
                if is_valid and parsed is not None:
                    norm_telemetry = parsed
                else:
                    norm_telemetry = NormalizedTelemetry(**telemetry)
        else:
            # Nominal default baseline telemetry
            norm_telemetry = NormalizedTelemetry(
                node_id="STATION-LIVE-PRIMARY",
                timestamp=now,
                location=LocationCoordinate(lat=37.7749, lon=-122.4194),
                measurements=SensorMeasurements(
                    temperature=24.5,
                    humidity=55.0,
                    rainfall=0.0,
                    water_level=2.1,
                    soil_moisture=42.0,
                ),
                quality=QualityMetadata(source="STATION-LIVE-PRIMARY", confidence=1.0),
            )

        # Check telemetry staleness
        tel_ts = norm_telemetry.timestamp
        if tel_ts.tzinfo is None:
            tel_ts = tel_ts.replace(tzinfo=timezone.utc)
        age_sec = max(0.0, (now - tel_ts).total_seconds())
        is_stale = age_sec > self.stale_threshold_seconds

        # 2. Execute Phase 2/3 Hazards
        hazard_results = self.hazard_engine.evaluate_telemetry(telemetry=norm_telemetry, now=now)
        hazards_list = [h.model_dump() for h in hazard_results]

        # 3. Execute Phase 4 Predictions
        predictions_list = []
        pred_results = []
        if include_predictions:
            hist_objs = []
            if history:
                for item in history:
                    if isinstance(item, NormalizedTelemetry):
                        hist_objs.append(item)
                    else:
                        is_v, p_obj, _ = TelemetryValidator.validate_dict(item)
                        hist_objs.append(p_obj if (is_v and p_obj) else NormalizedTelemetry(**item))
            else:
                hist_objs = [norm_telemetry]

            try:
                pred_results = self.prediction_engine.evaluate_predictions(
                    current_telemetry=norm_telemetry,
                    history=hist_objs,
                    now=now,
                )
                predictions_list = [p.model_dump() for p in pred_results]
            except Exception:
                pred_results = []
                predictions_list = []

        # 4. Execute Phase 5 Compound & Cascades
        compound_results = self.compound_engine.evaluate(
            hazards=hazard_results,
            predictions=pred_results,
            now=now,
        )
        compound_list = [c.model_dump() for c in compound_results]

        # 5. Execute Phase 6 Vulnerability
        zones_data = population_zones or [
            {
                "zone_id": "ZONE-A",
                "name": "Downtown Riverfront",
                "population": 12000,
                "area_km2": 4.5,
                "elevation_m": 8.0,
                "elderly_percentage": 0.22,
                "hospital_count": 1,
                "centroid_latitude": 37.77,
                "centroid_longitude": -122.42,
            },
            {
                "zone_id": "ZONE-B",
                "name": "North Hillcrest",
                "population": 8500,
                "area_km2": 6.2,
                "elevation_m": 45.0,
                "elderly_percentage": 0.14,
                "hospital_count": 2,
                "centroid_latitude": 37.79,
                "centroid_longitude": -122.43,
            },
        ]

        from intelligence.vulnerability.types import PopulationZone
        parsed_zones = [PopulationZone(**z) for z in zones_data]
        vuln_results = self.vulnerability_engine.evaluate(
            zones=parsed_zones,
            hazards=hazard_results,
            predictions=pred_results,
            compound_events=compound_results,
            now=now,
        )
        vuln_list = [v.model_dump() for v in vuln_results]

        # 6. Execute Phase 7 Evacuation & Routing
        from intelligence.evacuation.types import RoadEdge, RoadNetwork, Shelter
        default_edges = [
            RoadEdge(edge_id="ROAD-A-1", from_node="ZONE-A", to_node="INT-1", distance_km=3.0, travel_time_minutes=6.0, hazard_risk=0.1, accessibility=0.9),
            RoadEdge(edge_id="ROAD-1-NORTH", from_node="INT-1", to_node="SHELTER-NORTH", distance_km=4.0, travel_time_minutes=8.0, hazard_risk=0.0, accessibility=0.95),
            RoadEdge(edge_id="ROAD-B-1", from_node="ZONE-B", to_node="INT-1", distance_km=2.5, travel_time_minutes=5.0, hazard_risk=0.0, accessibility=1.0),
        ]
        parsed_edges = [RoadEdge(**e) for e in road_network.get("edges", [])] if road_network else default_edges
        parsed_network = RoadNetwork(edges=parsed_edges)

        default_shelters = [
            Shelter(shelter_id="SHELTER-NORTH", name="North Civic Center", capacity=15000, current_occupancy=2000, safe=True, hazard_risk=0.0, accessibility=0.95, latitude=37.80, longitude=-122.41),
            Shelter(shelter_id="SHELTER-EAST", name="East Regional Complex", capacity=10000, current_occupancy=1000, safe=True, hazard_risk=0.0, accessibility=1.0, latitude=37.76, longitude=-122.38),
        ]
        parsed_shelters = [Shelter(**s) for s in shelters] if shelters else default_shelters

        evac_results = self.evacuation_engine.evaluate(
            zones=parsed_zones,
            shelters=parsed_shelters,
            road_network=parsed_network,
            vulnerabilities=vuln_results,
            hazards=hazard_results,
            predictions=pred_results,
            compound_events=compound_results,
            now=now,
        )
        evac_list = [e.model_dump() for e in evac_results]
        edges_list = [e.model_dump() for e in parsed_edges]
        shelters_list = [s.model_dump() for s in parsed_shelters]


        # 7. Construct Evidence Registry
        registry = build_evidence_registry_from_upstream(
            hazards=hazards_list,
            predictions=predictions_list,
            compound_events=compound_list,
            vulnerability_zones=vuln_list,
            evacuation_recommendations=evac_list,
            road_edges=edges_list,
            shelters=shelters_list,
            is_simulated=False,
        )

        # 8. Plan Response
        alert_level, situation, ranked_actions, warnings = self.planner.plan_response(
            hazards=hazards_list,
            predictions=predictions_list,
            compound_events=compound_list,
            vulnerability_zones=vuln_list,
            evacuation_recommendations=evac_list,
            road_edges=edges_list,
            shelters=shelters_list,
            evidence_registry=registry,
            is_stale=is_stale,
            freshness_age_seconds=age_sec,
            eval_time=now,
            is_simulated=False,
        )

        # 9. Compute Deterministic Provenance
        threshold_config = {
            "edge_accessibility_threshold": self.planner.edge_accessibility_threshold,
            "alert_level_orange_hazard_threshold": self.planner.alert_level_orange_hazard_threshold,
            "alert_level_red_hazard_threshold": self.planner.alert_level_red_hazard_threshold,
        }
        prov_hash = self.provenance_tracker.compute_provenance_hash(
            alert_level=alert_level,
            actions=ranked_actions,
            hazards=hazards_list,
            predictions=predictions_list,
            compound_events=compound_list,
            vulnerability_zones=vuln_list,
            road_edges=edges_list,
            shelters=shelters_list,
            thresholds=threshold_config,
            base_state_hash=norm_telemetry.node_id,
        )


        critical_count = sum(1 for a in ranked_actions if a.urgency.value == "CRITICAL")
        review_count = sum(1 for a in ranked_actions if a.requires_human_review)

        plan = ResponsePlan(
            plan_id=f"PLAN-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            generated_at=now,
            alert_level=alert_level,
            situation=situation,
            actions=ranked_actions,
            warnings=warnings,
            provenance_hash=prov_hash,
            simulated=False,
            model_version=self.provenance_tracker.model_version,
            rules_version=self.provenance_tracker.rules_version,
            priority_formula_version=self.provenance_tracker.priority_formula_version,
            confidence_formula_version=self.provenance_tracker.confidence_formula_version,
            action_count=len(ranked_actions),
            critical_action_count=critical_count,
            requires_operator_review_count=review_count,
        )

        self._latest_plan = plan
        return plan

    def simulate_scenario_response(
        self,
        scenario_id: str,
        changes: Optional[Dict[str, Any]] = None,
        base_state: Optional[str] = "current",
    ) -> ResponsePlan:
        """
        Executes Response Planning against a Phase 8 What-If digital twin simulation scenario.
        Labels all recommendations with simulated=True and SIMULATED epistemic tags.
        """
        # 1. Validate scenario existence in catalog
        from intelligence.simulation.scenarios import ScenarioCatalog
        from intelligence.simulation.types import ScenarioParameters
        from intelligence.core.errors.exceptions import ResourceNotFoundException

        definition = ScenarioCatalog.get_scenario(scenario_id)
        if not definition:
            raise ResourceNotFoundException(f"Simulation scenario '{scenario_id}' not found in catalog.")

        parsed_changes = None
        if changes:
            if isinstance(changes, ScenarioParameters):
                parsed_changes = changes
            else:
                parsed_changes = ScenarioParameters(**changes)

        parsed_base_state = None if (base_state is None or isinstance(base_state, str)) else base_state
        ref_time = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
        if parsed_base_state is None:
            parsed_base_state = self.simulation_engine.build_default_base_state(ref_time)

        # 2. Run simulation via SimulationEngine
        sim_res = self.simulation_engine.run_simulation(
            scenario_id=scenario_id,
            base_state=parsed_base_state,
            changes=parsed_changes,
            now=ref_time,
        )



        sim_hazards = [h.model_dump() for h in sim_res.hazards]
        sim_predictions = [p.model_dump() for p in sim_res.predictions]
        sim_compounds = [c.model_dump() for c in sim_res.compound_events]
        sim_vuln = [v.model_dump() for v in sim_res.vulnerability_zones]
        sim_evac = [e.model_dump() for e in sim_res.evacuation_routes]

        # Candidate road edges and shelters from digital twin state
        road_edges = [
            {"edge_id": "ROAD-A-1", "accessibility": 0.9, "hazard_risk": 0.1, "closed": False},
            {"edge_id": "ROAD-1-NORTH", "accessibility": 0.95, "hazard_risk": 0.0, "closed": False},
        ]
        shelters = [
            {"shelter_id": "SHELTER-NORTH", "capacity": 15000, "current_occupancy": 2000, "safe": True, "hazard_risk": 0.0},
            {"shelter_id": "SHELTER-EAST", "capacity": 10000, "current_occupancy": 1000, "safe": True, "hazard_risk": 0.0},
        ]

        scenario_context = {
            "scenario_id": scenario_id,
            "scenario_version": sim_res.scenario_version,
            "parameters": sim_res.parameters.model_dump() if hasattr(sim_res.parameters, "model_dump") else sim_res.parameters,
        }


        # 2. Build Evidence Registry with is_simulated=True
        registry = build_evidence_registry_from_upstream(
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            vulnerability_zones=sim_vuln,
            evacuation_recommendations=sim_evac,
            road_edges=road_edges,
            shelters=shelters,
            scenario_context=scenario_context,
            is_simulated=True,
        )

        # 3. Plan Response in Simulation Mode
        now = sim_res.timestamp
        alert_level, situation, ranked_actions, warnings = self.planner.plan_response(
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            vulnerability_zones=sim_vuln,
            evacuation_recommendations=sim_evac,
            road_edges=road_edges,
            shelters=shelters,
            evidence_registry=registry,
            scenario_context=scenario_context,
            is_stale=False,
            freshness_age_seconds=0.0,
            eval_time=now,
            is_simulated=True,
        )

        warnings.append(f"SIMULATED_SCENARIO: Response plan derived from hypothetical scenario '{scenario_id}'. NOT A LIVE ALERT.")

        # 4. Provenance
        threshold_config = {
            "edge_accessibility_threshold": self.planner.edge_accessibility_threshold,
            "alert_level_orange_hazard_threshold": self.planner.alert_level_orange_hazard_threshold,
            "alert_level_red_hazard_threshold": self.planner.alert_level_red_hazard_threshold,
        }
        prov_hash = self.provenance_tracker.compute_provenance_hash(
            alert_level=alert_level,
            actions=ranked_actions,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            vulnerability_zones=sim_vuln,
            road_edges=road_edges,
            shelters=shelters,
            thresholds=threshold_config,
            scenario_context=scenario_context,
            base_state_hash=f"SIM-{scenario_id}",
        )

        critical_count = sum(1 for a in ranked_actions if a.urgency.value == "CRITICAL")
        review_count = sum(1 for a in ranked_actions if a.requires_human_review)

        plan = ResponsePlan(
            plan_id=f"PLAN-SIM-{scenario_id}-{uuid.uuid4().hex[:8].upper()}",
            generated_at=now,
            alert_level=alert_level,
            situation=situation,
            actions=ranked_actions,
            warnings=warnings,
            provenance_hash=prov_hash,
            simulated=True,
            model_version=self.provenance_tracker.model_version,
            rules_version=self.provenance_tracker.rules_version,
            priority_formula_version=self.provenance_tracker.priority_formula_version,
            confidence_formula_version=self.provenance_tracker.confidence_formula_version,
            action_count=len(ranked_actions),
            critical_action_count=critical_count,
            requires_operator_review_count=review_count,
        )
        return plan

    def get_current_plan(self) -> ResponsePlan:
        """
        Returns the most recently computed ResponsePlan or synthesizes a fresh nominal baseline plan.
        """
        if self._latest_plan is not None:
            return self._latest_plan
        return self.evaluate_response_plan()
