"""
Main engine for Phase 4: Compound & Cascading Disaster Intelligence.
Coordinates state extraction, deterministic rule matching, DAG construction,
cycle-safe chain traversal, severity & confidence calculation, and provenance generation.
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.compound.confidence import CompoundConfidenceCalculator
from intelligence.compound.features import StateFeatureExtractor
from intelligence.compound.graph import CascadeGraph
from intelligence.compound.rules import (
    CANONICAL_RULES,
    DEFAULT_COMPOUND_CONFIG,
    CompoundRuleConfig,
)
from intelligence.compound.types import (
    CompoundEvent,
    ContributingState,
    RelationshipEdge,
    RelationshipType,
    StateEvidenceType,
)
from intelligence.core.logging import get_logger
from intelligence.hazards.types import HazardResult
from intelligence.prediction.types import PredictionResult

logger = get_logger(__name__)


class CompoundDisasterEngine:
    """
    Deterministic rule- and graph-based engine detecting compound hazards,
    cascading disaster chains, and infrastructure consequences.
    """

    def __init__(self, config: CompoundRuleConfig = DEFAULT_COMPOUND_CONFIG):
        self.config = config
        self.rules = CANONICAL_RULES
        self._latest_events: List[CompoundEvent] = []

    def get_latest_events(self) -> List[CompoundEvent]:
        """Returns the most recent compound evaluation events."""
        return list(self._latest_events)

    def evaluate(
        self,
        hazards: Optional[List[HazardResult]] = None,
        predictions: Optional[List[PredictionResult]] = None,
        environmental_states: Optional[List[Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> List[CompoundEvent]:
        """
        Evaluates active observed hazards and predictions against deterministic compound & cascade rules.
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        # 1. Extract and normalize all candidate states
        active_states: Dict[str, ContributingState] = {}

        # From observed Phase 2 HazardResults
        if hazards:
            for h in hazards:
                state = StateFeatureExtractor.from_hazard_result(h)
                if state:
                    active_states[state.state_id] = state
                    # Derive physical sub-states (e.g. soil_saturation from soil_moisture)
                    for sub in StateFeatureExtractor.extract_environmental_substates(state):
                        if sub.state_id not in active_states:
                            active_states[sub.state_id] = sub

        # From predicted Phase 3 PredictionResults
        if predictions:
            for p in predictions:
                state = StateFeatureExtractor.from_prediction_result(p)
                if state:
                    # If an observed state already exists, keep both or index distinctly
                    key = f"pred_{state.state_id}_{p.forecast_horizon_minutes}m"
                    active_states[key] = state
                    # Also map to generic state_id if no observed equivalent exists
                    if state.state_id not in active_states:
                        active_states[state.state_id] = state
                    for sub in StateFeatureExtractor.extract_environmental_substates(state):
                        if sub.state_id not in active_states:
                            active_states[sub.state_id] = sub

        # From explicit environmental states
        if environmental_states:
            for raw in environmental_states:
                state = StateFeatureExtractor.from_raw_dict(raw, eval_time_utc)
                if state:
                    active_states[state.state_id] = state

        if not active_states:
            return []

        # 2. Build CascadeGraph and evaluate deterministic rules
        graph = CascadeGraph(max_depth=self.config.max_cascade_depth)
        for s in active_states.values():
            graph.add_node(s)

        matched_edges: List[RelationshipEdge] = []
        triggered_rules: Set[str] = set()

        for rule in self.rules:
            req_sources = rule["source_states"]
            req_ev_type = rule.get("required_evidence_type")
            # Check if all required source states exist and meet minimum severity
            present_sources = [
                active_states[src] for src in req_sources if src in active_states
            ]
            if len(present_sources) == len(req_sources):
                # Verify evidence type if required by rule
                if req_ev_type and any(s.evidence_type != req_ev_type for s in present_sources):
                    continue
                # Verify minimum severity
                if all(s.severity >= self.config.min_activation_severity for s in present_sources):
                    # Verify temporal alignment
                    ts_list = [s.timestamp for s in present_sources]
                    max_ts = max(ts_list)
                    min_ts = min(ts_list)
                    time_span_min = (max_ts - min_ts).total_seconds() / 60.0

                    if time_span_min <= self.config.relationship_window_minutes:
                        target_state_id = rule["target_state"]
                        # If target state is not already in graph, synthesize it as INFERRED
                        if target_state_id not in active_states:
                            avg_sev = sum(s.severity for s in present_sources) / len(present_sources)
                            avg_conf = sum(s.confidence for s in present_sources) / len(present_sources)
                            inferred_state = ContributingState(
                                state_id=target_state_id,
                                evidence_type=StateEvidenceType.INFERRED,
                                severity=round(min(1.0, avg_sev + rule["amplification"]), 4),
                                confidence=round(avg_conf * 0.90, 4),
                                timestamp=max_ts,
                                forecast_horizon_minutes=max(s.forecast_horizon_minutes for s in present_sources),
                                source_ref_id=f"INFER-{rule['rule_id']}",
                                metadata={"inferred_by_rule": rule["rule_id"]},
                            )
                            active_states[target_state_id] = inferred_state
                            graph.add_node(inferred_state)

                        # Create relationship edges from all sources to target
                        for src_state in present_sources:
                            edge = RelationshipEdge(
                                from_state=src_state.state_id,
                                to_state=target_state_id,
                                relationship_type=rule["relationship_type"],
                                rule_id=rule["rule_id"],
                                explanation=rule["explanation"],
                                weight=1.0 + rule["amplification"],
                            )
                            if graph.add_edge(edge):
                                matched_edges.append(edge)
                                triggered_rules.add(rule["rule_id"])

        # 3. Discover compound and cascade events
        discovered_events: List[CompoundEvent] = []
        emitted_signatures: Set[str] = set()

        # A. Discover cascading paths from graph
        chains = graph.find_all_chains()
        for chain in chains:
            event = self._build_event_from_chain(
                chain=chain,
                active_states=active_states,
                matched_edges=matched_edges,
                eval_time=eval_time_utc,
            )
            if event:
                sig = ":".join(event.chain)
                if sig not in emitted_signatures:
                    emitted_signatures.add(sig)
                    discovered_events.append(event)

        # B. Discover direct multi-hazard compound combinations (e.g. heat + drought)
        compound_rules = [r for r in self.rules if r["relationship_type"] == RelationshipType.COMPOUND]
        for rule in compound_rules:
            req_sources = rule["source_states"]
            present = [active_states[src] for src in req_sources if src in active_states]
            if len(present) == len(req_sources) and all(s.severity >= self.config.min_activation_severity for s in present):
                # Verify temporal window between sources
                ts_list = [s.timestamp for s in present]
                time_span_min = (max(ts_list) - min(ts_list)).total_seconds() / 60.0
                if time_span_min > self.config.relationship_window_minutes:
                    continue

                sig = ":".join(sorted(req_sources))
                if sig not in emitted_signatures:
                    emitted_signatures.add(sig)
                    event = self._build_direct_compound_event(
                        rule=rule,
                        present_states=present,
                        eval_time=eval_time_utc,
                    )
                    if event:
                        discovered_events.append(event)

        # Sort events deterministically by descending severity
        discovered_events.sort(key=lambda e: (-e.severity, -e.confidence, e.event_id))
        self._latest_events = discovered_events
        return discovered_events

    def _build_event_from_chain(
        self,
        chain: List[str],
        active_states: Dict[str, ContributingState],
        matched_edges: List[RelationshipEdge],
        eval_time: datetime,
    ) -> Optional[CompoundEvent]:
        """Constructs a validated CompoundEvent from a discovered graph chain."""
        chain_states = [active_states[s] for s in chain if s in active_states]
        if len(chain_states) < 2:
            return None

        # Filter edges belonging to this chain
        chain_pairs = set(zip(chain[:-1], chain[1:]))
        chain_edges = [
            e for e in matched_edges if (e.from_state, e.to_state) in chain_pairs
        ]

        # Calculate bounded severity: weighted combination + cascade amplification
        base_severity = sum(s.severity for s in chain_states) / len(chain_states)
        amplification_bonus = (len(chain_states) - 1) * self.config.cascade_amplification_factor
        final_severity = round(min(1.0, base_severity + amplification_bonus), 4)

        # Calculate time span
        ts_list = [s.timestamp for s in chain_states]
        time_span = (max(ts_list) - min(ts_list)).total_seconds() / 60.0

        confidence = CompoundConfidenceCalculator.compute_event_confidence(
            states=chain_states,
            edges=chain_edges,
            time_span_minutes=time_span,
            max_window_minutes=self.config.relationship_window_minutes,
        )

        # Collect evidence IDs
        evidence_ids = [s.source_ref_id for s in chain_states if s.source_ref_id]

        # Formulate drivers
        drivers = [
            f"Cascading chain detected ({len(chain)} stages): {' -> '.join(chain)}",
            f"Base contributor severity: {base_severity:.3f} with +{amplification_bonus:.2f} cascade amplification",
        ]
        for e in chain_edges:
            drivers.append(f"Link [{e.from_state} -> {e.to_state}]: {e.explanation} (Rule: {e.rule_id})")

        provenance_hash = self._compute_event_provenance(
            chain=chain,
            states=chain_states,
            edges=chain_edges,
            rule_version=self.config.rule_version,
        )

        return CompoundEvent(
            event_id=f"COMP-CASCADE-{provenance_hash[:8].upper()}",
            event_type=RelationshipType.CASCADE,
            severity=final_severity,
            confidence=confidence,
            timestamp=eval_time,
            chain=chain,
            contributing_states=chain_states,
            relationships=chain_edges,
            evidence_ids=evidence_ids,
            rule_version=self.config.rule_version,
            provenance_hash=provenance_hash,
            drivers=drivers,
            simulated=False,
        )

    def _build_direct_compound_event(
        self,
        rule: Dict[str, Any],
        present_states: List[ContributingState],
        eval_time: datetime,
    ) -> CompoundEvent:
        """Constructs a compound hazard event from interacting co-occurring hazards."""
        chain = sorted([s.state_id for s in present_states])
        base_sev = sum(s.severity for s in present_states) / len(present_states)
        final_sev = round(min(1.0, base_sev + self.config.compound_interaction_bonus), 4)

        ts_list = [s.timestamp for s in present_states]
        time_span = (max(ts_list) - min(ts_list)).total_seconds() / 60.0

        rel_edge = RelationshipEdge(
            from_state=chain[0],
            to_state=chain[1] if len(chain) > 1 else chain[0],
            relationship_type=RelationshipType.COMPOUND,
            rule_id=rule["rule_id"],
            explanation=rule["explanation"],
            weight=1.0 + rule["amplification"],
        )

        confidence = CompoundConfidenceCalculator.compute_event_confidence(
            states=present_states,
            edges=[rel_edge],
            time_span_minutes=time_span,
            max_window_minutes=self.config.relationship_window_minutes,
        )

        evidence_ids = [s.source_ref_id for s in present_states if s.source_ref_id]

        drivers = [
            f"Compound hazard condition detected: {' + '.join(chain)}",
            f"Interaction: {rule['explanation']} (Rule: {rule['rule_id']})",
            f"Mean severity {base_sev:.3f} amplified by +{self.config.compound_interaction_bonus:.2f} compound interaction",
        ]

        provenance_hash = self._compute_event_provenance(
            chain=chain,
            states=present_states,
            edges=[rel_edge],
            rule_version=self.config.rule_version,
        )

        return CompoundEvent(
            event_id=f"COMP-MULTI-{provenance_hash[:8].upper()}",
            event_type=RelationshipType.COMPOUND,
            severity=final_sev,
            confidence=confidence,
            timestamp=eval_time,
            chain=chain,
            contributing_states=present_states,
            relationships=[rel_edge],
            evidence_ids=evidence_ids,
            rule_version=self.config.rule_version,
            provenance_hash=provenance_hash,
            drivers=drivers,
            simulated=False,
        )

    def _compute_event_provenance(
        self,
        chain: List[str],
        states: List[ContributingState],
        edges: List[RelationshipEdge],
        rule_version: str,
    ) -> str:
        """Computes deterministic SHA-256 fingerprint tracing all contributing states, values, and rules."""
        # Canonical state fingerprints
        state_tokens = []
        for s in sorted(states, key=lambda x: x.state_id):
            state_tokens.append(f"{s.state_id}:{s.evidence_type.value}:{s.severity:.4f}:{s.confidence:.4f}:{s.provenance_hash or 'NO_HASH'}")

        # Canonical edge tokens
        edge_tokens = []
        for e in sorted(edges, key=lambda x: (x.from_state, x.to_state, x.rule_id)):
            edge_tokens.append(f"{e.from_state}->{e.to_state}:{e.rule_id}:{e.relationship_type.value}")

        payload = {
            "chain": chain,
            "rule_version": rule_version,
            "states": state_tokens,
            "edges": edge_tokens,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
