#!/usr/bin/env python3
"""
Quota Management API Package

This package provides quota monitoring, header parsing, and pause/resume
functionality for OpenAI API rate limiting management.

The package is organized into focused modules:
- parsing: Header parsing and usage metrics calculation
- monitor: Thread-safe quota monitoring
- controller: Pause/resume controller with events

All public APIs are re-exported here for backward compatibility.
"""

# Import from submodules
from .parsing import (
    parse_rate_limit_headers,
    calculate_usage_metrics,
    should_pause_processing,
)
from .monitor import QuotaMonitor
from .controller import PauseController

# Re-export for backward compatibility
__all__ = [
    # Parsing utilities
    "parse_rate_limit_headers",
    "calculate_usage_metrics",
    "should_pause_processing",
    # Classes
    "QuotaMonitor",
    "PauseController",
]