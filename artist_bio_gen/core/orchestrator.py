"""
Processing orchestration components.

This module provides high-level coordination for concurrent artist
processing without direct resource management concerns.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from ..models import ArtistData, ApiResponse
from ..api import call_openai_api
from .output import append_jsonl_response
from .resources import ProcessingContext, ResourceCoordinator, TimerManager
from .progress import ProgressTracker

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class ProcessingOrchestrator:
    """
    Orchestrates concurrent processing of artists.

    Coordinates task submission, progress tracking, and result handling
    without directly managing resources.
    """

    def __init__(
        self,
        context: ProcessingContext,
        prompt_id: str,
        version: Optional[str],
        max_workers: int,
        test_mode: bool = False,
    ):
        """
        Initialize processing orchestrator.

        Args:
            context: Processing context with initialized resources
            prompt_id: OpenAI prompt ID
            version: Optional prompt version
            max_workers: Maximum number of concurrent workers
            test_mode: If True, use test_artists table
        """
        self.context = context
        self.prompt_id = prompt_id
        self.version = version
        self.max_workers = max_workers
        self.test_mode = test_mode
        self.resource_coordinator = ResourceCoordinator(context)
        self.timer_manager = TimerManager()

    def process_artists(self, artists: List[ArtistData]) -> Tuple[int, int]:
        """
        Process a list of artists concurrently.

        Args:
            artists: List of artists to process

        Returns:
            Tuple of (successful_calls, failed_calls)
        """
        # Initialize progress tracker
        tracker = ProgressTracker(len(artists))

        logger.info(f"Starting concurrent processing with {self.max_workers} workers")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = self._submit_tasks(executor, artists)

            # Process completed tasks
            self._process_results(futures, tracker)

        # Clean up timers
        self.timer_manager.cancel_all()

        # Get final stats
        successful_calls, failed_calls = tracker.get_stats()
        logger.info(
            f"Concurrent processing completed: "
            f"{successful_calls} successful, {failed_calls} failed"
        )

        return successful_calls, failed_calls

    def _submit_tasks(
        self,
        executor: ThreadPoolExecutor,
        artists: List[ArtistData]
    ) -> Dict[Future, Tuple[ArtistData, str]]:
        """
        Submit all processing tasks to the executor.

        Args:
            executor: Thread pool executor
            artists: List of artists to process

        Returns:
            Dictionary mapping futures to (artist, worker_id) tuples
        """
        futures = {}

        for i, artist in enumerate(artists):
            # Check for pause before submitting new task
            self.resource_coordinator.wait_if_paused()

            # Generate worker ID
            worker_id = f"W{i % self.max_workers + 1:02d}"

            # Submit task
            future = executor.submit(
                call_openai_api,
                self.context.client,
                artist,
                self.prompt_id,
                self.version,
                worker_id,
                self.context.db_pool,
                False,  # skip_existing
                self.test_mode,
                self.context.quota_monitor,
                self.context.pause_controller
            )

            futures[future] = (artist, worker_id)

        return futures

    def _process_results(
        self,
        futures: Dict[Future, Tuple[ArtistData, str]],
        tracker: ProgressTracker
    ) -> None:
        """
        Process results as tasks complete.

        Args:
            futures: Dictionary of futures to process
            tracker: Progress tracker
        """
        for future in as_completed(futures):
            artist, worker_id = futures[future]

            try:
                api_response, duration = future.result()
                self._handle_response(api_response, artist, worker_id, duration, tracker)

            except Exception as e:
                self._handle_exception(e, artist, worker_id, tracker)

            # Log summary if needed
            if tracker.should_log_summary():
                quota_msg = self.context.get_quota_status_message()
                tracker.log_summary(quota_msg)

    def _handle_response(
        self,
        api_response: ApiResponse,
        artist: ArtistData,
        worker_id: str,
        duration: float,
        tracker: ProgressTracker
    ) -> None:
        """Handle a successful API response."""
        success = not bool(api_response.error)

        # Stream response to file
        try:
            append_jsonl_response(
                api_response,
                self.context.output_path,
                self.prompt_id,
                self.version
            )
            logger.debug(
                f"Streamed {'error ' if api_response.error else ''}response "
                f"for '{artist.name}' to {self.context.output_path}"
            )
        except Exception as e:
            logger.error(f"Failed to stream response for '{artist.name}': {e}")

        # Update progress
        tracker.update(success, artist.name, duration, worker_id)

        # Print successful responses to stdout
        if success:
            print(api_response.response_text)

            # Check for quota-based pause
            self._check_and_handle_quota_pause()

    def _handle_exception(
        self,
        exception: Exception,
        artist: ArtistData,
        worker_id: str,
        tracker: ProgressTracker
    ) -> None:
        """Handle an exception during processing."""
        exc_name = type(exception).__name__
        error_msg = f"Concurrent processing error [{exc_name}]: {str(exception)}"

        # Create error response
        error_response = ApiResponse(
            artist_id=artist.artist_id,
            artist_name=artist.name,
            artist_data=artist.data,
            response_text="",
            response_id="",
            created=0,
            error=error_msg,
        )

        # Stream error to file
        try:
            append_jsonl_response(
                error_response,
                self.context.output_path,
                self.prompt_id,
                self.version
            )
            logger.debug(
                f"Streamed exception error response for '{artist.name}' "
                f"to {self.context.output_path}"
            )
        except Exception as e:
            logger.error(
                f"Failed to stream exception error response for '{artist.name}': {e}"
            )

        # Update progress
        tracker.update(False, artist.name, 0.0, worker_id)

        logger.error(f"[{worker_id}] Thread error processing artist '{artist.name}': {error_msg}")

    def _check_and_handle_quota_pause(self) -> None:
        """Check quota status and pause if necessary."""
        should_pause, pause_reason = self.resource_coordinator.should_pause_for_quota()

        if should_pause:
            resume_at = self._estimate_resume_time()

            # Attempt to pause (idempotent operation)
            if self.resource_coordinator.pause_processing(pause_reason, resume_at):
                # Schedule auto-resume if pause was newly initiated
                self._schedule_auto_resume(resume_at)

                # Log pause status
                if resume_at is not None:
                    resume_dt = datetime.fromtimestamp(resume_at)
                    logger.warning(
                        f"Processing paused due to quota: {pause_reason} - "
                        f"Auto-resume scheduled for {resume_dt.isoformat()}"
                    )
                else:
                    logger.warning(
                        f"Processing paused due to quota: {pause_reason} - "
                        f"Manual resume required"
                    )

    def _estimate_resume_time(self) -> Optional[float]:
        """Estimate when processing can resume based on quota state."""
        if self.context.quota_monitor is None:
            return None

        status = self.context.quota_monitor.get_current_status()
        if status is not None:
            # Try to parse reset hints
            for reset_hint in (status.reset_requests, status.reset_tokens):
                resume_at = self._parse_reset_to_timestamp(reset_hint)
                if resume_at is not None:
                    return resume_at

        # Fall back to midnight if daily limit is set
        if self.context.quota_monitor.daily_limit_requests:
            now = datetime.now()
            next_midnight = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return next_midnight.timestamp()

        return None

    def _parse_reset_to_timestamp(self, reset_value: Optional[str]) -> Optional[float]:
        """Convert a quota reset hint into a UNIX timestamp."""
        if not reset_value:
            return None

        reset_str = str(reset_value).strip()
        if reset_str.lower() == "unknown":
            return None

        now = time.time()

        # Check for duration suffixes
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
                    seconds = amount * multiplier
                    if seconds >= 0:
                        return now + seconds
                except ValueError:
                    pass

        # Try parsing as raw seconds
        try:
            seconds = float(reset_str)
            if seconds >= 0:
                return now + seconds
        except ValueError:
            pass

        # Try parsing as ISO datetime
        try:
            reset_dt = datetime.fromisoformat(reset_str.replace("Z", "+00:00"))
            return reset_dt.timestamp()
        except ValueError:
            pass

        return None

    def _schedule_auto_resume(self, resume_at: Optional[float]) -> None:
        """Schedule automatic resume at the specified time."""
        if resume_at is None or self.context.pause_controller is None:
            return

        delay = max(0, resume_at - time.time())
        if delay > 0:
            timer = threading.Timer(
                delay,
                self.context.pause_controller.resume,
                args=("Auto-resume: quota reset",)
            )
            timer.daemon = True
            timer.start()
            self.timer_manager.add_timer(timer)

            resume_dt = datetime.fromtimestamp(resume_at)
            logger.info(
                f"Auto-resume scheduled for {resume_dt.isoformat()} "
                f"(in {delay:.0f} seconds)"
            )