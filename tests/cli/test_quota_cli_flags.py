#!/usr/bin/env python3
"""
Tests for new CLI flags related to quota configuration (Task 2.2).
"""

import unittest

from artist_bio_gen.cli.parser import create_argument_parser
from artist_bio_gen.cli.main import _build_cli_overrides


class TestQuotaCliFlags(unittest.TestCase):
    def test_flags_present_and_override_mapping(self):
        parser = create_argument_parser()
        args = parser.parse_args([
            "--input-file", "artists.csv",
            "--quota-threshold", "0.9",
            "--quota-monitoring", "false",
            "--daily-limit", "3000",
            "--pause-duration", "36",
            "--quota-log-interval", "200",
        ])

        overrides = _build_cli_overrides(args)
        self.assertEqual(overrides.get("QUOTA_THRESHOLD"), "0.9")
        self.assertEqual(overrides.get("QUOTA_MONITORING"), "false")
        self.assertEqual(overrides.get("DAILY_REQUEST_LIMIT"), "3000")
        self.assertEqual(overrides.get("PAUSE_DURATION_HOURS"), "36")
        self.assertEqual(overrides.get("QUOTA_LOG_INTERVAL"), "200")

    def test_no_overrides_when_not_provided(self):
        parser = create_argument_parser()
        args = parser.parse_args(["--input-file", "artists.csv"])  # no new flags
        overrides = _build_cli_overrides(args)
        self.assertNotIn("QUOTA_THRESHOLD", overrides)
        self.assertNotIn("QUOTA_MONITORING", overrides)
        self.assertNotIn("DAILY_REQUEST_LIMIT", overrides)
        self.assertNotIn("PAUSE_DURATION_HOURS", overrides)
        self.assertNotIn("QUOTA_LOG_INTERVAL", overrides)


if __name__ == "__main__":
    unittest.main()

