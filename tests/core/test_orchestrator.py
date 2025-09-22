"""
Unit tests for processing orchestration components.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
from concurrent.futures import Future
import time
import threading

from artist_bio_gen.core.orchestrator import ProcessingOrchestrator
from artist_bio_gen.core.resources import ProcessingContext
from artist_bio_gen.models import ArtistData, ApiResponse


class TestProcessingOrchestrator(unittest.TestCase):
    """Test cases for ProcessingOrchestrator class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock context
        self.mock_context = Mock(spec=ProcessingContext)
        self.mock_context.client = Mock()
        self.mock_context.output_path = "/tmp/test.jsonl"
        self.mock_context.db_pool = Mock()
        self.mock_context.quota_monitor = Mock()
        self.mock_context.pause_controller = Mock()

        # Create test artists
        self.test_artists = [
            ArtistData(
                artist_id=f"id_{i}",
                name=f"Artist {i}",
                data={"bio": f"Bio for artist {i}"}
            )
            for i in range(5)
        ]

        # Create orchestrator
        self.orchestrator = ProcessingOrchestrator(
            context=self.mock_context,
            prompt_id="test-prompt",
            version="v1",
            max_workers=2,
            test_mode=False
        )

    def test_initialization(self):
        """Test orchestrator initialization."""
        self.assertEqual(self.orchestrator.context, self.mock_context)
        self.assertEqual(self.orchestrator.prompt_id, "test-prompt")
        self.assertEqual(self.orchestrator.version, "v1")
        self.assertEqual(self.orchestrator.max_workers, 2)
        self.assertFalse(self.orchestrator.test_mode)
        self.assertIsNotNone(self.orchestrator.resource_coordinator)
        self.assertIsNotNone(self.orchestrator.timer_manager)

    @patch('artist_bio_gen.core.orchestrator.ThreadPoolExecutor')
    @patch('artist_bio_gen.core.orchestrator.as_completed')
    @patch('artist_bio_gen.core.orchestrator.call_openai_api')
    @patch('artist_bio_gen.core.orchestrator.ProgressTracker')
    def test_process_artists_success(
        self, mock_progress_tracker_class, mock_call_api, mock_as_completed, mock_executor_class
    ):
        """Test successful processing of artists."""
        # Setup mock progress tracker
        mock_tracker = Mock()
        mock_tracker.should_log_summary.return_value = False
        mock_tracker.get_stats.return_value = (5, 0)
        mock_progress_tracker_class.return_value = mock_tracker

        # Setup mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Setup mock futures
        mock_futures = []
        for i, artist in enumerate(self.test_artists):
            future = Mock(spec=Future)
            api_response = ApiResponse(
                artist_id=artist.artist_id,
                artist_name=artist.name,
                artist_data=artist.data,
                response_text=f"Generated bio for {artist.name}",
                response_id=f"resp_{i}",
                created=int(time.time()),
                error=None
            )
            future.result.return_value = (api_response, 1.0)
            mock_futures.append(future)

        # Configure executor.submit to return futures
        mock_executor.submit.side_effect = mock_futures

        # Configure as_completed to return futures in order
        mock_as_completed.return_value = iter(mock_futures)

        # Process artists
        with patch('artist_bio_gen.core.orchestrator.append_jsonl_response'):
            successful, failed = self.orchestrator.process_artists(self.test_artists)

        # Verify results
        self.assertEqual(successful, 5)
        self.assertEqual(failed, 0)

        # Verify executor was used correctly
        self.assertEqual(mock_executor.submit.call_count, 5)

        # Verify timer cleanup
        self.orchestrator.timer_manager.cancel_all()

    @patch('artist_bio_gen.core.orchestrator.ThreadPoolExecutor')
    @patch('artist_bio_gen.core.orchestrator.as_completed')
    @patch('artist_bio_gen.core.orchestrator.ProgressTracker')
    def test_process_artists_with_errors(
        self, mock_progress_tracker_class, mock_as_completed, mock_executor_class
    ):
        """Test processing with some errors."""
        # Setup mock progress tracker
        mock_tracker = Mock()
        mock_tracker.should_log_summary.return_value = False
        mock_tracker.get_stats.return_value = (2, 1)
        mock_progress_tracker_class.return_value = mock_tracker

        # Setup mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Setup mock futures with one error
        mock_futures = []
        for i, artist in enumerate(self.test_artists[:3]):
            future = Mock(spec=Future)

            if i == 1:
                # Second artist fails
                api_response = ApiResponse(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    artist_data=artist.data,
                    response_text="",
                    response_id="",
                    created=0,
                    error="API Error: Rate limit exceeded"
                )
            else:
                # Others succeed
                api_response = ApiResponse(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    artist_data=artist.data,
                    response_text=f"Generated bio for {artist.name}",
                    response_id=f"resp_{i}",
                    created=int(time.time()),
                    error=None
                )

            future.result.return_value = (api_response, 1.0)
            mock_futures.append(future)

        mock_executor.submit.side_effect = mock_futures
        mock_as_completed.return_value = iter(mock_futures)

        # Process artists
        with patch('artist_bio_gen.core.orchestrator.append_jsonl_response'):
            successful, failed = self.orchestrator.process_artists(
                self.test_artists[:3]
            )

        # Verify results
        self.assertEqual(successful, 2)
        self.assertEqual(failed, 1)

    @patch('artist_bio_gen.core.orchestrator.ThreadPoolExecutor')
    @patch('artist_bio_gen.core.orchestrator.as_completed')
    def test_process_artists_with_exception(
        self, mock_as_completed, mock_executor_class
    ):
        """Test processing with exception during API call."""
        # Setup mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Setup mock future that raises exception
        mock_future = Mock(spec=Future)
        mock_future.result.side_effect = Exception("Network error")
        mock_executor.submit.return_value = mock_future
        mock_as_completed.return_value = iter([mock_future])

        # Process single artist
        with patch('artist_bio_gen.core.orchestrator.append_jsonl_response'):
            with patch('artist_bio_gen.core.orchestrator.logger') as mock_logger:
                successful, failed = self.orchestrator.process_artists(
                    [self.test_artists[0]]
                )

        # Verify error handling
        self.assertEqual(successful, 0)
        self.assertEqual(failed, 1)

        # Verify error was logged
        mock_logger.error.assert_called()

    def test_check_and_handle_quota_pause(self):
        """Test quota pause checking and handling."""
        # Mock the resource coordinator methods
        self.orchestrator.resource_coordinator = Mock()
        self.orchestrator.resource_coordinator.should_pause_for_quota.return_value = (
            True, "Daily limit reached"
        )
        self.orchestrator.resource_coordinator.pause_processing.return_value = True

        with patch.object(
            self.orchestrator, '_estimate_resume_time'
        ) as mock_estimate:
            with patch.object(
                self.orchestrator, '_schedule_auto_resume'
            ) as mock_schedule:
                mock_estimate.return_value = time.time() + 3600  # 1 hour from now

                self.orchestrator._check_and_handle_quota_pause()

                # Verify pause was initiated
                self.orchestrator.resource_coordinator.pause_processing.assert_called_once()

                # Verify auto-resume was scheduled
                mock_schedule.assert_called_once()

    def test_estimate_resume_time(self):
        """Test resume time estimation."""
        # Test with reset hints
        mock_status = Mock()
        mock_status.reset_requests = "3600s"
        mock_status.reset_tokens = None
        self.mock_context.quota_monitor.get_current_status.return_value = mock_status

        resume_time = self.orchestrator._estimate_resume_time()
        self.assertIsNotNone(resume_time)
        self.assertGreater(resume_time, time.time())

        # Test with daily limit fallback
        mock_status.reset_requests = None
        mock_status.reset_tokens = None
        self.mock_context.quota_monitor.daily_limit_requests = 5000

        resume_time = self.orchestrator._estimate_resume_time()
        self.assertIsNotNone(resume_time)

        # Test with no quota monitor
        self.orchestrator.context.quota_monitor = None
        resume_time = self.orchestrator._estimate_resume_time()
        self.assertIsNone(resume_time)

    def test_parse_reset_to_timestamp(self):
        """Test parsing of reset values to timestamps."""
        now = time.time()

        # Test duration suffixes
        result = self.orchestrator._parse_reset_to_timestamp("60s")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, now + 60, delta=1)

        result = self.orchestrator._parse_reset_to_timestamp("5m")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, now + 300, delta=1)

        result = self.orchestrator._parse_reset_to_timestamp("2h")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, now + 7200, delta=1)

        result = self.orchestrator._parse_reset_to_timestamp("500ms")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, now + 0.5, delta=1)

        # Test raw seconds
        result = self.orchestrator._parse_reset_to_timestamp("120")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, now + 120, delta=1)

        # Test invalid values
        result = self.orchestrator._parse_reset_to_timestamp("unknown")
        self.assertIsNone(result)

        result = self.orchestrator._parse_reset_to_timestamp("")
        self.assertIsNone(result)

        result = self.orchestrator._parse_reset_to_timestamp(None)
        self.assertIsNone(result)

    @patch('artist_bio_gen.core.orchestrator.threading.Timer')
    def test_schedule_auto_resume(self, mock_timer_class):
        """Test auto-resume scheduling."""
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        resume_at = time.time() + 60  # 1 minute from now

        self.orchestrator._schedule_auto_resume(resume_at)

        # Verify timer was created and started
        mock_timer_class.assert_called_once()
        mock_timer.start.assert_called_once()

        # Verify timer was added to manager
        self.assertEqual(len(self.orchestrator.timer_manager._active_timers), 1)

        # Test with no pause controller
        self.orchestrator.context.pause_controller = None
        self.orchestrator._schedule_auto_resume(resume_at)

        # No additional timer should be created
        self.assertEqual(mock_timer_class.call_count, 1)

    def test_submit_tasks_with_pause(self):
        """Test task submission with pause checking."""
        mock_executor = MagicMock()

        # Create mock futures
        mock_futures = [Mock(spec=Future), Mock(spec=Future)]
        mock_executor.submit.side_effect = mock_futures

        # Mock the resource coordinator
        self.orchestrator.resource_coordinator = Mock()

        # Submit tasks
        futures = self.orchestrator._submit_tasks(
            mock_executor, self.test_artists[:2]
        )

        # Verify pause check was called
        self.assertEqual(
            self.orchestrator.resource_coordinator.wait_if_paused.call_count, 2
        )

        # Verify futures were created
        self.assertEqual(len(futures), 2)

        # Verify worker IDs were assigned correctly
        for future, (artist, worker_id) in futures.items():
            self.assertIn(artist, self.test_artists[:2])
            self.assertIn(worker_id, ["W01", "W02"])


if __name__ == '__main__':
    unittest.main()