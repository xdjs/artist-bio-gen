#!/usr/bin/env python3
"""
Quota Management API Module

This module handles OpenAI API quota monitoring, header parsing,
and pause/resume decision logic for rate limiting management.
"""

import logging
import re
import threading
import time
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from ..models.quota import QuotaStatus, QuotaMetrics, ErrorClassification

logger = logging.getLogger(__name__)


def parse_rate_limit_headers(headers: Dict[str, str], usage_stats: Optional[Dict[str, Any]] = None) -> QuotaStatus:
    """
    Parse OpenAI API response headers to extract rate limit information.

    Args:
        headers: HTTP response headers from OpenAI API
        usage_stats: Optional usage statistics from response body

    Returns:
        QuotaStatus with parsed rate limit information

    Raises:
        ValueError: If required headers are missing or invalid
    """
    try:
        # Parse required headers with fallback values
        requests_remaining = _parse_header_int(headers, 'x-ratelimit-remaining-requests', 0)
        requests_limit = _parse_header_int(headers, 'x-ratelimit-limit-requests', 5000)
        tokens_remaining = _parse_header_int(headers, 'x-ratelimit-remaining-tokens', 4000000)  # Default to full tokens
        tokens_limit = _parse_header_int(headers, 'x-ratelimit-limit-tokens', 4000000)

        # Parse reset times - can be seconds or duration strings
        reset_requests = _parse_reset_header(headers, 'x-ratelimit-reset-requests')
        reset_tokens = _parse_reset_header(headers, 'x-ratelimit-reset-tokens')

        # Use token usage from response body if available (more accurate than headers)
        if usage_stats and 'total_tokens' in usage_stats:
            # Adjust tokens_remaining based on actual usage
            tokens_used = usage_stats['total_tokens']
            # Only adjust if it seems reasonable (avoid negative values)
            if tokens_used > 0 and tokens_used <= tokens_remaining:
                tokens_remaining = max(0, tokens_remaining - tokens_used)

        quota_status = QuotaStatus(
            requests_remaining=requests_remaining,
            requests_limit=requests_limit,
            tokens_remaining=tokens_remaining,
            tokens_limit=tokens_limit,
            reset_requests=reset_requests,
            reset_tokens=reset_tokens,
            timestamp=datetime.now()
        )

        logger.debug(f"Parsed quota status: {requests_remaining}/{requests_limit} requests, "
                    f"{tokens_remaining}/{tokens_limit} tokens")

        return quota_status

    except Exception as e:
        logger.warning(f"Failed to parse rate limit headers: {e}")
        # Return safe defaults if parsing fails
        return QuotaStatus(
            requests_remaining=0,
            requests_limit=5000,
            tokens_remaining=4000000,  # Default to full tokens
            tokens_limit=4000000,
            reset_requests="unknown",
            reset_tokens="unknown",
            timestamp=datetime.now()
        )


def _parse_header_int(headers: Dict[str, str], key: str, default: int) -> int:
    """Parse integer value from header with graceful fallback."""
    value = headers.get(key)
    if value is None:
        return default

    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        logger.warning(f"Invalid integer in header {key}: {value}")
        return default


def _parse_reset_header(headers: Dict[str, str], key: str) -> str:
    """Parse reset time header, handling various formats."""
    value = headers.get(key, "unknown")

    if value == "unknown":
        return value

    # Try to parse as duration (e.g., "20ms", "5s", "2m")
    duration_match = re.match(r'^(\d+)(ms|s|m|h)$', str(value))
    if duration_match:
        number, unit = duration_match.groups()
        return value  # Return as-is, valid duration format

    # Try to parse as seconds (numeric)
    try:
        seconds = float(value)
        if seconds > 0:
            return str(int(seconds))
    except (ValueError, TypeError):
        pass

    # Try to parse as ISO timestamp
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value  # Valid ISO format
    except (ValueError, TypeError):
        pass

    logger.warning(f"Unknown reset time format in {key}: {value}")
    return "unknown"


def calculate_usage_metrics(quota_status: QuotaStatus, daily_limit: Optional[int] = None,
                          requests_used_today: int = 0) -> QuotaMetrics:
    """
    Calculate quota usage metrics and determine if processing should pause.

    Args:
        quota_status: Current quota status from headers
        daily_limit: Optional daily request limit
        requests_used_today: Number of requests used today

    Returns:
        QuotaMetrics with calculated usage and pause decision
    """
    # Calculate usage percentage based on daily limit
    if daily_limit is not None and daily_limit > 0:
        usage_percentage = (requests_used_today / daily_limit) * 100.0
    else:
        # Use immediate rate limit usage as fallback
        usage_percentage = quota_status.get_requests_usage_percentage()

    # Determine if we should pause
    should_pause = False
    pause_reason = None

    # Check daily limit threshold
    if daily_limit is not None and usage_percentage >= 80.0:
        should_pause = True
        pause_reason = f"Daily quota {usage_percentage:.1f}% used (limit: {daily_limit})"

    # Check immediate rate limits (95% threshold for safety)
    elif quota_status.get_requests_usage_percentage() >= 95.0:
        should_pause = True
        pause_reason = f"Rate limit {quota_status.get_requests_usage_percentage():.1f}% used"

    elif quota_status.get_tokens_usage_percentage() >= 95.0:
        should_pause = True
        pause_reason = f"Token limit {quota_status.get_tokens_usage_percentage():.1f}% used"

    return QuotaMetrics(
        requests_used_today=requests_used_today,
        daily_limit=daily_limit,
        usage_percentage=usage_percentage,
        should_pause=should_pause,
        pause_reason=pause_reason
    )


def should_pause_processing(quota_metrics: QuotaMetrics, threshold: float = 0.8) -> Tuple[bool, str]:
    """
    Determine if processing should pause based on quota metrics and threshold.

    Args:
        quota_metrics: Current quota metrics
        threshold: Pause threshold as decimal (0.8 = 80%)

    Returns:
        Tuple of (should_pause, reason)
    """
    threshold_percent = threshold * 100.0

    # Use the pause decision from quota metrics
    if quota_metrics.should_pause:
        return True, quota_metrics.pause_reason or "Quota threshold exceeded"

    # Double-check against custom threshold
    if quota_metrics.usage_percentage >= threshold_percent:
        reason = f"Usage {quota_metrics.usage_percentage:.1f}% exceeds threshold {threshold_percent:.1f}%"
        return True, reason

    return False, "Within quota limits"


class QuotaMonitor:
    """
    Thread-safe quota monitor for tracking API usage and managing pause/resume decisions.
    """

    def __init__(self, daily_limit_requests: Optional[int] = None, pause_threshold: float = 0.8):
        """
        Initialize quota monitor.

        Args:
            daily_limit_requests: Optional daily request limit
            pause_threshold: Pause threshold as decimal (0.8 = 80%)
        """
        self.daily_limit_requests = daily_limit_requests
        self.pause_threshold = pause_threshold
        self.requests_used_today = 0
        self.last_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_quota_status: Optional[QuotaStatus] = None
        self.current_quota_metrics: Optional[QuotaMetrics] = None

        # Thread safety
        # Use RLock to allow re-entrant locking when wait_if_paused()
        # triggers resume() while holding the lock.
        self._lock = threading.RLock()

        logger.info(f"QuotaMonitor initialized: daily_limit={daily_limit_requests}, "
                   f"threshold={pause_threshold}")

    def update_from_response(self, headers: Dict[str, str],
                           usage_stats: Optional[Dict[str, Any]] = None) -> QuotaMetrics:
        """
        Update quota state from API response headers and usage stats.

        Args:
            headers: HTTP response headers
            usage_stats: Optional usage statistics from response body

        Returns:
            Updated QuotaMetrics
        """
        with self._lock:
            # Parse headers to get current quota status
            self.current_quota_status = parse_rate_limit_headers(headers, usage_stats)

            # Check if we need to reset daily counter (new day)
            now = datetime.now()
            if now.date() > self.last_reset.date():
                logger.info(f"Resetting daily request counter (was {self.requests_used_today})")
                self.requests_used_today = 0
                self.last_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Increment daily request counter
            self.requests_used_today += 1

            # Calculate current metrics
            self.current_quota_metrics = calculate_usage_metrics(
                self.current_quota_status,
                self.daily_limit_requests,
                self.requests_used_today
            )

            return self.current_quota_metrics

    def should_pause(self) -> Tuple[bool, str]:
        """
        Check if processing should pause based on current quota state.

        Returns:
            Tuple of (should_pause, reason)
        """
        with self._lock:
            if self.current_quota_metrics is None:
                return False, "No quota data available"

            return should_pause_processing(self.current_quota_metrics, self.pause_threshold)

    def can_resume(self) -> bool:
        """
        Check if processing can resume (quota has reset or is below threshold).

        Returns:
            True if processing can resume
        """
        with self._lock:
            should_pause, _ = self.should_pause()
            return not should_pause

    def get_current_metrics(self) -> Optional[QuotaMetrics]:
        """Get current quota metrics (thread-safe)."""
        with self._lock:
            return self.current_quota_metrics

    def get_current_status(self) -> Optional[QuotaStatus]:
        """Get current quota status (thread-safe)."""
        with self._lock:
            return self.current_quota_status


class PauseController:
    """
    Thread-safe pause controller for managing processing pause/resume with events.
    """

    def __init__(self):
        """Initialize pause controller."""
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused
        self._pause_reason: Optional[str] = None
        self._resume_time: Optional[float] = None
        self._lock = threading.Lock()

        logger.debug("PauseController initialized (unpaused)")

    def pause(self, reason: str, resume_at: Optional[float] = None):
        """
        Pause processing with optional resume time.

        Args:
            reason: Reason for pausing
            resume_at: Optional timestamp to automatically resume
        """
        with self._lock:
            self._pause_event.clear()
            self._pause_reason = reason
            self._resume_time = resume_at

        if resume_at:
            resume_datetime = datetime.fromtimestamp(resume_at)
            logger.warning(f"PAUSED: {reason} - Will resume at {resume_datetime}")
        else:
            logger.warning(f"PAUSED: {reason} - Manual resume required")

    def resume(self, reason: str = "Manual resume"):
        """
        Resume processing.

        Args:
            reason: Reason for resuming
        """
        with self._lock:
            self._pause_event.set()
            self._pause_reason = None
            self._resume_time = None

        logger.info(f"RESUMED: {reason}")

    def wait_if_paused(self, timeout: Optional[float] = None):
        """
        Wait if currently paused, with optional timeout.

        Args:
            timeout: Maximum time to wait in seconds
        """
        # Check if we should auto-resume immediately
        with self._lock:
            if (self._resume_time is not None and
                time.time() >= self._resume_time and
                not self._pause_event.is_set()):
                self.resume("Auto-resume time reached")
                return

        # If we have a resume time, adjust timeout to not wait longer than needed
        adjusted_timeout = timeout
        with self._lock:
            if self._resume_time is not None and timeout is not None:
                time_until_resume = max(0, self._resume_time - time.time())
                adjusted_timeout = min(timeout, time_until_resume + 0.01)  # Small buffer

        # Wait for pause event to be set (unpaused)
        if not self._pause_event.wait(adjusted_timeout):
            # Check again if we should auto-resume after timeout
            with self._lock:
                if (self._resume_time is not None and
                    time.time() >= self._resume_time and
                    not self._pause_event.is_set()):
                    self.resume("Auto-resume time reached")
                elif adjusted_timeout == timeout:
                    logger.warning("Pause wait timeout reached")

    def is_paused(self) -> bool:
        """Check if currently paused."""
        return not self._pause_event.is_set()

    def get_pause_reason(self) -> Optional[str]:
        """Get current pause reason."""
        with self._lock:
            return self._pause_reason
