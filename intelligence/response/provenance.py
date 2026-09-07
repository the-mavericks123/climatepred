"""
Climate Eye View — Phase 9 Response Planner Deterministic Provenance.

Computes a cryptographic SHA-256 fingerprint representing the material inputs,
authoritative upstream evidence, configuration thresholds, and ranked action sequence.
Volatile execution fields (plan_id, generated_at, request_id) are strictly decoupled.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional
from intelligence.response.types import ActionItem, AlertLevel


class ResponseProvenanceTracker:
    """
    Computes deterministic provenance hashes for Phase 9 emergency response plans.
    """

    def __init__(
        self,
        model_version: str = "response-v1",
        rules_version: str = "response-rules-v1",
        priority_formula_version: str = "priority-v1",
        confidence_formula_version: str = "confidence-v1",
    ):
        self.model_version = model_version
        self.rules_version = rules_version
        self.priority_formula_version = priority_formula_version
        self.confidence_formula_version = confidence_formula_version

    def build_canonical_payload(
        self,
        alert_level: AlertLevel,
        actions: List[ActionItem],
        hazards: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        compound_events: List[Dict[str, Any]],
        vulnerability_zones: List[Dict[str, Any]],
        road_edges: List[Dict[str, Any]],
        shelters: List[Dict[str, Any]],
        thresholds: Dict[str, Any],
        scenario_context: Optional[Dict[str, Any]] = None,
        base_state_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Constructs the deterministic canonical material payload.
        Logically unordered collections are canonically sorted by ID.
        Order-sensitive sequences (actions sequence, causal chains) retain exact order.
        """
        # 1. Canonical hazards (order-insensitive: sort by hazard_id)
        canon_hazards = []
        for h in hazards:
            if h.get("is_relevant", True) is not False:
                canon_hazards.append({
                    "hazard_id": str(h.get("hazard_id", "")),
                    "hazard_type": str(h.get("hazard_type", "")),
                    "severity": round(float(h.get("severity", 0.0)), 4),
                    "confidence": round(float(h.get("confidence", 1.0)), 4),
                })
        canon_hazards.sort(key=lambda x: x["hazard_id"])

        # 2. Canonical predictions (order-insensitive: sort by prediction_id)
        canon_predictions = []
        for p in predictions:
            canon_predictions.append({
                "prediction_id": str(p.get("prediction_id", "")),
                "hazard": str(p.get("hazard", "")),
                "forecast_horizon_minutes": int(p.get("forecast_horizon_minutes", 0)),
                "severity": round(float(p.get("severity", 0.0)), 4),
                "confidence": round(float(p.get("confidence", 1.0)), 4),
            })
        canon_predictions.sort(key=lambda x: x["prediction_id"])

        # 3. Canonical compound events (order-insensitive collection, but causal_chain is order-sensitive)
        canon_compounds = []
        for c in compound_events:
            canon_compounds.append({
                "event_id": str(c.get("event_id", "")),
                "severity": round(float(c.get("severity", 0.0)), 4),
                "causal_chain": list(c.get("causal_chain", [])),  # ORDER-SENSITIVE
                "contributing_hazards": sorted(list(c.get("contributing_hazards", []))),
            })
        canon_compounds.sort(key=lambda x: x["event_id"])

        # 4. Canonical vulnerability zones (order-insensitive: sort by zone_id)
        canon_vuln = []
        for v in vulnerability_zones:
            canon_vuln.append({
                "zone_id": str(v.get("zone_id", "")),
                "population_exposed": int(v.get("population_exposed", 0)),
                "human_impact": round(float(v.get("human_impact", 0.0)), 4),
                "vulnerability": round(float(v.get("vulnerability", 0.0)), 4),
            })
        canon_vuln.sort(key=lambda x: x["zone_id"])

        # 5. Canonical road edges (order-insensitive: sort by edge_id)
        canon_edges = []
        for e in road_edges:
            canon_edges.append({
                "edge_id": str(e.get("edge_id", "")),
                "accessibility": round(float(e.get("accessibility", 1.0)), 4),
                "hazard_risk": round(float(e.get("hazard_risk", 0.0)), 4),
                "closed": bool(e.get("closed", False)),
            })
        canon_edges.sort(key=lambda x: x["edge_id"])

        # 6. Canonical shelters (order-insensitive: sort by shelter_id)
        canon_shelters = []
        for s in shelters:
            canon_shelters.append({
                "shelter_id": str(s.get("shelter_id", "")),
                "capacity": int(s.get("capacity", 0)),
                "current_occupancy": int(s.get("current_occupancy", 0)),
                "safe": bool(s.get("safe", True)),
                "hazard_risk": round(float(s.get("hazard_risk", 0.0)), 4),
            })
        canon_shelters.sort(key=lambda x: x["shelter_id"])

        # 7. Canonical Actions (ORDER-SENSITIVE: sequential ranked order matters!)
        canon_actions = []
        for act in actions:
            evidence_ids = sorted([ref.id for ref in act.evidence])
            canon_actions.append({
                "action": str(act.action.value if hasattr(act.action, "value") else act.action),
                "target": str(act.target),
                "priority": int(act.priority),
                "urgency": str(act.urgency.value if hasattr(act.urgency, "value") else act.urgency),
                "status": str(act.status.value if hasattr(act.status, "value") else act.status),
                "requires_human_review": bool(act.requires_human_review),
                "evidence_ids": evidence_ids,
            })

        payload: Dict[str, Any] = {
            "alert_level": str(alert_level.value if hasattr(alert_level, "value") else alert_level),
            "base_state_hash": base_state_hash or "BASE-UNSET",
            "model_version": self.model_version,
            "rules_version": self.rules_version,
            "priority_formula_version": self.priority_formula_version,
            "confidence_formula_version": self.confidence_formula_version,
            "thresholds": thresholds,
            "scenario": scenario_context or {},
            "evidence": {
                "hazards": canon_hazards,
                "predictions": canon_predictions,
                "compound_events": canon_compounds,
                "vulnerability_zones": canon_vuln,
                "road_edges": canon_edges,
                "shelters": canon_shelters,
            },
            "actions": canon_actions,
        }
        return payload

    def compute_provenance_hash(
        self,
        alert_level: AlertLevel,
        actions: List[ActionItem],
        hazards: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        compound_events: List[Dict[str, Any]],
        vulnerability_zones: List[Dict[str, Any]],
        road_edges: List[Dict[str, Any]],
        shelters: List[Dict[str, Any]],
        thresholds: Dict[str, Any],
        scenario_context: Optional[Dict[str, Any]] = None,
        base_state_hash: Optional[str] = None,
    ) -> str:
        """
        Produces a deterministic SHA-256 hash from the canonical material payload.
        """
        payload = self.build_canonical_payload(
            alert_level=alert_level,
            actions=actions,
            hazards=hazards,
            predictions=predictions,
            compound_events=compound_events,
            vulnerability_zones=vulnerability_zones,
            road_edges=road_edges,
            shelters=shelters,
            thresholds=thresholds,
            scenario_context=scenario_context,
            base_state_hash=base_state_hash,
        )
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
