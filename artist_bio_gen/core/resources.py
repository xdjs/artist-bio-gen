"""
Resource management components for processing lifecycle.

This module provides context managers and resource controllers that handle
the lifecycle of processing resources including database connections,
API clients, quota monitors, and output managers.
"""

import logging
import threading
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from ..api.quota import QuotaMonitor, PauseController
from ..models import ProcessingStats
from .output import initialize_jsonl_output

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class ProcessingContext:
    """
    Manages lifecycle of all processing resources.

    This context manager ensures proper initialization and cleanup of:
    - OpenAI API client
    - Database connection pool
    - Quota monitoring and pause control
    - Output file management
    - Progress tracking
    """

    def __init__(
        self,
        client: "OpenAI",
        output_path: str,
        db_pool: Optional[object] = None,
        resume_mode: bool = False,
        daily_request_limit: Optional[int] = None,
        quota_threshold: float = 0.8,
        quota_monitoring: bool = True,
    ):
        """
        Initialize processing context with required resources.

        Args:
            client: Initialized OpenAI client
            output_path: Path to JSONL output file
            db_pool: Optional database connection pool
            resume_mode: If True, append to existing file
            daily_request_limit: Optional daily request limit
            quota_threshold: Pause threshold as decimal (0.8 = 80%)
            quota_monitoring: If True, enable quota monitoring
        """
        self.client = client
        self.output_path = output_path
        self.db_pool = db_pool
        self.resume_mode = resume_mode
        self.daily_request_limit = daily_request_limit
        self.quota_threshold = quota_threshold
        self.quota_monitoring_enabled = quota_monitoring

        # Resources to be initialized
        self.quota_monitor: Optional[QuotaMonitor] = None
        self.pause_controller: Optional[PauseController] = None
        self.output_initialized: bool = False
        self._lock = threading.Lock()

    def __enter__(self) -> "ProcessingContext":
        """Initialize all processing resources."""
        try:
            # Initialize output file
            self._initialize_output()

            # Initialize quota monitoring if enabled
            if self.quota_monitoring_enabled:
                self._initialize_quota_monitoring()

            logger.info("Processing context initialized successfully")
            return self

        except Exception as e:
            logger.error(f"Failed to initialize processing context: {e}")
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up all processing resources."""
        # No special cleanup needed for current resources
        # DB pool is managed externally
        # Output file is closed after each write
        logger.debug("Processing context cleaned up")

    def _initialize_output(self):
        """Initialize streaming JSONL output file."""
        try:
            if self.resume_mode:
                initialize_jsonl_output(self.output_path, overwrite_existing=False)
                logger.info(f"Initialized streaming JSONL output for resume: {self.output_path}")
            else:
                initialize_jsonl_output(self.output_path, overwrite_existing=True)
                logger.info(f"Initialized streaming JSONL output: {self.output_path}")
            self.output_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize streaming output file: {e}")
            raise

    def _initialize_quota_monitoring(self):
        """Initialize quota monitoring and pause controller."""
        self.quota_monitor = QuotaMonitor(self.daily_request_limit, self.quota_threshold)
        self.pause_controller = PauseController()
        logger.info(
            f"Quota monitoring enabled: daily_limit={self.daily_request_limit}, "
            f"threshold={self.quota_threshold}"
        )

    def get_quota_status_message(self) -> str:
        """Get current quota status as a formatted message."""
        if self.quota_monitor is None:
            return ""

        metrics = self.quota_monitor.get_current_metrics()
        if metrics is None:
            return ""

        return f"Quota: {metrics.usage_percentage:.1f}% used"


class OutputManager:
    """
    Thread-safe manager for streaming output operations.

    Handles concurrent writes to JSONL output files with proper
    locking to prevent race conditions.
    """

    def __init__(self, output_path: str):
        """
        Initialize output manager.

        Args:
            output_path: Path to JSONL output file
        """
        self.output_path = output_path
        self._lock = threading.Lock()

    @contextmanager
    def write_lock(self):
        """Context manager for thread-safe write operations."""
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()


class TimerManager:
    """
    Manages auto-resume timers to prevent resource leaks.

    Tracks active timers and ensures proper cleanup on shutdown.
    """

    def __init__(self):
        """Initialize timer manager."""
        self._active_timers = []
        self._lock = threading.Lock()

    def add_timer(self, timer: threading.Timer):
        """Add a timer to track."""
        with self._lock:
            self._active_timers.append(timer)

    def cancel_all(self):
        """Cancel all active timers."""
        with self._lock:
            if self._active_timers:
                logger.debug(f"Cancelling {len(self._active_timers)} active auto-resume timer(s)")
                for timer in self._active_timers:
                    timer.cancel()
                self._active_timers.clear()

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up timers on exit."""
        self.cancel_all()


class ResourceCoordinator:
    """
    Coordinates resource management across processing components.

    Provides a unified interface for resource initialization,
    monitoring, and cleanup.
    """

    def __init__(self, context: ProcessingContext):
        """
        Initialize resource coordinator.

        Args:
            context: Processing context with initialized resources
        """
        self.context = context
        self.output_manager = OutputManager(context.output_path)
        self.timer_manager = TimerManager()

    def should_pause_for_quota(self) -> tuple[bool, Optional[str]]:
        """
        Check if processing should pause due to quota limits.

        Returns:
            Tuple of (should_pause, pause_reason)
        """
        if self.context.quota_monitor is None:
            return False, None

        return self.context.quota_monitor.should_pause()

    def pause_processing(self, reason: str, resume_at: Optional[float] = None) -> bool:
        """
        Pause processing with given reason.

        Args:
            reason: Reason for pausing
            resume_at: Optional timestamp for auto-resume

        Returns:
            True if pause was newly initiated
        """
        if self.context.pause_controller is None:
            return False

        return self.context.pause_controller.pause(reason, resume_at=resume_at)

    def wait_if_paused(self):
        """Block if processing is paused."""
        if self.context.pause_controller is not None:
            self.context.pause_controller.wait_if_paused()

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources."""
        self.timer_manager.cancel_all()