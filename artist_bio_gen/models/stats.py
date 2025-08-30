#!/usr/bin/env python3
"""
Statistics Models

This module contains data structures related to processing statistics
and performance metrics.
"""

from typing import NamedTuple


class ProcessingStats(NamedTuple):
    """
    Statistics for processing operations.
    
    Attributes:
        total_artists: Total number of artists to process
        successful_calls: Number of successful API calls
        failed_calls: Number of failed API calls
        skipped_lines: Number of skipped input lines
        error_lines: Number of input lines with errors
        start_time: Processing start timestamp
        end_time: Processing end timestamp
        total_duration: Total processing duration in seconds
        avg_time_per_artist: Average processing time per artist
        api_calls_per_second: API calls per second rate
    """
    
    total_artists: int
    successful_calls: int
    failed_calls: int
    skipped_lines: int
    error_lines: int
    start_time: float
    end_time: float
    total_duration: float
    avg_time_per_artist: float
    api_calls_per_second: float