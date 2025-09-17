#!/usr/bin/env python3
"""
API package for artist bio generator.

This package provides OpenAI API client management, operations,
and utilities for the artist bio generator application.
"""

from .client import (
    create_openai_client,
)

from .operations import (
    call_openai_api,
)

from .utils import (
    should_retry_error,
    calculate_retry_delay,
    retry_with_exponential_backoff,
)

from .quota import (
    parse_rate_limit_headers,
    calculate_usage_metrics,
    should_pause_processing,
    QuotaMonitor,
    PauseController,
)

__all__ = [
    # Client management
    "create_openai_client",
    # Operations
    "call_openai_api",
    # Utilities
    "should_retry_error",
    "calculate_retry_delay",
    "retry_with_exponential_backoff",
    # Quota management
    "parse_rate_limit_headers",
    "calculate_usage_metrics",
    "should_pause_processing",
    "QuotaMonitor",
    "PauseController",
]
