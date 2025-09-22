#!/usr/bin/env python3
"""
Pause Controller Module

Thread-safe pause controller for managing processing pause/resume with events.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class PauseController:
    """
    Thread-safe pause controller for managing processing pause/resume with events.
    """

    def __init__(self):
        """Initialize pause controller."""
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused
        self._pause_reason: Optional[str] = None
        self._resume_time: Optional[float] = None
        # Use a re-entrant lock since wait_if_paused may trigger resume() while
        # holding the lock, which also acquires the same lock. A standard Lock
        # would deadlock in that scenario when auto-resume fires.
        self._lock = threading.RLock()

        logger.debug("PauseController initialized (unpaused)")

    def pause(self, reason: str, resume_at: Optional[float] = None) -> bool:
        """
        Pause processing with optional resume time. Idempotent operation.

        Args:
            reason: Reason for pausing
            resume_at: Optional timestamp to automatically resume

        Returns:
            True if pause was newly initiated, False if already paused
        """
        with self._lock:
            was_already_paused = not self._pause_event.is_set()
            if was_already_paused:
                logger.debug(f"Already paused (reason: {self._pause_reason}), ignoring new pause: {reason}")
                return False

            self._pause_event.clear()
            self._pause_reason = reason
            self._resume_time = resume_at

        if resume_at:
            resume_datetime = datetime.fromtimestamp(resume_at)
            logger.warning(f"PAUSED: {reason} - Will resume at {resume_datetime}")
        else:
            logger.warning(f"PAUSED: {reason} - Manual resume required")

        return True

    def resume(self, reason: str = "Manual resume"):
        """
        Resume processing.

        Args:
            reason: Reason for resuming
        """
        with self._lock:
            self._pause_event.set()
            self._pause_reason = None
            self._resume_time = None

        logger.info(f"RESUMED: {reason}")

    def resume_at(self, timestamp: float) -> None:
        """Schedule an automatic resume at the given UNIX timestamp.

        Does not change the current pause state; call pause() first to pause.
        """
        with self._lock:
            self._resume_time = timestamp
            if not self._pause_event.is_set():
                resume_datetime = datetime.fromtimestamp(timestamp)
                logger.info(f"Auto-resume scheduled at {resume_datetime}")

    def wait_if_paused(self, timeout: Optional[float] = None):
        """
        Wait if currently paused, with optional timeout.

        Args:
            timeout: Maximum time to wait in seconds
        """
        # Check if we should auto-resume immediately
        with self._lock:
            if (self._resume_time is not None and
                time.time() >= self._resume_time and
                not self._pause_event.is_set()):
                self.resume("Auto-resume time reached")
                return

        # If we have a resume time, adjust timeout to not wait longer than needed
        adjusted_timeout = timeout
        with self._lock:
            if self._resume_time is not None and timeout is not None:
                time_until_resume = max(0, self._resume_time - time.time())
                adjusted_timeout = min(timeout, time_until_resume + 0.01)  # Small buffer

        # Wait for pause event to be set (unpaused)
        if not self._pause_event.wait(adjusted_timeout):
            # Check again if we should auto-resume after timeout
            with self._lock:
                if (self._resume_time is not None and
                    time.time() >= self._resume_time and
                    not self._pause_event.is_set()):
                    self.resume("Auto-resume time reached")
                elif adjusted_timeout == timeout:
                    logger.warning("Pause wait timeout reached")

    def is_paused(self) -> bool:
        """Check if currently paused."""
        return not self._pause_event.is_set()

    def get_pause_reason(self) -> Optional[str]:
        """Get current pause reason."""
        with self._lock:
            return self._pause_reason