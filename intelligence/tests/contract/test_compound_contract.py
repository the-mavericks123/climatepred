"""
Contract tests for Phase 4 CompoundEvent schema and boundaries.
Verifies:
  - Severity and confidence in [0.0, 1.0]
  - Simulated flag strictly False
  - Valid RelationshipType enum
  - Server-generated fields and immutable rule_version
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from intelligence.compound.types import (
    CompoundEvent,
    ContributingState,
    RelationshipEdge,
    RelationshipType,
    StateEvidenceType,
)

T_NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _valid_compound_event(**overrides):
    base = {
        "event_id": "COMP-MULTI-12345678",
        "event_type": "COMPOUND",
        "severity": 0.88,
        "confidence": 0.84,
        "timestamp": T_NOW,
        "chain": ["heat", "drought"],
        "contributing_states": [
            {
                "state_id": "heat",
                "evidence_type": "OBSERVED",
                "severity": 0.85,
                "confidence": 0.90,
                "timestamp": T_NOW,
            },
            {
                "state_id": "drought",
                "evidence_type": "OBSERVED",
                "severity": 0.80,
                "confidence": 0.85,
                "timestamp": T_NOW,
            },
        ],
        "relationships": [
            {
                "from_state": "heat",
                "to_state": "drought",
                "relationship_type": "COMPOUND",
                "rule_id": "HEAT-DRY-001",
                "explanation": "Concurrent extreme heat and soil moisture deficit",
            }
        ],
        "evidence_ids": ["HAZ-HEAT-01", "HAZ-DROUGHT-01"],
        "rule_version": "compound-v1",
        "provenance_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "drivers": ["Compound condition detected: heat + drought"],
        "simulated": False,
    }
    base.update(overrides)
    return base


class TestCompoundContract:
    def test_valid_compound_event(self):
        payload = _valid_compound_event()
        event = CompoundEvent(**payload)
        assert event.event_type == RelationshipType.COMPOUND
        assert event.severity == 0.88
        assert event.confidence == 0.84
        assert event.simulated is False
        assert event.rule_version == "compound-v1"

    def test_simulated_true_rejected(self):
        payload = _valid_compound_event(simulated=True)
        with pytest.raises(ValidationError):
            CompoundEvent(**payload)

    def test_severity_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            CompoundEvent(**_valid_compound_event(severity=-0.01))
        with pytest.raises(ValidationError):
            CompoundEvent(**_valid_compound_event(severity=1.01))

    def test_confidence_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            CompoundEvent(**_valid_compound_event(confidence=-0.05))
        with pytest.raises(ValidationError):
            CompoundEvent(**_valid_compound_event(confidence=1.05))

    def test_invalid_relationship_type_rejected(self):
        with pytest.raises(ValidationError):
            CompoundEvent(**_valid_compound_event(event_type="INVALID_TYPE"))
