"""
In-memory token bucket rate limiter for S2 Intelligence Service.
Protects compute-heavy endpoints (simulations, evaluations, calibrations) from overload.

NOTE: This is a node-local (in-memory) rate limiter. In a distributed multi-node
deployment, an external shared coordinator (e.g., Redis) would be required for
cluster-wide rate quotas.
"""

import threading
import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status
from intelligence.app.config import settings


class TokenBucket:
    """Individual client token bucket with thread-safe token consumption."""

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> Tuple[bool, float]:
        """
        Attempts to consume tokens in a thread-safe manner.
        Returns: (allowed, retry_after_seconds)
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now

            # Refill tokens up to capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

            if self.tokens >= amount:
                self.tokens -= amount
                return True, 0.0

            missing = amount - self.tokens
            retry_after = missing / self.refill_rate if self.refill_rate > 0 else 60.0
            return False, round(retry_after, 2)


class RateLimiter:
    """Manages rate limiting buckets per client key/IP."""

    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.refill_rate = requests_per_minute / 60.0
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str, cost: float = 1.0) -> Tuple[bool, float]:
        """Checks whether client is permitted to perform request."""
        with self._lock:
            if client_id not in self._buckets:
                self._buckets[client_id] = TokenBucket(capacity=float(self.burst), refill_rate=self.refill_rate)
            bucket = self._buckets[client_id]
        return bucket.consume(cost)

    def reset(self):
        """Clears all client buckets (useful for test isolation)."""
        with self._lock:
            self._buckets.clear()


# Default global instance configured from application settings
default_limiter = RateLimiter(
    requests_per_minute=settings.rate_limit_requests_per_minute,
    burst=settings.rate_limit_burst,
)


def limit_rate(cost: float = 1.0, limiter: RateLimiter = default_limiter):
    """
    FastAPI dependency that enforces rate limits for the calling endpoint.
    Executed before the endpoint body so throttled calls do not execute heavy compute.
    """
    def check_rate_limit(request: Request):
        if not settings.rate_limit_enabled:
            return

        client_host = request.client.host if request.client else "unknown-client"
        client_key = request.headers.get("X-API-Key") or request.headers.get("Authorization") or client_host

        allowed, retry_after = limiter.is_allowed(client_key, cost=cost)
        if not allowed:
            retry_seconds_int = max(1, int(retry_after) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    "details": {"retry_after_seconds": retry_after},
                },
                headers={"Retry-After": str(retry_seconds_int)},
            )

    return check_rate_limit
