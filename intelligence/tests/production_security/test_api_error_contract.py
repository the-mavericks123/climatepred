"""Tests for Standardized API Error Contract Containment."""
import pytest
from fastapi.testclient import TestClient

from intelligence.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestApiErrorContract:
    """Verifies that all error scenarios adhere strictly to the project error envelope."""

    def test_404_not_found_envelope(self, client):
        response = client.get("/api/v1/non_existent_endpoint")
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert "error" in body
        assert body["error"]["code"] == "NOT_FOUND"
        assert "message" in body["error"]
        assert "details" in body["error"]
        assert "request_id" in body
        assert body["request_id"] is not None

    def test_422_validation_error_envelope(self, client):
        # Empty body to endpoint expecting JSON
        response = client.post("/api/v1/telemetry/validate", json={})
        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "message" in body["error"]
        assert "details" in body["error"]
        assert "request_id" in body

    def test_no_stack_traces_leaked(self, client):
        # Trigger validation failure with invalid nested structure
        response = client.post("/api/v1/telemetry/validate", json={"timestamp": "not-a-date"})
        body = response.text
        assert "Traceback (most recent call last)" not in body
        assert 'File "' not in body
        assert "line " not in body.lower() or "error" in body.lower()
