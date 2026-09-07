"""
Unit tests for Phase 9 Confidence Aggregation Engine.
Verifies multi-source confidence pooling, staleness discounting, missing evidence penalties,
and warning emission.
"""

from intelligence.response.confidence import (
    calculate_action_confidence,
    calculate_plan_overall_confidence,
)
from intelligence.response.types import EvidenceReference


def test_action_confidence_nominal():
    refs = [
        EvidenceReference(type="hazard", id="HAZ-1", confidence=0.90),
        EvidenceReference(type="vulnerability", id="ZONE-A", confidence=0.80),
    ]
    conf, warnings = calculate_action_confidence(refs, is_stale=False, missing_evidence=False)
    assert conf == 0.85
    assert len(warnings) == 0


def test_action_confidence_stale_penalty():
    refs = [EvidenceReference(type="hazard", id="HAZ-1", confidence=0.90)]
    conf, warnings = calculate_action_confidence(refs, is_stale=True, stale_penalty=0.35)
    expected = round(0.90 * (1.0 - 0.35), 4)
    assert conf == expected
    assert "STALE_DATA" in warnings


def test_action_confidence_missing_evidence_penalty():
    refs = [EvidenceReference(type="hazard", id="HAZ-1", confidence=0.90)]
    conf, warnings = calculate_action_confidence(refs, is_stale=False, missing_evidence=True, missing_penalty=0.25)
    expected = round(0.90 * (1.0 - 0.25), 4)
    assert conf == expected
    assert "MISSING_EVIDENCE" in warnings


def test_action_confidence_low_confidence_warning():
    refs = [EvidenceReference(type="hazard", id="HAZ-1", confidence=0.40)]
    conf, warnings = calculate_action_confidence(refs, is_stale=True, stale_penalty=0.35)
    assert conf < 0.50
    assert "LOW_CONFIDENCE" in warnings


def test_plan_overall_confidence():
    haz_confs = [0.95, 0.90]
    pred_confs = [0.85, 0.80]
    comp_confs = [0.90]
    vuln_confs = [0.88]
    evac_confs = [0.92]

    conf, warnings = calculate_plan_overall_confidence(
        haz_confs, pred_confs, comp_confs, vuln_confs, evac_confs, is_stale=False
    )
    assert 0.85 <= conf <= 0.95
    assert len(warnings) == 0


def test_plan_overall_confidence_stale():
    haz_confs = [0.90]
    pred_confs = [0.80]
    comp_confs = []
    vuln_confs = []
    evac_confs = []

    conf, warnings = calculate_plan_overall_confidence(
        haz_confs, pred_confs, comp_confs, vuln_confs, evac_confs, is_stale=True, stale_penalty=0.35
    )
    base_mean = 0.85
    expected = round(base_mean * (1.0 - 0.35), 4)
    assert conf == expected
    assert "STALE_DATA" in warnings
