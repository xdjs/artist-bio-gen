"""
API operations module.

This module handles OpenAI API calls and response processing
for the artist bio generator application.
"""

import logging
import time
from typing import Optional, Tuple

from ..models import ArtistData, ApiResponse
from ..utils import strip_trailing_citations
from ..utils.logging import log_transaction_success, log_transaction_failure
from ..database import update_artist_bio, get_db_connection, release_db_connection
from .utils import retry_with_exponential_backoff

try:
    from openai import OpenAI
    import psycopg3
except ImportError:
    OpenAI = None
    psycopg3 = None

logger = logging.getLogger(__name__)


@retry_with_exponential_backoff(max_retries=5, base_delay=0.5, max_delay=4.0)
def call_openai_api(
    client: "OpenAI",
    artist: ArtistData,
    prompt_id: str,
    version: Optional[str] = None,
    worker_id: str = "main",
    db_pool: Optional["ConnectionPool"] = None,
    skip_existing: bool = False,
    test_mode: bool = False,
) -> Tuple[ApiResponse, float]:
    """
    Make an API call to OpenAI Responses API for a single artist and optionally update database.

    Args:
        client: Initialized OpenAI client
        artist: Artist data to process
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        worker_id: Unique identifier for the worker thread
        db_pool: Database connection pool for writing bio (optional)
        skip_existing: If True, skip database update if bio already exists
        test_mode: If True, use test database table

    Returns:
        Tuple of (ApiResponse with the result or error information, duration in seconds)
    """
    start_time = time.time()

    # Log start of processing
    logger.info(f"[{worker_id}] 🚀 Starting processing: {artist.name}")

    try:
        # Build variables dictionary
        variables = {
            "artist_name": artist.name,
            "artist_data": (
                artist.data if artist.data else "No additional data provided"
            ),
        }

        # Build prompt configuration
        prompt_config = {"id": prompt_id, "variables": variables}
        if version:
            prompt_config["version"] = version

        logger.debug(f"[{worker_id}] Calling API for artist: {artist.name}")

        # Make the API call
        response = client.responses.create(prompt=prompt_config)

        # Extract and clean response text
        raw_text = response.output_text
        cleaned_text = strip_trailing_citations(raw_text)
        if cleaned_text != raw_text:
            logger.info(
                f"[{worker_id}] ✂️ Stripped trailing citations from API response for {artist.name}"
            )
        response_text = cleaned_text
        response_id = response.id
        created = int(response.created_at)

        # Calculate timing
        end_time = time.time()
        duration = end_time - start_time

        # Attempt database write if pool provided
        db_status = "null"  # Default status when no database operation
        if db_pool is not None:
            db_connection = None
            try:
                # Get database connection just before database operation
                db_connection = get_db_connection(db_pool)
                if db_connection is None:
                    db_status = "error"
                    logger.warning(f"[{worker_id}] 💥 Failed to get database connection for {artist.name}")
                else:
                    db_result = update_artist_bio(
                        connection=db_connection,
                        artist_id=artist.artist_id,
                        bio=response_text,
                        skip_existing=skip_existing,
                        test_mode=test_mode,
                        worker_id=worker_id,
                    )

                    if db_result.success:
                        if db_result.rows_affected > 0:
                            db_status = "updated"
                            logger.debug(
                                f"[{worker_id}] 💾 Database updated for {artist.name}"
                            )
                        else:
                            db_status = "skipped"
                            logger.debug(
                                f"[{worker_id}] ⏭️ Database update skipped for {artist.name}"
                            )
                    else:
                        db_status = "error"
                        logger.warning(
                            f"[{worker_id}] 💥 Database update failed for {artist.name}: {db_result.error}"
                        )

            except Exception as db_error:
                db_status = "error"
                logger.error(
                    f"[{worker_id}] 💥 Database update error for {artist.name}: {str(db_error)}"
                )
            finally:
                # Always release the database connection back to the pool
                if db_connection is not None:
                    release_db_connection(db_pool, db_connection)
        
        # Log structured transaction information for database operations
        if db_pool is not None:
            if db_status in ["updated", "skipped"]:
                # Log successful transaction (including skipped as successful completion)
                log_transaction_success(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    worker_id=worker_id,
                    processing_duration=duration,
                    db_status=db_status,
                    response_id=response_id,
                    timestamp=end_time,
                    logger=logger
                )
            elif db_status == "error":
                # Log failed database transaction
                log_transaction_failure(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    worker_id=worker_id,
                    processing_duration=duration,
                    error_message=f"Database operation failed: {db_status}",
                    timestamp=end_time,
                    logger=logger
                )

        api_response = ApiResponse(
            artist_id=artist.artist_id,
            artist_name=artist.name,
            artist_data=artist.data,
            response_text=response_text,
            response_id=response_id,
            created=created,
            db_status=db_status,
        )

        logger.info(
            f"[{worker_id}] ✅ Completed processing: {artist.name} ({duration:.2f}s) [DB: {db_status}]"
        )
        return api_response, duration

    except Exception as e:
        # Calculate timing even for errors
        end_time = time.time()
        duration = end_time - start_time

        exc_name = type(e).__name__
        error_msg = f"API call failed for artist '{artist.name}' [{exc_name}]: {str(e)}"

        api_response = ApiResponse(
            artist_id=artist.artist_id,
            artist_name=artist.name,
            artist_data=artist.data,
            response_text="",
            response_id="",
            created=0,
            db_status="null",  # No database operation on API error
            error=error_msg,
        )

        # Log transaction failure for complete API errors
        log_transaction_failure(
            artist_id=artist.artist_id,
            artist_name=artist.name,
            worker_id=worker_id,
            processing_duration=duration,
            error_message=error_msg,
            timestamp=end_time,
            logger=logger
        )

        logger.error(
            f"[{worker_id}] ❌ Failed processing: {artist.name} ({duration:.2f}s) - {error_msg}"
        )
        return api_response, duration
