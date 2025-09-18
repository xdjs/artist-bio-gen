#!/usr/bin/env python3
"""
Tests for the enhanced logging and monitoring functionality.

This module contains comprehensive tests for the logging and monitoring features
including progress tracking, statistics calculation, and summary reporting.
"""

import os
import sys
import tempfile
import time
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

# Import models from their new location
from artist_bio_gen.models import (
    ProcessingStats,
)

# Import utility functions
from artist_bio_gen.utils import (
    create_progress_bar,
    setup_logging,
)

# Import quota monitoring logging functions
from artist_bio_gen.utils.logging import (
    log_quota_metrics,
    log_pause_event,
    log_resume_event,
    log_rate_limit_event,
    set_quota_log_interval,
)

# Import quota models for testing
from artist_bio_gen.models.quota import QuotaStatus, QuotaMetrics

# Import core processing functions
from artist_bio_gen.core import (
    calculate_processing_stats,
    log_processing_start,
    log_processing_summary,
    log_progress_update,
)

# Import CLI main function
from artist_bio_gen.cli import (
    main,
)


class TestProcessingStats(unittest.TestCase):
    """Test cases for the ProcessingStats NamedTuple."""

    def test_processing_stats_creation(self):
        """Test creating ProcessingStats with all fields."""
        stats = ProcessingStats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
            total_duration=10.0,
            avg_time_per_artist=1.0,
            api_calls_per_second=1.0,
        )

        self.assertEqual(stats.total_artists, 10)
        self.assertEqual(stats.successful_calls, 8)
        self.assertEqual(stats.failed_calls, 2)
        self.assertEqual(stats.skipped_lines, 3)
        self.assertEqual(stats.error_lines, 1)
        self.assertEqual(stats.start_time, 1000.0)
        self.assertEqual(stats.end_time, 1010.0)
        self.assertEqual(stats.total_duration, 10.0)
        self.assertEqual(stats.avg_time_per_artist, 1.0)
        self.assertEqual(stats.api_calls_per_second, 1.0)

    def test_processing_stats_immutable(self):
        """Test that ProcessingStats is immutable."""
        stats = ProcessingStats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
            total_duration=10.0,
            avg_time_per_artist=1.0,
            api_calls_per_second=1.0,
        )

        with self.assertRaises(AttributeError):
            stats.total_artists = 20


class TestProgressBar(unittest.TestCase):
    """Test cases for the progress bar functionality."""

    def test_progress_bar_empty(self):
        """Test progress bar with no progress."""
        bar = create_progress_bar(0, 10)
        self.assertEqual(bar, "[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]")

    def test_progress_bar_half(self):
        """Test progress bar at 50%."""
        bar = create_progress_bar(5, 10)
        # Should be approximately half filled (15 out of 30 characters)
        filled_chars = bar.count("█")
        self.assertEqual(filled_chars, 15)

    def test_progress_bar_full(self):
        """Test progress bar at 100%."""
        bar = create_progress_bar(10, 10)
        self.assertEqual(bar, "[██████████████████████████████]")

    def test_progress_bar_partial(self):
        """Test progress bar at 33%."""
        bar = create_progress_bar(1, 3)
        # Should be approximately 1/3 filled
        filled_chars = bar.count("█")
        self.assertGreater(filled_chars, 0)
        self.assertLess(filled_chars, 30)

    def test_progress_bar_zero_total(self):
        """Test progress bar with zero total."""
        bar = create_progress_bar(0, 0)
        self.assertEqual(bar, "[                              ]")


class TestStatisticsCalculation(unittest.TestCase):
    """Test cases for statistics calculation."""

    def test_calculate_processing_stats_basic(self):
        """Test basic statistics calculation."""
        stats = calculate_processing_stats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
        )

        self.assertEqual(stats.total_artists, 10)
        self.assertEqual(stats.successful_calls, 8)
        self.assertEqual(stats.failed_calls, 2)
        self.assertEqual(stats.skipped_lines, 3)
        self.assertEqual(stats.error_lines, 1)
        self.assertEqual(stats.start_time, 1000.0)
        self.assertEqual(stats.end_time, 1010.0)
        self.assertEqual(stats.total_duration, 10.0)
        self.assertEqual(stats.avg_time_per_artist, 1.0)
        self.assertEqual(stats.api_calls_per_second, 1.0)

    def test_calculate_processing_stats_zero_duration(self):
        """Test statistics calculation with zero duration."""
        stats = calculate_processing_stats(
            total_artists=0,
            successful_calls=0,
            failed_calls=0,
            skipped_lines=0,
            error_lines=0,
            start_time=1000.0,
            end_time=1000.0,
        )

        self.assertEqual(stats.total_duration, 0.0)
        self.assertEqual(stats.avg_time_per_artist, 0.0)
        self.assertEqual(stats.api_calls_per_second, 0.0)

    def test_calculate_processing_stats_zero_artists(self):
        """Test statistics calculation with zero artists."""
        stats = calculate_processing_stats(
            total_artists=0,
            successful_calls=0,
            failed_calls=0,
            skipped_lines=0,
            error_lines=0,
            start_time=1000.0,
            end_time=1010.0,
        )

        self.assertEqual(stats.avg_time_per_artist, 0.0)
        self.assertEqual(stats.api_calls_per_second, 0.0)


class TestLoggingFunctions(unittest.TestCase):
    """Test cases for logging functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("artist_bio_gen.core.processor.logger")
    def test_log_processing_start(self, mock_logger):
        """Test logging processing start."""
        start_time = log_processing_start(
            total_artists=10,
            input_file="test.csv",
            prompt_id="test_prompt",
            max_workers=4,
        )

        # Check that start time was returned
        self.assertIsInstance(start_time, float)
        self.assertGreater(start_time, 0)

        # Check that appropriate log messages were called
        mock_logger.info.assert_called()
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

        # Check for key log messages
        self.assertTrue(any("PROCESSING STARTED" in call for call in log_calls))
        self.assertTrue(any("test.csv" in call for call in log_calls))
        self.assertTrue(any("test_prompt" in call for call in log_calls))
        self.assertTrue(any("10" in call for call in log_calls))
        self.assertTrue(any("4" in call for call in log_calls))

    @patch("artist_bio_gen.core.processor.logger")
    def test_log_progress_update_success(self, mock_logger):
        """Test logging progress update for successful processing."""
        log_progress_update(5, 10, "Taylor Swift", True, 2.5)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        # Check for key elements in the log message
        self.assertIn("5/ 10", log_message)  # Note the space padding
        self.assertIn("50.0%", log_message)
        self.assertIn("✅", log_message)
        self.assertIn("Taylor Swift", log_message)
        self.assertIn("SUCCESS", log_message)
        self.assertIn("2.50s", log_message)

    @patch("artist_bio_gen.core.processor.logger")
    def test_log_progress_update_failure(self, mock_logger):
        """Test logging progress update for failed processing."""
        log_progress_update(3, 10, "Drake", False, 1.2)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        # Check for key elements in the log message
        self.assertIn("3/ 10", log_message)  # Note the space padding
        self.assertIn("30.0%", log_message)
        self.assertIn("❌", log_message)
        self.assertIn("Drake", log_message)
        self.assertIn("FAILED", log_message)
        self.assertIn("1.20s", log_message)

    @patch("artist_bio_gen.core.processor.logger")
    def test_log_processing_summary(self, mock_logger):
        """Test logging processing summary."""
        stats = ProcessingStats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
            total_duration=10.0,
            avg_time_per_artist=1.0,
            api_calls_per_second=1.0,
        )

        log_processing_summary(stats)

        # Check that multiple log messages were called
        self.assertGreater(mock_logger.info.call_count, 5)

        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

        # Check for key summary elements
        self.assertTrue(any("PROCESSING SUMMARY" in call for call in log_calls))
        self.assertTrue(any("10" in call for call in log_calls))  # Total artists
        self.assertTrue(any("8" in call for call in log_calls))  # Successful calls
        self.assertTrue(any("2" in call for call in log_calls))  # Failed calls
        self.assertTrue(any("80.0%" in call for call in log_calls))  # Success rate
        self.assertTrue(any("1.00s" in call for call in log_calls))  # Avg time
        self.assertTrue(any("1.00" in call for call in log_calls))  # Calls per second


class TestLoggingConfiguration(unittest.TestCase):
    """Test cases for logging configuration."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        # This is a bit tricky to test since logging is global
        # We'll just ensure the function exists and can be called
        setup_logging(verbose=False)
        # If we get here without error, the function works

    def test_setup_logging_verbose(self):
        """Test verbose logging setup."""
        setup_logging(verbose=True)
        # If we get here without error, the function works


class TestEnhancedMainFunction(unittest.TestCase):
    """Test cases for the enhanced main function with logging."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir)
        sys.argv = self.original_argv

    def create_temp_file(self, content: str) -> str:
        """Create a temporary file with given content."""
        temp_file = os.path.join(self.temp_dir, "test.csv")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        return temp_file

    @patch("artist_bio_gen.core.processor.logger")
    def test_main_function_verbose_flag(self, mock_logger):
        """Test that verbose flag is handled correctly."""
        content = """550e8400-e29b-41d4-a716-446655440037,Taylor Swift,Pop singer-songwriter"""
        temp_file = self.create_temp_file(content)

        sys.argv = [
            "py",
            "--input-file",
            temp_file,
            "--prompt-id",
            "test_prompt",
            "--verbose",
            "--dry-run",
        ]

        try:
            main()
        except SystemExit:
            pass

        # The verbose flag should be processed without error
        # (We can't easily test the actual logging level change without more complex mocking)


class TestQuotaMonitoringLogging(unittest.TestCase):
    """Test cases for quota monitoring and alerting logging functions."""

    def setUp(self):
        """Set up test fixtures."""
        from datetime import datetime

        # Create test quota metrics
        self.test_quota_metrics = QuotaMetrics(
            requests_used_today=50,
            daily_limit=100,
            usage_percentage=50.0,
            should_pause=False,
            pause_reason=None
        )

        # Create test quota status
        self.test_quota_status = QuotaStatus(
            requests_remaining=4950,
            requests_limit=5000,
            tokens_remaining=3900000,
            tokens_limit=4000000,
            reset_requests="60s",
            reset_tokens="60s",
            timestamp=datetime.now()
        )

    def test_log_quota_metrics_info_level(self):
        """Test logging quota metrics at info level (below warning threshold)."""
        mock_logger = MagicMock()

        log_quota_metrics(self.test_quota_metrics, "W01", mock_logger)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        # Check structured log format
        self.assertIn("QUOTA_METRICS:", log_message)
        self.assertIn('"event_type": "quota_metrics"', log_message)
        self.assertIn('"worker_id": "W01"', log_message)
        self.assertIn('"alert_level": "info"', log_message)
        self.assertIn('"usage_percentage": 50.0', log_message)

    def test_log_quota_metrics_warning_level(self):
        """Test logging quota metrics at warning level (60%+ usage)."""
        mock_logger = MagicMock()
        warning_metrics = QuotaMetrics(
            requests_used_today=65,
            daily_limit=100,
            usage_percentage=65.0,
            should_pause=False,
            pause_reason=None
        )

        log_quota_metrics(warning_metrics, "W02", mock_logger)

        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]

        self.assertIn("QUOTA_WARNING:", log_message)
        self.assertIn('"alert_level": "warning"', log_message)
        self.assertIn('"usage_percentage": 65.0', log_message)

    def test_log_quota_metrics_critical_level(self):
        """Test logging quota metrics at critical level (80%+ usage)."""
        mock_logger = MagicMock()
        critical_metrics = QuotaMetrics(
            requests_used_today=85,
            daily_limit=100,
            usage_percentage=85.0,
            should_pause=True,
            pause_reason="Critical threshold reached"
        )

        log_quota_metrics(critical_metrics, "W03", mock_logger)

        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]

        self.assertIn("QUOTA_CRITICAL:", log_message)
        self.assertIn('"alert_level": "critical"', log_message)
        self.assertIn('"should_pause": true', log_message)

    def test_log_quota_metrics_emergency_level(self):
        """Test logging quota metrics at emergency level (95%+ usage)."""
        mock_logger = MagicMock()
        emergency_metrics = QuotaMetrics(
            requests_used_today=97,
            daily_limit=100,
            usage_percentage=97.0,
            should_pause=True,
            pause_reason="Emergency threshold reached"
        )

        log_quota_metrics(emergency_metrics, "W04", mock_logger)

        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]

        self.assertIn("QUOTA_EMERGENCY:", log_message)
        self.assertIn('"alert_level": "emergency"', log_message)

    def test_log_quota_metrics_rate_limiting(self):
        """Test rate limiting functionality prevents log spam."""
        mock_logger = MagicMock()
        # Reset global state
        import artist_bio_gen.utils.logging as logging_module
        logging_module._last_quota_log_time = 0.0
        logging_module._last_quota_threshold = 0.0

        # Set short interval for testing
        set_quota_log_interval(1)

        # First call should log
        log_quota_metrics(self.test_quota_metrics, "W01", mock_logger)
        self.assertEqual(mock_logger.info.call_count, 1)

        # Immediate second call with same threshold should not log
        log_quota_metrics(self.test_quota_metrics, "W01", mock_logger)
        self.assertEqual(mock_logger.info.call_count, 1)  # Still 1, not 2

    def test_log_pause_event_with_resume_time(self):
        """Test logging pause event with scheduled resume time."""
        mock_logger = MagicMock()
        from datetime import datetime, timedelta

        resume_time = datetime.now() + timedelta(hours=1)
        log_pause_event("Quota threshold exceeded", resume_time, mock_logger)

        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]

        self.assertIn("QUOTA_PAUSE:", log_message)
        self.assertIn('"event_type": "quota_pause"', log_message)
        self.assertIn('"reason": "Quota threshold exceeded"', log_message)
        self.assertIn('"auto_resume": true', log_message)

    def test_log_pause_event_without_resume_time(self):
        """Test logging pause event without scheduled resume time."""
        mock_logger = MagicMock()
        log_pause_event("Manual pause requested", None, mock_logger)

        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]

        self.assertIn("QUOTA_PAUSE:", log_message)
        self.assertIn('"auto_resume": false', log_message)
        self.assertIn('"resume_time": null', log_message)

    def test_log_resume_event_with_quota_status(self):
        """Test logging resume event with quota status information."""
        mock_logger = MagicMock()
        duration_paused = 3661.5  # 1 hour, 1 minute, 1.5 seconds

        log_resume_event(duration_paused, self.test_quota_status, mock_logger)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        self.assertIn("QUOTA_RESUME:", log_message)
        self.assertIn('"event_type": "quota_resume"', log_message)
        self.assertIn('"duration_paused_seconds": 3661.5', log_message)
        self.assertIn('"duration_paused_minutes": 61.0', log_message)  # Allow minor rounding differences
        self.assertIn('"requests_remaining": 4950', log_message)
        self.assertIn('"tokens_remaining": 3900000', log_message)

    def test_log_resume_event_without_quota_status(self):
        """Test logging resume event without quota status information."""
        mock_logger = MagicMock()
        duration_paused = 120.5

        log_resume_event(duration_paused, None, mock_logger)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        self.assertIn("QUOTA_RESUME:", log_message)
        self.assertIn('"duration_paused_seconds": 120.5', log_message)
        # Should not contain quota status fields
        self.assertNotIn("requests_remaining", log_message)

    def test_log_rate_limit_event_quota_error(self):
        """Test logging rate limit event for quota errors."""
        mock_logger = MagicMock()
        log_rate_limit_event("insufficient_quota", 300, "W05", mock_logger)

        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]

        self.assertIn("RATE_LIMIT_QUOTA:", log_message)
        self.assertIn('"event_type": "rate_limit"', log_message)
        self.assertIn('"error_type": "insufficient_quota"', log_message)
        self.assertIn('"retry_after_seconds": 300', log_message)
        self.assertIn('"has_retry_after": true', log_message)

    def test_log_rate_limit_event_429_error(self):
        """Test logging rate limit event for 429 rate limiting."""
        mock_logger = MagicMock()
        log_rate_limit_event("rate_limit", 60, "W06", mock_logger)

        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]

        self.assertIn("RATE_LIMIT_429:", log_message)
        self.assertIn('"error_type": "rate_limit"', log_message)

    def test_log_rate_limit_event_no_retry_after(self):
        """Test logging rate limit event without Retry-After header."""
        mock_logger = MagicMock()
        log_rate_limit_event("server_error", None, "W07", mock_logger)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]

        self.assertIn("RATE_LIMIT_EVENT:", log_message)
        self.assertIn('"retry_after_seconds": null', log_message)
        self.assertIn('"has_retry_after": false', log_message)

    def test_set_quota_log_interval(self):
        """Test setting quota log interval."""
        import artist_bio_gen.utils.logging as logging_module

        original_interval = logging_module._quota_log_interval

        set_quota_log_interval(300)
        self.assertEqual(logging_module._quota_log_interval, 300)

        # Restore original
        logging_module._quota_log_interval = original_interval


if __name__ == "__main__":
    # Create a test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_classes = [
        TestProcessingStats,
        TestProgressBar,
        TestStatisticsCalculation,
        TestLoggingFunctions,
        TestLoggingConfiguration,
        TestEnhancedMainFunction,
        TestQuotaMonitoringLogging,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
