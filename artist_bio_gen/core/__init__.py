#!/usr/bin/env python3
"""
Core package for artist bio generator.

This package provides core business logic including input parsing,
processing coordination, and output generation for the artist bio generator.
"""

from .parser import (
    parse_input_file,
)

from .output import (
    write_jsonl_output,
)

from .processor import (
    process_artists_concurrent,
    log_progress_update,
    log_processing_start,
    log_processing_summary,
    calculate_processing_stats,
)

__all__ = [
    # Input parsing
    "parse_input_file",
    # Output generation
    "write_jsonl_output",
    # Processing coordination
    "process_artists_concurrent",
    "log_progress_update",
    "log_processing_start",
    "log_processing_summary",
    "calculate_processing_stats",
]
