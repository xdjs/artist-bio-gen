"""
Unit tests for progress tracking components.
"""

import unittest
from unittest.mock import patch, Mock
import time
import logging

from artist_bio_gen.core.progress import ProgressTracker, BatchProgressReporter


class TestProgressTracker(unittest.TestCase):
    """Test cases for ProgressTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = ProgressTracker(total_items=100, log_interval_percent=10)

    def test_initialization(self):
        """Test ProgressTracker initialization."""
        self.assertEqual(self.tracker.total_items, 100)
        self.assertEqual(self.tracker.successful_items, 0)
        self.assertEqual(self.tracker.failed_items, 0)
        self.assertEqual(self.tracker.log_interval, 10)  # 10% of 100
        self.assertEqual(self.tracker.min_time_between_logs, 5.0)

    def test_update_success(self):
        """Test updating with successful item."""
        with patch('artist_bio_gen.core.progress.logger') as mock_logger:
            self.tracker.update(
                success=True,
                artist_name="Test Artist",
                duration=1.5,
                worker_id="W01"
            )

            self.assertEqual(self.tracker.successful_items, 1)
            self.assertEqual(self.tracker.failed_items, 0)

            # Check that info log was called for success
            mock_logger.info.assert_called()

    def test_update_failure(self):
        """Test updating with failed item."""
        with patch('artist_bio_gen.core.progress.logger') as mock_logger:
            self.tracker.update(
                success=False,
                artist_name="Test Artist",
                duration=0.0,
                worker_id="W01"
            )

            self.assertEqual(self.tracker.successful_items, 0)
            self.assertEqual(self.tracker.failed_items, 1)

            # Check that warning log was called for failure
            mock_logger.warning.assert_called()

    def test_should_log_summary_interval(self):
        """Test summary logging based on interval."""
        # Should not log initially
        self.assertFalse(self.tracker.should_log_summary())

        # Add 9 items - should not trigger (less than 10%)
        for i in range(9):
            self.tracker.successful_items += 1
            self.assertFalse(self.tracker.should_log_summary())

        # Add 10th item - should trigger (10% reached)
        self.tracker.successful_items += 1
        self.assertTrue(self.tracker.should_log_summary())

    def test_should_log_summary_time(self):
        """Test summary logging based on time."""
        # Should not log initially
        self.assertFalse(self.tracker.should_log_summary())

        # Simulate time passing
        self.tracker.last_log_time -= 6.0  # 6 seconds ago

        # Should trigger due to time
        self.assertTrue(self.tracker.should_log_summary())

    def test_should_log_summary_completion(self):
        """Test summary logging on completion."""
        # Process all items
        self.tracker.successful_items = 100

        # Should trigger due to completion
        self.assertTrue(self.tracker.should_log_summary())

    def test_log_summary(self):
        """Test summary logging."""
        with patch('artist_bio_gen.core.progress.logger') as mock_logger:
            # Set some progress
            self.tracker.successful_items = 50
            self.tracker.failed_items = 5
            self.tracker.start_time = time.time() - 10  # 10 seconds ago

            # Log summary without quota
            self.tracker.log_summary()

            # Verify log was called
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]

            # Check message content
            self.assertIn("55/100", call_args)  # Total processed
            self.assertIn("55.0%", call_args)  # Progress percentage
            self.assertIn("artists/sec", call_args)  # Rate
            self.assertIn("remaining", call_args)  # ETA

            # Test with quota status
            mock_logger.reset_mock()
            self.tracker.log_summary(quota_status_message="Quota: 80.0% used")

            call_args = mock_logger.info.call_args[0][0]
            self.assertIn("Quota: 80.0% used", call_args)

    def test_get_stats(self):
        """Test getting statistics."""
        self.tracker.successful_items = 75
        self.tracker.failed_items = 25

        successful, failed = self.tracker.get_stats()
        self.assertEqual(successful, 75)
        self.assertEqual(failed, 25)

    def test_small_item_count(self):
        """Test with very small item count."""
        tracker = ProgressTracker(total_items=5, log_interval_percent=10)

        # Log interval should be at least 1
        self.assertEqual(tracker.log_interval, 1)


class TestBatchProgressReporter(unittest.TestCase):
    """Test cases for BatchProgressReporter class."""

    @patch('artist_bio_gen.core.progress.logger')
    def test_log_start(self, mock_logger):
        """Test batch start logging."""
        BatchProgressReporter.log_start(
            total_artists=100,
            prompt_id="test-prompt",
            version="v1",
            workers=4,
            test_mode=True,
            db_enabled=True,
            quota_monitoring=True
        )

        # Verify multiple info logs were made
        self.assertGreater(mock_logger.info.call_count, 5)

        # Check that key information was logged
        calls_str = str(mock_logger.info.call_args_list)
        self.assertIn("100", calls_str)  # Total artists
        self.assertIn("test-prompt", calls_str)  # Prompt ID
        self.assertIn("v1", calls_str)  # Version
        self.assertIn("4", calls_str)  # Workers

    @patch('artist_bio_gen.core.progress.logger')
    def test_log_start_without_version(self, mock_logger):
        """Test batch start logging without version."""
        BatchProgressReporter.log_start(
            total_artists=50,
            prompt_id="test-prompt",
            version=None,
            workers=2,
            test_mode=False,
            db_enabled=False,
            quota_monitoring=False
        )

        # Verify logs were made
        self.assertGreater(mock_logger.info.call_count, 5)

        # Version should not be in logs
        calls_str = str(mock_logger.info.call_args_list)
        self.assertNotIn("Prompt Version:", calls_str)

    @patch('artist_bio_gen.core.progress.logger')
    def test_log_completion(self, mock_logger):
        """Test batch completion logging."""
        BatchProgressReporter.log_completion(
            successful_calls=90,
            failed_calls=10,
            duration=100.0
        )

        # Verify multiple info logs were made
        self.assertGreater(mock_logger.info.call_count, 5)

        # Check that statistics were logged
        calls_str = str(mock_logger.info.call_args_list)
        self.assertIn("100", calls_str)  # Total processed
        self.assertIn("90", calls_str)  # Successful
        self.assertIn("10", calls_str)  # Failed
        self.assertIn("90.0%", calls_str)  # Success rate
        self.assertIn("100.00", calls_str)  # Duration
        self.assertIn("1.00", calls_str)  # Average time

    @patch('artist_bio_gen.core.progress.logger')
    def test_log_completion_zero_calls(self, mock_logger):
        """Test batch completion logging with zero calls."""
        BatchProgressReporter.log_completion(
            successful_calls=0,
            failed_calls=0,
            duration=0.0
        )

        # Should not crash with zero division
        self.assertGreater(mock_logger.info.call_count, 5)

        calls_str = str(mock_logger.info.call_args_list)
        self.assertIn("0", calls_str)  # Total processed
        self.assertIn("0.0%", calls_str)  # Success rate (0/0 handled)


if __name__ == '__main__':
    unittest.main()