"""
Evidence resolver for Phase 10 Explainability.
Traverses multi-phase intelligence records to resolve and link authoritative upstream entities.
"""

from typing import Any, Dict, List, Optional
from intelligence.explainability.types import EvidenceReference


class EvidenceResolver:
    """
    Extracts and normalizes upstream evidence references across Phase 2-9 artifacts.
    """

    @classmethod
    def resolve_hazard_evidence(cls, hazard_dict: Dict[str, Any]) -> List[EvidenceReference]:
        """Resolves telemetry evidence underlying a hazard result."""
        refs: List[EvidenceReference] = []
        node_id = hazard_dict.get("node_id") or hazard_dict.get("sensor_id")
        if node_id:
            refs.append(EvidenceReference(
                type="telemetry",
                id=str(node_id),
                severity=float(hazard_dict.get("severity", 0.0)),
                confidence=float(hazard_dict.get("confidence", 1.0)),
                provenance_hash=hazard_dict.get("provenance_hash"),
            ))
        return refs

    @classmethod
    def resolve_prediction_evidence(cls, pred_dict: Dict[str, Any]) -> List[EvidenceReference]:
        """Resolves baseline telemetry and historical series underlying a prediction."""
        refs: List[EvidenceReference] = []
        node_id = pred_dict.get("node_id")
        if node_id:
            refs.append(EvidenceReference(
                type="telemetry_baseline",
                id=str(node_id),
                severity=float(pred_dict.get("baseline_severity", 0.0)),
                confidence=float(pred_dict.get("confidence", 1.0)),
                provenance_hash=pred_dict.get("provenance_hash"),
            ))
        return refs

    @classmethod
    def resolve_compound_evidence(cls, comp_dict: Dict[str, Any]) -> List[EvidenceReference]:
        """Resolves contributing hazards and causal states underlying a compound disaster."""
        refs: List[EvidenceReference] = []
        for state in comp_dict.get("contributing_states", []):
            s_id = state.get("state_id") or state.get("source_ref_id")
            if s_id:
                refs.append(EvidenceReference(
                    type=str(state.get("evidence_type", "state")),
                    id=str(s_id),
                    severity=float(state.get("severity", 0.0)),
                    confidence=float(state.get("confidence", 1.0)),
                    provenance_hash=state.get("provenance_hash"),
                ))
        for haz in comp_dict.get("contributing_hazards", []):
            if isinstance(haz, str):
                refs.append(EvidenceReference(
                    type="hazard",
                    id=haz,
                    severity=float(comp_dict.get("severity", 0.0)),
                    confidence=float(comp_dict.get("confidence", 1.0)),
                ))
            elif isinstance(haz, dict):
                refs.append(EvidenceReference(
                    type="hazard",
                    id=haz.get("hazard_id") or haz.get("id", "HAZ-UNKNOWN"),
                    severity=float(haz.get("severity", comp_dict.get("severity", 0.0))),
                    confidence=float(haz.get("confidence", comp_dict.get("confidence", 1.0))),
                    provenance_hash=haz.get("provenance_hash"),
                ))
        return refs

    @classmethod
    def resolve_vulnerability_evidence(cls, vuln_dict: Dict[str, Any]) -> List[EvidenceReference]:
        """Resolves hazard and demographic evidence underlying a vulnerability score."""
        refs: List[EvidenceReference] = []
        for h_id in vuln_dict.get("applicable_hazard_types", []):
            refs.append(EvidenceReference(
                type="hazard_type",
                id=str(h_id),
                severity=float(vuln_dict.get("hazard_risk", 0.0)),
                confidence=float(vuln_dict.get("confidence", 1.0)),
            ))
        zone_id = vuln_dict.get("zone_id")
        if zone_id:
            refs.append(EvidenceReference(
                type="population_zone",
                id=str(zone_id),
                severity=float(vuln_dict.get("human_impact", 0.0)),
                confidence=float(vuln_dict.get("confidence", 1.0)),
                provenance_hash=vuln_dict.get("provenance_hash"),
            ))
        return refs

    @classmethod
    def resolve_evacuation_evidence(cls, evac_dict: Dict[str, Any]) -> List[EvidenceReference]:
        """Resolves route and shelter evidence underlying an evacuation recommendation."""
        refs: List[EvidenceReference] = []
        dest = evac_dict.get("destination")
        if dest and isinstance(dest, dict) and dest.get("shelter_id"):
            refs.append(EvidenceReference(
                type="shelter",
                id=str(dest.get("shelter_id")),
                severity=float(dest.get("shelter_safety_score", 1.0)),
            ))
        route = evac_dict.get("route")
        if route and isinstance(route, dict) and route.get("route_id"):
            refs.append(EvidenceReference(
                type="route",
                id=str(route.get("route_id")),
                severity=float(route.get("safety_score", 1.0)),
            ))
        return refs

    @classmethod
    def resolve_response_evidence(cls, action_dict: Dict[str, Any]) -> List[EvidenceReference]:
        """Resolves upstream hazard, vulnerability, and evacuation evidence for a response action."""
        refs: List[EvidenceReference] = []
        for ref in action_dict.get("evidence", action_dict.get("evidence_refs", [])):
            if isinstance(ref, str):
                refs.append(EvidenceReference(
                    type="upstream_evidence",
                    id=ref,
                    severity=float(action_dict.get("priority_score", action_dict.get("severity", 0.0))),
                    confidence=float(action_dict.get("confidence", 1.0)),
                ))
            elif isinstance(ref, dict):
                sev = ref.get("severity")
                if sev is None:
                    sev = action_dict.get("priority_score", action_dict.get("severity", 0.0))
                conf = ref.get("confidence")
                if conf is None:
                    conf = action_dict.get("confidence", 1.0)
                refs.append(EvidenceReference(
                    type=str(ref.get("type", "upstream_evidence")),
                    id=str(ref.get("id", ref.get("ref_id", "ref"))),
                    severity=float(sev or 0.0),
                    confidence=float(conf or 1.0),
                    provenance_hash=ref.get("provenance_hash"),
                ))
        return refs
