"""
Climate Eye View — Phase 9 Evidence Collection & Validation Engine.

Ingests, normalizes, indexes, and validates evidence items originating from
Phases 2 through 8. Ensures that every action references only verified upstream IDs.
"""

from typing import Any, Dict, List, Optional
from intelligence.response.types import EvidenceReference, EvidenceType


class EvidenceRegistry:
    """
    In-memory registry of all authoritative evidence items available to the Response Planner.
    Guarantees that recommendations reference genuinely existing upstream evidence IDs.
    """

    def __init__(self):
        self._evidence_by_id: Dict[str, EvidenceReference] = {}
        self._evidence_by_type: Dict[str, List[EvidenceReference]] = {}

    def register(self, item: EvidenceReference) -> None:
        """Registers an authoritative evidence reference."""
        self._evidence_by_id[item.id] = item
        self._evidence_by_type.setdefault(item.type, []).append(item)

    def get(self, evidence_id: str) -> Optional[EvidenceReference]:
        """Retrieves an evidence reference by ID."""
        return self._evidence_by_id.get(evidence_id)

    def contains(self, evidence_id: str) -> bool:
        """Checks if an evidence ID is registered."""
        return evidence_id in self._evidence_by_id

    def list_all(self) -> List[EvidenceReference]:
        """Returns all registered evidence items."""
        return list(self._evidence_by_id.values())

    def list_by_type(self, evidence_type: str) -> List[EvidenceReference]:
        """Returns evidence items of a specific type (e.g. 'hazard', 'vulnerability')."""
        return self._evidence_by_type.get(evidence_type, [])

    def validate_action_evidence(self, evidence_refs: List[EvidenceReference]) -> List[str]:
        """
        Validates that all evidence items referenced by an action exist in this registry.
        Returns a list of missing/unverified evidence IDs (empty if all valid).
        """
        missing = []
        for ref in evidence_refs:
            if not self.contains(ref.id):
                missing.append(ref.id)
        return missing


def build_evidence_registry_from_upstream(
    hazards: List[Dict[str, Any]],
    predictions: List[Dict[str, Any]],
    compound_events: List[Dict[str, Any]],
    vulnerability_zones: List[Dict[str, Any]],
    evacuation_recommendations: List[Dict[str, Any]],
    road_edges: List[Dict[str, Any]],
    shelters: List[Dict[str, Any]],
    scenario_context: Optional[Dict[str, Any]] = None,
    is_simulated: bool = False,
) -> EvidenceRegistry:
    """
    Constructs an authoritative EvidenceRegistry from structured outputs of Phases 2–8.
    """
    registry = EvidenceRegistry()
    base_ev_type = EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED

    # 1. Register Phase 2/3 Hazards
    for h in hazards:
        hid = h.get("hazard_id") or f"HAZ-{h.get('hazard_type', 'UNKNOWN').upper()}"
        ev_type = EvidenceType.SIMULATED if (is_simulated or h.get("simulated")) else EvidenceType.OBSERVED
        registry.register(EvidenceReference(
            type="hazard",
            id=hid,
            evidence_type=ev_type,
            severity=float(h.get("severity", 0.0)),
            confidence=float(h.get("confidence", 1.0)),
            description=f"Hazard {h.get('hazard_type', 'hazard')} severity {h.get('severity', 0.0)}",
        ))

    # 2. Register Phase 4 Predictions
    for p in predictions:
        pid = p.get("prediction_id") or f"PRED-{p.get('hazard', 'UNKNOWN').upper()}-{p.get('forecast_horizon_minutes', 0)}M"
        ev_type = EvidenceType.SIMULATED if (is_simulated or p.get("simulated")) else EvidenceType.PREDICTED
        registry.register(EvidenceReference(
            type="prediction",
            id=pid,
            evidence_type=ev_type,
            severity=float(p.get("severity", 0.0)),
            confidence=float(p.get("confidence", 1.0)),
            description=f"Prediction for {p.get('hazard')} at +{p.get('forecast_horizon_minutes', 0)}m",
        ))

    # 3. Register Phase 5 Compound & Cascading Events
    for c in compound_events:
        cid = c.get("event_id") or f"COMP-{c.get('rule_id', 'MULTI')}"
        ev_type = EvidenceType.SIMULATED if (is_simulated or c.get("simulated")) else EvidenceType.INFERRED
        registry.register(EvidenceReference(
            type="compound",
            id=cid,
            evidence_type=ev_type,
            severity=float(c.get("severity", 0.0)),
            confidence=float(c.get("confidence", 1.0)),
            description=f"Compound event {cid} causal chain: {' -> '.join(c.get('causal_chain', []))}",
        ))

    # 4. Register Phase 6 Vulnerability Zones
    for v in vulnerability_zones:
        zid = v.get("zone_id") or "ZONE-UNKNOWN"
        ev_type = EvidenceType.SIMULATED if (is_simulated or v.get("simulated")) else EvidenceType.OBSERVED
        registry.register(EvidenceReference(
            type="vulnerability",
            id=zid,
            evidence_type=ev_type,
            severity=float(v.get("human_impact", v.get("vulnerability", 0.0))),
            confidence=float(v.get("confidence", 1.0)),
            description=f"Vulnerability zone {zid} human impact {v.get('human_impact', 0.0)}",
        ))

    # 5. Register Phase 7 Evacuation Directives & Routes
    for e in evacuation_recommendations:
        eid = e.get("evacuation_id") or f"EVAC-{e.get('zone_id', 'UNKNOWN')}"
        ev_type = EvidenceType.SIMULATED if (is_simulated or e.get("simulated")) else EvidenceType.OBSERVED
        registry.register(EvidenceReference(
            type="evacuation",
            id=eid,
            evidence_type=ev_type,
            severity=float(e.get("priority", 0.0)),
            confidence=float(e.get("confidence", 1.0)),
            description=f"Evacuation directive {eid} status: {e.get('status', 'UNKNOWN')}",
        ))
        if e.get("route"):
            rid = e["route"].get("route_id") or f"ROUTE-{eid}"
            registry.register(EvidenceReference(
                type="route",
                id=rid,
                evidence_type=ev_type,
                severity=1.0 - float(e["route"].get("route_safety_score", 1.0)),
                confidence=float(e.get("confidence", 1.0)),
                description=f"Route {rid} safety score {e['route'].get('route_safety_score', 1.0)}",
            ))

    # 6. Register Phase 7 Road Network Edges
    for edge in road_edges:
        edge_id = edge.get("edge_id") or f"ROAD-{edge.get('from_node')}-{edge.get('to_node')}"
        ev_type = EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED
        hazard_risk = float(edge.get("hazard_risk") or 0.0)
        accessibility = float(edge.get("accessibility", 1.0) if edge.get("accessibility") is not None else 1.0)
        severity = max(hazard_risk, 1.0 - accessibility)

        registry.register(EvidenceReference(
            type="road_edge",
            id=edge_id,
            evidence_type=ev_type,
            severity=severity,
            confidence=1.0,
            description=f"Road edge {edge_id} closed={edge.get('closed', False)} accessibility={accessibility}",
        ))


    # 7. Register Phase 7 Shelters
    for s in shelters:
        sid = s.get("shelter_id") or "SHELTER-UNKNOWN"
        ev_type = EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED
        registry.register(EvidenceReference(
            type="shelter",
            id=sid,
            evidence_type=ev_type,
            severity=float(s.get("hazard_risk", 0.0)),
            confidence=1.0,
            description=f"Shelter {sid} safe={s.get('safe', True)} capacity={s.get('capacity', 0)}",
        ))

    # 8. Register Scenario Context if present
    if scenario_context and scenario_context.get("scenario_id"):
        sc_id = scenario_context["scenario_id"]
        registry.register(EvidenceReference(
            type="scenario",
            id=sc_id,
            evidence_type=EvidenceType.SIMULATED,
            severity=0.5,
            confidence=1.0,
            description=f"What-if scenario {sc_id} parameters: {scenario_context.get('parameters', {})}",
        ))

    return registry
