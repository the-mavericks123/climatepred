"""Tests for Token Bucket Rate Limiting and Endpoint Throttling."""
import pytest
import time
from fastapi import HTTPException

from intelligence.core.security.rate_limiter import (
    TokenBucket,
    RateLimiter,
    limit_rate,
)
from intelligence.app.config import settings


class TestTokenBucket:
    """Validates mathematical correctness of the token bucket algorithm."""

    def test_bucket_initial_capacity(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert bucket.tokens == 10.0

    def test_bucket_consumption_success(self):
        bucket = TokenBucket(capacity=5.0, refill_rate=1.0)
        allowed, retry_after = bucket.consume(3.0)
        assert allowed is True
        assert retry_after == 0.0
        assert bucket.tokens == 2.0

    def test_bucket_exhaustion_and_retry_after(self):
        bucket = TokenBucket(capacity=2.0, refill_rate=1.0)
        bucket.consume(2.0)
        allowed, retry_after = bucket.consume(1.0)
        assert allowed is False
        assert retry_after > 0.0

    def test_bucket_refills_over_time(self):
        bucket = TokenBucket(capacity=5.0, refill_rate=10.0)  # 10 tokens/sec
        bucket.consume(5.0)
        assert bucket.tokens == 0.0
        time.sleep(0.15)
        allowed, _ = bucket.consume(1.0)
        assert allowed is True


class TestRateLimiter:
    """Validates multi-client tracking and isolation."""

    def test_client_isolation(self):
        limiter = RateLimiter(requests_per_minute=60, burst=2)
        # Client 1 exhausts quota
        assert limiter.is_allowed("client-1")[0] is True
        assert limiter.is_allowed("client-1")[0] is True
        assert limiter.is_allowed("client-1")[0] is False

        # Client 2 should still have full quota
        assert limiter.is_allowed("client-2")[0] is True
        assert limiter.is_allowed("client-2")[0] is True
        assert limiter.is_allowed("client-2")[0] is False

    def test_reset_clears_quotas(self):
        limiter = RateLimiter(requests_per_minute=60, burst=1)
        assert limiter.is_allowed("client-A")[0] is True
        assert limiter.is_allowed("client-A")[0] is False
        limiter.reset()
        assert limiter.is_allowed("client-A")[0] is True


class TestRateLimiterDependency:
    """Validates FastAPI route-level rate limiting dependency behavior."""

    class MockRequest:
        def __init__(self, host="127.0.0.1", api_key=None):
            self.headers = {"X-API-Key": api_key} if api_key else {}
            self.client = type("Client", (), {"host": host})()

    def test_passthrough_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        limiter = RateLimiter(requests_per_minute=1, burst=1)
        checker = limit_rate(cost=1.0, limiter=limiter)
        req = self.MockRequest()
        checker(req)
        checker(req)  # Should not raise

    def test_throttles_when_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        limiter = RateLimiter(requests_per_minute=60, burst=1)
        checker = limit_rate(cost=1.0, limiter=limiter)
        req = self.MockRequest(host="10.0.0.1")

        checker(req)  # First request consumes burst
        with pytest.raises(HTTPException) as exc_info:
            checker(req)  # Second request should be rejected
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in exc_info.value.headers
