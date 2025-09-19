"""
API operations module.

This module handles OpenAI API calls and response processing
for the artist bio generator application.
"""

import logging
import time
from typing import Optional, Tuple

from ..core.pipeline import ResponseProcessor, RequestContext
from ..models import ArtistData, ApiResponse
from .utils import retry_with_exponential_backoff
from .quota import QuotaMonitor, PauseController

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
    quota_monitor: Optional[QuotaMonitor] = None,
    pause_controller: Optional[PauseController] = None,
    output_path: Optional[str] = None,
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
        quota_monitor: Optional quota monitor instance
        pause_controller: Optional pause controller instance
        output_path: Optional path to stream JSONL output

    Returns:
        Tuple of (ApiResponse with the result or error information, duration in seconds)
    """
    # Log start of processing
    logger.info(f"[{worker_id}] 🚀 Starting processing: {artist.name}")

    # Create request context
    context = RequestContext(
        worker_id=worker_id,
        prompt_id=prompt_id,
        version=version,
        output_path=output_path,
        skip_existing=skip_existing,
        test_mode=test_mode,
        db_pool=db_pool,
        quota_monitor=quota_monitor,
        pause_controller=pause_controller,
    )

    # Create response processor with configured components
    processor = ResponseProcessor(
        quota_monitor=quota_monitor,
        db_pool=db_pool,
    )

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

        # Honor pause controller if provided (gate API calls)
        if pause_controller is not None:
            pause_controller.wait_if_paused()

        # Make the API call with raw response for headers when available
        response = None
        fallback_reason: Optional[str] = None

        try:
            with_raw_response = client.responses.with_raw_response
        except AttributeError as attr_err:
            with_raw_response = None
            fallback_reason = f"with_raw_response attr missing: {attr_err}"

        if with_raw_response is not None:
            try:
                raw = with_raw_response.create(prompt=prompt_config)
            except (AttributeError, NotImplementedError) as raw_err:
                fallback_reason = f"with_raw_response.create unavailable: {raw_err}"
            else:
                response = raw

        if response is None:
            if fallback_reason is not None:
                logger.debug(
                    f"[{worker_id}] Raw response unavailable, falling back: {fallback_reason}"
                )
            response = client.responses.create(prompt=prompt_config)

        # Process response through the unified pipeline
        return processor.process(response, artist, context)

    except Exception as e:
        # Process error through the pipeline (for logging and output streaming)
        return processor.process_error(e, artist, context)
