#!/usr/bin/env python3
"""
Artist Bio Generator using OpenAI Responses API

This script processes CSV-like input files containing artist information
and uses the OpenAI Responses API to generate artist bios using reusable prompts.
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Any
from urllib.parse import urlparse

# Import data models
from .models import (
    ArtistData,
    ParseResult,
    ApiResponse,
    DatabaseConfig,
    DatabaseResult,
    ProcessingStats,
)

# Import constants
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

# Import database functions
from .database import (
    create_db_connection_pool,
    get_db_connection,
    close_db_connection_pool,
    validate_database_url,
    create_database_config,
    get_database_url_from_env,
    update_artist_bio,
    get_table_name,
    classify_database_error,
    validate_uuid,
)

# Import API functions
from .api import (
    create_openai_client,
    call_openai_api,
    should_retry_error,
    calculate_retry_delay,
    retry_with_exponential_backoff,
)

# Import core functions
from .core import (
    parse_input_file,
    write_jsonl_output,
    process_artists_concurrent,
    log_progress_update,
    log_processing_start,
    log_processing_summary,
    calculate_processing_stats,
)

# Import CLI functions
from .cli import (
    main,
    create_argument_parser,
)

# Import utilities
from .utils import (
    setup_logging,
    create_progress_bar,
    apply_environment_defaults,
    _is_output_path_writable,
)

# Import OpenAI for type annotations
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import psycopg3
    from psycopg3 import pool
except ImportError:
    psycopg3 = None
    pool = None

# Load environment variables from .env.local file
try:
    from dotenv import load_dotenv

    load_dotenv(".env.local")
except ImportError:
    # dotenv not available, continue without it
    pass


# Configure logging
setup_logging()
logger = logging.getLogger("__main__")

# CLI Utility Functions




def log_processing_start(
    total_artists: int, input_file: str, prompt_id: str, max_workers: int
) -> float:
    """
    Log the start of processing with configuration details.

    Args:
        total_artists: Total number of artists to process
        input_file: Path to input file
        prompt_id: OpenAI prompt ID
        max_workers: Maximum number of concurrent workers

    Returns:
        Start timestamp for timing calculations
    """
    start_time = time.time()
    start_datetime = datetime.fromtimestamp(start_time)

    logger.info("=" * 70)
    logger.info("ARTIST BIO GENERATION - PROCESSING STARTED")
    logger.info("=" * 70)
    logger.info(f"Start time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Prompt ID: {prompt_id}")
    logger.info(f"Total artists to process: {total_artists}")
    logger.info(f"Max concurrent workers: {max_workers}")
    logger.info("=" * 70)

    return start_time




def log_progress_update(
    current: int,
    total: int,
    artist_name: str,
    success: bool,
    duration: float,
    worker_id: str = "main",
):
    """
    Log progress update for individual artist processing.

    Args:
        current: Current artist number (1-based)
        total: Total number of artists
        artist_name: Name of the artist being processed
        success: Whether the processing was successful
        duration: Time taken for this artist
        worker_id: Unique identifier for the worker thread
    """
    percentage = (current / total) * 100
    status_icon = "✅" if success else "❌"
    status_text = "SUCCESS" if success else "FAILED"
    progress_bar = create_progress_bar(current, total)

    logger.info(
        f"{progress_bar} [{current:3d}/{total:3d}] ({percentage:5.1f}%) [{worker_id}] {status_icon} {artist_name} - {status_text} ({duration:.2f}s)"
    )


def log_processing_summary(stats: ProcessingStats):
    """
    Log comprehensive processing summary with statistics.

    Args:
        stats: Processing statistics to log
    """
    end_datetime = datetime.fromtimestamp(stats.end_time)

    logger.info("=" * 70)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 70)
    logger.info(f"End time: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(
        f"Total duration: {stats.total_duration:.2f} seconds ({timedelta(seconds=int(stats.total_duration))})"
    )
    logger.info("")
    logger.info("INPUT STATISTICS:")
    logger.info(f"  Total artists processed: {stats.total_artists}")
    logger.info(f"  Skipped lines (comments/blanks): {stats.skipped_lines}")
    logger.info(f"  Error lines (invalid data): {stats.error_lines}")
    logger.info("")
    logger.info("API CALL STATISTICS:")
    logger.info(f"  Successful calls: {stats.successful_calls}")
    logger.info(f"  Failed calls: {stats.failed_calls}")
    logger.info(
        f"  Success rate: {(stats.successful_calls / stats.total_artists * 100):.1f}%"
    )
    logger.info("")
    logger.info("PERFORMANCE STATISTICS:")
    logger.info(f"  Average time per artist: {stats.avg_time_per_artist:.2f}s")
    logger.info(f"  API calls per second: {stats.api_calls_per_second:.2f}")

    if stats.successful_calls > 0:
        estimated_total_time = stats.avg_time_per_artist * stats.total_artists
        logger.info(f"  Estimated total time: {estimated_total_time:.2f}s")

    # Calculate efficiency metrics
    if stats.total_artists > 0:
        processing_efficiency = (stats.successful_calls / stats.total_artists) * 100
        logger.info(f"  Processing efficiency: {processing_efficiency:.1f}%")

    # Time breakdown
    if stats.total_duration > 0:
        successful_time = stats.avg_time_per_artist * stats.successful_calls
        failed_time = stats.total_duration - successful_time
        logger.info(f"  Time spent on successful calls: {successful_time:.2f}s")
        if failed_time > 0:
            logger.info(f"  Time spent on failed calls: {failed_time:.2f}s")

    logger.info("=" * 70)

    # Log warnings for any issues
    if stats.failed_calls > 0:
        logger.warning(f"⚠️  {stats.failed_calls} artists failed to process")

    if stats.error_lines > 0:
        logger.warning(f"⚠️  {stats.error_lines} lines had parsing errors")

    if stats.skipped_lines > 0:
        logger.info(f"ℹ️  {stats.skipped_lines} lines were skipped (comments/blanks)")


def process_artists_concurrent(
    artists: List[ArtistData],
    client: OpenAI,
    prompt_id: str,
    version: Optional[str],
    max_workers: int,
) -> Tuple[int, int, List[ApiResponse]]:
    """
    Process artists concurrently using ThreadPoolExecutor with enhanced error isolation.

    Args:
        artists: List of artists to process
        client: Initialized OpenAI client
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        max_workers: Maximum number of concurrent workers

    Returns:
        Tuple of (successful_calls, failed_calls, all_responses)
    """
    successful_calls = 0
    failed_calls = 0
    all_responses = []

    logger.info(f"Starting concurrent processing with {max_workers} workers")

    # Track progress for periodic updates
    progress_interval = max(
        1, len(artists) // 10
    )  # Log every 10% or at least every artist
    last_progress_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks with unique worker IDs
        future_to_artist = {}
        future_to_worker = {}
        for i, artist in enumerate(artists):
            worker_id = f"W{i % max_workers + 1:02d}"  # W01, W02, W03, etc.
            future = executor.submit(
                call_openai_api, client, artist, prompt_id, version, worker_id
            )
            future_to_artist[future] = artist
            future_to_worker[future] = worker_id

        # Process completed tasks as they finish
        for future in as_completed(future_to_artist):
            artist = future_to_artist[future]
            worker_id = future_to_worker[future]
            try:
                api_response, duration = future.result()
                all_responses.append(api_response)

                if api_response.error:
                    failed_calls += 1
                    log_progress_update(
                        len(all_responses),
                        len(artists),
                        artist.name,
                        False,
                        duration,
                        worker_id,
                    )
                else:
                    successful_calls += 1
                    log_progress_update(
                        len(all_responses),
                        len(artists),
                        artist.name,
                        True,
                        duration,
                        worker_id,
                    )
                    # Print response to stdout
                    print(api_response.response_text)

            except Exception as e:
                # Enhanced error isolation - each thread failure is isolated
                failed_calls += 1
                exc_name = type(e).__name__
                error_msg = f"Concurrent processing error [{exc_name}]: {str(e)}"

                error_response = ApiResponse(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    artist_data=artist.data,
                    response_text="",
                    response_id="",
                    created=0,
                    error=error_msg,
                )
                all_responses.append(error_response)
                log_progress_update(
                    len(all_responses), len(artists), artist.name, False, 0.0, worker_id
                )
                logger.error(
                    f"[{worker_id}] Thread error processing artist '{artist.name}': {error_msg}"
                )

            # Log periodic progress updates during concurrent processing
            current_time = time.time()
            if (
                len(all_responses) % progress_interval == 0
                or len(all_responses) == len(artists)
                or current_time - last_progress_time >= 5.0
            ):  # At least every 5 seconds

                elapsed_time = current_time - last_progress_time
                current_rate = (
                    len(all_responses) / elapsed_time if elapsed_time > 0 else 0
                )
                remaining_artists = len(artists) - len(all_responses)
                estimated_remaining_time = (
                    remaining_artists / current_rate if current_rate > 0 else 0
                )

                logger.info(
                    f"📊 Concurrent Progress: {len(all_responses)}/{len(artists)} artists processed "
                    f"({(len(all_responses)/len(artists)*100):.1f}%) - "
                    f"Rate: {current_rate:.2f} artists/sec - "
                    f"ETA: {estimated_remaining_time:.0f}s remaining"
                )
                last_progress_time = current_time

    logger.info(
        f"Concurrent processing completed: {successful_calls} successful, {failed_calls} failed"
    )
    return successful_calls, failed_calls, all_responses


def write_jsonl_output(responses: List[ApiResponse], output_path: str, prompt_id: str, version: Optional[str] = None) -> None:
    """
    Write all API responses to a JSONL output file.
    
    Args:
        responses: List of API responses to write
        output_path: Path to the output JSONL file
        prompt_id: OpenAI prompt ID used for requests
        version: Optional prompt version used for requests
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for response in responses:
                # Build the JSONL record
                record = {
                    "artist_name": response.artist_name,
                    "request": {
                        "prompt_id": prompt_id,
                        "variables": {
                            "artist_name": response.artist_name,
                            "artist_data": response.artist_data if response.artist_data else "No additional data provided"
                        }
                    },
                    "response_text": response.response_text,
                    "response_id": response.response_id,
                    "created": response.created,
                    "error": response.error
                }
                
                # Add version to request if provided
                if version:
                    record["request"]["version"] = version
                
                # Omit artist_data from top level if empty (as per spec)
                if response.artist_data:
                    record["artist_data"] = response.artist_data
                
                # Write the JSONL record (one JSON object per line)
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        logger.info(f"Successfully wrote {len(responses)} records to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to write JSONL output to {output_path}: {e}")
        raise


def calculate_processing_stats(
    total_artists: int,
    successful_calls: int,
    failed_calls: int,
    skipped_lines: int,
    error_lines: int,
    start_time: float,
    end_time: float,
) -> ProcessingStats:
    """
    Calculate comprehensive processing statistics.

    Args:
        total_artists: Total number of artists
        successful_calls: Number of successful API calls
        failed_calls: Number of failed API calls
        skipped_lines: Number of skipped lines
        error_lines: Number of error lines
        start_time: Processing start timestamp
        end_time: Processing end timestamp

    Returns:
        ProcessingStats object with calculated statistics
    """
    total_duration = end_time - start_time
    avg_time_per_artist = total_duration / total_artists if total_artists > 0 else 0
    api_calls_per_second = total_artists / total_duration if total_duration > 0 else 0

    return ProcessingStats(
        total_artists=total_artists,
        successful_calls=successful_calls,
        failed_calls=failed_calls,
        skipped_lines=skipped_lines,
        error_lines=error_lines,
        start_time=start_time,
        end_time=end_time,
        total_duration=total_duration,
        avg_time_per_artist=avg_time_per_artist,
        api_calls_per_second=api_calls_per_second,
    )


if __name__ == "__main__":
    main()
