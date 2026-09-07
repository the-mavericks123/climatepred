"""
Cryptographic SHA-256 provenance tracking for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Guarantees strict auditability, deterministic canonicalization, and tamper-detection across all material
inputs: demographic demand, Phase 5 human vulnerability, Phase 2 hazard evidence, Phase 3 prediction evidence,
Phase 4 cascading events, road network edge states, routing configurations, candidate shelters, and route results.
"""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional


class EvacuationProvenanceTracker:
    """
    Computes deterministic SHA-256 cryptographic digests tracing all material decision inputs
    and routing recommendations for evacuation directives.

    Collection Ordering Guarantees:
    - Order-Sensitive Collections (Order is semantically meaningful, never sorted):
        * route_nodes: Sequential path progression [origin, intermediate..., destination]
        * route_edges: Sequential traversal of road edge IDs
        * causal_chain: Temporal/causal progression of cascading hazard states
    - Order-Insensitive Collections (Sorted canonically by stable identifiers):
        * avoid_edges: Sorted lexicographically by edge ID
        * candidate_shelters: Sorted lexicographically by shelter_id
        * candidate_edges: Sorted lexicographically by edge_id
        * hazards: Sorted lexicographically by hazard_id
        * predictions: Sorted lexicographically by prediction_id
        * compound_events: Sorted lexicographically by event_id
        * evidence_ids: Sorted lexicographically by evidence ID
        * contributing_hazards: Sorted lexicographically
    """

    CONFIDENCE_FORMULA_VERSION = "conf-v1"
    ROUTING_ALGORITHM = "dijkstra-hazard-v1"
    COST_FORMULA_VERSION = "cost-v1"
    HAZARD_MULTIPLIER_VERSION = "hazard-mult-v1"
    ACCESSIBILITY_MULTIPLIER_VERSION = "access-mult-v1"
    ROUTE_SAFETY_FORMULA_VERSION = "safety-v1"

    @classmethod
    def build_canonical_payload(
        cls,
        # 1. Zone & Population
        zone_id: str,
        total_population: int,
        population_exposed: int,
        population_to_evacuate: int,
        priority: float,
        # 2. Vulnerability & Human Impact (Phase 5)
        vulnerability: float,
        human_impact: float,
        accessibility_risk: float,
        evidence_ids: Optional[List[str]] = None,
        source_confidence: float = 1.0,
        assessment_confidence: float = 1.0,
        # 3. Hazard Evidence (Phase 2)
        hazards: Optional[List[Dict[str, Any]]] = None,
        # 4. Prediction Evidence (Phase 3)
        predictions: Optional[List[Dict[str, Any]]] = None,
        # 5. Compound Event Evidence (Phase 4)
        compound_events: Optional[List[Dict[str, Any]]] = None,
        # 6. Road Network Inputs
        candidate_edges: Optional[List[Dict[str, Any]]] = None,
        # 7. Routing Configuration
        accessibility_threshold: float = 0.40,
        hazard_threshold: float = 0.95,
        algorithm_version: Optional[str] = None,
        cost_formula_version: Optional[str] = None,
        # 8. Shelter Inputs
        candidate_shelters: Optional[List[Dict[str, Any]]] = None,
        # 9. Final Route Result
        selected_shelter_id: Optional[str] = None,
        route_nodes: Optional[List[str]] = None,
        route_edges: Optional[List[str]] = None,
        distance_km: float = 0.0,
        travel_time_minutes: float = 0.0,
        hazard_exposure: float = 0.0,
        route_accessibility: float = 1.0,
        route_safety_score: float = 1.0,
        avoid_edges: Optional[List[str]] = None,
        assigned_population: int = 0,
        status: str = "RECOMMENDED",
        reason: str = "",
        no_route_reason: Optional[str] = None,
        # 10. Confidence
        final_confidence: float = 1.0,
        confidence_formula_version: Optional[str] = None,
        horizon_discount: float = 0.0,
        synthetic_data_discount: float = 0.0,
        cascade_penalty: float = 0.0,
        simulated: bool = True,
        forecast_horizon_minutes: int = 0,
    ) -> Dict[str, Any]:
        """
        Assembles all material evacuation decision inputs into a strict, canonical dictionary.
        """
        exposure_ratio = round(population_exposed / total_population, 4) if total_population > 0 else 0.0

        # Canonicalize hazards (order-insensitive: sorted by hazard_id)
        canon_hazards = []
        if hazards:
            for h in sorted(hazards, key=lambda x: str(x.get("hazard_id", ""))):
                ts = h.get("timestamp")
                ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")
                canon_hazards.append({
                    "confidence": round(float(h.get("confidence", 0.0)), 4),
                    "forecast_horizon_minutes": int(h.get("forecast_horizon_minutes", 0)),
                    "hazard_id": str(h.get("hazard_id", "")),
                    "hazard_type": str(h.get("hazard", h.get("hazard_type", ""))),
                    "model_version": str(h.get("model_version", "v1")),
                    "severity": round(float(h.get("severity", 0.0)), 4),
                    "simulated": bool(h.get("simulated", False)),
                    "timestamp": ts_str,
                })

        # Canonicalize predictions (order-insensitive: sorted by prediction_id)
        canon_predictions = []
        if predictions:
            for p in sorted(predictions, key=lambda x: str(x.get("prediction_id", ""))):
                canon_predictions.append({
                    "confidence": round(float(p.get("confidence", 0.0)), 4),
                    "forecast_horizon_minutes": int(p.get("forecast_horizon_minutes", 0)),
                    "forecast_time": str(p.get("forecast_time", p.get("target_time", ""))),
                    "hazard": str(p.get("hazard", "")),
                    "model_version": str(p.get("model_version", "v1")),
                    "prediction_id": str(p.get("prediction_id", "")),
                    "prediction_time": str(p.get("prediction_time", p.get("timestamp", ""))),
                    "severity": round(float(p.get("severity", 0.0)), 4),
                    "simulated": bool(p.get("simulated", False)),
                })

        # Canonicalize compound events (order-insensitive events, but causal_chain is ORDER-SENSITIVE)
        canon_compounds = []
        if compound_events:
            for ce in sorted(compound_events, key=lambda x: str(x.get("event_id", ""))):
                # causal_chain preserves exact sequential causal order!
                chain = list(ce.get("chain", ce.get("causal_chain", [])))
                # contributing hazards order-insensitive
                contrib = sorted(list(ce.get("contributing_hazards", [])))
                canon_compounds.append({
                    "causal_chain": chain,
                    "confidence": round(float(ce.get("confidence", 0.0)), 4),
                    "contributing_hazards": contrib,
                    "event_id": str(ce.get("event_id", "")),
                    "rule_version": str(ce.get("rule_version", "v1")),
                    "severity": round(float(ce.get("severity", 0.0)), 4),
                    "simulated": bool(ce.get("simulated", False)),
                })

        # Canonicalize candidate road edges (order-insensitive: sorted by edge_id)
        canon_edges = []
        if candidate_edges:
            for e in sorted(candidate_edges, key=lambda x: str(x.get("edge_id", ""))):
                inf_risk = e.get("inferred_failure_risk")
                canon_edges.append({
                    "accessibility": round(float(e.get("accessibility", 1.0)), 4),
                    "closed": bool(e.get("closed", False)),
                    "distance_km": round(float(e.get("distance_km", 0.0)), 2),
                    "edge_id": str(e.get("edge_id", "")),
                    "from_node": str(e.get("from_node", "")),
                    "hazard_risk": round(float(e.get("hazard_risk", 0.0)), 4),
                    "inferred_failure_risk": round(float(inf_risk), 4) if inf_risk is not None else None,
                    "to_node": str(e.get("to_node", "")),
                    "travel_time_minutes": round(float(e.get("travel_time_minutes", 0.0)), 1),
                })

        # Canonicalize candidate shelters (order-insensitive: sorted by shelter_id)
        canon_shelters = []
        if candidate_shelters:
            for s in sorted(candidate_shelters, key=lambda x: str(x.get("shelter_id", ""))):
                cap = int(s.get("capacity", 0))
                occ = int(s.get("current_occupancy", 0))
                avail = int(s.get("available_capacity", max(0, cap - occ)))
                canon_shelters.append({
                    "accessibility": round(float(s.get("accessibility", 1.0)), 4),
                    "available_capacity": avail,
                    "capacity": cap,
                    "current_occupancy": occ,
                    "hazard_risk": round(float(s.get("hazard_risk", 0.0)), 4),
                    "latitude": round(float(s.get("latitude", 0.0)), 4),
                    "longitude": round(float(s.get("longitude", 0.0)), 4),
                    "safe": bool(s.get("safe", True)),
                    "shelter_id": str(s.get("shelter_id", "")),
                    "simulated": bool(s.get("simulated", False)),
                })

        # Assemble full canonical payload
        payload = {
            "confidence_evaluation": {
                "cascade_penalty": round(float(cascade_penalty), 4),
                "confidence": round(float(final_confidence), 4),
                "confidence_formula_version": str(confidence_formula_version or cls.CONFIDENCE_FORMULA_VERSION),
                "horizon_discount": round(float(horizon_discount), 4),
                "synthetic_data_discount": round(float(synthetic_data_discount), 4),
            },
            "evidence": {
                "compound_events": canon_compounds,
                "hazards": canon_hazards,
                "predictions": canon_predictions,
            },
            "network_inputs": {
                "candidate_edges": canon_edges,
            },
            "result": {
                "accessibility": round(float(route_accessibility), 4),
                "assigned_population": int(assigned_population),
                "avoid_edges": sorted(list(set(avoid_edges or []))),  # order-insensitive
                "distance_km": round(float(distance_km), 2),
                "hazard_exposure": round(float(hazard_exposure), 4),
                "no_route_reason": str(no_route_reason) if no_route_reason else "NONE",
                "reason": str(reason),
                "route_edges": list(route_edges or []),  # order-sensitive!
                "route_nodes": list(route_nodes or []),  # order-sensitive!
                "route_safety_score": round(float(route_safety_score), 4),
                "selected_shelter_id": str(selected_shelter_id or "NONE"),
                "status": str(status),
                "travel_time_minutes": round(float(travel_time_minutes), 1),
            },
            "routing_config": {
                "accessibility_multiplier_version": cls.ACCESSIBILITY_MULTIPLIER_VERSION,
                "accessibility_threshold": round(float(accessibility_threshold), 4),
                "algorithm": cls.ROUTING_ALGORITHM,
                "algorithm_version": str(algorithm_version or cls.ROUTING_ALGORITHM),
                "cost_formula_version": str(cost_formula_version or cls.COST_FORMULA_VERSION),
                "hazard_multiplier_version": cls.HAZARD_MULTIPLIER_VERSION,
                "hazard_threshold": round(float(hazard_threshold), 4),
                "route_safety_formula_version": cls.ROUTE_SAFETY_FORMULA_VERSION,
            },
            "shelters": canon_shelters,
            "vulnerability_assessment": {
                "accessibility_risk": round(float(accessibility_risk), 4),
                "confidence": round(float(assessment_confidence), 4),
                "evidence_ids": sorted(list(set(evidence_ids or []))),  # order-insensitive
                "human_impact": round(float(human_impact), 4),
                "source_confidence": round(float(source_confidence), 4),
                "vulnerability": round(float(vulnerability), 4),
            },
            "zone": {
                "exposure_ratio": exposure_ratio,
                "forecast_horizon_minutes": int(forecast_horizon_minutes),
                "population_exposed": int(population_exposed),
                "population_to_evacuate": int(population_to_evacuate),
                "priority": round(float(priority), 4),
                "simulated": bool(simulated),
                "total_population": int(total_population),
                "zone_id": str(zone_id),
            },
        }

        return payload

    @classmethod
    def compute_provenance_hash(
        cls,
        zone_id: Optional[str] = None,
        population_to_evacuate: Optional[int] = None,
        priority: Optional[float] = None,
        status: Optional[str] = None,
        shelter_id: Optional[str] = None,
        route_nodes: Optional[List[str]] = None,
        avoid_edges: Optional[List[str]] = None,
        algorithm_version: Optional[str] = None,
        cost_formula_version: Optional[str] = None,
        forecast_horizon_minutes: int = 0,
        simulated: bool = True,
        *,
        canonical_payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Computes canonical SHA-256 digest across all material evacuation directive factors.
        """
        if canonical_payload is not None:
            serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        # Construct canonical payload using provided arguments
        canonical_payload = cls.build_canonical_payload(
                zone_id=zone_id or "ZONE-DEFAULT",
                total_population=int(kwargs.get("total_population", kwargs.get("population_total", (population_to_evacuate or 0) * 2 or 1000))),
                population_exposed=int(kwargs.get("population_exposed", population_to_evacuate or 0)),
                population_to_evacuate=int(population_to_evacuate or 0),
                priority=float(priority or 0.0),
                vulnerability=float(kwargs.get("vulnerability", 0.50)),
                human_impact=float(kwargs.get("human_impact", 0.50)),
                accessibility_risk=float(kwargs.get("accessibility_risk", 0.20)),
                evidence_ids=kwargs.get("evidence_ids", []),
                source_confidence=float(kwargs.get("source_confidence", 1.0)),
                assessment_confidence=float(kwargs.get("assessment_confidence", kwargs.get("confidence", 1.0))),
                hazards=kwargs.get("hazards", []),
                predictions=kwargs.get("predictions", []),
                compound_events=kwargs.get("compound_events", []),
                candidate_edges=kwargs.get("candidate_edges", kwargs.get("road_edges", [])),
                accessibility_threshold=float(kwargs.get("accessibility_threshold", 0.40)),
                hazard_threshold=float(kwargs.get("hazard_threshold", 0.95)),
                algorithm_version=algorithm_version or cls.ROUTING_ALGORITHM,
                cost_formula_version=cost_formula_version or cls.COST_FORMULA_VERSION,
                candidate_shelters=kwargs.get("candidate_shelters", kwargs.get("shelters", [])),
                selected_shelter_id=shelter_id,
                route_nodes=route_nodes or [],
                route_edges=kwargs.get("route_edges", []),
                distance_km=float(kwargs.get("distance_km", 0.0)),
                travel_time_minutes=float(kwargs.get("travel_time_minutes", 0.0)),
                hazard_exposure=float(kwargs.get("hazard_exposure", 0.0)),
                route_accessibility=float(kwargs.get("route_accessibility", kwargs.get("accessibility", 1.0))),
                route_safety_score=float(kwargs.get("route_safety_score", kwargs.get("safety_score", 1.0))),
                avoid_edges=avoid_edges or [],
                assigned_population=int(kwargs.get("assigned_population", population_to_evacuate or 0)),
                status=status or "RECOMMENDED",
                reason=str(kwargs.get("reason", "")),
                no_route_reason=kwargs.get("no_route_reason"),
                final_confidence=float(kwargs.get("confidence", 1.0)),
                confidence_formula_version=kwargs.get("confidence_formula_version", cls.CONFIDENCE_FORMULA_VERSION),
                horizon_discount=float(kwargs.get("horizon_discount", 0.0)),
                synthetic_data_discount=float(kwargs.get("synthetic_data_discount", 0.0)),
                cascade_penalty=float(kwargs.get("cascade_penalty", 0.0)),
                simulated=simulated,
                forecast_horizon_minutes=forecast_horizon_minutes,
            )

        serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
