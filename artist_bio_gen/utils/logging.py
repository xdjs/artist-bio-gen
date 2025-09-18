"""
Logging utilities for the artist bio generator.

This module provides centralized logging configuration and utilities
to ensure consistent logging behavior across the application.
"""

import json
import logging
import threading
import time
from datetime import datetime
from typing import Optional


def setup_logging(verbose: bool = False):
    """Setup logging configuration with appropriate level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    format_string = "%(asctime)s - %(levelname)s - %(message)s"

    logging.basicConfig(level=level, format=format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Set specific logger levels
    logging.getLogger("openai").setLevel(logging.WARNING)  # Reduce OpenAI client noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Reduce HTTP client noise


def log_transaction_success(
    artist_id: str,
    artist_name: str,
    worker_id: str,
    processing_duration: float,
    db_status: str,
    response_id: str,
    timestamp: Optional[float] = None,
    logger: Optional[logging.Logger] = None
):
    """
    Log structured transaction-level information for successful database commits.
    
    This function creates machine-readable log entries that contain all necessary
    information for crash recovery and audit trails. The log format is designed
    to be easily parsed by automated tools.
    
    Args:
        artist_id: Unique identifier for the artist
        artist_name: Human-readable artist name
        worker_id: Identifier for the processing worker thread
        processing_duration: Total time taken to process this artist (seconds)
        db_status: Database operation status (updated, skipped, error)
        response_id: OpenAI API response ID
        timestamp: Transaction timestamp (defaults to current time)
        logger: Logger instance to use (defaults to current module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if timestamp is None:
        timestamp = time.time()
    
    # Create structured transaction record
    transaction_record = {
        "event_type": "database_transaction",
        "timestamp": timestamp,
        "artist_id": artist_id,
        "artist_name": artist_name,
        "worker_id": worker_id,
        "processing_duration_seconds": round(processing_duration, 3),
        "db_status": db_status,
        "response_id": response_id,
        "success": db_status == "updated"
    }
    
    # Log as INFO level with structured format for easy parsing
    logger.info(f"TRANSACTION: {json.dumps(transaction_record, ensure_ascii=False)}")


def log_transaction_failure(
    artist_id: str,
    artist_name: str,
    worker_id: str,
    processing_duration: float,
    error_message: str,
    timestamp: Optional[float] = None,
    logger: Optional[logging.Logger] = None
):
    """
    Log structured transaction-level information for failed processing attempts.
    
    Args:
        artist_id: Unique identifier for the artist
        artist_name: Human-readable artist name
        worker_id: Identifier for the processing worker thread
        processing_duration: Total time taken before failure (seconds)
        error_message: Description of the error that occurred
        timestamp: Failure timestamp (defaults to current time)
        logger: Logger instance to use (defaults to current module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if timestamp is None:
        timestamp = time.time()
    
    # Create structured failure record
    failure_record = {
        "event_type": "transaction_failure",
        "timestamp": timestamp,
        "artist_id": artist_id,
        "artist_name": artist_name,
        "worker_id": worker_id,
        "processing_duration_seconds": round(processing_duration, 3),
        "error_message": error_message,
        "success": False
    }
    
    # Log as WARNING level for failures
    logger.warning(f"TRANSACTION_FAILURE: {json.dumps(failure_record, ensure_ascii=False)}")


# Global rate limiting state for preventing log spam
_last_quota_log_time = 0.0
_last_quota_threshold = 0.0
_quota_log_interval = 100  # Log every N requests by default
_quota_state_lock = threading.Lock()


def log_quota_metrics(quota_metrics, worker_id: str, logger: Optional[logging.Logger] = None):
    """
    Log structured quota metrics with rate limiting to prevent spam.

    Alert thresholds:
    - Warning: 60% quota usage
    - Critical: 80% quota usage
    - Emergency: 95% quota usage

    Args:
        quota_metrics: QuotaMetrics object with current usage information
        worker_id: Identifier for the processing worker thread
        logger: Logger instance to use (defaults to current module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    global _last_quota_log_time, _last_quota_threshold, _quota_log_interval

    current_time = time.time()
    usage_percentage = quota_metrics.usage_percentage

    # Determine alert level
    alert_level = "info"
    if usage_percentage >= 95.0:
        alert_level = "emergency"
    elif usage_percentage >= 80.0:
        alert_level = "critical"
    elif usage_percentage >= 60.0:
        alert_level = "warning"

    # Rate limiting logic - log if:
    # 1. Alert level changed (threshold crossing)
    # 2. Emergency level (always log)
    # 3. Time interval passed since last log
    with _quota_state_lock:
        should_log = (
            abs(usage_percentage - _last_quota_threshold) >= 10.0 or  # 10% threshold change
            alert_level == "emergency" or
            current_time - _last_quota_log_time >= _quota_log_interval
        )

        if should_log:
            _last_quota_log_time = current_time
            _last_quota_threshold = usage_percentage

    if should_log:
        # Create structured quota metrics record
        quota_record = {
            "event_type": "quota_metrics",
            "timestamp": current_time,
            "worker_id": worker_id,
            "alert_level": alert_level,
            "usage_percentage": round(usage_percentage, 2),
            "requests_used_today": quota_metrics.requests_used_today,
            "daily_limit": quota_metrics.daily_limit,
            "should_pause": quota_metrics.should_pause,
            "pause_reason": quota_metrics.pause_reason
        }

        # Log at appropriate level based on alert severity
        if alert_level == "emergency":
            logger.error(f"QUOTA_EMERGENCY: {json.dumps(quota_record, ensure_ascii=False)}")
        elif alert_level == "critical":
            logger.error(f"QUOTA_CRITICAL: {json.dumps(quota_record, ensure_ascii=False)}")
        elif alert_level == "warning":
            logger.warning(f"QUOTA_WARNING: {json.dumps(quota_record, ensure_ascii=False)}")
        else:
            logger.info(f"QUOTA_METRICS: {json.dumps(quota_record, ensure_ascii=False)}")


def log_pause_event(reason: str, resume_time: Optional[datetime] = None, logger: Optional[logging.Logger] = None):
    """
    Log structured pause event with resume time information.

    Args:
        reason: Reason for pausing processing
        resume_time: Optional scheduled resume time
        logger: Logger instance to use (defaults to current module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Create structured pause event record
    pause_record = {
        "event_type": "quota_pause",
        "timestamp": time.time(),
        "reason": reason,
        "resume_time": resume_time.isoformat() if resume_time else None,
        "auto_resume": resume_time is not None
    }

    # Log as WARNING level for visibility
    logger.warning(f"QUOTA_PAUSE: {json.dumps(pause_record, ensure_ascii=False)}")


def log_resume_event(duration_paused: float, quota_status=None, logger: Optional[logging.Logger] = None):
    """
    Log structured resume event with pause duration and current quota status.

    Args:
        duration_paused: Duration paused in seconds
        quota_status: Optional QuotaStatus object with current state
        logger: Logger instance to use (defaults to current module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Create structured resume event record
    resume_record = {
        "event_type": "quota_resume",
        "timestamp": time.time(),
        "duration_paused_seconds": round(duration_paused, 2),
        "duration_paused_minutes": round(duration_paused / 60.0, 2)
    }

    # Add quota status if available
    if quota_status:
        resume_record.update({
            "requests_remaining": quota_status.requests_remaining,
            "tokens_remaining": quota_status.tokens_remaining,
            "requests_limit": quota_status.requests_limit,
            "tokens_limit": quota_status.tokens_limit
        })

    # Log as INFO level for normal operation
    logger.info(f"QUOTA_RESUME: {json.dumps(resume_record, ensure_ascii=False)}")


def log_rate_limit_event(error_type: str, retry_after: Optional[int], worker_id: str, logger: Optional[logging.Logger] = None):
    """
    Log structured rate limit event with retry information.

    Args:
        error_type: Type of rate limit error (rate_limit, quota, server, network)
        retry_after: Retry delay in seconds from Retry-After header
        worker_id: Identifier for the processing worker thread
        logger: Logger instance to use (defaults to current module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Create structured rate limit event record
    rate_limit_record = {
        "event_type": "rate_limit",
        "timestamp": time.time(),
        "worker_id": worker_id,
        "error_type": error_type,
        "retry_after_seconds": retry_after,
        "has_retry_after": retry_after is not None
    }

    # Log at appropriate level based on error type
    if error_type in ["quota", "insufficient_quota"]:
        logger.error(f"RATE_LIMIT_QUOTA: {json.dumps(rate_limit_record, ensure_ascii=False)}")
    elif error_type == "rate_limit":
        logger.warning(f"RATE_LIMIT_429: {json.dumps(rate_limit_record, ensure_ascii=False)}")
    else:
        logger.info(f"RATE_LIMIT_EVENT: {json.dumps(rate_limit_record, ensure_ascii=False)}")


def set_quota_log_interval(interval_seconds: int):
    """
    Set the interval for quota metrics logging to prevent spam.

    Args:
        interval_seconds: Minimum seconds between quota metric logs
    """
    global _quota_log_interval
    with _quota_state_lock:
        _quota_log_interval = interval_seconds
