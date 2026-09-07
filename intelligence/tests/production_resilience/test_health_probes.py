"""Tests for Health, Liveness, Readiness, and Observability Endpoints."""
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.app.dependencies import get_source_registry
from intelligence.ingestion.source_registry import SourceRegistry


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthProbes:
    """Verifies orchestration health probes (liveness, readiness, metrics)."""

    def test_health_check_endpoint(self, client):
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "climate-intelligence"
        assert "version" in data
        assert "timestamp" in data

    def test_legacy_health_alias(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

    def test_liveness_probe(self, client):
        res = client.get("/api/v1/health/live")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ALIVE"
        assert data["live"] is True

    def test_readiness_probe_with_sources(self, client):
        res = client.get("/api/v1/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "READY"
        assert data["ready"] is True
        assert data["registered_sources_count"] >= 1

    def test_readiness_probe_fails_when_no_sources(self, client):
        empty_registry = SourceRegistry()
        empty_registry._sources.clear()
        app.dependency_overrides[get_source_registry] = lambda: empty_registry
        try:
            res = client.get("/api/v1/health/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "UNAVAILABLE"
            assert data["ready"] is False
        finally:
            app.dependency_overrides.clear()

    def test_liveness_survives_readiness_failure(self, client):
        # Even if readiness is degraded, liveness must return 200 ALIVE
        empty_registry = SourceRegistry()
        empty_registry._sources.clear()
        app.dependency_overrides[get_source_registry] = lambda: empty_registry
        try:
            res_live = client.get("/api/v1/health/live")
            assert res_live.status_code == 200
            assert res_live.json()["live"] is True
        finally:
            app.dependency_overrides.clear()

    def test_metrics_endpoint(self, client):
        res = client.get("/api/v1/metrics")
        assert res.status_code == 200
        data = res.json()
        assert "requests" in data
        assert "errors" in data
        assert "mqtt" in data
        assert "latencies_ms" in data
