"""
API utilities module.

This module provides utility functions for API operations including
error handling, retry logic, and delay calculations.

Enhanced in Task 1.3 to include:
- Error classification using HTTP status and error codes
- Unified backoff computation with jitter and caps
- Retry-After header extraction for 429/503
"""

import logging
import random
import time
from functools import wraps
from typing import Callable, Any, Optional, Tuple

from ..models.quota import ErrorClassification

logger = logging.getLogger(__name__)


def _extract_openai_error_info(exc: Exception) -> Tuple[Optional[int], Optional[str], Optional[int]]:
    """Best-effort extraction of HTTP status, error code, and Retry-After seconds.

    Supports multiple OpenAI SDK versions by probing common attributes.
    """
    status = None
    code = None
    retry_after = None

    # Common attributes across SDK versions
    for attr in ("status_code", "status", "http_status"):
        if hasattr(exc, attr):
            try:
                status = int(getattr(exc, attr))
                break
            except Exception:
                pass

    # Error code may be nested
    # Check .code
    if hasattr(exc, "code") and isinstance(getattr(exc, "code"), str):
        code = getattr(exc, "code")
    # Check .error.code (e.g., newer SDKs may have error dict/object)
    if code is None and hasattr(exc, "error"):
        err = getattr(exc, "error")
        try:
            code = getattr(err, "code", None)
        except Exception:
            pass
        if code is None and isinstance(err, dict):
            code = err.get("code")

    # Retry-After can be on headers or response.headers
    headers = None
    if hasattr(exc, "headers"):
        headers = getattr(exc, "headers")
    elif hasattr(exc, "response") and hasattr(getattr(exc, "response"), "headers"):
        headers = getattr(exc, "response").headers

    if headers:
        # normalize keys to lower-case strings
        try:
            # headers may behave like dict; be defensive
            for key in ("retry-after", "Retry-After"):
                if key in headers:
                    val = headers[key]
                    try:
                        retry_after = int(val)
                    except Exception:
                        # Some servers return HTTP-date; ignore parsing for simplicity
                        retry_after = None
                    break
        except Exception:
            pass

    return status, code, retry_after


def classify_error(exc: Exception) -> ErrorClassification:
    """Classify error using SDK types, HTTP status, and error codes.

    Returns an ErrorClassification with kind in {rate_limit, quota, server, network}
    and whether it should be retried along with an optional retry_after seconds.
    """
    # Try to import OpenAI SDK exception classes for precise classification
    RateLimitError = InternalServerError = APITimeoutError = APIConnectionError = None
    try:
        from openai import (
            RateLimitError as _RateLimitError,
            InternalServerError as _InternalServerError,
            APITimeoutError as _APITimeoutError,
            APIConnectionError as _APIConnectionError,
        )

        RateLimitError = _RateLimitError
        InternalServerError = _InternalServerError
        APITimeoutError = _APITimeoutError
        APIConnectionError = _APIConnectionError
    except Exception:
        # Older/newer SDKs may differ; fall through to generic logic
        pass

    status, code, retry_after = _extract_openai_error_info(exc)

    # Network-type errors
    network_types = (ConnectionError, TimeoutError, OSError)
    if (APIConnectionError and isinstance(exc, APIConnectionError)) or (
        APITimeoutError and isinstance(exc, APITimeoutError)
    ) or isinstance(exc, network_types):
        return ErrorClassification(kind="network", retry_after=None, should_retry=True)

    # 429 rate limit vs quota depletion
    if (RateLimitError and isinstance(exc, RateLimitError)) or status == 429:
        # If the error code signals billing quota exhaustion, classify as quota
        quota_codes = {"insufficient_quota", "billing_hard_limit_reached", "quota_exceeded"}
        if code in quota_codes:
            return ErrorClassification(kind="quota", retry_after=retry_after, should_retry=True)
        return ErrorClassification(kind="rate_limit", retry_after=retry_after, should_retry=True)

    # 5xx server errors
    if (InternalServerError and isinstance(exc, InternalServerError)) or (
        isinstance(status, int) and 500 <= status <= 599
    ):
        return ErrorClassification(kind="server", retry_after=retry_after, should_retry=True)

    # Other 4xx are considered non-retryable client errors
    if isinstance(status, int) and 400 <= status <= 499:
        return ErrorClassification(kind="rate_limit", retry_after=retry_after, should_retry=False)

    # Default: not retryable
    return ErrorClassification(kind="server", retry_after=retry_after, should_retry=False)


def compute_backoff(
    attempt: int,
    kind: str,
    retry_after: Optional[int] = None,
    base: Optional[float] = None,
    cap: Optional[float] = None,
    jitter: float = 0.10,
) -> float:
    """Compute backoff delay with caps and jitter for a given error classification.

    - For rate_limit (429): honor Retry-After; default base 60s, cap 300s
    - For quota (insufficient_quota): base 300s, cap 3600s
    - For server/network: base 0.5s, cap 4s
    """
    # Determine defaults by kind if not specified
    if kind == "rate_limit":
        base = 60.0 if base is None else base
        cap = 300.0 if cap is None else cap
        # If Retry-After present on early attempts, use it directly
        if retry_after and attempt == 0:
            delay = float(retry_after)
        else:
            delay = min(base * (2**attempt), cap)
    elif kind == "quota":
        base = 300.0 if base is None else base
        cap = 3600.0 if cap is None else cap
        delay = min(base * (2**attempt), cap)
    else:  # server or network
        base = 0.5 if base is None else base
        cap = 4.0 if cap is None else cap
        delay = min(base * (2**attempt), cap)

    # Apply jitter: +/- jitter% using random in [0,1)
    r = random.random()
    factor = 1.0 + jitter * (2 * r - 1)
    jittered = max(0.1, delay * factor)
    return jittered


def should_retry_error(exception: Exception) -> bool:
    """Determine if an error should trigger a retry using classify_error."""
    try:
        classification = classify_error(exception)
        return classification.should_retry
    except Exception:
        return False


def calculate_retry_delay(
    attempt: int, base_delay: float = 0.5, max_delay: float = 4.0
) -> float:
    """
    Backward-compatible helper retained for existing callers.
    Uses 25% jitter as before for generic retries.
    """
    delay = min(base_delay * (2**attempt), max_delay)
    jitter = delay * 0.25 * (2 * random.random() - 1)
    return max(0.1, delay + jitter)


def retry_with_exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
):
    """
    Decorator for retrying functions with exponential backoff.

    Enhanced to use error classification and Retry-After for 429/503.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay for generic (server/network) backoff
        max_delay: Maximum delay between retries for generic backoff
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            worker_id = kwargs.get("worker_id", "main")
            last_exception = None

            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 - propagate after retries
                    last_exception = e

                    # Classify error and decide retry policy
                    classification = classify_error(e)

                    # Last attempt or non-retryable
                    if attempt == max_retries or not classification.should_retry:
                        logger.error(
                            f"[{worker_id}] Final/Non-retryable error after {attempt} attempts: "
                            f"{type(e).__name__}: {str(e)}"
                        )
                        break

                    # Compute backoff using unified helper
                    if classification.kind in {"server", "network"}:
                        delay = compute_backoff(
                            attempt, classification.kind,
                            classification.retry_after, base_delay, max_delay, 0.10
                        )
                    else:
                        delay = compute_backoff(
                            attempt, classification.kind, classification.retry_after, None, None, 0.10
                        )

                    logger.warning(
                        f"[{worker_id}] Attempt {attempt + 1} failed ({classification.kind}: {type(e).__name__}), "
                        f"retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)

            # If we get here, all retries failed
            raise last_exception

        return wrapper

    return decorator
