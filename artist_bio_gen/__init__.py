#!/usr/bin/env python3
"""
Artist Bio Generator Package

A Python package for generating artist biographies using OpenAI's API
with UUID-based artist identification and optional PostgreSQL persistence.

This package provides both a command-line interface and a programmatic API
for processing artist data and generating biographies.
"""

__version__ = "1.0.0"
__author__ = "Artist Bio Generator"
__description__ = "Generate artist biographies using OpenAI API with database persistence"

# Import models for public API
from .models import (
    ArtistData,
    ParseResult,
    ApiResponse,
    DatabaseConfig,
    DatabaseResult,
    ProcessingStats,
)

# Import constants for public API
from .constants import (
    EXIT_SUCCESS,
    EXIT_INPUT_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_API_FAILURES,
    EXIT_INTERRUPTED,
    EXIT_UNEXPECTED_ERROR,
    DEFAULT_POOL_SIZE,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_QUERY_TIMEOUT,
)

# Public API exports
__all__ = [
    "__version__",
    "__author__", 
    "__description__",
    # Data models
    "ArtistData",
    "ParseResult",
    "ApiResponse", 
    "DatabaseConfig",
    "DatabaseResult",
    "ProcessingStats",
    # Constants
    "EXIT_SUCCESS",
    "EXIT_INPUT_ERROR",
    "EXIT_CONFIG_ERROR",
    "EXIT_API_FAILURES",
    "EXIT_INTERRUPTED", 
    "EXIT_UNEXPECTED_ERROR",
    "DEFAULT_POOL_SIZE",
    "DEFAULT_MAX_OVERFLOW",
    "DEFAULT_CONNECTION_TIMEOUT",
    "DEFAULT_QUERY_TIMEOUT",
]