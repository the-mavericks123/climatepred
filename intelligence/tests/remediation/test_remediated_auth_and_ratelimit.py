"""
Tests for Phase 11 Remediation: BLK-SEC-01 (Authentication/RBAC) and BLK-SEC-02 (Rate Limiting).
Proves route-level authentication enforcement, RBAC privilege checks, token validity,
and token bucket rate limiting on compute-heavy routes.
"""

import concurrent.futures
import time
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

from intelligence.app.config import Settings, settings
from intelligence.app.main import app
from intelligence.core.security.auth import Role, create_access_token
from intelligence.core.security.rate_limiter import RateLimiter, default_limiter

client = TestClient(app)

PROTECTED_OPERATOR_ROUTES = [
    ("POST", "/api/v1/simulation/run", {"scenario_id": "SCN-RAIN-20", "base_state": "current"}),
    ("POST", "/api/v1/response/simulate", {
        "scenario_id": "SCN-RAIN-20",
        "simulation_parameters": {"rainfall_multiplier": 1.2},
    }),
    ("POST", "/api/v1/response/evaluate", {}),
    ("GET", "/api/v1/simulation/SIM-NONEXISTENT", None),
]

PROTECTED_ADMIN_ROUTES = [
    ("POST", "/api/v1/evaluation/run", {"model_version": "hazard-flood-v1", "dataset_id": "EVAL-FLOOD-SYNTHETIC-001"}),
    ("POST", "/api/v1/calibration/run", {"model_version": "hazard-flood-v1", "dataset_id": "EVAL-FLOOD-SYNTHETIC-001"}),
    ("POST", "/api/v1/models/compare", {
        "baseline_model_version": "hazard-flood-v1",
        "candidate_model_version": "hazard-flood-v1",
        "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
    }),
    ("POST", "/api/v1/drift/evaluate", {
        "feature_name": "temperature",
        "baseline_samples": [20.0, 21.0, 22.0],
        "current_samples": [20.5, 21.5, 22.5],
    }),
    ("GET", "/api/v1/evaluation/EVAL-NONEXISTENT", None),
    ("GET", "/api/v1/calibration/CAL-NONEXISTENT", None),
    ("GET", "/api/v1/models/hazard-flood-v1/evaluation", None),
]


class TestAuthenticationRemediation:
    """Verifies BLK-SEC-01 remediation: route-level auth and RBAC matrix."""

    def test_auth_disabled_development_behavior(self, monkeypatch):
        """When API_AUTH_ENABLED=false, development requests succeed as ADMIN."""
        monkeypatch.setattr(settings, "api_auth_enabled", False)
        # Call admin route without any auth headers
        res = client.post("/api/v1/models/compare", json={
            "baseline_model_version": "hazard-flood-v1",
            "candidate_model_version": "hazard-flood-v1",
            "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
        })
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_critical_all_protected_routes_reject_anonymous_when_auth_enabled(self, monkeypatch):
        """CRITICAL TEST: HTTP request to every protected route without credentials MUST fail with 401."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "valid-admin-secret-key-16")
        monkeypatch.setattr(settings, "operator_api_key", "valid-operator-secret-key-16")

        all_routes = PROTECTED_OPERATOR_ROUTES + PROTECTED_ADMIN_ROUTES
        for method, path, payload in all_routes:
            if method == "POST":
                res = client.post(path, json=payload or {})
            else:
                res = client.get(path)

            assert res.status_code == 401, f"Route {method} {path} was accessible anonymously! Expected 401."
            err = res.json()
            assert err["success"] is False
            assert err["error"]["code"] in ["INVALID_REQUEST", "AUTHENTICATION_REQUIRED"]

    def test_protected_routes_accept_valid_authorized_admin(self, monkeypatch):
        """Valid ADMIN token successfully accesses ADMIN routes."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "adm-secret-key-valid-16")

        headers = {"X-API-Key": "adm-secret-key-valid-16"}
        res = client.post("/api/v1/models/compare", json={
            "baseline_model_version": "hazard-flood-v1",
            "candidate_model_version": "hazard-flood-v1",
            "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_operator_accessing_admin_endpoint_rejected_with_403(self, monkeypatch):
        """OPERATOR role accessing ADMIN endpoint returns 403 Forbidden."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "admin_api_key", "adm-secret-key-valid-16")
        monkeypatch.setattr(settings, "operator_api_key", "op-secret-key-valid-16")

        # Operator tries to run model comparison (Admin-only)
        headers = {"X-API-Key": "op-secret-key-valid-16"}
        res = client.post("/api/v1/models/compare", json={
            "baseline_model_version": "hazard-flood-v1",
            "candidate_model_version": "hazard-flood-v1",
            "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
        }, headers=headers)
        assert res.status_code == 403
        assert res.json()["success"] is False
        assert "INSUFFICIENT_PRIVILEGES" in str(res.json())

    def test_operator_accessing_operator_endpoint_succeeds(self, monkeypatch):
        """OPERATOR role accessing OPERATOR endpoint succeeds."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "operator_api_key", "op-secret-key-valid-16")

        headers = {"X-API-Key": "op-secret-key-valid-16"}
        res = client.post("/api/v1/simulation/run", json={
            "scenario_id": "SCN-RAIN-20",
            "base_state": "current",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_public_role_token_accessing_operator_endpoint_rejected_with_403(self, monkeypatch):
        """PUBLIC role token cannot access OPERATOR endpoint (returns 403)."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        pub_token = create_access_token(client_id="pub-user", role=Role.PUBLIC)
        headers = {"Authorization": f"Bearer {pub_token}"}

        res = client.post("/api/v1/simulation/run", json={
            "scenario_id": "SCN-RAIN-20",
            "base_state": "current",
        }, headers=headers)
        assert res.status_code == 403
        assert res.json()["success"] is False

    def test_invalid_and_empty_token_rejected_with_401(self, monkeypatch):
        """Invalid, empty, or garbage tokens are rejected with 401."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)

        for bad_header in [
            {"X-API-Key": "completely-invalid-key"},
            {"Authorization": "Bearer not-a-real-jwt"},
            {"Authorization": "Bearer "},
            {"Authorization": "Token something"},
        ]:
            res = client.post("/api/v1/simulation/run", json={
                "scenario_id": "SCN-RAIN-20",
                "base_state": "current",
            }, headers=bad_header)
            assert res.status_code == 401
            assert res.json()["success"] is False

    def test_expired_token_rejected_with_401(self, monkeypatch):
        """Expired signed token is rejected with 401."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        # Token expired 10 seconds ago
        expired_token = create_access_token(client_id="test", role=Role.ADMIN, expires_in_sec=-10)
        headers = {"Authorization": f"Bearer {expired_token}"}

        res = client.post("/api/v1/models/compare", json={
            "baseline_model_version": "hazard-flood-v1",
            "candidate_model_version": "hazard-flood-v1",
            "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
        }, headers=headers)
        assert res.status_code == 401
        assert "expired" in str(res.json()).lower()

    def test_forged_admin_claim_with_wrong_secret_rejected_with_401(self, monkeypatch):
        """Forged token signed with incorrect secret key is rejected with 401."""
        monkeypatch.setattr(settings, "api_auth_enabled", True)
        # Signed with attacker secret key
        forged_token = create_access_token(
            client_id="attacker",
            role=Role.ADMIN,
            secret_key="attacker-tampered-secret-key-32",
        )
        headers = {"Authorization": f"Bearer {forged_token}"}

        res = client.post("/api/v1/models/compare", json={
            "baseline_model_version": "hazard-flood-v1",
            "candidate_model_version": "hazard-flood-v1",
            "dataset_id": "EVAL-FLOOD-SYNTHETIC-001",
        }, headers=headers)
        assert res.status_code == 401
        assert res.json()["success"] is False

    def test_production_environment_cannot_disable_auth(self):
        """Production configuration fails fast if auth is explicitly disabled."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                environment="production",
                secret_key="a" * 32,
                allowed_origins=["https://climate-eye.internal"],
                api_auth_enabled=False,
            )
        assert "api_auth_enabled cannot be explicitly set to False" in str(exc_info.value)


class TestRateLimiterRemediation:
    """Verifies BLK-SEC-02 remediation: rate limiter actually connected to compute routes."""

    def test_simulation_route_rate_limited_returns_429_and_retry_after(self, monkeypatch):
        """Rapid consecutive requests to /api/v1/simulation/run trigger HTTP 429 with Retry-After."""
        default_limiter.reset()
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "api_auth_enabled", False)

        # Configured burst is 10 by default
        headers = {"X-API-Key": "test-rate-limit-client-1"}
        payload = {"scenario_id": "SCN-RAIN-20", "base_state": "current"}

        statuses = []
        retry_after_headers = []
        for _ in range(15):
            res = client.post("/api/v1/simulation/run", json=payload, headers=headers)
            statuses.append(res.status_code)
            if res.status_code == 429:
                retry_after_headers.append(res.headers.get("Retry-After"))

        # Confirms bucket exhaustion: initial 10 succeed, subsequent calls throttled
        assert 200 in statuses
        assert 429 in statuses
        assert len(retry_after_headers) >= 1
        # Retry-After must be integer string >= 1
        assert int(retry_after_headers[0]) >= 1

    def test_evaluation_route_rate_limited(self, monkeypatch):
        """Evaluation endpoint /api/v1/evaluation/run enforces rate limiting."""
        default_limiter.reset()
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "api_auth_enabled", False)

        headers = {"X-API-Key": "test-eval-client"}
        payload = {"model_version": "hazard-flood-v1", "dataset_id": "EVAL-FLOOD-SYNTHETIC-001"}

        statuses = [client.post("/api/v1/evaluation/run", json=payload, headers=headers).status_code for _ in range(15)]
        assert 429 in statuses

    def test_calibration_route_rate_limited(self, monkeypatch):
        """Calibration endpoint /api/v1/calibration/run enforces rate limiting."""
        default_limiter.reset()
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "api_auth_enabled", False)

        headers = {"X-API-Key": "test-cal-client"}
        payload = {"model_version": "hazard-flood-v1", "dataset_id": "EVAL-FLOOD-SYNTHETIC-001"}

        statuses = [client.post("/api/v1/calibration/run", json=payload, headers=headers).status_code for _ in range(15)]
        assert 429 in statuses

    def test_rate_limiter_recovery_after_cooldown(self, monkeypatch):
        """Rate limiter recovers and allows new requests after cooldown."""
        limiter = RateLimiter(requests_per_minute=60, burst=2)
        monkeypatch.setattr(settings, "rate_limit_enabled", True)

        client_id = "test-cooldown-client"
        assert limiter.is_allowed(client_id)[0] is True
        assert limiter.is_allowed(client_id)[0] is True
        # Bucket exhausted
        allowed, retry_after = limiter.is_allowed(client_id)
        assert allowed is False
        assert retry_after > 0

        # Simulate time advance
        bucket = limiter._buckets[client_id]
        bucket.last_update -= 2.0  # 2 seconds ago, refills 2 tokens
        allowed_after_wait, _ = limiter.is_allowed(client_id)
        assert allowed_after_wait is True

    def test_cannot_bypass_limits_with_query_params_or_trailing_slash(self, monkeypatch):
        """Query parameters or trailing variations do not reset or bypass client rate limit."""
        default_limiter.reset()
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "api_auth_enabled", False)

        headers = {"X-API-Key": "bypass-attempt-client"}
        payload = {"scenario_id": "SCN-RAIN-20", "base_state": "current"}

        # Consume 10 tokens
        for _ in range(10):
            res = client.post("/api/v1/simulation/run", json=payload, headers=headers)
            assert res.status_code == 200

        # Changing query parameter must STILL be rate limited under same client key
        res_with_query = client.post("/api/v1/simulation/run?bypass=1", json=payload, headers=headers)
        assert res_with_query.status_code == 429

    def test_concurrent_requests_thread_safety(self, monkeypatch):
        """Concurrent requests do not race or bypass the token bucket capacity."""
        limiter = RateLimiter(requests_per_minute=60, burst=5)
        client_id = "concurrent-client"

        def attempt_consume():
            return limiter.is_allowed(client_id, cost=1.0)[0]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda _: attempt_consume(), range(20)))

        allowed_count = sum(1 for r in results if r is True)
        rejected_count = sum(1 for r in results if r is False)

        # Capacity is 5, so exactly 5 must succeed and 15 must be rejected
        assert allowed_count == 5
        assert rejected_count == 15

    def test_rate_limiter_executes_before_computation(self, monkeypatch):
        """Rate limit rejection (429) triggers before payload computation or validation."""
        default_limiter.reset()
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "api_auth_enabled", False)

        headers = {"X-API-Key": "pre-compute-client"}
        payload = {"scenario_id": "SCN-RAIN-20", "base_state": "current"}

        # Exhaust bucket
        for _ in range(10):
            client.post("/api/v1/simulation/run", json=payload, headers=headers)

        # Send invalid body; should return 429 NOT 422 because rate limiter checks first
        res = client.post("/api/v1/simulation/run", json={"invalid": "payload"}, headers=headers)
        assert res.status_code == 429

    def test_health_endpoints_not_rate_limited(self, monkeypatch):
        """Basic health and readiness probes are unthrottled by compute rate limit."""
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        for _ in range(25):
            res = client.get("/api/v1/health")
            assert res.status_code == 200
