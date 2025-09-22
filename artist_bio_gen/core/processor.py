"""
Processing coordination module.

This module handles concurrent processing coordination, progress tracking,
and statistics calculation for the artist bio generator application.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from ..models import ArtistData, ApiResponse, ProcessingStats
from ..api import call_openai_api
from ..api.quota import QuotaMonitor, PauseController
from ..utils import create_progress_bar
# Database connection handling now done in call_openai_api
from .output import append_jsonl_response, initialize_jsonl_output
from .resources import ProcessingContext
from .orchestrator import ProcessingOrchestrator
from .progress import BatchProgressReporter

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

# Global tracking for auto-resume timers to prevent resource leaks
_active_timers = []
_timer_lock = threading.Lock()


def _parse_reset_to_timestamp(reset_value: Optional[str]) -> Optional[float]:
    """Convert a quota reset hint into a UNIX timestamp."""

    if not reset_value:
        return None

    reset_str = str(reset_value).strip()
    if reset_str.lower() == "unknown":
        return None

    now = time.time()

    suffix_multipliers = {
        "ms": 0.001,
        "s": 1.0,
        "m": 60.0,
        "h": 3600.0,
    }

    for suffix, multiplier in suffix_multipliers.items():
        if reset_str.endswith(suffix):
            try:
                amount = float(reset_str[: -len(suffix)])
            except ValueError:
                return None

            seconds = amount * multiplier
            if seconds < 0:
                return None
            return now + seconds

    try:
        seconds = float(reset_str)
    except ValueError:
        seconds = None

    if seconds is not None and seconds >= 0:
        return now + seconds

    try:
        reset_dt = datetime.fromisoformat(reset_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    return reset_dt.timestamp()


def _estimate_resume_time(quota_monitor: QuotaMonitor) -> Optional[float]:
    """Estimate when processing can resume based on quota state."""

    status = quota_monitor.get_current_status()
    if status is not None:
        for reset_hint in (status.reset_requests, status.reset_tokens):
            resume_at = _parse_reset_to_timestamp(reset_hint)
            if resume_at is not None:
                return resume_at

    if quota_monitor.daily_limit_requests:
        now = datetime.now()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return next_midnight.timestamp()

    return None


def _schedule_auto_resume(pause_controller: PauseController, resume_at: Optional[float]) -> None:
    """Schedule automatic resume if a resume time is available."""

    if resume_at is None:
        return

    delay = max(0.0, resume_at - time.time())

    if delay <= 0:
        pause_controller.resume("Quota window reset")
        return

    # Cancel any existing timers to prevent resource leaks
    with _timer_lock:
        for existing_timer in _active_timers:
            existing_timer.cancel()
        _active_timers.clear()

        # Create and track the new timer
        timer = threading.Timer(delay, pause_controller.resume, kwargs={"reason": "Quota window reset"})
        timer.daemon = True
        timer.start()
        _active_timers.append(timer)

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
    output_path: str,
    db_pool: Optional[object] = None,
    test_mode: bool = False,
    resume_mode: bool = False,
    daily_request_limit: Optional[int] = None,
    quota_threshold: float = 0.8,
    quota_monitoring: bool = True,
) -> Tuple[int, int]:
    """
    Process artists concurrently with streaming JSONL output.

    Responses are written to the JSONL file immediately after successful
    API calls and database commits, ensuring memory-efficient processing
    and fault-tolerant operation.

    Args:
        artists: List of artists to process
        client: Initialized OpenAI client
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        max_workers: Maximum number of concurrent workers
        output_path: Path to JSONL output file for streaming writes
        db_pool: Database connection pool for bio updates (optional)
        test_mode: If True, use test_artists table
        resume_mode: If True, append to existing file instead of overwriting
        daily_request_limit: Optional daily request limit for quota monitoring
        quota_threshold: Pause threshold as decimal (0.8 = 80%)
        quota_monitoring: If True, enable quota monitoring and pause/resume

    Returns:
        Tuple of (successful_calls, failed_calls)
    """
    # Create processing context with all resources
    context = ProcessingContext(
        client=client,
        output_path=output_path,
        db_pool=db_pool,
        resume_mode=resume_mode,
        daily_request_limit=daily_request_limit,
        quota_threshold=quota_threshold,
        quota_monitoring=quota_monitoring,
    )

    # Use context manager for proper resource lifecycle
    with context:
        # Create orchestrator to handle processing logic
        orchestrator = ProcessingOrchestrator(
            context=context,
            prompt_id=prompt_id,
            version=version,
            max_workers=max_workers,
            test_mode=test_mode,
        )

        # Process artists and return results
        return orchestrator.process_artists(artists)
