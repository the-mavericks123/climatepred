"""Tests for Security Headers, Correlation Tracking, and Payload Limits."""
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app
from intelligence.app.config import settings


@pytest.fixture
def client():
    return TestClient(app)


class TestSecurityHeaders:
    """Verifies injection of defensive HTTP headers across all endpoints."""

    def test_baseline_security_headers_present(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in response.headers.get("Content-Security-Policy", "")

    def test_hsts_header_in_production(self, client, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        response = client.get("/api/v1/health")
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]

    def test_hsts_omitted_in_development(self, client, monkeypatch):
        monkeypatch.setattr(settings, "environment", "development")
        response = client.get("/api/v1/health")
        assert "Strict-Transport-Security" not in response.headers


class TestRequestCorrelation:
    """Verifies end-to-end request correlation propagation."""

    def test_preserves_supplied_request_id(self, client):
        custom_id = "REQ-CUSTOM-TRACE-999"
        response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id

    def test_generates_request_id_if_missing(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        req_id = response.headers.get("X-Request-ID")
        assert req_id is not None
        assert req_id.startswith("REQ-")

    def test_injects_response_timing_header(self, client):
        response = client.get("/api/v1/health")
        assert "X-Response-Time-Ms" in response.headers
        timing = float(response.headers["X-Response-Time-Ms"])
        assert timing >= 0.0


class TestPayloadSizeLimits:
    """Verifies that oversized request bodies are rejected prior to execution."""

    def test_normal_payload_accepted(self, client):
        payload = {"data": "a" * 1024}
        response = client.post(
            "/api/v1/telemetry/validate",
            json=payload,
            headers={"Content-Length": str(len(str(payload)))}
        )
        # Endpoint may return 422 for schema invalidity, but NOT 413
        assert response.status_code != 413

    def test_oversized_payload_rejected(self, client, monkeypatch):
        # Temporarily set max bytes to 500 bytes for testing
        monkeypatch.setattr(settings, "max_request_body_bytes", 500)
        oversized_str = "x" * 600
        response = client.post(
            "/api/v1/telemetry/validate",
            data=oversized_str,
            headers={"Content-Length": "600", "Content-Type": "application/json"}
        )
        assert response.status_code == 413
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert "exceeds limit" in body["error"]["message"]
        assert "request_id" in body
