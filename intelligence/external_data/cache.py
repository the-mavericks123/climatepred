"""
Thread-safe TTL Cache with Stale Fallback and Circuit Breaker for External Feeds.
"""

import threading
import time
from typing import Any, Callable, Dict, Generic, Optional, Tuple, TypeVar
from intelligence.core.logging import get_logger

logger = get_logger("external_cache")
T = TypeVar("T")


class CachedEntry(Generic[T]):
    def __init__(self, data: T, ttl_seconds: float):
        self.data: T = data
        self.created_at: float = time.time()
        self.ttl_seconds: float = ttl_seconds

    @property
    def is_fresh(self) -> bool:
        return (time.time() - self.created_at) <= self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class CircuitBreaker:
    """Simple 3-state circuit breaker: CLOSED (normal), OPEN (broken), HALF-OPEN (probing)."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 300.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(
                    f"Circuit breaker tripped to OPEN state after {self.failure_count} consecutive failures"
                )

    def can_attempt(self) -> bool:
        with self._lock:
            if self.state == "CLOSED":
                return True
            if self.state == "OPEN":
                if (time.time() - self.last_failure_time) >= self.recovery_timeout_sec:
                    self.state = "HALF-OPEN"
                    logger.info("Circuit breaker entered HALF-OPEN state, attempting probe")
                    return True
                return False
            # HALF-OPEN: allow one probe
            return True


class ExternalDataCache:
    """Thread-safe cache for external data providers with circuit breaker and stale fallback."""

    def __init__(self):
        self._cache: Dict[str, CachedEntry[Any]] = {}
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_breaker(self, key: str) -> CircuitBreaker:
        with self._lock:
            if key not in self._breakers:
                self._breakers[key] = CircuitBreaker()
            return self._breakers[key]

    def set(self, key: str, data: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._cache[key] = CachedEntry(data, ttl_seconds)

    def get(self, key: str) -> Tuple[Optional[Any], bool]:
        """
        Returns (data, is_fresh).
        If entry exists but is expired, returns (data, False) enabling stale-while-revalidate.
        If entry does not exist, returns (None, False).
        """
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None, False
            return entry.data, entry.is_fresh

    def get_entry(self, key: str) -> Optional[CachedEntry[Any]]:
        with self._lock:
            return self._cache.get(key)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._breakers.clear()
