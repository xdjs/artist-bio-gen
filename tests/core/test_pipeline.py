#!/usr/bin/env python3
"""
Tests for the Response Processing Pipeline

This module tests the unified response processing pipeline
and individual processing steps.
"""

import logging
import time
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from dataclasses import dataclass

from artist_bio_gen.core.pipeline import (
    RequestContext,
    ProcessingResult,
    ProcessingStep,
    HeaderExtractionStep,
    ResponseParsingStep,
    QuotaUpdateStep,
    DatabaseUpdateStep,
    TransactionLoggingStep,
    OutputStreamingStep,
    ResponseProcessor,
)
from artist_bio_gen.models.artist import ArtistData
from artist_bio_gen.models.api import ApiResponse
from artist_bio_gen.models.quota import QuotaMetrics


class TestProcessingResult(unittest.TestCase):
    """Test ProcessingResult dataclass."""

    def test_calculate_duration(self):
        """Test duration calculation."""
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)

        # Set start time to past
        result.start_time = time.time() - 1.0
        duration = result.calculate_duration()

        self.assertGreater(duration, 0.9)
        self.assertLess(duration, 1.5)
        self.assertEqual(result.duration, duration)
        self.assertIsNotNone(result.end_time)

    def test_to_api_response(self):
        """Test conversion to ApiResponse."""
        artist = ArtistData("123", "Test Artist", "Extra data")
        result = ProcessingResult(
            artist=artist,
            response_text="Bio text",
            response_id="resp_123",
            created=1234567890,
            db_status="updated",
            error=None
        )

        api_response = result.to_api_response()

        self.assertEqual(api_response.artist_id, "123")
        self.assertEqual(api_response.artist_name, "Test Artist")
        self.assertEqual(api_response.artist_data, "Extra data")
        self.assertEqual(api_response.response_text, "Bio text")
        self.assertEqual(api_response.response_id, "resp_123")
        self.assertEqual(api_response.created, 1234567890)
        self.assertEqual(api_response.db_status, "updated")
        self.assertIsNone(api_response.error)


class TestHeaderExtractionStep(unittest.TestCase):
    """Test HeaderExtractionStep."""

    def test_extract_headers_from_raw_response(self):
        """Test header extraction from raw response."""
        step = HeaderExtractionStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        context = RequestContext()

        # Mock raw response with headers
        raw_response = Mock()
        raw_response.headers = {"x-ratelimit-remaining": "100"}
        parsed = Mock()
        parsed.usage = {"tokens": 50}
        raw_response.parse.return_value = parsed

        result.raw_response = raw_response

        # Process
        result = step.process(result, context)

        # Verify
        self.assertEqual(result.headers, {"x-ratelimit-remaining": "100"})
        self.assertEqual(result.usage_stats, {"tokens": 50})
        self.assertEqual(result.raw_response, parsed)

    def test_no_raw_response(self):
        """Test handling when no raw response available."""
        step = HeaderExtractionStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        context = RequestContext()

        # Process without raw response
        result = step.process(result, context)

        # Should return unchanged
        self.assertEqual(result.headers, {})
        self.assertIsNone(result.usage_stats)


class TestResponseParsingStep(unittest.TestCase):
    """Test ResponseParsingStep."""

    @patch('artist_bio_gen.core.pipeline.strip_trailing_citations')
    def test_parse_and_clean_response(self, mock_strip):
        """Test response parsing and text cleaning."""
        mock_strip.return_value = "Clean bio"

        step = ResponseParsingStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        context = RequestContext()

        # Mock response
        response = Mock()
        response.output_text = "Bio with citations [1]"
        response.id = "resp_123"
        response.created_at = 1234567890
        response.usage = {"tokens": 100}

        result.raw_response = response

        # Process
        result = step.process(result, context)

        # Verify
        self.assertEqual(result.response_text, "Clean bio")
        self.assertEqual(result.response_id, "resp_123")
        self.assertEqual(result.created, 1234567890)
        mock_strip.assert_called_once_with("Bio with citations [1]")


class TestQuotaUpdateStep(unittest.TestCase):
    """Test QuotaUpdateStep."""

    def test_update_quota_monitor(self):
        """Test quota monitor update."""
        step = QuotaUpdateStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        result.headers = {"x-ratelimit-remaining": "100"}
        result.usage_stats = {"tokens": 50}

        # Mock quota monitor
        quota_monitor = Mock()
        metrics = QuotaMetrics(
            requests_used_today=10,
            daily_limit=1000,
            usage_percentage=1.0,
            should_pause=False,
            pause_reason=None
        )
        quota_monitor.update_from_response.return_value = metrics

        context = RequestContext(quota_monitor=quota_monitor)

        # Process
        result = step.process(result, context)

        # Verify
        quota_monitor.update_from_response.assert_called_once_with(
            {"x-ratelimit-remaining": "100"},
            {"tokens": 50}
        )

    def test_no_quota_monitor(self):
        """Test when no quota monitor provided."""
        step = QuotaUpdateStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        context = RequestContext(quota_monitor=None)

        # Should not raise error
        result = step.process(result, context)


class TestDatabaseUpdateStep(unittest.TestCase):
    """Test DatabaseUpdateStep."""

    @patch('artist_bio_gen.core.pipeline.release_db_connection')
    @patch('artist_bio_gen.core.pipeline.update_artist_bio')
    @patch('artist_bio_gen.core.pipeline.get_db_connection')
    def test_successful_database_update(self, mock_get_conn, mock_update, mock_release):
        """Test successful database update."""
        # Setup mocks
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        db_result = Mock()
        db_result.success = True
        db_result.rows_affected = 1
        mock_update.return_value = db_result

        step = DatabaseUpdateStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist, response_text="Bio text")
        db_pool = Mock()
        context = RequestContext(db_pool=db_pool, test_mode=True)

        # Process
        result = step.process(result, context)

        # Verify
        self.assertEqual(result.db_status, "updated")
        mock_get_conn.assert_called_once_with(db_pool)
        mock_update.assert_called_once_with(
            connection=mock_conn,
            artist_id="123",
            bio="Bio text",
            skip_existing=False,
            test_mode=True,
            worker_id="main"
        )
        mock_release.assert_called_once_with(db_pool, mock_conn)

    @patch('artist_bio_gen.core.pipeline.release_db_connection')
    @patch('artist_bio_gen.core.pipeline.get_db_connection')
    def test_database_connection_failure(self, mock_get_conn, mock_release):
        """Test handling of database connection failure."""
        mock_get_conn.return_value = None

        step = DatabaseUpdateStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        db_pool = Mock()
        context = RequestContext(db_pool=db_pool)

        # Process
        result = step.process(result, context)

        # Verify
        self.assertEqual(result.db_status, "error")
        mock_release.assert_not_called()


class TestTransactionLoggingStep(unittest.TestCase):
    """Test TransactionLoggingStep."""

    @patch('artist_bio_gen.core.pipeline.log_transaction_success')
    def test_log_successful_transaction(self, mock_log_success):
        """Test logging of successful transaction."""
        step = TransactionLoggingStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(
            artist=artist,
            db_status="updated",
            response_id="resp_123",
            duration=1.5
        )
        db_pool = Mock()
        context = RequestContext(db_pool=db_pool)

        # Process
        result = step.process(result, context)

        # Verify
        mock_log_success.assert_called_once()
        call_args = mock_log_success.call_args[1]
        self.assertEqual(call_args['artist_id'], "123")
        self.assertEqual(call_args['artist_name'], "Test Artist")
        self.assertEqual(call_args['db_status'], "updated")

    @patch('artist_bio_gen.core.pipeline.log_transaction_failure')
    def test_log_failed_transaction(self, mock_log_failure):
        """Test logging of failed transaction."""
        step = TransactionLoggingStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(
            artist=artist,
            db_status="error",
            error="Database error",
            duration=1.5
        )
        db_pool = Mock()
        context = RequestContext(db_pool=db_pool)

        # Process
        result = step.process(result, context)

        # Verify
        mock_log_failure.assert_called_once()
        call_args = mock_log_failure.call_args[1]
        self.assertEqual(call_args['artist_id'], "123")
        self.assertEqual(call_args['error_message'], "Database error")


class TestOutputStreamingStep(unittest.TestCase):
    """Test OutputStreamingStep."""

    @patch('artist_bio_gen.core.output.append_jsonl_response')
    def test_stream_to_output(self, mock_append):
        """Test streaming response to JSONL file."""
        step = OutputStreamingStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(
            artist=artist,
            response_text="Bio text",
            response_id="resp_123",
            created=1234567890
        )
        context = RequestContext(
            output_path="/tmp/output.jsonl",
            prompt_id="prompt_123",
            version="v1"
        )

        # Process
        result = step.process(result, context)

        # Verify
        mock_append.assert_called_once()
        api_response_arg = mock_append.call_args[0][0]
        self.assertEqual(api_response_arg.artist_id, "123")
        self.assertEqual(api_response_arg.response_text, "Bio text")

    def test_no_output_path(self):
        """Test when no output path configured."""
        step = OutputStreamingStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist)
        context = RequestContext(output_path=None)

        # Should not raise error
        result = step.process(result, context)


class TestResponseProcessor(unittest.TestCase):
    """Test ResponseProcessor integration."""

    @patch('artist_bio_gen.core.pipeline.strip_trailing_citations')
    def test_full_pipeline_processing(self, mock_strip):
        """Test full pipeline processing of successful response."""
        mock_strip.return_value = "Clean bio"

        # Setup artist and response
        artist = ArtistData("123", "Test Artist", "Extra data")

        raw_response = Mock()
        raw_response.headers = {"x-ratelimit-remaining": "100"}
        raw_response.parse.return_value = raw_response
        raw_response.output_text = "Bio with citations"
        raw_response.id = "resp_123"
        raw_response.created_at = 1234567890
        raw_response.usage = {"tokens": 50}

        # Create processor with minimal steps for testing
        processor = ResponseProcessor(
            steps=[
                HeaderExtractionStep(),
                ResponseParsingStep(),
            ]
        )

        # Process
        api_response, duration = processor.process(raw_response, artist)

        # Verify
        self.assertEqual(api_response.artist_id, "123")
        self.assertEqual(api_response.response_text, "Clean bio")
        self.assertEqual(api_response.response_id, "resp_123")
        self.assertGreater(duration, 0)
        self.assertIsNone(api_response.error)

    def test_process_error(self):
        """Test error processing."""
        artist = ArtistData("123", "Test Artist", None)
        exception = ValueError("Test error")

        processor = ResponseProcessor()

        # Process error
        api_response, duration = processor.process_error(exception, artist)

        # Verify
        self.assertEqual(api_response.artist_id, "123")
        self.assertEqual(api_response.error, "ValueError: Test error")
        self.assertEqual(api_response.response_text, "")
        self.assertGreaterEqual(duration, 0)

    def test_step_failure_handling(self):
        """Test handling of step failures."""
        artist = ArtistData("123", "Test Artist", None)
        raw_response = Mock()

        # Create failing step
        failing_step = Mock(spec=ProcessingStep)
        failing_step.process.side_effect = RuntimeError("Step failed")
        failing_step.__str__ = Mock(return_value="FailingStep")

        processor = ResponseProcessor(steps=[failing_step])

        # Process
        api_response, duration = processor.process(raw_response, artist)

        # Verify error was captured
        self.assertIn("FailingStep failed", api_response.error)
        self.assertGreater(duration, 0)


class TestCustomProcessingStep(unittest.TestCase):
    """Test custom processing step implementation."""

    def test_custom_step(self):
        """Test implementing a custom processing step."""

        class CustomStep(ProcessingStep):
            def process(self, result, context):
                result.response_text = result.response_text.upper()
                return result

        step = CustomStep()
        artist = ArtistData("123", "Test Artist", None)
        result = ProcessingResult(artist=artist, response_text="lower case")
        context = RequestContext()

        # Process
        result = step.process(result, context)

        # Verify
        self.assertEqual(result.response_text, "LOWER CASE")


if __name__ == "__main__":
    unittest.main()