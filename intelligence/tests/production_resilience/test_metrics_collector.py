"""Tests for Operational Metrics Collection and Reporting."""
import pytest
from intelligence.core.metrics.collector import MetricsCollector


class TestMetricsCollector:
    """Verifies operational telemetry tracking and latency distribution calculations."""

    def test_request_and_error_counting(self):
        m = MetricsCollector()
        m.record_request("/api/v1/health", 200, 0.005)
        m.record_request("/api/v1/health", 200, 0.006)
        m.record_request("/api/v1/hazards/evaluate", 500, 0.050)

        snapshot = m.get_snapshot()
        assert snapshot["requests"]["total"] == 3
        assert snapshot["requests"]["by_endpoint_and_status"]["/api/v1/health:200"] == 2
        assert snapshot["requests"]["by_endpoint_and_status"]["/api/v1/hazards/evaluate:500"] == 1
        assert snapshot["errors"]["total"] == 1
        assert snapshot["errors"]["by_type"]["500"] == 1

    def test_mqtt_metrics(self):
        m = MetricsCollector()
        m.record_mqtt_received(10)
        m.record_mqtt_rejected(2)
        m.set_stale_nodes(3)

        snapshot = m.get_snapshot()
        assert snapshot["mqtt"]["received"] == 10
        assert snapshot["mqtt"]["rejected"] == 2
        assert snapshot["mqtt"]["stale_nodes"] == 3

    def test_latency_distribution_statistics(self):
        m = MetricsCollector()
        for i in range(1, 101):
            m.record_simulation_duration(i / 1000.0)  # 1ms to 100ms

        snapshot = m.get_snapshot()
        sim_stats = snapshot["latencies_ms"]["simulation"]
        assert sim_stats["count"] == 100
        assert sim_stats["max_ms"] == 100.0
        assert 90.0 <= sim_stats["p95_ms"] <= 96.0

    def test_domain_latencies_tracking(self):
        m = MetricsCollector()
        m.record_database_latency(0.012)
        m.record_intelligence_latency(0.025)
        m.record_evaluation_duration(0.080)
        m.record_calibration_duration(0.045)

        snapshot = m.get_snapshot()
        assert snapshot["latencies_ms"]["database"]["count"] == 1
        assert snapshot["latencies_ms"]["intelligence"]["count"] == 1
        assert snapshot["latencies_ms"]["evaluation"]["count"] == 1
        assert snapshot["latencies_ms"]["calibration"]["count"] == 1

    def test_reset_functionality(self):
        m = MetricsCollector()
        m.record_request("/api/v1/health", 200, 0.01)
        m.record_mqtt_received(5)
        m.reset()

        snapshot = m.get_snapshot()
        assert snapshot["requests"]["total"] == 0
        assert snapshot["mqtt"]["received"] == 0
        assert snapshot["latencies_ms"]["database"]["count"] == 0
