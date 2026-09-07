"""Safe bounded retry with exponential backoff and jitter."""
import time
import random
import functools
from typing import Callable, Any, Tuple, Type

def retry_with_backoff(
    retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """Decorator to retry a function call with exponential backoff and optional jitter."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = initial_delay
            while True:
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    attempt += 1
                    if attempt > retries:
                        raise exc
                    
                    sleep_time = delay
                    if jitter:
                        sleep_time += random.uniform(0, sleep_time * 0.1)
                    sleep_time = min(sleep_time, max_delay)
                    
                    time.sleep(sleep_time)
                    delay = min(delay * backoff_factor, max_delay)
        return wrapper
    return decorator
