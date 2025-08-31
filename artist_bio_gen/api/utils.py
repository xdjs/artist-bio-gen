"""
API utilities module.

This module provides utility functions for API operations including
error handling, retry logic, and delay calculations.
"""

import logging
import random
import time
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


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