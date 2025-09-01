#!/usr/bin/env python3
"""
Database package for artist bio generator.

This package provides database connection management, configuration,
operations, and utilities for the artist bio generator application.
"""

from .connection import (
    create_db_connection_pool,
    get_db_connection,
    close_db_connection_pool,
)

from .config import (
    validate_database_url,
    create_database_config,
)

from .operations import (
    update_artist_bio,
    get_table_name,
    retry_with_exponential_backoff,
)

from .utils import (
    classify_database_error,
    validate_uuid,
)

__all__ = [
    # Connection management
    "create_db_connection_pool",
    "get_db_connection",
    "close_db_connection_pool",
    # Configuration
    "validate_database_url",
    "create_database_config",
    # Operations
    "update_artist_bio",
    "get_table_name",
    "retry_with_exponential_backoff",
    # Utilities
    "classify_database_error",
    "validate_uuid",
]
