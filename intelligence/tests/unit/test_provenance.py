"""
Unit tests for data provenance tracking.
"""

from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.provenance.tracker import ProvenanceTracker


def test_fingerprint_determinism(normal_telemetry):
    hash1 = ProvenanceTracker.compute_record_hash(normal_telemetry)
    hash2 = ProvenanceTracker.compute_record_hash(normal_telemetry)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 length


def test_tamper_detection(normal_telemetry_dict):
    t1 = NormalizedTelemetry.model_validate(normal_telemetry_dict)
    original_hash = ProvenanceTracker.compute_record_hash(t1)

    # Tamper with temperature
    tampered_dict = dict(normal_telemetry_dict)
    tampered_dict["measurements"] = dict(tampered_dict["measurements"])
    tampered_dict["measurements"]["temperature"] = 35.0
    t2 = NormalizedTelemetry.model_validate(tampered_dict)
    tampered_hash = ProvenanceTracker.compute_record_hash(t2)

    assert original_hash != tampered_hash
    assert ProvenanceTracker.verify_fingerprint(t1, original_hash) is True
    assert ProvenanceTracker.verify_fingerprint(t2, original_hash) is False


def test_provenance_record_generation(normal_telemetry):
    record = ProvenanceTracker.generate_record(normal_telemetry, source_type="IOT_STATION")
    assert record.node_id == "STATION-HYD-001"
    assert record.source == "ESP32"
    assert record.source_type == "IOT_STATION"
    assert record.quality_valid is True
    assert len(record.record_hash) == 64
