#!/usr/bin/env python3
"""
Quota Management API Module - Legacy Re-exports

This module maintains backward compatibility by re-exporting from the new
quota package structure. New code should import directly from the quota
submodules or package.

DEPRECATED: This file is maintained for backward compatibility only.
Import from artist_bio_gen.api.quota instead.
"""

# Re-export everything from the new quota package for backward compatibility
from .quota import (
    parse_rate_limit_headers,
    calculate_usage_metrics,
    should_pause_processing,
    QuotaMonitor,
    PauseController,
)

__all__ = [
    "parse_rate_limit_headers",
    "calculate_usage_metrics",
    "should_pause_processing",
    "QuotaMonitor",
    "PauseController",
]