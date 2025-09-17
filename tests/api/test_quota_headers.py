#!/usr/bin/env python3
"""
Tests for quota header parsing functionality.

This module tests the HTTP header parsing, quota calculation,
and pause/resume logic for OpenAI API rate limiting.
"""

import threading
import time
import unittest
from datetime import datetime
from unittest.mock import patch

from artist_bio_gen.api.quota import (
    parse_rate_limit_headers,
    calculate_usage_metrics,
    should_pause_processing,
    QuotaMonitor,
    PauseController,
    _parse_header_int,
    _parse_reset_header
)
from artist_bio_gen.models.quota import QuotaStatus, QuotaMetrics


class TestHeaderParsing(unittest.TestCase):
    """Test HTTP header parsing functions."""

    def test_parse_rate_limit_headers_complete(self):
        """Test parsing with complete headers."""
        headers = {
            'x-ratelimit-remaining-requests': '4500',
            'x-ratelimit-limit-requests': '5000',
            'x-ratelimit-remaining-tokens': '3500000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60',
            'x-ratelimit-reset-tokens': '3600'
        }

        quota_status = parse_rate_limit_headers(headers)

        self.assertEqual(quota_status.requests_remaining, 4500)
        self.assertEqual(quota_status.requests_limit, 5000)
        self.assertEqual(quota_status.tokens_remaining, 3500000)
        self.assertEqual(quota_status.tokens_limit, 4000000)
        self.assertEqual(quota_status.reset_requests, '60')
        self.assertEqual(quota_status.reset_tokens, '3600')
        self.assertIsInstance(quota_status.timestamp, datetime)

    def test_parse_rate_limit_headers_missing(self):
        """Test parsing with missing headers (should use defaults)."""
        headers = {}

        quota_status = parse_rate_limit_headers(headers)

        self.assertEqual(quota_status.requests_remaining, 0)
        self.assertEqual(quota_status.requests_limit, 5000)
        self.assertEqual(quota_status.tokens_remaining, 4000000)  # Default to full tokens
        self.assertEqual(quota_status.tokens_limit, 4000000)
        self.assertEqual(quota_status.reset_requests, 'unknown')
        self.assertEqual(quota_status.reset_tokens, 'unknown')

    def test_parse_rate_limit_headers_with_usage_stats(self):
        """Test parsing with usage statistics from response body."""
        headers = {
            'x-ratelimit-remaining-requests': '4500',
            'x-ratelimit-limit-requests': '5000',
            'x-ratelimit-remaining-tokens': '3500000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60',
            'x-ratelimit-reset-tokens': '3600'
        }
        usage_stats = {'total_tokens': 1000}

        quota_status = parse_rate_limit_headers(headers, usage_stats)

        # Tokens remaining should be adjusted based on actual usage
        self.assertEqual(quota_status.tokens_remaining, 3499000)  # 3500000 - 1000

    def test_parse_rate_limit_headers_invalid_data(self):
        """Test parsing with invalid header values."""
        headers = {
            'x-ratelimit-remaining-requests': 'invalid',
            'x-ratelimit-limit-requests': '-100',
            'x-ratelimit-remaining-tokens': 'not_a_number',
            'x-ratelimit-limit-tokens': '0',  # Invalid limit
            'x-ratelimit-reset-requests': 'bad_format',
            'x-ratelimit-reset-tokens': 'also_bad'
        }

        # Should not raise exception, return safe defaults
        quota_status = parse_rate_limit_headers(headers)

        self.assertEqual(quota_status.requests_remaining, 0)
        self.assertEqual(quota_status.requests_limit, 5000)  # Falls back to safe default
        self.assertEqual(quota_status.tokens_remaining, 4000000)  # Falls back to safe default (full tokens)
        self.assertEqual(quota_status.tokens_limit, 4000000)  # Falls back to safe default


class TestHeaderParsingHelpers(unittest.TestCase):
    """Test helper functions for header parsing."""

    def test_parse_header_int_valid(self):
        """Test parsing valid integer headers."""
        headers = {'test': '123'}
        result = _parse_header_int(headers, 'test', 0)
        self.assertEqual(result, 123)

    def test_parse_header_int_missing(self):
        """Test parsing missing headers."""
        headers = {}
        result = _parse_header_int(headers, 'missing', 999)
        self.assertEqual(result, 999)

    def test_parse_header_int_invalid(self):
        """Test parsing invalid integer headers."""
        headers = {'test': 'not_a_number'}
        result = _parse_header_int(headers, 'test', 999)
        self.assertEqual(result, 999)

    def test_parse_header_int_negative(self):
        """Test parsing negative integers (should be clamped to 0)."""
        headers = {'test': '-50'}
        result = _parse_header_int(headers, 'test', 0)
        self.assertEqual(result, 0)

    def test_parse_reset_header_formats(self):
        """Test parsing various reset header formats."""
        headers = {
            'seconds': '60',
            'duration_s': '30s',
            'duration_m': '5m',
            'duration_ms': '500ms',
            'iso': '2024-01-01T12:00:00Z',
            'unknown': 'garbage',
            'float': '60.5'
        }

        self.assertEqual(_parse_reset_header(headers, 'seconds'), '60')
        self.assertEqual(_parse_reset_header(headers, 'duration_s'), '30s')
        self.assertEqual(_parse_reset_header(headers, 'duration_m'), '5m')
        self.assertEqual(_parse_reset_header(headers, 'duration_ms'), '500ms')
        self.assertEqual(_parse_reset_header(headers, 'iso'), '2024-01-01T12:00:00Z')
        self.assertEqual(_parse_reset_header(headers, 'unknown'), 'unknown')
        self.assertEqual(_parse_reset_header(headers, 'float'), '60')
        self.assertEqual(_parse_reset_header(headers, 'missing'), 'unknown')


class TestUsageCalculations(unittest.TestCase):
    """Test quota usage calculations."""

    def setUp(self):
        """Set up test fixtures."""
        self.quota_status = QuotaStatus(
            requests_remaining=4000,
            requests_limit=5000,
            tokens_remaining=3000000,
            tokens_limit=4000000,
            reset_requests='60',
            reset_tokens='3600',
            timestamp=datetime.now()
        )

    def test_calculate_usage_metrics_with_daily_limit(self):
        """Test usage calculation with daily limit."""
        metrics = calculate_usage_metrics(
            self.quota_status,
            daily_limit=1000,
            requests_used_today=200
        )

        self.assertEqual(metrics.requests_used_today, 200)
        self.assertEqual(metrics.daily_limit, 1000)
        self.assertEqual(metrics.usage_percentage, 20.0)  # 200/1000 * 100
        self.assertFalse(metrics.should_pause)
        self.assertIsNone(metrics.pause_reason)

    def test_calculate_usage_metrics_no_daily_limit(self):
        """Test usage calculation without daily limit."""
        metrics = calculate_usage_metrics(self.quota_status)

        self.assertEqual(metrics.requests_used_today, 0)
        self.assertIsNone(metrics.daily_limit)
        # Should use immediate rate limit usage: (5000-4000)/5000 * 100 = 20.0
        self.assertEqual(metrics.usage_percentage, 20.0)
        self.assertFalse(metrics.should_pause)

    def test_calculate_usage_metrics_pause_daily_threshold(self):
        """Test pause trigger based on daily limit."""
        metrics = calculate_usage_metrics(
            self.quota_status,
            daily_limit=1000,
            requests_used_today=850  # 85% usage
        )

        self.assertTrue(metrics.should_pause)
        self.assertIn("Daily quota 85.0% used", metrics.pause_reason)

    def test_calculate_usage_metrics_pause_rate_limit(self):
        """Test pause trigger based on immediate rate limit."""
        quota_status = QuotaStatus(
            requests_remaining=200,  # Only 200 out of 5000 remaining (96% used)
            requests_limit=5000,
            tokens_remaining=3000000,
            tokens_limit=4000000,
            reset_requests='60',
            reset_tokens='3600',
            timestamp=datetime.now()
        )

        metrics = calculate_usage_metrics(quota_status)

        self.assertTrue(metrics.should_pause)
        self.assertIn("Rate limit 96.0% used", metrics.pause_reason)

    def test_calculate_usage_metrics_pause_token_limit(self):
        """Test pause trigger based on token limit."""
        quota_status = QuotaStatus(
            requests_remaining=4000,
            requests_limit=5000,
            tokens_remaining=100000,  # Only 100k out of 4M remaining (97.5% used)
            tokens_limit=4000000,
            reset_requests='60',
            reset_tokens='3600',
            timestamp=datetime.now()
        )

        metrics = calculate_usage_metrics(quota_status)

        self.assertTrue(metrics.should_pause)
        self.assertIn("Token limit 97.5% used", metrics.pause_reason)


class TestPauseProcessing(unittest.TestCase):
    """Test pause processing logic."""

    def test_should_pause_processing_within_limits(self):
        """Test pause decision when within limits."""
        metrics = QuotaMetrics(
            requests_used_today=400,
            daily_limit=1000,
            usage_percentage=40.0,
            should_pause=False,
            pause_reason=None
        )

        should_pause, reason = should_pause_processing(metrics, threshold=0.8)
        self.assertFalse(should_pause)
        self.assertEqual(reason, "Within quota limits")

    def test_should_pause_processing_exceeds_threshold(self):
        """Test pause decision when exceeding custom threshold."""
        metrics = QuotaMetrics(
            requests_used_today=850,
            daily_limit=1000,
            usage_percentage=85.0,
            should_pause=False,  # Metrics don't think we should pause
            pause_reason=None
        )

        should_pause, reason = should_pause_processing(metrics, threshold=0.8)
        self.assertTrue(should_pause)
        self.assertIn("85.0% exceeds threshold 80.0%", reason)

    def test_should_pause_processing_metrics_say_pause(self):
        """Test pause decision when metrics indicate pause."""
        metrics = QuotaMetrics(
            requests_used_today=950,
            daily_limit=1000,
            usage_percentage=95.0,
            should_pause=True,
            pause_reason="Daily quota 95.0% used"
        )

        should_pause, reason = should_pause_processing(metrics, threshold=0.8)
        self.assertTrue(should_pause)
        self.assertEqual(reason, "Daily quota 95.0% used")


class TestQuotaMonitor(unittest.TestCase):
    """Test QuotaMonitor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.monitor = QuotaMonitor(daily_limit_requests=1000, pause_threshold=0.8)

    def test_quota_monitor_initialization(self):
        """Test QuotaMonitor initialization."""
        self.assertEqual(self.monitor.daily_limit_requests, 1000)
        self.assertEqual(self.monitor.pause_threshold, 0.8)
        self.assertEqual(self.monitor.requests_used_today, 0)
        self.assertIsNone(self.monitor.current_quota_status)
        self.assertIsNone(self.monitor.current_quota_metrics)

    def test_update_from_response(self):
        """Test updating monitor from API response."""
        headers = {
            'x-ratelimit-remaining-requests': '4500',
            'x-ratelimit-limit-requests': '5000',
            'x-ratelimit-remaining-tokens': '3500000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60',
            'x-ratelimit-reset-tokens': '3600'
        }

        metrics = self.monitor.update_from_response(headers)

        self.assertEqual(self.monitor.requests_used_today, 1)
        self.assertIsNotNone(self.monitor.current_quota_status)
        self.assertIsNotNone(self.monitor.current_quota_metrics)
        self.assertEqual(metrics.requests_used_today, 1)

    def test_should_pause_no_data(self):
        """Test pause decision with no data."""
        should_pause, reason = self.monitor.should_pause()
        self.assertFalse(should_pause)
        self.assertEqual(reason, "No quota data available")

    def test_can_resume_no_data(self):
        """Test resume decision with no data."""
        self.assertTrue(self.monitor.can_resume())

    def test_thread_safety(self):
        """Test thread safety of QuotaMonitor."""
        headers = {
            'x-ratelimit-remaining-requests': '4500',
            'x-ratelimit-limit-requests': '5000',
            'x-ratelimit-remaining-tokens': '3500000',
            'x-ratelimit-limit-tokens': '4000000',
            'x-ratelimit-reset-requests': '60',
            'x-ratelimit-reset-tokens': '3600'
        }

        def update_quota():
            for _ in range(10):
                self.monitor.update_from_response(headers)
                time.sleep(0.001)

        # Run multiple threads updating quota
        threads = [threading.Thread(target=update_quota) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have 30 requests total (3 threads * 10 updates each)
        self.assertEqual(self.monitor.requests_used_today, 30)

    @patch('artist_bio_gen.api.quota.datetime')
    def test_daily_reset(self, mock_datetime):
        """Test daily counter reset functionality."""
        # Set up initial state
        base_date = datetime(2024, 1, 1, 10, 0, 0)
        mock_datetime.now.return_value = base_date
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        # Initialize monitor (will set last_reset to today)
        monitor = QuotaMonitor(daily_limit_requests=1000)
        headers = {
            'x-ratelimit-remaining-requests': '4500',
            'x-ratelimit-limit-requests': '5000',
            'x-ratelimit-remaining-tokens': '3500000',
            'x-ratelimit-limit-tokens': '4000000'
        }

        # Make some requests on day 1
        monitor.update_from_response(headers)
        monitor.update_from_response(headers)
        self.assertEqual(monitor.requests_used_today, 2)

        # Move to next day
        next_day = datetime(2024, 1, 2, 10, 0, 0)
        mock_datetime.now.return_value = next_day

        # Next update should reset counter
        monitor.update_from_response(headers)
        self.assertEqual(monitor.requests_used_today, 1)  # Reset and incremented


class TestPauseController(unittest.TestCase):
    """Test PauseController class."""

    def test_pause_controller_initialization(self):
        """Test PauseController initialization."""
        controller = PauseController()
        self.assertFalse(controller.is_paused())
        self.assertIsNone(controller.get_pause_reason())

    def test_pause_and_resume(self):
        """Test basic pause and resume functionality."""
        controller = PauseController()

        # Initially not paused
        self.assertFalse(controller.is_paused())

        # Pause
        controller.pause("Test pause")
        self.assertTrue(controller.is_paused())
        self.assertEqual(controller.get_pause_reason(), "Test pause")

        # Resume
        controller.resume("Test resume")
        self.assertFalse(controller.is_paused())
        self.assertIsNone(controller.get_pause_reason())

    def test_wait_if_paused_not_paused(self):
        """Test wait when not paused (should return immediately)."""
        controller = PauseController()
        start_time = time.time()
        controller.wait_if_paused(timeout=1.0)
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 0.1)  # Should return quickly

    def test_wait_if_paused_timeout(self):
        """Test wait with timeout when paused."""
        controller = PauseController()
        controller.pause("Test pause")

        start_time = time.time()
        controller.wait_if_paused(timeout=0.05)  # Shorter timeout
        elapsed = time.time() - start_time
        self.assertGreaterEqual(elapsed, 0.05)
        self.assertTrue(controller.is_paused())

    def test_pause_resume_state_management(self):
        """Test pause/resume state management without timing dependencies."""
        controller = PauseController()

        # Test initial state
        self.assertFalse(controller.is_paused())
        self.assertIsNone(controller.get_pause_reason())

        # Test pause with future resume time
        future_time = time.time() + 3600  # 1 hour from now
        controller.pause("Test pause", resume_at=future_time)
        self.assertTrue(controller.is_paused())
        self.assertEqual(controller.get_pause_reason(), "Test pause")
        self.assertEqual(controller._resume_time, future_time)

        # Test manual resume clears resume time
        controller.resume("Manual resume")
        self.assertFalse(controller.is_paused())
        self.assertIsNone(controller.get_pause_reason())
        self.assertIsNone(controller._resume_time)

    def test_thread_safety(self):
        """Test thread safety of PauseController."""
        controller = PauseController()
        results = []

        def pause_resume_worker():
            controller.pause("Worker pause")
            time.sleep(0.01)
            controller.resume("Worker resume")
            results.append("completed")

        # Run multiple threads
        threads = [threading.Thread(target=pause_resume_worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 5)
        self.assertFalse(controller.is_paused())


if __name__ == '__main__':
    unittest.main()