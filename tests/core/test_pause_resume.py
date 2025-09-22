#!/usr/bin/env python3
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from artist_bio_gen.api.quota import (
    QuotaMonitor,
    PauseController,
    parse_rate_limit_headers,
)
from artist_bio_gen.core.processor import process_artists_concurrent
from artist_bio_gen.models import ArtistData


class TestPauseResume(unittest.TestCase):
    def test_quota_monitor_persistence_roundtrip(self):
        qm = QuotaMonitor(daily_limit_requests=100, pause_threshold=0.8)

        # Simulate an update from response
        headers = {
            'x-ratelimit-remaining-requests': '95',
            'x-ratelimit-limit-requests': '100',
            'x-ratelimit-remaining-tokens': '3999000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60s',
            'x-ratelimit-reset-tokens': '60s',
        }
        qm.update_from_response(headers, usage_stats={'total_tokens': 100})

        # Persist and reload
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'quota_state.json')
            qm.persist_state(path)

            qm2 = QuotaMonitor()
            ok = qm2.load_state(path)
            self.assertTrue(ok)
            self.assertEqual(qm2.daily_limit_requests, 100)
            self.assertAlmostEqual(qm2.pause_threshold, 0.8)
            self.assertGreaterEqual(qm2.requests_used_today, 1)
            self.assertIsNotNone(qm2.get_current_status())
            self.assertIsNotNone(qm2.get_current_metrics())

    def test_pause_controller_pause_resume(self):
        pc = PauseController()
        self.assertFalse(pc.is_paused())

        pc.pause("Testing pause")
        self.assertTrue(pc.is_paused())
        self.assertEqual(pc.get_pause_reason(), "Testing pause")

        # wait_if_paused should block until resumed; simulate with a thread
        unblock = []
        def waiter():
            pc.wait_if_paused(timeout=0.2)
            unblock.append(True)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)
        pc.resume("Done")
        t.join(timeout=1.0)
        self.assertTrue(unblock)
        self.assertFalse(pc.is_paused())

    def test_pause_controller_auto_resume(self):
        pc = PauseController()
        pc.pause("Auto", resume_at=time.time() + 0.1)
        self.assertTrue(pc.is_paused())

        # wait_if_paused should auto-resume shortly
        pc.wait_if_paused(timeout=0.5)
        self.assertFalse(pc.is_paused())

    def test_pause_controller_schedule_resume(self):
        pc = PauseController()
        pc.pause("Schedule")
        ts = time.time() + 0.05
        pc.resume_at(ts)
        # It should auto-resume by time
        pc.wait_if_paused(timeout=0.5)
        self.assertFalse(pc.is_paused())

    def test_processor_quota_integration(self):
        """Test that processor properly integrates with quota monitoring and pause/resume."""
        # Create test artists
        artists = [
            ArtistData(artist_id=1, name="Test Artist 1", data="Test data 1"),
            ArtistData(artist_id=2, name="Test Artist 2", data="Test data 2"),
        ]

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.output_text = "Test bio"
        mock_response.id = "test_response_id"
        mock_response.created_at = 1234567890
        mock_response.usage = None

        # Mock successful API calls
        with patch('artist_bio_gen.core.orchestrator.call_openai_api') as mock_call_api:
            # Setup mock to return successful response
            from artist_bio_gen.models import ApiResponse
            mock_api_response = ApiResponse(
                artist_id=1,
                artist_name="Test Artist",
                artist_data="Test data",
                response_text="Test bio",
                response_id="test_id",
                created=1234567890,
                db_status="null",
                error=None
            )
            mock_call_api.return_value = (mock_api_response, 0.5)

            # Test with quota monitoring enabled
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "test_output.jsonl")

                successful, failed = process_artists_concurrent(
                    artists=artists,
                    client=mock_client,
                    prompt_id="test_prompt",
                    version=None,
                    max_workers=1,
                    output_path=output_path,
                    db_pool=None,
                    test_mode=True,
                    resume_mode=False,
                    daily_request_limit=100,
                    quota_threshold=0.8,
                    quota_monitoring=True,
                )

                # Verify basic processing
                self.assertEqual(successful + failed, len(artists))

                # Verify that call_openai_api was called with quota parameters
                self.assertEqual(mock_call_api.call_count, len(artists))
                for call_args in mock_call_api.call_args_list:
                    args, kwargs = call_args
                    # Check that quota_monitor and pause_controller were passed
                    self.assertIsNotNone(args[8])  # quota_monitor
                    self.assertIsNotNone(args[9])  # pause_controller

    def test_processor_auto_resumes_after_quota_pause(self):
        artists = [
            ArtistData(artist_id=1, name="A", data="data"),
            ArtistData(artist_id=2, name="B", data="data"),
        ]

        resume_timestamp = time.time() + 60

        with patch("artist_bio_gen.core.orchestrator.call_openai_api") as mock_call_api, \
             patch(
                 "artist_bio_gen.core.orchestrator.ProcessingOrchestrator._estimate_resume_time",
                 return_value=resume_timestamp,
             ) as mock_estimate, \
             patch("artist_bio_gen.core.orchestrator.threading.Timer") as mock_timer_ctor, \
             patch.object(
                 QuotaMonitor,
                 "should_pause",
                 side_effect=[(True, "Daily quota reached"), (False, "Within quota")],
             ):

            from artist_bio_gen.models import ApiResponse

            mock_api_response = ApiResponse(
                artist_id=1,
                artist_name="Test Artist",
                artist_data="Test data",
                response_text="Test bio",
                response_id="test_id",
                created=1234567890,
                db_status="null",
                error=None,
            )
            mock_call_api.return_value = (mock_api_response, 0.1)

            timer_instance = Mock()
            timer_instance.start = Mock()
            mock_timer_ctor.return_value = timer_instance

            resume_values = []
            original_pause = PauseController.pause

            def pause_wrapper(self, reason, resume_at=None):
                resume_values.append(resume_at)
                return original_pause(self, reason, resume_at)

            with patch.object(PauseController, "pause", new=pause_wrapper):
                with tempfile.TemporaryDirectory() as tmpdir:
                    output_path = os.path.join(tmpdir, "output.jsonl")

                    process_artists_concurrent(
                        artists=artists,
                        client=Mock(),
                        prompt_id="prompt",
                        version=None,
                        max_workers=1,
                        output_path=output_path,
                        db_pool=None,
                        test_mode=True,
                        resume_mode=False,
                        daily_request_limit=10,
                        quota_threshold=0.8,
                        quota_monitoring=True,
                    )

        self.assertTrue(resume_values)
        self.assertEqual(resume_values[0], resume_timestamp)
        mock_estimate.assert_called()
        mock_timer_ctor.assert_called_once()

        delay_arg = mock_timer_ctor.call_args[0][0]
        resume_callable = mock_timer_ctor.call_args[0][1]
        self.assertGreaterEqual(delay_arg, 0.0)
        self.assertTrue(callable(resume_callable))

        timer_instance.start.assert_called_once()
        self.assertTrue(timer_instance.daemon)

    def test_processor_quota_disabled(self):
        """Test that processor works correctly with quota monitoring disabled."""
        # Create test artists
        artists = [ArtistData(artist_id=1, name="Test Artist 1", data="Test data 1")]

        # Mock OpenAI client
        mock_client = Mock()

        # Mock successful API calls
        with patch('artist_bio_gen.core.orchestrator.call_openai_api') as mock_call_api:
            from artist_bio_gen.models import ApiResponse
            mock_api_response = ApiResponse(
                artist_id=1,
                artist_name="Test Artist",
                artist_data="Test data",
                response_text="Test bio",
                response_id="test_id",
                created=1234567890,
                db_status="null",
                error=None
            )
            mock_call_api.return_value = (mock_api_response, 0.5)

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "test_output.jsonl")

                successful, failed = process_artists_concurrent(
                    artists=artists,
                    client=mock_client,
                    prompt_id="test_prompt",
                    version=None,
                    max_workers=1,
                    output_path=output_path,
                    quota_monitoring=False,  # Disabled
                )

                # Verify basic processing
                self.assertEqual(successful + failed, len(artists))

                # Verify that call_openai_api was called with None quota parameters
                self.assertEqual(mock_call_api.call_count, len(artists))
                args, kwargs = mock_call_api.call_args_list[0]
                self.assertIsNone(args[8])  # quota_monitor should be None
                self.assertIsNone(args[9])  # pause_controller should be None


if __name__ == "__main__":
    unittest.main()

