#!/usr/bin/env python3
"""
Tests for quota management models.

This module tests the data structures and methods for quota monitoring
and error classification.
"""

import json
import unittest
from datetime import datetime
from artist_bio_gen.models.quota import (
    QuotaStatus,
    QuotaMetrics,
    ErrorClassification,
    serialize_quota_state,
    deserialize_quota_state
)


class TestQuotaStatus(unittest.TestCase):
    """Test QuotaStatus model."""

    def setUp(self):
        """Set up test fixtures."""
        self.timestamp = datetime.now()
        self.quota_status = QuotaStatus(
            requests_remaining=4500,
            requests_limit=5000,
            tokens_remaining=3500000,
            tokens_limit=4000000,
            reset_requests="2024-01-01T12:00:00Z",
            reset_tokens="2024-01-01T12:00:00Z",
            timestamp=self.timestamp
        )

    def test_quota_status_creation(self):
        """Test basic QuotaStatus creation."""
        self.assertEqual(self.quota_status.requests_remaining, 4500)
        self.assertEqual(self.quota_status.requests_limit, 5000)
        self.assertEqual(self.quota_status.tokens_remaining, 3500000)
        self.assertEqual(self.quota_status.tokens_limit, 4000000)

    def test_quota_status_validation(self):
        """Test QuotaStatus validation."""
        # Test negative values are clamped to 0
        quota = QuotaStatus(
            requests_remaining=-10,
            requests_limit=5000,
            tokens_remaining=-1000,
            tokens_limit=4000000,
            reset_requests="2024-01-01T12:00:00Z",
            reset_tokens="2024-01-01T12:00:00Z",
            timestamp=self.timestamp
        )
        self.assertEqual(quota.requests_remaining, 0)
        self.assertEqual(quota.tokens_remaining, 0)

        # Test invalid limits raise errors
        with self.assertRaises(ValueError):
            QuotaStatus(
                requests_remaining=100,
                requests_limit=0,  # Invalid
                tokens_remaining=1000,
                tokens_limit=4000000,
                reset_requests="2024-01-01T12:00:00Z",
                reset_tokens="2024-01-01T12:00:00Z",
                timestamp=self.timestamp
            )

    def test_requests_usage_percentage(self):
        """Test requests usage percentage calculation."""
        percentage = self.quota_status.get_requests_usage_percentage()
        # (5000 - 4500) / 5000 * 100 = 10.0
        self.assertEqual(percentage, 10.0)

        # Test edge case with zero limit
        quota = QuotaStatus(
            requests_remaining=0,
            requests_limit=1,  # Minimum valid
            tokens_remaining=0,
            tokens_limit=1,
            reset_requests="2024-01-01T12:00:00Z",
            reset_tokens="2024-01-01T12:00:00Z",
            timestamp=self.timestamp
        )
        quota.requests_limit = 0  # Bypass validation for edge case test
        self.assertEqual(quota.get_requests_usage_percentage(), 0.0)

    def test_tokens_usage_percentage(self):
        """Test tokens usage percentage calculation."""
        percentage = self.quota_status.get_tokens_usage_percentage()
        # (4000000 - 3500000) / 4000000 * 100 = 12.5
        self.assertEqual(percentage, 12.5)

    def test_serialization(self):
        """Test QuotaStatus serialization and deserialization."""
        # Test to_dict
        data = self.quota_status.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data['requests_remaining'], 4500)
        self.assertEqual(data['timestamp'], self.timestamp.isoformat())

        # Test from_dict
        restored = QuotaStatus.from_dict(data)
        self.assertEqual(restored.requests_remaining, self.quota_status.requests_remaining)
        self.assertEqual(restored.timestamp, self.quota_status.timestamp)


class TestQuotaMetrics(unittest.TestCase):
    """Test QuotaMetrics model."""

    def setUp(self):
        """Set up test fixtures."""
        self.quota_metrics = QuotaMetrics(
            requests_used_today=1000,
            daily_limit=5000,
            usage_percentage=20.0,
            should_pause=False,
            pause_reason=None
        )

    def test_quota_metrics_creation(self):
        """Test basic QuotaMetrics creation."""
        self.assertEqual(self.quota_metrics.requests_used_today, 1000)
        self.assertEqual(self.quota_metrics.daily_limit, 5000)
        self.assertEqual(self.quota_metrics.usage_percentage, 20.0)
        self.assertFalse(self.quota_metrics.should_pause)
        self.assertIsNone(self.quota_metrics.pause_reason)

    def test_quota_metrics_validation(self):
        """Test QuotaMetrics validation."""
        # Test negative values are clamped
        metrics = QuotaMetrics(
            requests_used_today=-100,
            daily_limit=5000,
            usage_percentage=20.0,
            should_pause=False,
            pause_reason=None
        )
        self.assertEqual(metrics.requests_used_today, 0)

        # Test invalid daily limit
        with self.assertRaises(ValueError):
            QuotaMetrics(
                requests_used_today=100,
                daily_limit=-1,  # Invalid
                usage_percentage=20.0,
                should_pause=False,
                pause_reason=None
            )

        # Test invalid usage percentage (way over 100%)
        with self.assertRaises(ValueError):
            QuotaMetrics(
                requests_used_today=100,
                daily_limit=5000,
                usage_percentage=150.0,  # Too high
                should_pause=False,
                pause_reason=None
            )

    def test_get_remaining_requests(self):
        """Test remaining requests calculation."""
        remaining = self.quota_metrics.get_remaining_requests()
        self.assertEqual(remaining, 4000)  # 5000 - 1000

        # Test with no daily limit
        metrics = QuotaMetrics(
            requests_used_today=1000,
            daily_limit=None,
            usage_percentage=0.0,
            should_pause=False,
            pause_reason=None
        )
        self.assertIsNone(metrics.get_remaining_requests())

        # Test with over-usage (staying within validation limits)
        metrics = QuotaMetrics(
            requests_used_today=6000,
            daily_limit=5000,
            usage_percentage=105.0,  # Within allowed range (up to 110%)
            should_pause=True,
            pause_reason="Over limit"
        )
        self.assertEqual(metrics.get_remaining_requests(), 0)

    def test_serialization(self):
        """Test QuotaMetrics serialization."""
        data = self.quota_metrics.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data['requests_used_today'], 1000)

        restored = QuotaMetrics.from_dict(data)
        self.assertEqual(restored.requests_used_today, self.quota_metrics.requests_used_today)
        self.assertEqual(restored.daily_limit, self.quota_metrics.daily_limit)


class TestErrorClassification(unittest.TestCase):
    """Test ErrorClassification model."""

    def test_error_classification_creation(self):
        """Test basic ErrorClassification creation."""
        error = ErrorClassification(
            kind="rate_limit",
            retry_after=60,
            should_retry=True
        )
        self.assertEqual(error.kind, "rate_limit")
        self.assertEqual(error.retry_after, 60)
        self.assertTrue(error.should_retry)

    def test_error_classification_validation(self):
        """Test ErrorClassification validation."""
        # Test invalid kind
        with self.assertRaises(ValueError):
            ErrorClassification(
                kind="invalid_kind",
                retry_after=60,
                should_retry=True
            )

        # Test negative retry_after
        with self.assertRaises(ValueError):
            ErrorClassification(
                kind="rate_limit",
                retry_after=-10,
                should_retry=True
            )

        # Test valid kinds
        valid_kinds = ['rate_limit', 'quota', 'server', 'network']
        for kind in valid_kinds:
            error = ErrorClassification(
                kind=kind,
                retry_after=None,
                should_retry=True
            )
            self.assertEqual(error.kind, kind)

    def test_serialization(self):
        """Test ErrorClassification serialization."""
        error = ErrorClassification(
            kind="quota",
            retry_after=300,
            should_retry=False
        )

        data = error.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data['kind'], 'quota')

        restored = ErrorClassification.from_dict(data)
        self.assertEqual(restored.kind, error.kind)
        self.assertEqual(restored.retry_after, error.retry_after)
        self.assertEqual(restored.should_retry, error.should_retry)


class TestStateSerialization(unittest.TestCase):
    """Test quota state serialization functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.timestamp = datetime.now()
        self.quota_status = QuotaStatus(
            requests_remaining=4500,
            requests_limit=5000,
            tokens_remaining=3500000,
            tokens_limit=4000000,
            reset_requests="2024-01-01T12:00:00Z",
            reset_tokens="2024-01-01T12:00:00Z",
            timestamp=self.timestamp
        )
        self.quota_metrics = QuotaMetrics(
            requests_used_today=500,
            daily_limit=5000,
            usage_percentage=10.0,
            should_pause=False,
            pause_reason=None
        )

    def test_serialize_quota_state(self):
        """Test quota state serialization to JSON."""
        json_str = serialize_quota_state(self.quota_status, self.quota_metrics)

        # Verify it's valid JSON
        data = json.loads(json_str)
        self.assertIn('quota_status', data)
        self.assertIn('quota_metrics', data)

        # Verify structure
        self.assertEqual(data['quota_status']['requests_remaining'], 4500)
        self.assertEqual(data['quota_metrics']['requests_used_today'], 500)

    def test_deserialize_quota_state(self):
        """Test quota state deserialization from JSON."""
        json_str = serialize_quota_state(self.quota_status, self.quota_metrics)
        restored_status, restored_metrics = deserialize_quota_state(json_str)

        # Verify QuotaStatus
        self.assertEqual(restored_status.requests_remaining, self.quota_status.requests_remaining)
        self.assertEqual(restored_status.timestamp, self.quota_status.timestamp)

        # Verify QuotaMetrics
        self.assertEqual(restored_metrics.requests_used_today, self.quota_metrics.requests_used_today)
        self.assertEqual(restored_metrics.daily_limit, self.quota_metrics.daily_limit)

    def test_round_trip_serialization(self):
        """Test complete round-trip serialization."""
        # Serialize
        json_str = serialize_quota_state(self.quota_status, self.quota_metrics)

        # Deserialize
        restored_status, restored_metrics = deserialize_quota_state(json_str)

        # Serialize again
        json_str2 = serialize_quota_state(restored_status, restored_metrics)

        # Should be identical (ignoring formatting)
        data1 = json.loads(json_str)
        data2 = json.loads(json_str2)
        self.assertEqual(data1, data2)


if __name__ == '__main__':
    unittest.main()