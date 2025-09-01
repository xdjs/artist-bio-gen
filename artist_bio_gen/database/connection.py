"""
Database connection management module.

This module handles database connection pool creation, connection retrieval,
and connection pool cleanup for the artist bio generator application.
"""

import logging
from typing import Optional

from ..models import DatabaseConfig

try:
    import psycopg as psycopg3
    from psycopg_pool import ConnectionPool
    pool = True  # Mark that pool functionality is available
except ImportError:
    psycopg3 = None
    ConnectionPool = None
    pool = None

logger = logging.getLogger(__name__)


def create_db_connection_pool(config: DatabaseConfig) -> Optional["ConnectionPool"]:
    """
    Create a database connection pool.

    Args:
        config: Database configuration settings

    Returns:
        Connection pool or None if psycopg3 not available

    Raises:
        Exception: If unable to create connection pool
    """
    if psycopg3 is None:
        logger.error(
            "psycopg3 not available. Install with: pip install psycopg3[binary]"
        )
        return None

    try:
        logger.info(
            f"Creating database connection pool (size={config.pool_size}, max_overflow={config.max_overflow})"
        )

        # Create connection pool
        connection_pool = ConnectionPool(
            config.url,
            min_size=1,  # Minimum connections to keep open
            max_size=config.pool_size + config.max_overflow,
            open=True,  # Open the pool immediately
        )

        logger.info("Database connection pool created successfully")
        return connection_pool

    except Exception as e:
        logger.error(f"Failed to create database connection pool: {str(e)}")
        raise


def get_db_connection(pool: "ConnectionPool") -> Optional["psycopg3.Connection"]:
    """
    Get a database connection from the pool.

    Args:
        pool: Database connection pool

    Returns:
        Database connection or None if failed
    """
    if pool is None:
        logger.error("Connection pool is None")
        return None

    try:
        connection = pool.getconn()
        logger.debug("Retrieved database connection from pool")
        return connection

    except Exception as e:
        logger.error(f"Failed to get database connection from pool: {str(e)}")
        return None


def release_db_connection(pool: "ConnectionPool", connection: Optional["psycopg3.Connection"]) -> None:
    """
    Return a database connection to the pool.

    Args:
        pool: Database connection pool
        connection: Connection to return (ignored if None)
    """
    if pool is None or connection is None:
        return

    try:
        pool.putconn(connection)
        logger.debug("Returned database connection to pool")
    except Exception as e:
        logger.warning(f"Failed to return connection to pool: {str(e)}")


def close_db_connection_pool(pool: "ConnectionPool") -> None:
    """
    Close the database connection pool.

    Args:
        pool: Database connection pool to close
    """
    if pool is None:
        logger.debug("Connection pool is None, nothing to close")
        return

    try:
        logger.info("Closing database connection pool")
        pool.close()
        logger.info("Database connection pool closed successfully")

    except Exception as e:
        logger.error(f"Error closing database connection pool: {str(e)}")
