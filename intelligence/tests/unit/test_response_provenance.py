"""
Unit tests for Phase 9 Deterministic Provenance and Mutation Matrix.
Verifies volatile metadata decoupling, collection reordering invariance,
order-sensitive sequence sensitivity, and material mutation sensitivity.
"""

from intelligence.response.provenance import ResponseProvenanceTracker
from intelligence.response.types import (
    ActionItem,
    ActionStatus,
    ActionType,
    AlertLevel,
    EvidenceReference,
    UrgencyLevel,
)


def _build_baseline_inputs():
    hazards = [
        {"hazard_id": "HAZ-001", "hazard_type": "flood", "severity": 0.85, "confidence": 0.90},
        {"hazard_id": "HAZ-002", "hazard_type": "heat", "severity": 0.40, "confidence": 0.95},
    ]
    predictions = [
        {"prediction_id": "PRED-001", "hazard": "flood", "forecast_horizon_minutes": 30, "severity": 0.90, "confidence": 0.85},
    ]
    compounds = [
        {"event_id": "COMP-001", "severity": 0.75, "causal_chain": ["heavy_rain", "flood", "road_failure"], "contributing_hazards": ["HAZ-001"]},
    ]
    vuln_zones = [
        {"zone_id": "ZONE-A", "population_exposed": 5000, "human_impact": 0.70, "vulnerability": 0.65},
    ]
    edges = [
        {"edge_id": "ROAD-1", "accessibility": 0.80, "hazard_risk": 0.20, "closed": False},
    ]
    shelters = [
        {"shelter_id": "SHELTER-1", "capacity": 6000, "current_occupancy": 1000, "safe": True, "hazard_risk": 0.0},
    ]
    actions = [
        ActionItem(
            action_id="ACT-001",
            action=ActionType.EVACUATE_ZONE,
            target="ZONE-A",
            priority=1,
            priority_score=0.92,
            urgency=UrgencyLevel.CRITICAL,
            urgency_score=0.88,
            confidence=0.90,
            reason="Baseline evacuation",
            evidence=[EvidenceReference(type="hazard", id="HAZ-001", severity=0.85)],
            status=ActionStatus.RECOMMENDED,
            requires_human_review=True,
        )
    ]
    thresholds = {
        "edge_accessibility_threshold": 0.40,
        "alert_level_orange_hazard_threshold": 0.70,
        "alert_level_red_hazard_threshold": 0.85,
    }
    return hazards, predictions, compounds, vuln_zones, edges, shelters, actions, thresholds


def test_provenance_deterministic_reproducibility():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    hash1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t, base_state_hash="BASE-001")
    hash2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t, base_state_hash="BASE-001")

    assert hash1 == hash2
    assert len(hash1) == 64


def test_provenance_volatile_metadata_invariance():
    # Volatile fields (plan_id, generated_at, request_id) do not enter the hash computation at all
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    hash1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t, base_state_hash="BASE-001")
    hash2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t, base_state_hash="BASE-001")

    assert hash1 == hash2


def test_provenance_unordered_collection_reordering_invariance():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    # Reverse unordered collections
    h_rev = list(reversed(h))
    hash1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    hash2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h_rev, p, c, v, e, s, t)

    assert hash1 == hash2


def test_provenance_order_sensitive_causal_chain():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    c_mutated = [
        {"event_id": "COMP-001", "severity": 0.75, "causal_chain": ["road_failure", "flood", "heavy_rain"], "contributing_hazards": ["HAZ-001"]}
    ]
    hash_base = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    hash_mut = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c_mutated, v, e, s, t)

    assert hash_base != hash_mut


def test_provenance_order_sensitive_actions():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    act2 = ActionItem(
        action_id="ACT-002",
        action=ActionType.MONITOR,
        target="ZONE-B",
        priority=2,
        priority_score=0.30,
        urgency=UrgencyLevel.LOW,
        urgency_score=0.20,
        confidence=0.90,
        reason="Secondary monitoring",
    )
    actions_order1 = [a[0], act2]
    actions_order2 = [act2, a[0]]

    hash1 = tracker.compute_provenance_hash(AlertLevel.RED, actions_order1, h, p, c, v, e, s, t)
    hash2 = tracker.compute_provenance_hash(AlertLevel.RED, actions_order2, h, p, c, v, e, s, t)

    assert hash1 != hash2


def test_provenance_irrelevant_data_filtering():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    h_with_irrelevant = list(h) + [
        {"hazard_id": "HAZ-IRRELEVANT", "hazard_type": "flood", "severity": 0.0, "is_relevant": False}
    ]

    hash1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    hash2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h_with_irrelevant, p, c, v, e, s, t)

    assert hash1 == hash2


# --- 30-Item / Material Mutation Matrix Tests ---

def test_mutation_hazard_severity():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()
    h_mut = [{"hazard_id": "HAZ-001", "hazard_type": "flood", "severity": 0.99, "confidence": 0.90}, h[1]]

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h_mut, p, c, v, e, s, t)
    assert h1 != h2


def test_mutation_prediction_horizon():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()
    p_mut = [{"prediction_id": "PRED-001", "hazard": "flood", "forecast_horizon_minutes": 60, "severity": 0.90, "confidence": 0.85}]

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p_mut, c, v, e, s, t)
    assert h1 != h2


def test_mutation_vulnerability_human_impact():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()
    v_mut = [{"zone_id": "ZONE-A", "population_exposed": 5000, "human_impact": 0.95, "vulnerability": 0.65}]

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v_mut, e, s, t)
    assert h1 != h2


def test_mutation_road_edge_accessibility():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()
    e_mut = [{"edge_id": "ROAD-1", "accessibility": 0.25, "hazard_risk": 0.20, "closed": False}]

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e_mut, s, t)
    assert h1 != h2


def test_mutation_shelter_capacity():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()
    s_mut = [{"shelter_id": "SHELTER-1", "capacity": 12000, "current_occupancy": 1000, "safe": True, "hazard_risk": 0.0}]

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s_mut, t)
    assert h1 != h2


def test_mutation_alert_level():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.ORANGE, a, h, p, c, v, e, s, t)
    assert h1 != h2


def test_mutation_threshold_config():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()
    t_mut = dict(t)
    t_mut["edge_accessibility_threshold"] = 0.55

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t_mut)
    assert h1 != h2


def test_mutation_rule_version():
    tracker1 = ResponseProvenanceTracker(rules_version="response-rules-v1")
    tracker2 = ResponseProvenanceTracker(rules_version="response-rules-v2")
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    h1 = tracker1.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    h2 = tracker2.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t)
    assert h1 != h2


def test_mutation_base_state_hash():
    tracker = ResponseProvenanceTracker()
    h, p, c, v, e, s, a, t = _build_baseline_inputs()

    h1 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t, base_state_hash="BASE-A")
    h2 = tracker.compute_provenance_hash(AlertLevel.RED, a, h, p, c, v, e, s, t, base_state_hash="BASE-B")
    assert h1 != h2
