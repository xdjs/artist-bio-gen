"""
Processing coordination module.

This module handles concurrent processing coordination, progress tracking,
and statistics calculation for the artist bio generator application.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from ..models import ArtistData, ApiResponse, ProcessingStats
from ..api import call_openai_api
from ..utils import create_progress_bar
from ..database import get_db_connection, release_db_connection
from .output import append_jsonl_response, initialize_jsonl_output

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


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


def process_artists_concurrent(
    artists: List[ArtistData],
    client: "OpenAI",
    prompt_id: str,
    version: Optional[str],
    max_workers: int,
    db_pool: Optional[object] = None,
    test_mode: bool = False,
    output_path: Optional[str] = None,
    stream_output: bool = False,
) -> Tuple[int, int, List[ApiResponse]]:
    """
    Process artists concurrently using ThreadPoolExecutor with enhanced error isolation.

    Args:
        artists: List of artists to process
        client: Initialized OpenAI client
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        max_workers: Maximum number of concurrent workers
        db_pool: Database connection pool for bio updates (optional)
        test_mode: If True, use test_artists table
        output_path: Path to JSONL output file for streaming writes (optional)
        stream_output: If True, write responses to JSONL immediately after DB commit

    Returns:
        Tuple of (successful_calls, failed_calls, all_responses)
        Note: If stream_output=True, all_responses will be empty to save memory
    """
    successful_calls = 0
    failed_calls = 0
    all_responses = []

    # Initialize streaming output file if streaming is enabled
    if stream_output and output_path:
        try:
            initialize_jsonl_output(output_path, overwrite_existing=True)
            logger.info(f"Initialized streaming JSONL output: {output_path}")
        except Exception as e:
            logger.error(f"Failed to initialize streaming output file: {e}")
            # Continue without streaming rather than failing completely
            stream_output = False

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
        future_to_connection = {}
        for i, artist in enumerate(artists):
            worker_id = f"W{i % max_workers + 1:02d}"  # W01, W02, W03, etc.
            
            # Get database connection if pool is provided
            db_connection = None
            if db_pool is not None:
                try:
                    db_connection = get_db_connection(db_pool)
                except Exception as e:
                    logger.warning(f"Failed to get database connection for {artist.name}: {e}")
            
            future = executor.submit(
                call_openai_api, 
                client, 
                artist, 
                prompt_id, 
                version, 
                worker_id,
                db_connection,
                False,  # skip_existing
                test_mode
            )
            future_to_artist[future] = artist
            future_to_worker[future] = worker_id
            future_to_connection[future] = db_connection

        # Process completed tasks as they finish
        for future in as_completed(future_to_artist):
            artist = future_to_artist[future]
            worker_id = future_to_worker[future]
            try:
                api_response, duration = future.result()
                
                # Only accumulate responses in memory if not streaming (to save memory)
                if not stream_output:
                    all_responses.append(api_response)

                if api_response.error:
                    failed_calls += 1
                    log_progress_update(
                        successful_calls + failed_calls,
                        len(artists),
                        artist.name,
                        False,
                        duration,
                        worker_id,
                    )
                else:
                    successful_calls += 1
                    
                    # Stream to JSONL file immediately if streaming is enabled
                    if stream_output and output_path:
                        try:
                            append_jsonl_response(api_response, output_path, prompt_id, version)
                            logger.debug(f"Streamed response for '{artist.name}' to {output_path}")
                        except Exception as e:
                            logger.error(f"Failed to stream response for '{artist.name}': {e}")
                    
                    log_progress_update(
                        successful_calls + failed_calls,
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
                
                # Only accumulate responses in memory if not streaming
                if not stream_output:
                    all_responses.append(error_response)
                
                # Stream error responses too if streaming is enabled
                if stream_output and output_path:
                    try:
                        append_jsonl_response(error_response, output_path, prompt_id, version)
                        logger.debug(f"Streamed error response for '{artist.name}' to {output_path}")
                    except Exception as stream_e:
                        logger.error(f"Failed to stream error response for '{artist.name}': {stream_e}")
                
                log_progress_update(
                    successful_calls + failed_calls, len(artists), artist.name, False, 0.0, worker_id
                )
                logger.error(
                    f"[{worker_id}] Thread error processing artist '{artist.name}': {error_msg}"
                )
            finally:
                # Always return DB connection to the pool if it was acquired
                if db_pool is not None:
                    try:
                        release_db_connection(db_pool, future_to_connection.get(future))
                    except Exception:
                        pass

            # Log periodic progress updates during concurrent processing
            current_time = time.time()
            total_processed = successful_calls + failed_calls
            if (
                total_processed % progress_interval == 0
                or total_processed == len(artists)
                or current_time - last_progress_time >= 5.0
            ):  # At least every 5 seconds

                elapsed_time = current_time - last_progress_time
                current_rate = (
                    total_processed / elapsed_time if elapsed_time > 0 else 0
                )
                remaining_artists = len(artists) - total_processed
                estimated_remaining_time = (
                    remaining_artists / current_rate if current_rate > 0 else 0
                )

                logger.info(
                    f"📊 Concurrent Progress: {total_processed}/{len(artists)} artists processed "
                    f"({(total_processed/len(artists)*100):.1f}%) - "
                    f"Rate: {current_rate:.2f} artists/sec - "
                    f"ETA: {estimated_remaining_time:.0f}s remaining"
                )
                last_progress_time = current_time

    logger.info(
        f"Concurrent processing completed: {successful_calls} successful, {failed_calls} failed"
    )
    return successful_calls, failed_calls, all_responses
