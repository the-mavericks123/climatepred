"""
Evaluation tests for S2 telemetry quality gates and confidence calibration.
"""

from datetime import datetime, timezone, timedelta
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.ingestion.normalized_adapter import NormalizedAdapter
from intelligence.ingestion.source_registry import SourceRegistry


def test_quality_gate_preserves_anomaly_flags(critical_flood_telemetry_dict):
    adapter = NormalizedAdapter()
    telemetry = adapter.adapt(critical_flood_telemetry_dict)
    assert telemetry.quality.valid is True
    assert "CRITICAL_FLOOD_STAGE" in telemetry.quality.flags
    assert telemetry.quality.anomaly_score == 0.85


def test_adapter_assigns_missing_received_at():
    adapter = NormalizedAdapter()
    raw_packet = {
        "schema_version": "1.0",
        "node_id": "TEST-AUTO-RECV-01",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": 12.0, "lon": 77.0},
        "measurements": {"temperature": 25.0},
        "quality": {"valid": True, "source": "ESP32"},
    }
    telemetry = adapter.adapt(raw_packet)
    assert telemetry.quality.received_at is not None
    assert isinstance(telemetry.quality.received_at, datetime)
