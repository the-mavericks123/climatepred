"""Tests for Telemetry Packet Deduplication and Ingestion Idempotency."""
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

from intelligence.ingestion.deduplication import TelemetryDeduplicator


class TestTelemetryDeduplication:
    """Verifies that duplicate sensor telemetry packets are detected and rejected."""

    def test_first_packet_accepted(self):
        dedup = TelemetryDeduplicator()
        packet = {
            "node_id": "NODE-001",
            "timestamp": "2026-09-07T12:00:00Z",
            "readings": {"temperature_c": 28.5}
        }
        assert dedup.check_and_record(packet) is True

    def test_duplicate_packet_rejected(self):
        dedup = TelemetryDeduplicator()
        packet = {
            "node_id": "NODE-001",
            "timestamp": "2026-09-07T12:00:00Z",
            "readings": {"temperature_c": 28.5}
        }
        assert dedup.check_and_record(packet) is True
        assert dedup.check_and_record(packet) is False  # Duplicate

    def test_dedup_by_explicit_message_id(self):
        dedup = TelemetryDeduplicator()
        p1 = {"message_id": "MSG-999-XYZ", "data": 1}
        p2 = {"message_id": "MSG-999-XYZ", "data": 2}
        assert dedup.check_and_record(p1) is True
        assert dedup.check_and_record(p2) is False

    def test_dedup_by_explicit_packet_id(self):
        dedup = TelemetryDeduplicator()
        p1 = {"packet_id": "PKT-111", "data": "A"}
        p2 = {"packet_id": "PKT-111", "data": "B"}
        assert dedup.check_and_record(p1) is True
        assert dedup.check_and_record(p2) is False

    def test_different_sensor_readings_not_duplicate(self):
        dedup = TelemetryDeduplicator()
        p1 = {
            "node_id": "NODE-001",
            "timestamp": "2026-09-07T12:00:00Z",
            "readings": {"temperature_c": 28.5}
        }
        p2 = {
            "node_id": "NODE-001",
            "timestamp": "2026-09-07T12:00:00Z",
            "readings": {"temperature_c": 32.1}  # Different value
        }
        assert dedup.check_and_record(p1) is True
        assert dedup.check_and_record(p2) is True

    def test_capacity_eviction_policy(self):
        dedup = TelemetryDeduplicator(max_signatures=2)
        p1 = {"message_id": "ID-1"}
        p2 = {"message_id": "ID-2"}
        p3 = {"message_id": "ID-3"}

        assert dedup.check_and_record(p1) is True
        assert dedup.check_and_record(p2) is True
        assert dedup.check_and_record(p3) is True  # Evicts ID-1

        # ID-1 was evicted, so it can be re-recorded
        assert dedup.check_and_record(p1) is True
        # ID-2 was evicted when ID-1 re-entered
        assert dedup.check_and_record(p3) is False  # Still in cache

    def test_ttl_expiry(self):
        dedup = TelemetryDeduplicator(ttl_sec=0.05)
        p = {"message_id": "TTL-TEST"}
        assert dedup.check_and_record(p) is True
        assert dedup.check_and_record(p) is False

        time.sleep(0.06)
        assert dedup.check_and_record(p) is True  # Expired, accepted again

    def test_cache_clear(self):
        dedup = TelemetryDeduplicator()
        p = {"message_id": "ID-CLEAR"}
        assert dedup.check_and_record(p) is True
        dedup.clear()
        assert dedup.check_and_record(p) is True

    def test_thread_safety_under_concurrent_ingestion(self):
        dedup = TelemetryDeduplicator()
        packet = {"message_id": "CONCURRENT-ID"}

        def record():
            return dedup.check_and_record(packet)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: record(), range(20)))

        # Exactly one thread should succeed, all others flagged duplicate
        assert results.count(True) == 1
        assert results.count(False) == 19
