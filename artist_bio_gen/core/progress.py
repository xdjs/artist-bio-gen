"""
Progress tracking and reporting components.

This module provides components for tracking and reporting progress
during concurrent artist processing operations.
"""

import logging
import time
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Tracks and reports processing progress.

    Handles progress calculations, ETA estimation, and logging
    of progress updates during concurrent processing.
    """

    def __init__(self, total_items: int, log_interval_percent: int = 10):
        """
        Initialize progress tracker.

        Args:
            total_items: Total number of items to process
            log_interval_percent: Log progress every N percent (default 10%)
        """
        self.total_items = total_items
        self.successful_items = 0
        self.failed_items = 0
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.last_logged_count = 0

        # Calculate logging interval
        self.log_interval = max(1, total_items // (100 // log_interval_percent))
        self.min_time_between_logs = 5.0  # Minimum 5 seconds between logs

    def update(
        self,
        success: bool,
        artist_name: str,
        duration: float,
        worker_id: str,
    ) -> None:
        """
        Update progress with a completed item.

        Args:
            success: Whether the item was processed successfully
            artist_name: Name of the processed artist
            duration: Processing duration in seconds
            worker_id: ID of the worker that processed the item
        """
        if success:
            self.successful_items += 1
        else:
            self.failed_items += 1

        total_processed = self.successful_items + self.failed_items

        # Log individual progress
        self._log_item_progress(
            total_processed,
            artist_name,
            success,
            duration,
            worker_id
        )

    def should_log_summary(self) -> bool:
        """
        Determine if a progress summary should be logged.

        Returns:
            True if summary should be logged based on interval or time
        """
        total_processed = self.successful_items + self.failed_items
        current_time = time.time()

        # Check if we've completed processing
        if total_processed == self.total_items:
            return True

        # Check interval-based logging
        if total_processed - self.last_logged_count >= self.log_interval:
            return True

        # Check time-based logging
        if current_time - self.last_log_time >= self.min_time_between_logs:
            return True

        return False

    def log_summary(self, quota_status_message: str = "") -> None:
        """
        Log a progress summary.

        Args:
            quota_status_message: Optional quota status to include
        """
        total_processed = self.successful_items + self.failed_items
        current_time = time.time()

        elapsed_time = current_time - self.start_time
        current_rate = total_processed / elapsed_time if elapsed_time > 0 else 0
        remaining_items = self.total_items - total_processed
        estimated_remaining = remaining_items / current_rate if current_rate > 0 else 0

        progress_percent = (total_processed / self.total_items * 100) if self.total_items > 0 else 0

        # Build progress message
        message = (
            f"📊 Concurrent Progress: {total_processed}/{self.total_items} artists processed "
            f"({progress_percent:.1f}%) - "
            f"Rate: {current_rate:.2f} artists/sec - "
            f"ETA: {estimated_remaining:.0f}s remaining"
        )

        if quota_status_message:
            message += f" - {quota_status_message}"

        logger.info(message)

        # Update tracking
        self.last_log_time = current_time
        self.last_logged_count = total_processed

    def get_stats(self) -> Tuple[int, int]:
        """
        Get current processing statistics.

        Returns:
            Tuple of (successful_calls, failed_calls)
        """
        return self.successful_items, self.failed_items

    def _log_item_progress(
        self,
        total_processed: int,
        artist_name: str,
        success: bool,
        duration: float,
        worker_id: str
    ) -> None:
        """Log progress for an individual item."""
        status_emoji = "✓" if success else "✗"
        status_text = "Success" if success else "Failed"

        # Calculate progress percentage
        progress_percent = (total_processed / self.total_items * 100) if self.total_items > 0 else 0

        # Log at appropriate level
        if success:
            logger.info(
                f"[{worker_id}] {status_emoji} {artist_name} - "
                f"{status_text} ({duration:.2f}s) - "
                f"Progress: {total_processed}/{self.total_items} ({progress_percent:.1f}%)"
            )
        else:
            logger.warning(
                f"[{worker_id}] {status_emoji} {artist_name} - "
                f"{status_text} - "
                f"Progress: {total_processed}/{self.total_items} ({progress_percent:.1f}%)"
            )


class BatchProgressReporter:
    """
    Reports progress for batch operations.

    Provides formatted progress reporting for the start and
    completion of batch processing operations.
    """

    @staticmethod
    def log_start(
        total_artists: int,
        prompt_id: str,
        version: Optional[str],
        workers: int,
        test_mode: bool,
        db_enabled: bool,
        quota_monitoring: bool
    ) -> None:
        """Log the start of batch processing."""
        logger.info("=" * 60)
        logger.info("🚀 Starting Artist Bio Generation")
        logger.info("=" * 60)
        logger.info(f"📊 Processing Details:")
        logger.info(f"  • Total Artists: {total_artists}")
        logger.info(f"  • OpenAI Prompt: {prompt_id}")
        if version:
            logger.info(f"  • Prompt Version: {version}")
        logger.info(f"  • Concurrent Workers: {workers}")
        logger.info(f"  • Test Mode: {'✓' if test_mode else '✗'}")
        logger.info(f"  • Database Updates: {'✓' if db_enabled else '✗'}")
        logger.info(f"  • Quota Monitoring: {'✓' if quota_monitoring else '✗'}")
        logger.info("=" * 60)

    @staticmethod
    def log_completion(
        successful_calls: int,
        failed_calls: int,
        duration: float
    ) -> None:
        """Log the completion of batch processing."""
        total_calls = successful_calls + failed_calls
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
        avg_time = duration / total_calls if total_calls > 0 else 0

        logger.info("=" * 60)
        logger.info("✅ Processing Complete")
        logger.info("=" * 60)
        logger.info(f"📊 Final Statistics:")
        logger.info(f"  • Total Processed: {total_calls}")
        logger.info(f"  • Successful: {successful_calls} ({success_rate:.1f}%)")
        logger.info(f"  • Failed: {failed_calls}")
        logger.info(f"  • Total Duration: {duration:.2f} seconds")
        logger.info(f"  • Average Time/Artist: {avg_time:.2f} seconds")
        logger.info("=" * 60)