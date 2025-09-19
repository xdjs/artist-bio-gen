"""
Unit tests for resource management components.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import tempfile
import os

from artist_bio_gen.core.resources import (
    ProcessingContext,
    OutputManager,
    TimerManager,
    ResourceCoordinator,
)


class TestProcessingContext(unittest.TestCase):
    """Test cases for ProcessingContext class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.jsonl', delete=False
        )
        self.output_path = self.temp_file.name
        self.temp_file.close()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.output_path):
            os.unlink(self.output_path)

    def test_context_initialization(self):
        """Test ProcessingContext initialization."""
        context = ProcessingContext(
            client=self.mock_client,
            output_path=self.output_path,
            db_pool=None,
            resume_mode=False,
            daily_request_limit=5000,
            quota_threshold=0.8,
            quota_monitoring=True,
        )

        self.assertEqual(context.client, self.mock_client)
        self.assertEqual(context.output_path, self.output_path)
        self.assertIsNone(context.db_pool)
        self.assertFalse(context.resume_mode)
        self.assertEqual(context.daily_request_limit, 5000)
        self.assertEqual(context.quota_threshold, 0.8)
        self.assertTrue(context.quota_monitoring_enabled)

    @patch('artist_bio_gen.core.resources.initialize_jsonl_output')
    @patch('artist_bio_gen.core.resources.QuotaMonitor')
    @patch('artist_bio_gen.core.resources.PauseController')
    def test_context_manager_enter(
        self, mock_pause_controller, mock_quota_monitor, mock_init_output
    ):
        """Test context manager enter method."""
        context = ProcessingContext(
            client=self.mock_client,
            output_path=self.output_path,
            quota_monitoring=True,
        )

        with context as ctx:
            self.assertEqual(ctx, context)
            mock_init_output.assert_called_once()
            mock_quota_monitor.assert_called_once()
            mock_pause_controller.assert_called_once()
            self.assertIsNotNone(context.quota_monitor)
            self.assertIsNotNone(context.pause_controller)
            self.assertTrue(context.output_initialized)

    @patch('artist_bio_gen.core.resources.initialize_jsonl_output')
    def test_context_without_quota_monitoring(self, mock_init_output):
        """Test context initialization without quota monitoring."""
        context = ProcessingContext(
            client=self.mock_client,
            output_path=self.output_path,
            quota_monitoring=False,
        )

        with context:
            mock_init_output.assert_called_once()
            self.assertIsNone(context.quota_monitor)
            self.assertIsNone(context.pause_controller)

    @patch('artist_bio_gen.core.resources.initialize_jsonl_output')
    def test_resume_mode(self, mock_init_output):
        """Test context initialization in resume mode."""
        context = ProcessingContext(
            client=self.mock_client,
            output_path=self.output_path,
            resume_mode=True,
        )

        with context:
            mock_init_output.assert_called_once_with(
                self.output_path, overwrite_existing=False
            )

    def test_get_quota_status_message(self):
        """Test quota status message generation."""
        context = ProcessingContext(
            client=self.mock_client,
            output_path=self.output_path,
            quota_monitoring=False,
        )

        # Without quota monitoring
        message = context.get_quota_status_message()
        self.assertEqual(message, "")

        # With quota monitoring
        context.quota_monitor = Mock()
        mock_metrics = Mock(usage_percentage=75.5)
        context.quota_monitor.get_current_metrics.return_value = mock_metrics

        message = context.get_quota_status_message()
        self.assertEqual(message, "Quota: 75.5% used")

        # With no metrics
        context.quota_monitor.get_current_metrics.return_value = None
        message = context.get_quota_status_message()
        self.assertEqual(message, "")


class TestOutputManager(unittest.TestCase):
    """Test cases for OutputManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.jsonl', delete=False
        )
        self.output_path = self.temp_file.name
        self.temp_file.close()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.output_path):
            os.unlink(self.output_path)

    def test_output_manager_initialization(self):
        """Test OutputManager initialization."""
        manager = OutputManager(self.output_path)
        self.assertEqual(manager.output_path, self.output_path)
        self.assertIsInstance(manager._lock, type(threading.Lock()))

    def test_write_lock_context_manager(self):
        """Test write lock context manager."""
        manager = OutputManager(self.output_path)

        with manager.write_lock():
            # Lock should be acquired
            self.assertFalse(manager._lock.acquire(blocking=False))

        # Lock should be released
        self.assertTrue(manager._lock.acquire(blocking=False))
        manager._lock.release()


class TestTimerManager(unittest.TestCase):
    """Test cases for TimerManager class."""

    def test_timer_manager_initialization(self):
        """Test TimerManager initialization."""
        manager = TimerManager()
        self.assertEqual(len(manager._active_timers), 0)
        self.assertIsInstance(manager._lock, type(threading.Lock()))

    def test_add_timer(self):
        """Test adding a timer."""
        manager = TimerManager()
        mock_timer = Mock(spec=threading.Timer)

        manager.add_timer(mock_timer)
        self.assertEqual(len(manager._active_timers), 1)
        self.assertIn(mock_timer, manager._active_timers)

    def test_cancel_all_timers(self):
        """Test cancelling all timers."""
        manager = TimerManager()

        # Add multiple mock timers
        mock_timers = [Mock(spec=threading.Timer) for _ in range(3)]
        for timer in mock_timers:
            manager.add_timer(timer)

        # Cancel all
        manager.cancel_all()

        # Verify all were cancelled
        for timer in mock_timers:
            timer.cancel.assert_called_once()

        # Verify list is empty
        self.assertEqual(len(manager._active_timers), 0)

    def test_context_manager(self):
        """Test TimerManager as context manager."""
        manager = TimerManager()
        mock_timer = Mock(spec=threading.Timer)

        with manager:
            manager.add_timer(mock_timer)
            self.assertEqual(len(manager._active_timers), 1)

        # Exiting context should cancel all timers
        mock_timer.cancel.assert_called_once()
        self.assertEqual(len(manager._active_timers), 0)


class TestResourceCoordinator(unittest.TestCase):
    """Test cases for ResourceCoordinator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_context = Mock(spec=ProcessingContext)
        self.mock_context.output_path = "/tmp/test.jsonl"
        self.mock_context.quota_monitor = Mock()
        self.mock_context.pause_controller = Mock()

    def test_coordinator_initialization(self):
        """Test ResourceCoordinator initialization."""
        coordinator = ResourceCoordinator(self.mock_context)

        self.assertEqual(coordinator.context, self.mock_context)
        self.assertIsNotNone(coordinator.output_manager)
        self.assertIsNotNone(coordinator.timer_manager)

    def test_should_pause_for_quota(self):
        """Test quota pause checking."""
        coordinator = ResourceCoordinator(self.mock_context)

        # Test with quota monitor returning should pause
        self.mock_context.quota_monitor.should_pause.return_value = (
            True, "Quota exceeded"
        )
        should_pause, reason = coordinator.should_pause_for_quota()
        self.assertTrue(should_pause)
        self.assertEqual(reason, "Quota exceeded")

        # Test with no quota monitor
        self.mock_context.quota_monitor = None
        should_pause, reason = coordinator.should_pause_for_quota()
        self.assertFalse(should_pause)
        self.assertIsNone(reason)

    def test_pause_processing(self):
        """Test processing pause."""
        coordinator = ResourceCoordinator(self.mock_context)

        # Test successful pause
        self.mock_context.pause_controller.pause.return_value = True
        result = coordinator.pause_processing("Test reason", resume_at=123.45)

        self.assertTrue(result)
        self.mock_context.pause_controller.pause.assert_called_once_with(
            "Test reason", resume_at=123.45
        )

        # Test with no pause controller
        self.mock_context.pause_controller = None
        result = coordinator.pause_processing("Test reason")
        self.assertFalse(result)

    def test_wait_if_paused(self):
        """Test wait if paused."""
        coordinator = ResourceCoordinator(self.mock_context)

        # Test with pause controller
        coordinator.wait_if_paused()
        self.mock_context.pause_controller.wait_if_paused.assert_called_once()

        # Test without pause controller
        self.mock_context.pause_controller = None
        coordinator.wait_if_paused()  # Should not raise

    def test_context_manager(self):
        """Test ResourceCoordinator as context manager."""
        coordinator = ResourceCoordinator(self.mock_context)
        mock_timer = Mock(spec=threading.Timer)

        with coordinator:
            coordinator.timer_manager.add_timer(mock_timer)

        # Should cancel timers on exit
        mock_timer.cancel.assert_called_once()


if __name__ == '__main__':
    unittest.main()