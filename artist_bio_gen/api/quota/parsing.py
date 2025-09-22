#!/usr/bin/env python3
"""
Quota Header Parsing Utilities

This module contains utilities for parsing OpenAI API rate limit headers
and calculating usage metrics.
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from ...models.quota import QuotaStatus, QuotaMetrics

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