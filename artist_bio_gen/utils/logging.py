"""
Logging utilities for the artist bio generator.

This module provides centralized logging configuration and utilities
to ensure consistent logging behavior across the application.
"""

import json
import logging
import time
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
