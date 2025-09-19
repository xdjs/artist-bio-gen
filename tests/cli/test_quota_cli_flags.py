#!/usr/bin/env python3
"""
Tests for new CLI flags related to quota configuration (Task 2.2).
"""

import unittest
from unittest.mock import patch
import os

from artist_bio_gen.cli.parser import create_argument_parser
from artist_bio_gen.config import Env


class TestQuotaCliFlags(unittest.TestCase):
    def setUp(self):
        """Clear the singleton before each test."""
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        """Clear the singleton after each test."""
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
    }, clear=True)
    def test_flags_present_and_override_environment(self):
        """Test that CLI flags properly override environment variables."""
        parser = create_argument_parser()
        args = parser.parse_args([
            "--input-file", "artists.csv",
            "--quota-threshold", "0.9",
            "--quota-monitoring", "false",
            "--daily-limit", "3000",
            "--pause-duration", "36",
            "--quota-log-interval", "200",
        ])

        # Use ConfigLoader to load with CLI args
        from artist_bio_gen.config.loader import ConfigLoader
        from artist_bio_gen.config.schema import ConfigSchema
        config = ConfigLoader.load(schema=ConfigSchema, cli_args=args)

        # Check that values were properly set from CLI
        self.assertEqual(config.quota_threshold, 0.9)
        self.assertFalse(config.quota_monitoring)
        self.assertEqual(config.daily_request_limit, 3000)
        self.assertEqual(config.pause_duration_hours, 36)
        self.assertEqual(config.quota_log_interval, 200)

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "QUOTA_THRESHOLD": "0.7",
        "QUOTA_MONITORING": "true"
    }, clear=True)
    def test_defaults_when_not_provided(self):
        """Test that defaults are used when CLI flags are not provided."""
        parser = create_argument_parser()
        args = parser.parse_args(["--input-file", "artists.csv"])  # no quota flags

        # Use ConfigLoader to load with CLI args
        from artist_bio_gen.config.loader import ConfigLoader
        from artist_bio_gen.config.schema import ConfigSchema
        config = ConfigLoader.load(schema=ConfigSchema, cli_args=args)

        # Check environment values and defaults
        self.assertEqual(config.quota_threshold, 0.7)  # From env
        self.assertTrue(config.quota_monitoring)  # From env
        self.assertIsNone(config.daily_request_limit)  # Default
        self.assertEqual(config.pause_duration_hours, 24)  # Default
        self.assertEqual(config.quota_log_interval, 100)  # Default

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
    }, clear=True)
    def test_parser_accepts_quota_flags(self):
        """Test that the parser correctly accepts all quota-related flags."""
        parser = create_argument_parser()

        # Test all valid quota flags
        args = parser.parse_args([
            "--input-file", "test.csv",
            "--quota-threshold", "0.5",
            "--quota-monitoring", "false",
            "--daily-limit", "1000",
            "--pause-duration", "48",
            "--quota-log-interval", "50"
        ])

        # Verify parser correctly parsed the values
        self.assertEqual(args.quota_threshold, 0.5)
        self.assertEqual(args.quota_monitoring, "false")
        self.assertEqual(args.daily_limit, 1000)
        self.assertEqual(args.pause_duration, 48)
        self.assertEqual(args.quota_log_interval, 50)


if __name__ == "__main__":
    unittest.main()