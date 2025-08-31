"""
Database operations module.

This module handles database write operations including artist bio updates,
retry logic with exponential backoff, and table name resolution.
"""

import logging
import time
from functools import wraps
from typing import Optional

from ..models import DatabaseResult
from .utils import classify_database_error, validate_uuid

try:
    import psycopg3
except ImportError:
    psycopg3 = None

logger = logging.getLogger(__name__)


def get_table_name(test_mode: bool = False) -> str:
    """
    Get the table name based on environment/mode.
    
    Args:
        test_mode: If True, return test table name
        
    Returns:
        Table name string
    """
    return "test_artists" if test_mode else "artists"


def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator to retry database operations with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    error_type = classify_database_error(e)
                    
                    # Don't retry permanent or systemic errors
                    if error_type in ["permanent", "systemic"]:
                        logger.warning(f"Database error ({error_type}): {str(e)} - not retrying")
                        break
                        
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.error(f"Database operation failed after {max_retries} retries: {str(e)}")
                        break
                        
                    # Calculate delay with exponential backoff
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)} - retrying in {delay:.1f}s")
                    time.sleep(delay)
            
            # If we get here, all retries failed - return error result
            error_type = classify_database_error(last_exception)
            return DatabaseResult(
                success=False,
                rows_affected=0,
                error=f"Database operation failed ({error_type}): {str(last_exception)}"
            )
            
        return wrapper
    return decorator


@retry_with_exponential_backoff(max_retries=3)
def update_artist_bio(
    connection: "psycopg3.Connection",
    artist_id: str,
    bio: str,
    skip_existing: bool = False,
    test_mode: bool = False,
    worker_id: str = "main"
) -> DatabaseResult:
    """
    Update artist bio in database with retry logic.
    
    Args:
        connection: Database connection
        artist_id: UUID of the artist
        bio: Bio text to update
        skip_existing: If True, only update if bio is NULL
        test_mode: If True, use test table
        worker_id: Worker thread identifier for logging
        
    Returns:
        DatabaseResult with operation status
    """
    if connection is None:
        return DatabaseResult(
            success=False,
            rows_affected=0,
            error="Database connection is None"
        )
    
    # Validate UUID format
    if not validate_uuid(artist_id):
        return DatabaseResult(
            success=False,
            rows_affected=0,
            error=f"Invalid UUID format: {artist_id}"
        )
    
    table_name = get_table_name(test_mode)
    
    try:
        cursor = connection.cursor()
        
        # Build SQL query based on skip_existing flag
        if skip_existing:
            # Only update if bio is NULL
            sql = f"UPDATE {table_name} SET bio = %s WHERE id = %s AND bio IS NULL"
        else:
            # Always update (overwrite existing)
            sql = f"UPDATE {table_name} SET bio = %s WHERE id = %s"
        
        logger.debug(f"[{worker_id}] Executing SQL: {sql}")
        
        # Execute the update
        cursor.execute(sql, (bio, artist_id))
        rows_affected = cursor.rowcount
        
        # Commit the transaction
        connection.commit()
        
        if rows_affected > 0:
            logger.debug(f"[{worker_id}] Updated bio for artist {artist_id} in {table_name}")
            status = "updated"
        else:
            logger.debug(f"[{worker_id}] No rows updated for artist {artist_id} in {table_name} (may not exist or already has bio)")
            status = "skipped"
        
        return DatabaseResult(
            success=True,
            rows_affected=rows_affected,
            error=None
        )
        
    except Exception as e:
        # Rollback on error
        try:
            connection.rollback()
        except:
            pass  # Ignore rollback errors
            
        error_type = classify_database_error(e)
        logger.error(f"[{worker_id}] Database error ({error_type}) updating artist {artist_id}: {str(e)}")
        
        # Let the retry decorator handle this
        raise