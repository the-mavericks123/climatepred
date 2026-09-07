"""
Climate Eye View — Phase 9 Deterministic Emergency Response Rules.

Generates candidate ActionItems from authoritative outputs across Phases 2 through 8.
Adheres strictly to the controlled action vocabulary and never fabricates numerical data.
"""

from typing import Any, Dict, List, Optional
from intelligence.response.confidence import calculate_action_confidence
from intelligence.response.evidence import EvidenceRegistry
from intelligence.response.priorities import calculate_priority_score, calculate_urgency
from intelligence.response.types import (
    ActionItem,
    ActionStatus,
    ActionType,
    EvidenceReference,
    EvidenceType,
    UrgencyLevel,
)



class ResponseRuleEngine:
    """
    Deterministic rule engine that produces candidate response actions
    grounded in authoritative upstream evidence.
    """

    def __init__(
        self,
        edge_accessibility_threshold: float = 0.40,
        stale_confidence_penalty: float = 0.35,
        missing_evidence_penalty: float = 0.25,
    ):
        self.edge_accessibility_threshold = edge_accessibility_threshold
        self.stale_confidence_penalty = stale_confidence_penalty
        self.missing_evidence_penalty = missing_evidence_penalty

    def generate_candidate_actions(
        self,
        hazards: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        compound_events: List[Dict[str, Any]],
        vulnerability_zones: List[Dict[str, Any]],
        evacuation_recommendations: List[Dict[str, Any]],
        road_edges: List[Dict[str, Any]],
        shelters: List[Dict[str, Any]],
        evidence_registry: EvidenceRegistry,
        is_stale: bool = False,
        is_simulated: bool = False,
    ) -> List[ActionItem]:
        """
        Executes all deterministic response rules and compiles candidate ActionItems.
        """
        candidates: List[ActionItem] = []
        action_counter = 1

        # ------------------------------------------------------------------
        # 1. Flood Evacuation Rules (Observed)
        # ------------------------------------------------------------------
        flood_hazard = next((h for h in hazards if h.get("hazard") == "flood" or h.get("hazard_type") == "flood"), None)
        flood_severity = float(flood_hazard.get("severity", 0.0)) if flood_hazard else 0.0
        flood_conf = float(flood_hazard.get("confidence", 1.0)) if flood_hazard else 1.0
        flood_id = flood_hazard.get("hazard_id", "HAZ-FLOOD") if flood_hazard else "HAZ-FLOOD"


        for zone in vulnerability_zones:
            zone_id = zone.get("zone_id", "ZONE-UNKNOWN")
            human_impact = float(zone.get("human_impact", 0.0))
            vulnerability = float(zone.get("vulnerability", 0.0))
            pop_exposed = int(zone.get("population_exposed", 0))

            # Find matching evacuation recommendation if available
            evac_rec = next((e for e in evacuation_recommendations if e.get("zone_id") == zone_id), None)
            evac_id = evac_rec.get("evacuation_id") if evac_rec else None
            evac_status = evac_rec.get("status") if evac_rec else None

            # RULE 1A: NO_ROUTE Condition
            if evac_status == "NO_ROUTE":
                ev_refs = []
                if flood_hazard:
                    ev_refs.append(evidence_registry.get(flood_id) or EvidenceReference(type="hazard", id=flood_id, severity=flood_severity, confidence=flood_conf))
                ev_refs.append(evidence_registry.get(zone_id) or EvidenceReference(type="vulnerability", id=zone_id, severity=human_impact))
                if evac_id:
                    ev_refs.append(evidence_registry.get(evac_id) or EvidenceReference(type="evacuation", id=evac_id))

                conf, _ = calculate_action_confidence(ev_refs, is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=flood_severity,
                    human_impact=human_impact,
                    accessibility_risk=1.0,  # Total blockage
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                )
                prio_score = calculate_priority_score(urg_score, vulnerability, 0.90, conf)

                candidates.append(ActionItem(
                    action_id=f"ACT-VERIFY-{action_counter:03d}",
                    action=ActionType.REQUEST_FIELD_VERIFICATION,
                    target=zone_id,
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Evacuation corridor for {zone_id} is completely blocked (NO_ROUTE). Urgent field verification of alternative extraction paths is required.",
                    evidence=ev_refs,
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=True,
                    review_reason="Critical access failure: No feasible ground evacuation route exists. Immediate manual operations review required.",
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

                candidates.append(ActionItem(
                    action_id=f"ACT-REASSESS-{action_counter:03d}",
                    action=ActionType.REASSESS,
                    target=zone_id,
                    priority=1,
                    priority_score=prio_score * 0.95,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Reassess evacuation routing parameters and shelter allocations for isolated zone {zone_id}.",
                    evidence=ev_refs,
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=True,
                    review_reason="Automated router reached NO_ROUTE; human dispatch intervention required.",
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

            # RULE 1B: Active Flood Evacuation
            elif flood_severity >= 0.70 and human_impact >= 0.50:
                ev_refs = []
                if flood_hazard:
                    ev_refs.append(evidence_registry.get(flood_id) or EvidenceReference(type="hazard", id=flood_id, severity=flood_severity, confidence=flood_conf))
                ev_refs.append(evidence_registry.get(zone_id) or EvidenceReference(type="vulnerability", id=zone_id, severity=human_impact))
                if evac_id:
                    ev_refs.append(evidence_registry.get(evac_id) or EvidenceReference(type="evacuation", id=evac_id))

                conf, _ = calculate_action_confidence(ev_refs, is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=flood_severity,
                    human_impact=human_impact,
                    accessibility_risk=float(zone.get("accessibility_risk", 0.3)),
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                )
                prio_score = calculate_priority_score(urg_score, vulnerability, 0.50, conf)

                label_prefix = "SIMULATED WHAT-IF: " if is_simulated else ""
                candidates.append(ActionItem(
                    action_id=f"ACT-EVAC-{action_counter:03d}",
                    action=ActionType.EVACUATE_ZONE,
                    target=zone_id,
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"{label_prefix}Severe flood conditions (severity {flood_severity:.2f}) exposing {pop_exposed:,} residents with high human impact ({human_impact:.2f}).",
                    evidence=ev_refs,
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=True,
                    review_reason="Emergency zone evacuation directive requires designated incident commander sign-off.",
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

            # RULE 1C: Vulnerable Population Prioritization
            if human_impact >= 0.60 or (vulnerability >= 0.55 and human_impact >= 0.35) or vulnerability >= 0.70:
                ev_refs = [
                    evidence_registry.get(zone_id) or EvidenceReference(type="vulnerability", id=zone_id, severity=human_impact)
                ]
                if flood_hazard:
                    ev_refs.append(evidence_registry.get(flood_id) or EvidenceReference(type="hazard", id=flood_id, severity=flood_severity))

                conf, _ = calculate_action_confidence(ev_refs, is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=flood_severity,
                    human_impact=max(human_impact, vulnerability * 0.7),
                    accessibility_risk=float(zone.get("accessibility_risk", 0.4)),
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                )
                prio_score = calculate_priority_score(urg_score, vulnerability, 0.40, conf)



                candidates.append(ActionItem(
                    action_id=f"ACT-VULN-{action_counter:03d}",
                    action=ActionType.PRIORITIZE_VULNERABLE_POPULATION,
                    target=zone_id,
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Elevated demographic vulnerability ({vulnerability:.2f}) and healthcare access deficit in {zone_id}. Prioritize non-ambulatory transport and medical support.",
                    evidence=ev_refs,
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=False,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

        # ------------------------------------------------------------------
        # 2. Predicted Flood / Hazard Rules (Forecasted)
        # ------------------------------------------------------------------
        for pred in predictions:
            pred_id = pred.get("prediction_id", "PRED-UNKNOWN")
            hazard_type = pred.get("hazard", "unknown")
            severity = float(pred.get("severity", 0.0))
            horizon = int(pred.get("forecast_horizon_minutes", 0))
            conf_val = float(pred.get("confidence", 1.0))

            if severity >= 0.65:
                ev_ref = evidence_registry.get(pred_id) or EvidenceReference(
                    type="prediction",
                    id=pred_id,
                    evidence_type=EvidenceType.SIMULATED if is_simulated else EvidenceType.PREDICTED,
                    severity=severity,
                    confidence=conf_val,
                )
                conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=severity,
                    human_impact=0.60,
                    accessibility_risk=0.40,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.PREDICTED,
                    forecast_horizon_minutes=horizon,
                )
                prio_score = calculate_priority_score(urg_score, 0.60, 0.40, conf)

                label_prefix = "SIMULATED: " if is_simulated else "PREDICTED: "
                candidates.append(ActionItem(
                    action_id=f"ACT-PRED-{action_counter:03d}",
                    action=ActionType.PREPARE_EVACUATION if severity >= 0.80 else ActionType.ISSUE_WARNING,
                    target=f"REGION-{hazard_type.upper()}",
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"{label_prefix}Forecast model projects {hazard_type} escalation to severity {severity:.2f} at +{horizon} min horizon. Initiate staged preparation.",
                    evidence=[ev_ref],
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=False,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.PREDICTED,
                    forecast_horizon_minutes=horizon,
                    simulated=is_simulated,
                ))
                action_counter += 1

        # ------------------------------------------------------------------
        # 3. Compound & Cascading Disaster Rules
        # ------------------------------------------------------------------
        for comp in compound_events:
            event_id = comp.get("event_id", "COMP-UNKNOWN")
            severity = float(comp.get("severity", 0.0))
            chain = comp.get("causal_chain", [])
            conf_val = float(comp.get("confidence", 1.0))

            if severity >= 0.70:
                ev_ref = evidence_registry.get(event_id) or EvidenceReference(
                    type="compound",
                    id=event_id,
                    evidence_type=EvidenceType.SIMULATED if is_simulated else EvidenceType.INFERRED,
                    severity=severity,
                    confidence=conf_val,
                )
                conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=severity,
                    human_impact=0.70,
                    accessibility_risk=0.75,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.INFERRED,
                )
                prio_score = calculate_priority_score(urg_score, 0.70, severity, conf)

                chain_str = " -> ".join(chain) if chain else "compound interaction"
                candidates.append(ActionItem(
                    action_id=f"ACT-CASCADE-{action_counter:03d}",
                    action=ActionType.PREPOSITION_RESPONSE_RESOURCES,
                    target="MULTIZONE-CORRIDOR",
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Cascading disaster detected ({chain_str}) with compound severity {severity:.2f}. Pre-position flood pumps and rapid recovery teams.",
                    evidence=[ev_ref],
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=False,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.INFERRED,
                    simulated=is_simulated,
                ))
                action_counter += 1

        # ------------------------------------------------------------------
        # 4. Road Network & Bridge Closure Rules
        # ------------------------------------------------------------------
        for edge in road_edges:
            edge_id = edge.get("edge_id", "ROAD-UNKNOWN")
            closed = bool(edge.get("closed", False))
            accessibility = float(edge.get("accessibility", 1.0) if edge.get("accessibility") is not None else 1.0)
            inferred_fail = float(edge.get("inferred_failure_risk") or 0.0)
            hazard_risk = float(edge.get("hazard_risk") or 0.0)


            is_bridge = "BRIDGE" in edge_id.upper() or "BRIDGE" in edge.get("name", "").upper()

            if closed or accessibility < self.edge_accessibility_threshold or inferred_fail >= 0.70 or hazard_risk >= 0.85:
                ev_ref = evidence_registry.get(edge_id) or EvidenceReference(
                    type="road_edge",
                    id=edge_id,
                    evidence_type=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    severity=max(hazard_risk, 1.0 - accessibility, inferred_fail),
                )
                conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=max(hazard_risk, inferred_fail),
                    human_impact=0.60,
                    accessibility_risk=1.0 - accessibility,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                )
                prio_score = calculate_priority_score(urg_score, 0.50, inferred_fail, conf)

                action_type = ActionType.CLOSE_BRIDGE if is_bridge else ActionType.CLOSE_ROAD
                reason_detail = "physically closed" if closed else f"accessibility degraded ({accessibility:.2f} < {self.edge_accessibility_threshold:.2f})"
                candidates.append(ActionItem(
                    action_id=f"ACT-ROAD-{action_counter:03d}",
                    action=action_type,
                    target=edge_id,
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Infrastructure corridor {edge_id} is {reason_detail} with elevated failure risk ({inferred_fail:.2f}). Restrict public transit.",
                    evidence=[ev_ref],
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=False,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

        # ------------------------------------------------------------------
        # 5. Shelter Safety & Capacity Allocation Rules
        # ------------------------------------------------------------------
        for shelter in shelters:
            shelter_id = shelter.get("shelter_id", "SHELTER-UNKNOWN")
            is_safe = bool(shelter.get("safe", True))
            hazard_risk = float(shelter.get("hazard_risk", 0.0))
            capacity = int(shelter.get("capacity", 0))
            current_occupancy = int(shelter.get("current_occupancy", 0))
            avail = max(0, capacity - current_occupancy)

            ev_ref = evidence_registry.get(shelter_id) or EvidenceReference(
                type="shelter",
                id=shelter_id,
                evidence_type=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                severity=hazard_risk,
            )

            # Shelter is unsafe
            if not is_safe or hazard_risk >= 0.60:
                conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=hazard_risk,
                    human_impact=0.70,
                    accessibility_risk=0.50,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                )
                prio_score = calculate_priority_score(urg_score, 0.70, 0.60, conf)

                candidates.append(ActionItem(
                    action_id=f"ACT-SHELTER-{action_counter:03d}",
                    action=ActionType.REDIRECT_EVACUATION,
                    target=shelter_id,
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Shelter {shelter_id} compromised by local hazard exposure (risk {hazard_risk:.2f}). DO NOT allocate evacuees to this facility.",
                    evidence=[ev_ref],
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=True,
                    review_reason="Compromised shelter facility requires emergency decontamination or alternative site activation.",
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

            # Shelter capacity deficit / near full
            elif avail < 100:
                conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
                urg_score, urg_lvl = calculate_urgency(
                    hazard_severity=0.40,
                    human_impact=0.60,
                    accessibility_risk=0.30,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                )
                prio_score = calculate_priority_score(urg_score, 0.50, 0.30, conf)

                candidates.append(ActionItem(
                    action_id=f"ACT-SHELTER-{action_counter:03d}",
                    action=ActionType.OPEN_SHELTER,
                    target=shelter_id,
                    priority=1,
                    priority_score=prio_score,
                    urgency=urg_lvl,
                    urgency_score=urg_score,
                    confidence=conf,
                    reason=f"Shelter {shelter_id} is near exhaustion ({current_occupancy}/{capacity} occupied, {avail} remaining). Open auxiliary shelter.",
                    evidence=[ev_ref],
                    status=ActionStatus.RECOMMENDED,
                    requires_human_review=False,
                    temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                    simulated=is_simulated,
                ))
                action_counter += 1

        # ------------------------------------------------------------------
        # 6. Heat & Drought Hazard Rules
        # ------------------------------------------------------------------
        heat_hazard = next((h for h in hazards if h.get("hazard") == "heat" or h.get("hazard_type") == "heat"), None)
        if heat_hazard and float(heat_hazard.get("severity", 0.0)) >= 0.75:
            h_sev = float(heat_hazard.get("severity", 0.0))
            h_id = heat_hazard.get("hazard_id", "HAZ-HEAT")
            ev_ref = evidence_registry.get(h_id) or EvidenceReference(type="hazard", id=h_id, severity=h_sev)
            conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
            urg_score, urg_lvl = calculate_urgency(h_sev, 0.65, 0.20, EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED)
            prio_score = calculate_priority_score(urg_score, 0.60, 0.30, conf)

            candidates.append(ActionItem(
                action_id=f"ACT-HEAT-{action_counter:03d}",
                action=ActionType.PROTECT_CRITICAL_FACILITY,
                target="COOLING-CENTERS",
                priority=1,
                priority_score=prio_score,
                urgency=urg_lvl,
                urgency_score=urg_score,
                confidence=conf,
                reason=f"Extreme lethal heat conditions (severity {h_sev:.2f}). Activate municipal cooling centers and prioritize vulnerable elder care facilities.",
                evidence=[ev_ref],
                status=ActionStatus.RECOMMENDED,
                requires_human_review=False,
                temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                simulated=is_simulated,
            ))
            action_counter += 1

        drought_hazard = next((h for h in hazards if h.get("hazard") == "drought" or h.get("hazard_type") == "drought"), None)

        if drought_hazard and float(drought_hazard.get("severity", 0.0)) >= 0.75:
            d_sev = float(drought_hazard.get("severity", 0.0))
            d_id = drought_hazard.get("hazard_id", "HAZ-DROUGHT")
            ev_ref = evidence_registry.get(d_id) or EvidenceReference(type="hazard", id=d_id, severity=d_sev)
            conf, _ = calculate_action_confidence([ev_ref], is_stale, self.stale_confidence_penalty)
            urg_score, urg_lvl = calculate_urgency(d_sev, 0.50, 0.10, EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED)
            prio_score = calculate_priority_score(urg_score, 0.50, 0.20, conf)

            candidates.append(ActionItem(
                action_id=f"ACT-DROUGHT-{action_counter:03d}",
                action=ActionType.PREPOSITION_RESPONSE_RESOURCES,
                target="WATER-RESERVES",
                priority=1,
                priority_score=prio_score,
                urgency=urg_lvl,
                urgency_score=urg_score,
                confidence=conf,
                reason=f"Critical agricultural/soil drought deficit (severity {d_sev:.2f}). Deploy emergency water tankers and reservoir conservation directives.",
                evidence=[ev_ref],
                status=ActionStatus.RECOMMENDED,
                requires_human_review=False,
                temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                simulated=is_simulated,
            ))
            action_counter += 1

        # ------------------------------------------------------------------
        # 7. Normal Baseline Condition
        # ------------------------------------------------------------------
        if not candidates:
            candidates.append(ActionItem(
                action_id="ACT-MONITOR-001",
                action=ActionType.MAINTAIN_MONITORING,
                target="REGIONAL-OBSERVATION",
                priority=1,
                priority_score=0.10,
                urgency=UrgencyLevel.LOW,
                urgency_score=0.10,
                confidence=0.95,
                reason="Environmental parameters within nominal safety thresholds. Maintain regular telemetry polling.",
                evidence=[],
                status=ActionStatus.RECOMMENDED,
                requires_human_review=False,
                temporal_category=EvidenceType.SIMULATED if is_simulated else EvidenceType.OBSERVED,
                simulated=is_simulated,
            ))

        return candidates
