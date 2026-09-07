"""Tests for Circuit Breaker Pattern protecting external services."""
import pytest
import time

from intelligence.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenException,
)


class TestCircuitBreaker:
    """Verifies state machine transitions and fail-fast behavior."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("weather-api", failure_threshold=3, recovery_timeout_sec=0.1)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_successful_call_remains_closed(self):
        cb = CircuitBreaker("weather-api", failure_threshold=3)
        res = cb.call(lambda x, y: x + y, 2, 3)
        assert res == 5
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_failure_increments_count(self):
        cb = CircuitBreaker("weather-api", failure_threshold=3)
        def fail():
            raise RuntimeError("API timeout")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1

    def test_trips_to_open_upon_reaching_threshold(self):
        cb = CircuitBreaker("weather-api", failure_threshold=2)
        def fail():
            raise RuntimeError("Network error")

        with pytest.raises(RuntimeError):
            cb.call(fail)
        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 2

    def test_open_circuit_fails_fast_without_calling_function(self):
        cb = CircuitBreaker("weather-api", failure_threshold=1, recovery_timeout_sec=10.0)
        def fail():
            raise RuntimeError("Primary service down")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN

        called = False
        def should_not_run():
            nonlocal called
            called = True
            return 42

        with pytest.raises(CircuitBreakerOpenException) as exc_info:
            cb.call(should_not_run)

        assert "is OPEN. Fast failing request." in str(exc_info.value)
        assert called is False

    def test_fallback_executed_when_open(self):
        cb = CircuitBreaker("routing-service", failure_threshold=1, recovery_timeout_sec=10.0)
        def fail():
            raise RuntimeError("Routing timeout")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN

        fallback_called = False
        def fallback():
            nonlocal fallback_called
            fallback_called = True
            return "DEGRADED_FALLBACK_ROUTE"

        result = cb.call(lambda: "NORMAL_ROUTE", fallback=fallback)
        assert result == "DEGRADED_FALLBACK_ROUTE"
        assert fallback_called is True

    def test_transitions_to_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("weather-api", failure_threshold=1, recovery_timeout_sec=0.05)
        def fail():
            raise RuntimeError("Temporary error")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)

        # Next call attempts half-open probe
        res = cb.call(lambda: "PROBE_SUCCESS")
        assert res == "PROBE_SUCCESS"
        assert cb.state in (CircuitState.HALF_OPEN, CircuitState.CLOSED)

    def test_half_open_success_threshold_recovers_to_closed(self):
        cb = CircuitBreaker(
            "routing-service",
            failure_threshold=1,
            recovery_timeout_sec=0.05,
            half_open_success_threshold=2
        )
        def fail():
            raise RuntimeError("Temporary glitch")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)

        # First successful probe -> still half-open
        cb.call(lambda: "OK_1")
        assert cb.state == CircuitState.HALF_OPEN

        # Second successful probe -> recovered to closed
        cb.call(lambda: "OK_2")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_immediately_re_opens(self):
        cb = CircuitBreaker("weather-api", failure_threshold=1, recovery_timeout_sec=0.05)
        def fail():
            raise RuntimeError("Fault")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)

        with pytest.raises(ValueError):
            cb.call(lambda: int("not_a_number"))

        assert cb.state == CircuitState.OPEN

    def test_manual_reset(self):
        cb = CircuitBreaker("geocoding-service", failure_threshold=1)
        def fail():
            raise RuntimeError("Reset test fail")

        with pytest.raises(RuntimeError):
            cb.call(fail)

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
