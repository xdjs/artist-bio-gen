#!/usr/bin/env python3
"""
Database Models

This module contains data structures related to database configuration
and operation results.
"""

from typing import Optional, NamedTuple


class DatabaseConfig(NamedTuple):
    """
    Database configuration settings.

    Attributes:
        url: Database connection URL
        pool_size: Number of connections in the pool
        max_overflow: Maximum overflow connections beyond pool_size
        connection_timeout: Timeout for getting connections (seconds)
        query_timeout: Timeout for individual queries (seconds)
    """

    url: str
    pool_size: int = 4  # Match default worker count
    max_overflow: int = 8  # Allow burst connections
    connection_timeout: int = 30  # seconds
    query_timeout: int = 60  # seconds


class DatabaseResult(NamedTuple):
    """
    Result of a database operation.

    Attributes:
        success: Whether the operation succeeded
        rows_affected: Number of rows affected by the operation
        error: Error message if the operation failed
    """

    success: bool
    rows_affected: int
    error: Optional[str] = None
