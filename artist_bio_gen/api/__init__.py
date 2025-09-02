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
    RateLimiter,
    should_retry_error,
    calculate_retry_delay,
    call_with_retry,
)

__all__ = [
    # Client management
    "create_openai_client",
    # Operations
    "call_openai_api",
    # Utilities
    "RateLimiter",
    "should_retry_error",
    "calculate_retry_delay",
    "call_with_retry",
]
