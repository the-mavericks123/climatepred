"""
Main orchestration engine for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Integrates Phase 2-5 intelligence, road network graph analysis, shelter capacity allocation,
and deterministic Dijkstra hazard-aware routing into explainable evacuation directives.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from intelligence.app.config import settings
from intelligence.compound.types import CompoundEvent, StateEvidenceType
from intelligence.evacuation.confidence import EvacuationConfidenceCalculator
from intelligence.evacuation.demand import EvacuationDemandCalculator
from intelligence.evacuation.network import RoadNetworkGraph
from intelligence.evacuation.provenance import EvacuationProvenanceTracker
from intelligence.evacuation.routing import HazardAwareRouter
from intelligence.evacuation.shelters import ShelterManager
from intelligence.evacuation.types import (
    DestinationAssignment,
    EvacuationDemand,
    EvacuationRecommendation,
    EvacuationRoute,
    EvacuationStatus,
    NoRouteReason,
    RoadNetwork,
    Shelter,
)
from intelligence.hazards.types import HazardResult
from intelligence.prediction.types import PredictionResult
from intelligence.vulnerability.engine import VulnerabilityEngine
from intelligence.vulnerability.types import PopulationZone, VulnerabilityZoneAssessment


class EvacuationEngine:
    """
    Deterministic Evacuation & Adaptive Route Intelligence Engine.
    Coordinates evacuation demand, capacity-constrained refuge matching, and hazard-aware routing.
    """

    def __init__(self, vulnerability_engine: Optional[VulnerabilityEngine] = None):
        self._vuln_engine = vulnerability_engine or VulnerabilityEngine()
        self._latest_recommendations: List[EvacuationRecommendation] = []

    def get_latest_recommendations(self) -> List[EvacuationRecommendation]:
        """Returns cached directives from the most recent evaluation session."""
        return list(self._latest_recommendations)

    def evaluate(
        self,
        zones: List[PopulationZone],
        shelters: List[Shelter],
        road_network: RoadNetwork,
        vulnerabilities: Optional[List[VulnerabilityZoneAssessment]] = None,
        hazards: Optional[List[HazardResult]] = None,
        predictions: Optional[List[PredictionResult]] = None,
        compound_events: Optional[List[CompoundEvent]] = None,
        accessibility_threshold: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> List[EvacuationRecommendation]:
        """
        Executes end-to-end evacuation demand evaluation, shelter assignment, and route calculation.
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        access_thresh = (
            accessibility_threshold
            if accessibility_threshold is not None
            else getattr(settings, "edge_accessibility_threshold", 0.40)
        )
        max_hazard_lim = getattr(settings, "max_route_hazard_limit", 0.95)

        # 1. Build road network graph and apply Phase 4 dynamic disruptions
        graph = RoadNetworkGraph(road_network)
        disrupted_edges = graph.apply_cascade_disruptions(compound_events)
        has_cascade = len(disrupted_edges) > 0

        # 2. Obtain Phase 5 VulnerabilityZoneAssessments if not directly provided
        assessments_by_zone: Dict[str, VulnerabilityZoneAssessment] = {}
        if vulnerabilities:
            for v in vulnerabilities:
                assessments_by_zone[v.zone_id] = v
        else:
            computed_vulns = self._vuln_engine.evaluate(
                zones=zones,
                hazards=hazards,
                predictions=predictions,
                compound_events=compound_events,
                now=eval_time_utc,
            )
            for v in computed_vulns:
                assessments_by_zone[v.zone_id] = v

        # 3. Calculate EvacuationDemand for each zone
        zone_demands: List[Tuple[EvacuationDemand, PopulationZone, VulnerabilityZoneAssessment]] = []
        for zone in zones:
            ass = assessments_by_zone.get(zone.zone_id)
            if not ass:
                continue
            demand = EvacuationDemandCalculator.calculate_demand(ass)
            zone_demands.append((demand, zone, ass))

        # 4. Sort demands deterministically by priority descending, then population exposed, then zone_id
        zone_demands.sort(
            key=lambda x: (
                -x[0].priority,
                -x[0].population_to_evacuate,
                x[1].zone_id,
            )
        )

        # 5. Initialize shelter capacity manager
        shelter_mgr = ShelterManager(shelters)
        recommendations: List[EvacuationRecommendation] = []

        # 6. Evaluate recommendations per zone
        for demand, zone, ass in zone_demands:
            origin_node = zone.zone_id  # Node identifier corresponds to zone_id in standard mapping

            # Check if evacuation is required
            if not demand.evacuation_required:
                rec_id = f"EVAC-{zone.zone_id}-STANDBY"
                canon_payload = EvacuationProvenanceTracker.build_canonical_payload(
                    zone_id=zone.zone_id,
                    total_population=zone.population,
                    population_exposed=demand.population_exposed,
                    population_to_evacuate=0,
                    priority=0.0,
                    vulnerability=ass.vulnerability,
                    human_impact=ass.human_impact,
                    accessibility_risk=ass.accessibility_risk,
                    evidence_ids=ass.evidence_ids,
                    source_confidence=1.0,
                    assessment_confidence=ass.confidence,
                    hazards=[h.model_dump() for h in hazards] if hazards else [],
                    predictions=[p.model_dump() for p in predictions] if predictions else [],
                    compound_events=[ce.model_dump() for ce in compound_events] if compound_events else [],
                    candidate_edges=[e.model_dump() for e in graph.edges],
                    accessibility_threshold=access_thresh,
                    hazard_threshold=max_hazard_lim,
                    algorithm_version=HazardAwareRouter.ALGORITHM_VERSION,
                    cost_formula_version=HazardAwareRouter.COST_FORMULA_VERSION,
                    candidate_shelters=[s.model_dump() for s in shelters],
                    selected_shelter_id=None,
                    route_nodes=[],
                    route_edges=[],
                    distance_km=0.0,
                    travel_time_minutes=0.0,
                    hazard_exposure=0.0,
                    route_accessibility=1.0,
                    route_safety_score=1.0,
                    avoid_edges=[],
                    assigned_population=0,
                    status=EvacuationStatus.RECOMMENDED.value,
                    reason="Zone hazard and human impact are below evacuation thresholds; shelter in place recommended",
                    no_route_reason=None,
                    final_confidence=ass.confidence,
                    confidence_formula_version=EvacuationProvenanceTracker.CONFIDENCE_FORMULA_VERSION,
                    horizon_discount=0.0,
                    synthetic_data_discount=0.10 if zone.simulated else 0.0,
                    cascade_penalty=0.0,
                    simulated=zone.simulated,
                    forecast_horizon_minutes=ass.forecast_horizon_minutes,
                )
                prov_hash = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=canon_payload)
                recommendations.append(
                    EvacuationRecommendation(
                        evacuation_id=rec_id,
                        zone_id=zone.zone_id,
                        timestamp=eval_time_utc,
                        forecast_horizon_minutes=ass.forecast_horizon_minutes,
                        evidence_type=ass.evidence_type,
                        population_exposed=demand.population_exposed,
                        population_to_evacuate=0,
                        priority=0.0,
                        destination=None,
                        route=None,
                        avoid_edges=[],
                        status=EvacuationStatus.RECOMMENDED,
                        reason="Zone hazard and human impact are below evacuation thresholds; shelter in place recommended",
                        no_route_reason=None,
                        confidence=ass.confidence,
                        simulated=zone.simulated,
                        provenance_hash=prov_hash,
                        drivers=demand.drivers,
                    )
                )
                continue

            # Route & Shelter search with configurable accessibility threshold
            best_shelter, best_route, status, no_route_reason, explanation = (
                shelter_mgr.find_best_shelter_and_route(
                    graph=graph,
                    origin_node=origin_node,
                    demand=demand,
                    accessibility_threshold=access_thresh,
                    max_allowed_hazard=max_hazard_lim,
                )
            )

            # Avoid edges
            avoid_edges = HazardAwareRouter.identify_avoid_edges(
                graph=graph,
                chosen_route=best_route,
                hazard_threshold=getattr(settings, "evacuation_hazard_risk_threshold", 0.70),
                accessibility_threshold=access_thresh,
            )

            # Destination allocation if shelter and route are feasible
            destination_assignment: Optional[DestinationAssignment] = None
            if best_shelter is not None and best_route is not None:
                destination_assignment = shelter_mgr.allocate_capacity(
                    shelter=best_shelter,
                    requested_population=demand.population_to_evacuate,
                )

            # Confidence calculation
            confidence = EvacuationConfidenceCalculator.calculate_confidence(
                assessment=ass,
                shelter=best_shelter,
                route=best_route,
                is_predicted=ass.evidence_type == StateEvidenceType.PREDICTED,
                has_cascade_disruption=has_cascade,
            )

            is_sim = bool(
                zone.simulated
                or ass.simulated
                or (best_shelter.simulated if best_shelter else True)
            )

            route_nodes = best_route.nodes if best_route else []
            shelter_id = best_shelter.shelter_id if best_shelter else None

            # Complete Canonical Provenance Hashing
            canon_payload = EvacuationProvenanceTracker.build_canonical_payload(
                zone_id=zone.zone_id,
                total_population=zone.population,
                population_exposed=demand.population_exposed,
                population_to_evacuate=demand.population_to_evacuate,
                priority=demand.priority,
                vulnerability=ass.vulnerability,
                human_impact=ass.human_impact,
                accessibility_risk=ass.accessibility_risk,
                evidence_ids=ass.evidence_ids,
                source_confidence=1.0,
                assessment_confidence=ass.confidence,
                hazards=[h.model_dump() for h in hazards] if hazards else [],
                predictions=[p.model_dump() for p in predictions] if predictions else [],
                compound_events=[ce.model_dump() for ce in compound_events] if compound_events else [],
                candidate_edges=[e.model_dump() for e in graph.edges],
                accessibility_threshold=access_thresh,
                hazard_threshold=max_hazard_lim,
                algorithm_version=HazardAwareRouter.ALGORITHM_VERSION,
                cost_formula_version=HazardAwareRouter.COST_FORMULA_VERSION,
                candidate_shelters=[s.model_dump() for s in shelters],
                selected_shelter_id=shelter_id,
                route_nodes=route_nodes,
                route_edges=best_route.edge_ids if best_route else [],
                distance_km=best_route.distance_km if best_route else 0.0,
                travel_time_minutes=best_route.estimated_travel_minutes if best_route else 0.0,
                hazard_exposure=best_route.hazard_exposure if best_route else 0.0,
                route_accessibility=best_route.accessibility if best_route else 1.0,
                route_safety_score=best_route.safety_score if best_route else 0.0,
                avoid_edges=avoid_edges,
                assigned_population=destination_assignment.assigned_population if destination_assignment else 0,
                status=status.value,
                reason=explanation,
                no_route_reason=no_route_reason.value if no_route_reason else None,
                final_confidence=confidence,
                confidence_formula_version=EvacuationProvenanceTracker.CONFIDENCE_FORMULA_VERSION,
                horizon_discount=0.15 if ass.evidence_type == StateEvidenceType.PREDICTED else 0.0,
                synthetic_data_discount=0.10 if is_sim else 0.0,
                cascade_penalty=0.10 if has_cascade else 0.0,
                simulated=is_sim,
                forecast_horizon_minutes=ass.forecast_horizon_minutes,
            )
            prov_hash = EvacuationProvenanceTracker.compute_provenance_hash(canonical_payload=canon_payload)

            rec_id = f"EVAC-{zone.zone_id}-{prov_hash[:8].upper()}"

            combined_drivers = list(demand.drivers)
            if best_route:
                combined_drivers.append(
                    f"Route: {best_route.distance_km} km ({best_route.estimated_travel_minutes} min), Safety score: {best_route.safety_score:.2f}"
                )
            if avoid_edges:
                combined_drivers.append(f"Avoided severed/hazardous segments: {', '.join(avoid_edges[:4])}")

            recommendations.append(
                EvacuationRecommendation(
                    evacuation_id=rec_id,
                    zone_id=zone.zone_id,
                    timestamp=eval_time_utc,
                    forecast_horizon_minutes=ass.forecast_horizon_minutes,
                    evidence_type=ass.evidence_type,
                    population_exposed=demand.population_exposed,
                    population_to_evacuate=demand.population_to_evacuate,
                    priority=demand.priority,
                    destination=destination_assignment,
                    route=best_route,
                    avoid_edges=avoid_edges,
                    status=status,
                    reason=explanation,
                    no_route_reason=no_route_reason,
                    confidence=confidence,
                    simulated=is_sim,
                    provenance_hash=prov_hash,
                    algorithm_version=HazardAwareRouter.ALGORITHM_VERSION,
                    cost_formula_version=HazardAwareRouter.COST_FORMULA_VERSION,
                    drivers=combined_drivers,
                )
            )

        # Sort recommendations deterministically by priority descending, then zone_id
        recommendations.sort(key=lambda r: (-r.priority, r.zone_id))
        self._latest_recommendations = recommendations
        return recommendations
