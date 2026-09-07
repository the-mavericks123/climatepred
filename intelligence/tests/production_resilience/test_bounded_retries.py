"""Tests for Bounded Retries with Exponential Backoff and Jitter."""
import pytest
import time

from intelligence.core.resilience.retry import retry_with_backoff


class TestBoundedRetries:
    """Verifies safe retry mechanisms for idempotent operations."""

    def test_success_on_first_try(self):
        attempts = 0

        @retry_with_backoff(retries=3, initial_delay=0.01)
        def reliable_call():
            nonlocal attempts
            attempts += 1
            return "SUCCESS"

        result = reliable_call()
        assert result == "SUCCESS"
        assert attempts == 1

    def test_eventual_success_after_transient_failures(self):
        attempts = 0

        @retry_with_backoff(retries=3, initial_delay=0.01, jitter=False)
        def transient_call():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ConnectionResetError("Transient network drop")
            return "RECOVERED"

        result = transient_call()
        assert result == "RECOVERED"
        assert attempts == 3

    def test_exhaustion_raises_final_exception(self):
        attempts = 0

        @retry_with_backoff(retries=2, initial_delay=0.01, jitter=False)
        def failing_call():
            nonlocal attempts
            attempts += 1
            raise TimeoutError("Dead backend")

        with pytest.raises(TimeoutError) as exc_info:
            failing_call()

        assert "Dead backend" in str(exc_info.value)
        assert attempts == 3  # Initial + 2 retries

    def test_non_retryable_exception_fails_immediately(self):
        attempts = 0

        @retry_with_backoff(
            retries=3,
            initial_delay=0.01,
            retryable_exceptions=(ConnectionError, TimeoutError)
        )
        def unrecoverable_call():
            nonlocal attempts
            attempts += 1
            raise ValueError("Malformed input data")

        with pytest.raises(ValueError):
            unrecoverable_call()

        assert attempts == 1  # Did NOT retry

    def test_exponential_delay_scaling(self):
        start = time.perf_counter()

        @retry_with_backoff(
            retries=2,
            initial_delay=0.05,
            backoff_factor=2.0,
            jitter=False
        )
        def timed_call():
            raise IOError("Disk IO error")

        with pytest.raises(IOError):
            timed_call()

        elapsed = time.perf_counter() - start
        # Attempt 1 -> sleep 0.05
        # Attempt 2 -> sleep 0.10
        # Total sleep >= 0.15s
        assert elapsed >= 0.14
