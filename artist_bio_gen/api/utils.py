"""
API utilities module.

This module provides utility functions for API operations including
error handling, retry logic, and delay calculations.
"""

import logging
import random
import time
from collections import deque
from functools import wraps
from threading import Lock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple thread-safe rate limiter for OpenAI API calls."""

    def __init__(
        self,
        rpm: int = 500,
        tpm: int = 200_000,
        tpd: int = 2_000_000,
    ) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self.tpd = tpd
        self.min_interval = 60.0 / rpm
        self._next_request_time = time.monotonic()
        self._tokens_window: deque[tuple[float, int]] = deque()
        self._tokens_day = 0
        self._avg_tokens = 0.0
        self._lock = Lock()

    def _purge_window(self, now: float) -> None:
        while self._tokens_window and now - self._tokens_window[0][0] > 60:
            self._tokens_window.popleft()

    def estimate_tokens(self) -> int:
        return max(1, int(self._avg_tokens) or 1)

    def wait(
        self, tokens_estimate: Optional[int] = None, worker_id: str = "main"
    ) -> None:
        if tokens_estimate is None:
            tokens_estimate = self.estimate_tokens()

        with self._lock:
            now = time.monotonic()
            if now < self._next_request_time:
                delay = self._next_request_time - now
                logger.debug(f"[{worker_id}] Throttling for RPM: sleeping {delay:.2f}s")
                time.sleep(delay)
                now = time.monotonic()
            self._next_request_time = now + self.min_interval

            wall = time.time()
            self._purge_window(wall)
            tokens_last_minute = sum(t for _, t in self._tokens_window)
            if tokens_last_minute + tokens_estimate > self.tpm:
                excess = tokens_last_minute + tokens_estimate - self.tpm
                wait_until = wall
                cumulative = tokens_last_minute
                for ts, tok in self._tokens_window:
                    cumulative -= tok
                    if cumulative + tokens_estimate <= self.tpm:
                        wait_until = ts + 60
                        break
                delay = max(0, wait_until - wall)
                logger.debug(f"[{worker_id}] Throttling for TPM: sleeping {delay:.2f}s")
                time.sleep(delay)
                self._next_request_time = (
                    max(self._next_request_time, time.monotonic()) + self.min_interval
                )

            if self._tokens_day + tokens_estimate > self.tpd:
                raise RuntimeError("Daily token cap exceeded")

    def record(self, tokens_used: int) -> None:
        with self._lock:
            now = time.time()
            self._tokens_window.append((now, tokens_used))
            self._tokens_day += tokens_used
            self._avg_tokens = self._avg_tokens * 0.9 + tokens_used * 0.1
            self._purge_window(now)


def should_retry_error(exception: Exception) -> bool:
    """
    Determine if an error should trigger a retry.

    Args:
        exception: The exception that occurred

    Returns:
        True if the error should be retried, False otherwise
    """
    # Import OpenAI exceptions locally to avoid import issues
    try:
        from openai import (
            RateLimitError,
            InternalServerError,
            APITimeoutError,
            APIConnectionError,
        )
    except ImportError:
        # Fallback for different OpenAI versions
        return False

    # Retry on these specific OpenAI errors
    if isinstance(
        exception,
        (RateLimitError, InternalServerError, APITimeoutError, APIConnectionError),
    ):
        return True

    # Retry on network-related errors
    if isinstance(exception, (ConnectionError, TimeoutError, OSError)):
        return True

    # Don't retry on client errors (4xx) or other exceptions
    return False


def calculate_retry_delay(
    attempt: int, base_delay: float = 0.5, max_delay: float = 4.0
) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter
    """
    # Exponential backoff: 0.5s, 1s, 2s, 4s
    delay = min(base_delay * (2**attempt), max_delay)

    # Add jitter (±25% of the delay)
    jitter = delay * 0.25 * (2 * random.random() - 1)

    return max(0.1, delay + jitter)  # Minimum 0.1s delay


def call_with_retry(
    func: Callable[[], Any],
    *,
    rate_limiter: RateLimiter,
    max_retries: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    worker_id: str = "main",
) -> Any:
    """Call an OpenAI function with shared rate limiting and retries."""

    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            rate_limiter.wait(worker_id=worker_id)
            response = func()
            usage = getattr(response, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) if usage else 0
            rate_limiter.record(tokens)
            return response
        except Exception as e:  # noqa: BLE001
            last_exception = e

            if attempt == max_retries or not should_retry_error(e):
                raise

            retry_after = None
            resp = getattr(e, "response", None)
            if resp is not None:
                retry_after = resp.headers.get("Retry-After") or resp.headers.get(
                    "retry-after"
                )
            if retry_after is not None:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = calculate_retry_delay(attempt, base_delay, max_delay)
            else:
                delay = calculate_retry_delay(attempt, base_delay, max_delay)

            logger.warning(
                f"[{worker_id}] Attempt {attempt + 1} failed ({type(e).__name__}), retrying in {delay:.2f}s: {e}"
            )
            time.sleep(delay)

    raise last_exception


def retry_with_exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay for exponential backoff
        max_delay: Maximum delay between retries
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Extract worker_id from kwargs or use default
            worker_id = kwargs.get("worker_id", "main")
            last_exception = None

            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        logger.error(
                            f"[{worker_id}] Final attempt failed after {max_retries} retries: {type(e).__name__}: {str(e)}"
                        )
                        break

                    # Check if this error should be retried
                    if not should_retry_error(e):
                        logger.error(
                            f"[{worker_id}] Non-retryable error on attempt {attempt + 1}: {type(e).__name__}: {str(e)}"
                        )
                        break

                    # Calculate delay and wait
                    delay = calculate_retry_delay(attempt, base_delay, max_delay)
                    logger.warning(
                        f"[{worker_id}] Attempt {attempt + 1} failed ({type(e).__name__}), retrying in {delay:.2f}s: {str(e)}"
                    )
                    time.sleep(delay)

            # If we get here, all retries failed
            raise last_exception

        return wrapper

    return decorator
