"""
Unit tests for Phase 4: Compound & Cascading Disaster Engine.
Tests:
  - Rule evaluation and matching
  - Cascade DAG construction, cycle rejection, and chain discovery
  - Severity calculation and interaction amplification
  - Multi-factor confidence calculation
  - Deterministic provenance sensitivity to contributors and rules
  - Deduplication control
"""

from datetime import datetime, timezone, timedelta
import pytest

from intelligence.compound.types import (
    ContributingState,
    RelationshipEdge,
    RelationshipType,
    StateEvidenceType,
)
from intelligence.compound.graph import CascadeGraph
from intelligence.compound.rules import DEFAULT_COMPOUND_CONFIG, CompoundRuleConfig
from intelligence.compound.confidence import CompoundConfidenceCalculator
from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.hazards.types import HazardClassification, HazardResult, HazardStatus, HazardType
from intelligence.prediction.types import PredictionResult
from intelligence.core.contracts.telemetry import LocationCoordinate

T_NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
LOC = LocationCoordinate(lat=25.5941, lon=85.1376)


def _make_hazard(hazard: HazardType, severity: float, conf: float = 0.90, dt_min: int = 0, feats: dict = None) -> HazardResult:
    return HazardResult(
        hazard_id=f"HAZ-{hazard.value.upper()}-{int(severity*100)}",
        hazard=hazard,
        severity=severity,
        confidence=conf,
        classification=HazardClassification.HIGH if severity >= 0.70 else HazardClassification.MODERATE,
        status=HazardStatus.DETECTED,
        timestamp=T_NOW + timedelta(minutes=dt_min),
        forecast_horizon_minutes=0,
        location=LOC,
        features=feats or {},
        drivers=[f"Active {hazard.value} hazard"],
        model_version=f"{hazard.value}-v1",
        simulated=False,
        provenance_hash=f"prov-{hazard.value}-{int(severity*100)}",
    )


class TestCascadeGraph:
    def test_add_edge_and_find_chain(self):
        graph = CascadeGraph(max_depth=5)
        e1 = RelationshipEdge(
            from_state="rain",
            to_state="soil_sat",
            relationship_type=RelationshipType.CASCADE,
            rule_id="R1",
            explanation="rain saturates soil",
        )
        e2 = RelationshipEdge(
            from_state="soil_sat",
            to_state="flood",
            relationship_type=RelationshipType.CASCADE,
            rule_id="R2",
            explanation="soil saturation causes flood",
        )
        assert graph.add_edge(e1) is True
        assert graph.add_edge(e2) is True

        chains = graph.find_all_chains()
        assert ["rain", "soil_sat", "flood"] in chains

    def test_cycle_rejection_prevents_infinite_recursion(self):
        graph = CascadeGraph(max_depth=5)
        e1 = RelationshipEdge(from_state="A", to_state="B", relationship_type=RelationshipType.CASCADE, rule_id="R1", explanation="A->B")
        e2 = RelationshipEdge(from_state="B", to_state="C", relationship_type=RelationshipType.CASCADE, rule_id="R2", explanation="B->C")
        e3_cycle = RelationshipEdge(from_state="C", to_state="A", relationship_type=RelationshipType.CASCADE, rule_id="R3", explanation="C->A (cycle)")

        assert graph.add_edge(e1) is True
        assert graph.add_edge(e2) is True
        # Adding edge C->A would form a cycle (A -> B -> C -> A)
        assert graph.add_edge(e3_cycle) is False


class TestCompoundEngineUnit:
    def test_no_hazards_produces_no_events(self):
        engine = CompoundDisasterEngine()
        events = engine.evaluate(hazards=[], predictions=[])
        assert events == []

    def test_sub_threshold_hazard_produces_no_events(self):
        engine = CompoundDisasterEngine()
        # Severity below min_activation_severity (0.35)
        h1 = _make_hazard(HazardType.HEAT, severity=0.20)
        h2 = _make_hazard(HazardType.DROUGHT, severity=0.25)
        events = engine.evaluate(hazards=[h1, h2])
        assert events == []

    def test_heat_and_drought_compound_detection(self):
        engine = CompoundDisasterEngine()
        h_heat = _make_hazard(HazardType.HEAT, severity=0.75, conf=0.90)
        h_drought = _make_hazard(HazardType.DROUGHT, severity=0.80, conf=0.88)

        events = engine.evaluate(hazards=[h_heat, h_drought])
        assert len(events) >= 1

        compound_ev = next(e for e in events if e.event_type == RelationshipType.COMPOUND)
        assert "heat" in compound_ev.chain
        assert "drought" in compound_ev.chain
        # Base severity = (0.75 + 0.80)/2 = 0.775 + 0.15 compound bonus = 0.925
        assert compound_ev.severity >= 0.85
        assert 0.0 <= compound_ev.confidence <= 1.0
        assert compound_ev.simulated is False

    def test_cascade_flood_to_road_and_access_loss(self):
        engine = CompoundDisasterEngine()
        h_flood = _make_hazard(HazardType.FLOOD, severity=0.85, feats={"water_level": 12.0, "rainfall": 75.0})

        events = engine.evaluate(hazards=[h_flood])
        cascade_events = [e for e in events if e.event_type == RelationshipType.CASCADE]
        assert len(cascade_events) >= 1

        chain = cascade_events[0].chain
        assert "flood" in chain
        assert "inferred_road_failure_risk" in chain
        assert "inferred_access_loss" in chain

    def test_temporal_window_rejection_unrelated_timestamps(self):
        engine = CompoundDisasterEngine(config=CompoundRuleConfig(relationship_window_minutes=60.0))
        # Heat at T, Drought at T + 3 hours (180 minutes apart > 60m window)
        h_heat = _make_hazard(HazardType.HEAT, severity=0.80, dt_min=0)
        h_drought = _make_hazard(HazardType.DROUGHT, severity=0.80, dt_min=180)

        events = engine.evaluate(hazards=[h_heat, h_drought])
        # Should not match compound rule due to temporal distance
        compound_events = [e for e in events if "heat" in e.chain and "drought" in e.chain]
        assert len(compound_events) == 0

    def test_provenance_sensitivity_to_contributor_severity(self):
        engine = CompoundDisasterEngine()
        h_heat_1 = _make_hazard(HazardType.HEAT, severity=0.70)
        h_heat_2 = _make_hazard(HazardType.HEAT, severity=0.85)
        h_drought = _make_hazard(HazardType.DROUGHT, severity=0.75)

        events_1 = engine.evaluate(hazards=[h_heat_1, h_drought])
        events_2 = engine.evaluate(hazards=[h_heat_2, h_drought])

        assert events_1[0].provenance_hash != events_2[0].provenance_hash
        assert events_1[0].severity != events_2[0].severity
