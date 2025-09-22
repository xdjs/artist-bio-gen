#!/usr/bin/env python3
"""
Quota Monitor Module

Thread-safe quota monitor for tracking API usage and managing pause/resume decisions.
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from ...models.quota import QuotaStatus, QuotaMetrics
from .parsing import parse_rate_limit_headers, calculate_usage_metrics, should_pause_processing

logger = logging.getLogger(__name__)


class QuotaMonitor:
    """
    Thread-safe quota monitor for tracking API usage and managing pause/resume decisions.
    """

    def __init__(self, daily_limit_requests: Optional[int] = None, pause_threshold: float = 0.8):
        """
        Initialize quota monitor.

        Args:
            daily_limit_requests: Optional daily request limit
            pause_threshold: Pause threshold as decimal (0.8 = 80%)
        """
        self.daily_limit_requests = daily_limit_requests
        self.pause_threshold = pause_threshold
        self.requests_used_today = 0
        self.last_reset = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.current_quota_status: Optional[QuotaStatus] = None
        self.current_quota_metrics: Optional[QuotaMetrics] = None

        # Thread safety
        # Use RLock to allow re-entrant locking when wait_if_paused()
        # triggers resume() while holding the lock.
        self._lock = threading.RLock()

        logger.info(f"QuotaMonitor initialized: daily_limit={daily_limit_requests}, "
                   f"threshold={pause_threshold}")

    def update_from_response(self, headers: Dict[str, str],
                           usage_stats: Optional[Dict[str, Any]] = None) -> QuotaMetrics:
        """
        Update quota state from API response headers and usage stats.

        Args:
            headers: HTTP response headers
            usage_stats: Optional usage statistics from response body

        Returns:
            Updated QuotaMetrics
        """
        with self._lock:
            # Parse headers to get current quota status
            self.current_quota_status = parse_rate_limit_headers(headers, usage_stats)

            # Check if we need to reset daily counter (new day)
            now = datetime.now()
            if now.date() > self.last_reset.date():
                logger.info(f"Resetting daily request counter (was {self.requests_used_today})")
                self.requests_used_today = 0
                self.last_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Increment daily request counter
            self.requests_used_today += 1

            # Calculate current metrics
            self.current_quota_metrics = calculate_usage_metrics(
                self.current_quota_status,
                self.daily_limit_requests,
                self.requests_used_today,
            )

            return self.current_quota_metrics

    def should_pause(self) -> Tuple[bool, str]:
        """
        Check if processing should pause based on current quota state.

        Returns:
            Tuple of (should_pause, reason)
        """
        with self._lock:
            if self.current_quota_metrics is None:
                return False, "No quota data available"

            return should_pause_processing(self.current_quota_metrics, self.pause_threshold)

    def can_resume(self) -> bool:
        """
        Check if processing can resume (quota has reset or is below threshold).

        Returns:
            True if processing can resume
        """
        with self._lock:
            should_pause, _ = self.should_pause()
            return not should_pause

    def get_current_metrics(self) -> Optional[QuotaMetrics]:
        """Get current quota metrics (thread-safe)."""
        with self._lock:
            return self.current_quota_metrics

    def get_current_status(self) -> Optional[QuotaStatus]:
        """Get current quota status (thread-safe)."""
        with self._lock:
            return self.current_quota_status

    def persist_state(self, filepath: str) -> None:
        """Persist current quota state to disk using atomic write.

        Writes to a temporary file in the same directory and renames it to ensure
        atomic replacement.
        """
        with self._lock:
            state = {
                "daily_limit_requests": self.daily_limit_requests,
                "pause_threshold": self.pause_threshold,
                "requests_used_today": self.requests_used_today,
                "last_reset": self.last_reset.isoformat(),
                "quota_status": self.current_quota_status.to_dict() if self.current_quota_status else None,
                "quota_metrics": self.current_quota_metrics.to_dict() if self.current_quota_metrics else None,
            }

        # Perform atomic write
        directory = os.path.dirname(filepath) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".quota_tmp_", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp_path, filepath)
            logger.debug(f"Persisted quota state to {filepath}")
        except Exception as e:
            logger.error(f"Failed to persist quota state to {filepath}: {e}")
            # Best-effort cleanup of temp file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def load_state(self, filepath: str) -> bool:
        """Load quota state from disk. Returns True if successful."""
        from ...models.quota import QuotaStatus as _QS, QuotaMetrics as _QM

        if not os.path.exists(filepath):
            logger.info(f"Quota state file not found: {filepath}")
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                self.daily_limit_requests = data.get("daily_limit_requests")
                self.pause_threshold = float(data.get("pause_threshold", self.pause_threshold))
                self.requests_used_today = int(data.get("requests_used_today", 0))
                last_reset_str = data.get("last_reset")
                if last_reset_str:
                    try:
                        self.last_reset = datetime.fromisoformat(last_reset_str)
                    except Exception:
                        pass
                qs = data.get("quota_status")
                qm = data.get("quota_metrics")
                self.current_quota_status = _QS.from_dict(qs) if qs else None
                self.current_quota_metrics = _QM.from_dict(qm) if qm else None

            logger.debug(f"Loaded quota state from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load quota state from {filepath}: {e}")
            return False