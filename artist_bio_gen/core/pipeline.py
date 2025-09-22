#!/usr/bin/env python3
"""
Response Processing Pipeline

This module provides a unified pipeline for processing API responses with
clear separation of concerns. Each step in the pipeline handles a specific
aspect of response processing, eliminating code duplication across the codebase.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..database.connection import get_db_connection, release_db_connection
from ..database.operations import update_artist_bio
from ..models.api import ApiResponse
from ..models.artist import ArtistData
from ..models.quota import ErrorClassification
from ..utils.logging import log_transaction_failure, log_transaction_success
from ..utils.text import strip_trailing_citations

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Context information for the request being processed."""

    worker_id: str = "main"
    prompt_id: Optional[str] = None
    version: Optional[str] = None
    output_path: Optional[str] = None
    skip_existing: bool = False
    test_mode: bool = False
    db_pool: Optional[Any] = None
    quota_monitor: Optional[Any] = None
    pause_controller: Optional[Any] = None


@dataclass
class ProcessingResult:
    """Carries state through the processing pipeline."""

    artist: ArtistData
    raw_response: Optional[Any] = None
    headers: Dict[str, Any] = field(default_factory=dict)
    usage_stats: Optional[Any] = None
    response_text: str = ""
    response_id: str = ""
    created: int = 0
    db_status: str = "null"
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None

    def calculate_duration(self) -> float:
        """Calculate and set the duration."""
        if self.end_time is None:
            self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        return self.duration

    def to_api_response(self) -> ApiResponse:
        """Convert to ApiResponse for backward compatibility."""
        return ApiResponse(
            artist_id=self.artist.artist_id,
            artist_name=self.artist.name,
            artist_data=self.artist.data,
            response_text=self.response_text,
            response_id=self.response_id,
            created=self.created,
            db_status=self.db_status,
            error=self.error,
        )


class ProcessingStep(ABC):
    """Base class for response processing steps."""

    @abstractmethod
    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """
        Process the result through this step.

        Args:
            result: Current processing result
            context: Request context

        Returns:
            Updated processing result

        Raises:
            Exception: If processing fails (will be caught by pipeline)
        """
        pass

    def __str__(self) -> str:
        """Return step name for logging."""
        return self.__class__.__name__


class HeaderExtractionStep(ProcessingStep):
    """Extract headers from raw API response."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Extract headers and usage stats from raw response."""
        if result.raw_response is None:
            return result

        # Try to extract headers
        result.headers = getattr(result.raw_response, "headers", {}) or {}

        # Try to parse response if raw response available
        if hasattr(result.raw_response, "parse"):
            try:
                parsed = result.raw_response.parse()
                result.usage_stats = getattr(parsed, "usage", None)
                # Store parsed response for next steps
                result.raw_response = parsed
            except (AttributeError, NotImplementedError) as e:
                logger.debug(f"[{context.worker_id}] Could not parse raw response: {e}")

        return result


class ResponseParsingStep(ProcessingStep):
    """Parse API response and extract/clean text."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Extract and clean response text."""
        if result.raw_response is None:
            return result

        response = result.raw_response

        # Extract response fields
        raw_text = getattr(response, "output_text", "")
        result.response_id = getattr(response, "id", "")
        result.created = int(getattr(response, "created_at", 0))

        # Clean response text (strip citations)
        cleaned_text = strip_trailing_citations(raw_text)
        if cleaned_text != raw_text:
            logger.info(
                f"[{context.worker_id}] ✂️ Stripped trailing citations from API response for {result.artist.name}"
            )
        result.response_text = cleaned_text

        # Extract usage if not already done
        if result.usage_stats is None:
            result.usage_stats = getattr(response, "usage", None)

        return result


class QuotaUpdateStep(ProcessingStep):
    """Update quota monitor with response metrics."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Update quota monitor if provided."""
        if context.quota_monitor is None:
            return result

        try:
            metrics = context.quota_monitor.update_from_response(
                result.headers,
                result.usage_stats
            )
            logger.debug(
                f"[{context.worker_id}] Quota metrics: used_today={metrics.requests_used_today}, "
                f"usage={metrics.usage_percentage:.1f}% pause={metrics.should_pause}"
            )
        except Exception as e:
            logger.warning(f"[{context.worker_id}] Failed to update quota monitor: {e}")

        return result


class DatabaseUpdateStep(ProcessingStep):
    """Handle database connection and bio updates."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Update database with bio if pool provided."""
        if context.db_pool is None or result.error is not None:
            return result

        db_connection = None
        try:
            # Get database connection
            db_connection = get_db_connection(context.db_pool)
            if db_connection is None:
                result.db_status = "error"
                logger.warning(
                    f"[{context.worker_id}] 💥 Failed to get database connection for {result.artist.name}"
                )
                return result

            # Update database
            db_result = update_artist_bio(
                connection=db_connection,
                artist_id=result.artist.artist_id,
                bio=result.response_text,
                skip_existing=context.skip_existing,
                test_mode=context.test_mode,
                worker_id=context.worker_id,
            )

            if db_result.success:
                if db_result.rows_affected > 0:
                    result.db_status = "updated"
                    logger.debug(f"[{context.worker_id}] 💾 Database updated for {result.artist.name}")
                else:
                    result.db_status = "skipped"
                    logger.debug(f"[{context.worker_id}] ⏭️ Database update skipped for {result.artist.name}")
            else:
                result.db_status = "error"
                logger.warning(
                    f"[{context.worker_id}] 💥 Database update failed for {result.artist.name}: {db_result.error}"
                )

        except Exception as e:
            result.db_status = "error"
            logger.error(
                f"[{context.worker_id}] 💥 Database update error for {result.artist.name}: {str(e)}"
            )
        finally:
            # Always release connection back to pool
            if db_connection is not None:
                release_db_connection(context.db_pool, db_connection)

        return result


class TransactionLoggingStep(ProcessingStep):
    """Log transaction success or failure."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Log structured transaction information."""
        # Calculate duration if not set
        if result.duration is None:
            result.calculate_duration()

        # Only log if database operation was attempted
        if context.db_pool is None:
            return result

        if result.db_status in ["updated", "skipped"]:
            # Log successful transaction
            log_transaction_success(
                artist_id=result.artist.artist_id,
                artist_name=result.artist.name,
                worker_id=context.worker_id,
                processing_duration=result.duration,
                db_status=result.db_status,
                response_id=result.response_id,
                timestamp=result.end_time,
                logger=logger
            )
        elif result.db_status == "error" or result.error:
            # Log failed transaction
            error_msg = result.error or f"Database operation failed: {result.db_status}"
            log_transaction_failure(
                artist_id=result.artist.artist_id,
                artist_name=result.artist.name,
                worker_id=context.worker_id,
                processing_duration=result.duration,
                error_message=error_msg,
                timestamp=result.end_time,
                logger=logger
            )

        return result


class OutputStreamingStep(ProcessingStep):
    """Stream response to JSONL output file."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Stream response to output file if configured."""
        if context.output_path is None:
            return result

        # Import here to avoid circular dependency
        from ..core.output import append_jsonl_response

        try:
            api_response = result.to_api_response()
            append_jsonl_response(
                api_response,
                context.output_path,
                context.prompt_id,
                context.version
            )
            logger.debug(f"Streamed response for '{result.artist.name}' to {context.output_path}")
        except Exception as e:
            logger.error(f"Failed to stream response for '{result.artist.name}': {e}")

        return result


class ErrorClassificationStep(ProcessingStep):
    """Classify errors for retry logic."""

    def process(self, result: ProcessingResult, context: RequestContext) -> ProcessingResult:
        """Classify any error that occurred."""
        # This step is mainly for documentation/structure
        # Actual error classification happens in retry decorator
        return result


class ResponseProcessor:
    """Unified pipeline for processing API responses."""

    def __init__(
        self,
        steps: Optional[List[ProcessingStep]] = None,
        quota_monitor: Optional[Any] = None,
        db_pool: Optional[Any] = None,
    ):
        """
        Initialize the response processor.

        Args:
            steps: Custom list of processing steps (uses defaults if None)
            quota_monitor: Quota monitor instance
            db_pool: Database connection pool
        """
        if steps is None:
            # Default processing pipeline
            self.steps = [
                HeaderExtractionStep(),
                ResponseParsingStep(),
                QuotaUpdateStep(),
                DatabaseUpdateStep(),
                TransactionLoggingStep(),
                OutputStreamingStep(),
            ]
        else:
            self.steps = steps

        self.quota_monitor = quota_monitor
        self.db_pool = db_pool

    def process(
        self,
        raw_response: Any,
        artist: ArtistData,
        context: Optional[RequestContext] = None,
    ) -> tuple[ApiResponse, float]:
        """
        Process response through the pipeline.

        Args:
            raw_response: Raw API response object
            artist: Artist being processed
            context: Request context (creates default if None)

        Returns:
            Tuple of (ApiResponse, duration in seconds)
        """
        if context is None:
            context = RequestContext(
                quota_monitor=self.quota_monitor,
                db_pool=self.db_pool,
            )
        else:
            # Ensure quota monitor and db_pool are set
            if context.quota_monitor is None:
                context.quota_monitor = self.quota_monitor
            if context.db_pool is None:
                context.db_pool = self.db_pool

        # Initialize result
        result = ProcessingResult(
            artist=artist,
            raw_response=raw_response,
        )

        # Process through pipeline
        for step in self.steps:
            try:
                logger.debug(f"[{context.worker_id}] Processing step: {step}")
                result = step.process(result, context)
            except Exception as e:
                # Handle step error
                result.error = f"{step} failed: {str(e)}"
                result.calculate_duration()

                # Log the error
                logger.error(
                    f"[{context.worker_id}] Pipeline step {step} failed for {artist.name}: {e}"
                )

                # Continue processing remaining steps (they should handle error state)

        # Calculate final duration
        if result.duration is None:
            result.calculate_duration()

        # Log completion
        if result.error:
            logger.error(
                f"[{context.worker_id}] ❌ Failed processing: {result.artist.name} "
                f"({result.duration:.2f}s) - {result.error}"
            )
        else:
            logger.info(
                f"[{context.worker_id}] ✅ Completed processing: {result.artist.name} "
                f"({result.duration:.2f}s) [DB: {result.db_status}]"
            )

        return result.to_api_response(), result.duration

    def process_error(
        self,
        exception: Exception,
        artist: ArtistData,
        context: Optional[RequestContext] = None,
    ) -> tuple[ApiResponse, float]:
        """
        Create error response for failed API call.

        Args:
            exception: Exception that occurred
            artist: Artist being processed
            context: Request context

        Returns:
            Tuple of (ApiResponse with error, duration)
        """
        if context is None:
            context = RequestContext()

        # Create error result
        result = ProcessingResult(
            artist=artist,
            error=f"{type(exception).__name__}: {str(exception)}",
        )
        result.calculate_duration()

        # Still run output streaming and logging steps for errors
        steps_to_run = [
            TransactionLoggingStep(),
            OutputStreamingStep(),
        ]

        for step in steps_to_run:
            try:
                result = step.process(result, context)
            except Exception as e:
                logger.debug(f"Step {step} failed during error processing: {e}")

        # Log the error
        logger.error(
            f"[{context.worker_id}] ❌ Failed processing: {result.artist.name} "
            f"({result.duration:.2f}s) - {result.error}"
        )

        return result.to_api_response(), result.duration