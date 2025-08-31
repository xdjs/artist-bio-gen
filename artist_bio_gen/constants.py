#!/usr/bin/env python3
"""
Application Constants

This module contains all configuration constants and exit codes used
throughout the artist bio generator application.
"""

# Exit codes for different failure modes
EXIT_SUCCESS = 0
EXIT_INPUT_ERROR = 2
EXIT_CONFIG_ERROR = 3
EXIT_API_FAILURES = 4
EXIT_INTERRUPTED = 130  # Conventional exit code for Ctrl+C
EXIT_UNEXPECTED_ERROR = 10

# Database connection pool constants
DEFAULT_POOL_SIZE = 4  # Match default worker count
DEFAULT_MAX_OVERFLOW = 8  # Allow burst connections
DEFAULT_CONNECTION_TIMEOUT = 30  # seconds
DEFAULT_QUERY_TIMEOUT = 60  # seconds
