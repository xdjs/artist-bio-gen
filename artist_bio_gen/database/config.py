"""
Database configuration management module.

This module handles database configuration creation, URL validation,
and environment variable management for database connections.
"""

import logging
import os
from typing import Optional
from urllib.parse import urlparse

from ..models import DatabaseConfig
from ..constants import (
    DEFAULT_POOL_SIZE,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


def validate_database_url(url: str) -> bool:
    """
    Validate that a database URL has the correct format.

    Args:
        url: Database URL to validate

    Returns:
        True if URL format is valid, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        # Check for required components
        if not parsed.scheme:
            logger.error("Database URL missing scheme (e.g., postgresql://)")
            return False

        if parsed.scheme not in ["postgresql", "postgres"]:
            logger.error(
                f"Database URL scheme '{parsed.scheme}' not supported. Use 'postgresql://' or 'postgres://'"
            )
            return False

        if not parsed.hostname:
            logger.error("Database URL missing hostname")
            return False

        if not parsed.username:
            logger.error("Database URL missing username")
            return False

        if not parsed.path or parsed.path == "/":
            logger.error("Database URL missing database name")
            return False

        return True

    except Exception as e:
        logger.error(f"Invalid database URL format: {str(e)}")
        return False


def create_database_config(
    url: str,
    pool_size: Optional[int] = None,
    max_overflow: Optional[int] = None,
    connection_timeout: Optional[int] = None,
    query_timeout: Optional[int] = None,
    test_mode: bool = False,
) -> Optional[DatabaseConfig]:
    """
    Create a database configuration with validation.

    Args:
        url: Database connection URL
        pool_size: Number of connections in pool (default: DEFAULT_POOL_SIZE)
        max_overflow: Maximum overflow connections (default: DEFAULT_MAX_OVERFLOW)
        connection_timeout: Connection timeout in seconds (default: DEFAULT_CONNECTION_TIMEOUT)
        query_timeout: Query timeout in seconds (default: DEFAULT_QUERY_TIMEOUT)
        test_mode: Whether this is for testing (affects defaults)

    Returns:
        DatabaseConfig object or None if validation fails
    """
    if not validate_database_url(url):
        return None

    # Use defaults if not specified
    final_pool_size = pool_size if pool_size is not None else DEFAULT_POOL_SIZE
    final_max_overflow = (
        max_overflow if max_overflow is not None else DEFAULT_MAX_OVERFLOW
    )
    final_connection_timeout = (
        connection_timeout
        if connection_timeout is not None
        else DEFAULT_CONNECTION_TIMEOUT
    )
    final_query_timeout = (
        query_timeout if query_timeout is not None else DEFAULT_QUERY_TIMEOUT
    )

    # Test mode no longer restricts pool size - use full defaults

    # Validate configuration values
    if final_pool_size < 1:
        logger.error(f"Pool size must be at least 1, got {final_pool_size}")
        return None

    if final_max_overflow < 0:
        logger.error(f"Max overflow must be non-negative, got {final_max_overflow}")
        return None

    if final_connection_timeout < 1:
        logger.error(
            f"Connection timeout must be at least 1 second, got {final_connection_timeout}"
        )
        return None

    if final_query_timeout < 1:
        logger.error(
            f"Query timeout must be at least 1 second, got {final_query_timeout}"
        )
        return None

    return DatabaseConfig(
        url=url,
        pool_size=final_pool_size,
        max_overflow=final_max_overflow,
        connection_timeout=final_connection_timeout,
        query_timeout=final_query_timeout,
    )


def get_database_url_from_env(test_mode: bool = False) -> Optional[str]:
    """
    Get database URL from environment variables.

    Args:
        test_mode: Unused parameter (kept for backward compatibility)

    Returns:
        Database URL string or None if not found
    """
    # Always use standard DATABASE_URL regardless of test mode
    url = os.getenv("DATABASE_URL")
    if url:
        logger.debug("Using DATABASE_URL from environment")
        return url

    logger.error("No database URL found. Set DATABASE_URL environment variable.")
    return None
