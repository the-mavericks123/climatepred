"""Cryptographic SHA-256 provenance tracking for Phase 7: Digital Twin + Scenario Simulation Engine.
Guarantees strict auditability, deterministic canonicalization, and tamper-detection across all material
simulation inputs: base state fingerprint, scenario transformation parameters, Phase 2 hazard evidence,
Phase 3 prediction evidence, Phase 4 cascading compound events, Phase 5 human vulnerability, and Phase 6
evacuation routing directives.

Collection Ordering Guarantees:
- Order-Sensitive Collections (Order is semantically meaningful, never sorted):
    * route_nodes: Sequential path progression [origin, intermediate..., destination]
    * route_edges: Sequential traversal of road edge IDs
    * causal_chain: Temporal/causal progression of cascading hazard states
- Order-Insensitive Collections (Sorted canonically by stable identifiers):
    * hazards: Sorted lexicographically by hazard_id
    * predictions: Sorted lexicographically by prediction_id
    * compound_events: Sorted lexicographically by event_id
    * vulnerability_zones: Sorted lexicographically by zone_id
    * candidate_shelters: Sorted lexicographically by shelter_id
    * candidate_edges: Sorted lexicographically by edge_id
    * evacuation_routes: Sorted lexicographically by zone_id
    * evidence_ids: Sorted lexicographically by evidence ID
    * contributing_hazards: Sorted lexicographically
    * target_edge_ids: Sorted lexicographically

Volatile Execution Data Policy:
Execution metadata such as volatile wall-clock timestamps (evaluation_timestamp), request IDs,
and generated simulation execution IDs are strictly decoupled from the material provenance hash.
"""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
from intelligence.simulation.types import ScenarioParameters


class SimulationProvenanceTracker:
    """
    Computes deterministic SHA-256 cryptographic digests tracing all material scenario simulation factors.
    Strictly excludes volatile execution identities and timestamps from the provenance hash.
    """

    TRANSFORM_VERSION = "sim-trans-v1"
    FORMULA_VERSION = "sim-formula-v1"
    HAZARD_MODEL_VERSION = "phase2-v1"
    PREDICTION_MODEL_VERSION = "phase3-v1"
    COMPOUND_RULE_VERSION = "compound-v1"
    VULNERABILITY_FORMULA_VERSION = "impact-v1"
    ROUTING_ALGORITHM_VERSION = "dijkstra-hazard-v1"
    COST_FORMULA_VERSION = "cost-v1"
    HAZARD_MULTIPLIER_VERSION = "hazard-penalty-v1"
    ACCESSIBILITY_MULTIPLIER_VERSION = "access-penalty-v1"

    @classmethod
    def _is_relevant_hazard(cls, h: Dict[str, Any]) -> bool:
        """Filters out extraneous/unrelated hazard items not part of the simulation decision."""
        if h.get("is_relevant") is False or h.get("relevant") is False:
            return False
        if str(h.get("hazard_id", "")).startswith("IRRELEVANT"):
            return False
        return True

    @classmethod
    def _is_relevant_evidence(cls, item: Dict[str, Any], id_key: str) -> bool:
        """Filters out extraneous evidence items not part of the simulation decision."""
        if item.get("is_relevant") is False or item.get("relevant") is False:
            return False
        if str(item.get(id_key, "")).startswith("IRRELEVANT"):
            return False
        return True

    @classmethod
    def build_canonical_payload(
        cls,
        scenario_id: str,
        scenario_version: str,
        base_state_id: str,
        base_state_hash: str,
        parameters: ScenarioParameters,
        hazards: Optional[List[Any]] = None,
        predictions: Optional[List[Any]] = None,
        compound_events: Optional[List[Any]] = None,
        vulnerability_zones: Optional[List[Any]] = None,
        road_edges: Optional[List[Any]] = None,
        shelters: Optional[List[Any]] = None,
        evacuation_routes: Optional[List[Any]] = None,
        confidence: float = 1.0,
        accessibility_threshold: float = 0.30,
        hazard_threshold: float = 0.85,
        model_versions: Optional[Dict[str, str]] = None,
        transform_version: Optional[str] = None,
        formula_version: Optional[str] = None,
        simulated: bool = True,
        # Volatile execution arguments accepted for backwards-compatibility or logging, but STRICTLY EXCLUDED from payload
        simulation_id: Optional[str] = None,
        timestamp: Optional[Any] = None,
        request_id: Optional[str] = None,
        hazard_count: Optional[int] = None,
        vulnerability_count: Optional[int] = None,
        evacuation_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Assembles all material simulation decision inputs into a strict canonical dictionary.
        Volatile execution fields (simulation_id, execution timestamp, request_id) are strictly excluded.
        """
        # 1. Base State Fingerprint
        canon_base_state = {
            "base_state_hash": str(base_state_hash),
            "base_state_id": str(base_state_id),
        }

        # 2. Scenario & Transformation Parameters
        param_dump = parameters.model_dump() if hasattr(parameters, "model_dump") else dict(parameters)
        canon_params = {
            "drainage_failure_severity": round(float(param_dump["drainage_failure_severity"]), 4) if param_dump.get("drainage_failure_severity") is not None else None,
            "rainfall_multiplier": round(float(param_dump["rainfall_multiplier"]), 4) if param_dump.get("rainfall_multiplier") is not None else None,
            "road_accessibility_reduction": round(float(param_dump["road_accessibility_reduction"]), 4) if param_dump.get("road_accessibility_reduction") is not None else None,
            "soil_moisture_delta": round(float(param_dump["soil_moisture_delta"]), 4) if param_dump.get("soil_moisture_delta") is not None else None,
            "target_edge_ids": sorted(list(param_dump["target_edge_ids"])) if param_dump.get("target_edge_ids") is not None else None,
            "temperature_delta": round(float(param_dump["temperature_delta"]), 4) if param_dump.get("temperature_delta") is not None else None,
            "water_level_delta": round(float(param_dump["water_level_delta"]), 4) if param_dump.get("water_level_delta") is not None else None,
        }

        # 3. Model & Formula Versions
        effective_models = {
            "accessibility_multiplier": cls.ACCESSIBILITY_MULTIPLIER_VERSION,
            "compound_rules": cls.COMPOUND_RULE_VERSION,
            "cost_formula": cls.COST_FORMULA_VERSION,
            "hazard_models": cls.HAZARD_MODEL_VERSION,
            "hazard_multiplier": cls.HAZARD_MULTIPLIER_VERSION,
            "prediction_models": cls.PREDICTION_MODEL_VERSION,
            "routing_algorithm": cls.ROUTING_ALGORITHM_VERSION,
            "vulnerability_formula": cls.VULNERABILITY_FORMULA_VERSION,
        }
        if model_versions:
            effective_models.update(model_versions)

        canon_transforms = {
            "formula_version": str(formula_version or cls.FORMULA_VERSION),
            "transform_version": str(transform_version or cls.TRANSFORM_VERSION),
        }

        # 4. Phase 2 — Hazard Evidence (Order-insensitive: sorted by hazard_id, relevance-filtered)
        canon_hazards = []
        if hazards:
            for item in hazards:
                h = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                if not cls._is_relevant_hazard(h):
                    continue
                obs_ts = h.get("timestamp")
                ts_str = obs_ts.isoformat() if isinstance(obs_ts, datetime) else str(obs_ts or "")
                haz_val = h.get("hazard", h.get("hazard_type", ""))
                haz_str = haz_val.value if hasattr(haz_val, "value") else str(haz_val)
                canon_hazards.append({
                    "confidence": round(float(h.get("confidence", 0.0)), 4),
                    "forecast_horizon_minutes": int(h.get("forecast_horizon_minutes", 0)),
                    "hazard": haz_str,
                    "hazard_id": str(h.get("hazard_id", "")),
                    "model_version": str(h.get("model_version", "v1")),
                    "severity": round(float(h.get("severity", 0.0)), 4),
                    "simulated": bool(h.get("simulated", False)),
                    "source": str(h.get("source", "model")),
                    "timestamp": ts_str,
                })
        canon_hazards.sort(key=lambda x: x["hazard_id"])

        # 5. Phase 3 — Prediction Evidence (Order-insensitive: sorted by prediction_id, relevance-filtered)
        canon_predictions = []
        if predictions:
            for item in predictions:
                p = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                if not cls._is_relevant_evidence(p, "prediction_id"):
                    continue
                p_haz = p.get("hazard", "")
                p_haz_str = p_haz.value if hasattr(p_haz, "value") else str(p_haz)
                p_time = p.get("prediction_time", p.get("timestamp", ""))
                f_time = p.get("forecast_time", p.get("target_time", ""))
                canon_predictions.append({
                    "confidence": round(float(p.get("confidence", 0.0)), 4),
                    "forecast_time": p_time.isoformat() if isinstance(p_time, datetime) else str(p_time),
                    "hazard": p_haz_str,
                    "model_version": str(p.get("model_version", "v1")),
                    "prediction_id": str(p.get("prediction_id", "")),
                    "prediction_time": f_time.isoformat() if isinstance(f_time, datetime) else str(f_time),
                    "severity": round(float(p.get("severity", 0.0)), 4),
                    "simulated": bool(p.get("simulated", False)),
                })
        canon_predictions.sort(key=lambda x: x["prediction_id"])

        # 6. Phase 4 — Compound Event Evidence (Events sorted by event_id, causal_chain is ORDER-SENSITIVE)
        canon_compounds = []
        if compound_events:
            for item in compound_events:
                ce = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                if not cls._is_relevant_evidence(ce, "event_id"):
                    continue
                # causal_chain preserves exact sequential causal order!
                chain = list(ce.get("chain", ce.get("causal_chain", [])))
                contrib = sorted(list(ce.get("contributing_hazards", ce.get("evidence_ids", []))))
                ce_ts = ce.get("timestamp", "")
                canon_compounds.append({
                    "causal_chain": chain,
                    "confidence": round(float(ce.get("confidence", 0.0)), 4),
                    "contributing_hazards": contrib,
                    "event_id": str(ce.get("event_id", "")),
                    "rule_version": str(ce.get("rule_version", "v1")),
                    "severity": round(float(ce.get("severity", 0.0)), 4),
                    "simulated": bool(ce.get("simulated", False)),
                    "timestamp": ce_ts.isoformat() if isinstance(ce_ts, datetime) else str(ce_ts),
                })
        canon_compounds.sort(key=lambda x: x["event_id"])

        # 7. Phase 5 — Vulnerability Evidence (Order-insensitive: sorted by zone_id)
        canon_vulns = []
        if vulnerability_zones:
            for item in vulnerability_zones:
                v = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                if not cls._is_relevant_evidence(v, "zone_id"):
                    continue
                ev_ids = sorted(list(v.get("evidence_ids", [])))
                canon_vulns.append({
                    "accessibility": round(float(v.get("accessibility", 1.0)), 4),
                    "accessibility_risk": round(float(v.get("accessibility_risk", 0.0)), 4),
                    "confidence": round(float(v.get("confidence", 1.0)), 4),
                    "evidence_ids": ev_ids,
                    "exposure_ratio": round(float(v.get("exposure_ratio", 0.0)), 4),
                    "formula_version": str(v.get("formula_version", "v1")),
                    "human_impact": round(float(v.get("human_impact", 0.0)), 4),
                    "population_exposed": int(v.get("population_exposed", 0)),
                    "simulated": bool(v.get("simulated", True)),
                    "vulnerability": round(float(v.get("vulnerability", 0.0)), 4),
                    "zone_id": str(v.get("zone_id", "")),
                })
        canon_vulns.sort(key=lambda x: x["zone_id"])

        # 8. Phase 6 — Evacuation Evidence
        # Candidate road edges (sorted by edge_id)
        canon_edges = []
        if road_edges:
            for item in road_edges:
                e = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                inf_risk = e.get("inferred_failure_risk")
                canon_edges.append({
                    "accessibility": round(float(e.get("accessibility", 1.0)), 4),
                    "closed": bool(e.get("closed", False)),
                    "distance_km": round(float(e.get("distance_km", 0.0)), 4),
                    "edge_id": str(e.get("edge_id", "")),
                    "from_node": str(e.get("from_node", "")),
                    "hazard_risk": round(float(e.get("hazard_risk", 0.0)), 4),
                    "inferred_failure_risk": round(float(inf_risk), 4) if inf_risk is not None else None,
                    "to_node": str(e.get("to_node", "")),
                    "travel_time_minutes": round(float(e.get("travel_time_minutes", 0.0)), 4),
                })
        canon_edges.sort(key=lambda x: x["edge_id"])

        # Candidate shelters (sorted by shelter_id)
        canon_shelters = []
        if shelters:
            for item in shelters:
                s = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                cap = int(s.get("capacity", 0))
                occ = int(s.get("current_occupancy", 0))
                avail = int(s.get("available_capacity", max(0, cap - occ)))
                canon_shelters.append({
                    "accessibility": round(float(s.get("accessibility", 1.0)), 4),
                    "available_capacity": avail,
                    "capacity": cap,
                    "current_occupancy": occ,
                    "hazard_risk": round(float(s.get("hazard_risk", 0.0)), 4),
                    "latitude": round(float(s.get("latitude", 0.0)), 6),
                    "longitude": round(float(s.get("longitude", 0.0)), 6),
                    "safe": bool(s.get("safe", True)),
                    "shelter_id": str(s.get("shelter_id", "")),
                    "simulated": bool(s.get("simulated", True)),
                })
        canon_shelters.sort(key=lambda x: x["shelter_id"])

        # Evacuation routes (sorted by zone_id, route_nodes and route_edges are ORDER-SENSITIVE)
        canon_routes = []
        if evacuation_routes:
            for item in evacuation_routes:
                r = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                route_obj = r.get("route") or {}
                dest_obj = r.get("destination") or {}
                # route_nodes and route_edges preserve exact sequential path traversal order!
                r_nodes = list(route_obj.get("nodes", []))
                r_edges = list(route_obj.get("edge_ids", []))
                status_val = r.get("status", "RECOMMENDED")
                status_str = status_val.value if hasattr(status_val, "value") else str(status_val)
                canon_routes.append({
                    "accessibility": round(float(route_obj.get("accessibility", 1.0)), 4),
                    "assigned_population": int(dest_obj.get("assigned_population", 0)),
                    "distance_km": round(float(route_obj.get("distance_km", 0.0)), 4),
                    "hazard_exposure": round(float(route_obj.get("hazard_exposure", 0.0)), 4),
                    "reason": str(r.get("reason", "")),
                    "route_edges": r_edges,
                    "route_nodes": r_nodes,
                    "route_safety": round(float(route_obj.get("safety_score", 1.0)), 4),
                    "selected_shelter_id": str(dest_obj.get("shelter_id", "")) if dest_obj else None,
                    "status": status_str,
                    "travel_time_minutes": round(float(route_obj.get("estimated_travel_minutes", 0.0)), 4),
                    "zone_id": str(r.get("zone_id", "")),
                })
        canon_routes.sort(key=lambda x: x["zone_id"])

        canon_routing_config = {
            "accessibility_threshold": round(float(accessibility_threshold), 4),
            "hazard_threshold": round(float(hazard_threshold), 4),
        }

        # Assemble full deterministic material payload
        payload = {
            "base_state": canon_base_state,
            "confidence": round(float(confidence), 4),
            "evacuation": {
                "candidate_edges": canon_edges,
                "candidate_shelters": canon_shelters,
                "routing_configuration": canon_routing_config,
                "routes": canon_routes,
            },
            "hazards": canon_hazards,
            "model_versions": effective_models,
            "parameters": canon_params,
            "predictions": canon_predictions,
            "compound_events": canon_compounds,
            "scenario": {
                "scenario_id": str(scenario_id),
                "scenario_version": str(scenario_version),
            },
            "simulated": bool(simulated),
            "transformations": canon_transforms,
            "vulnerability_zones": canon_vulns,
        }
        return payload

    @classmethod
    def compute_provenance_hash(
        cls,
        canonical_payload: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Computes deterministic SHA-256 digest from canonical simulation payload.
        """
        if canonical_payload is not None:
            serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        built_payload = cls.build_canonical_payload(**kwargs)
        serialized = json.dumps(built_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
