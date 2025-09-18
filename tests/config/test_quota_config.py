#!/usr/bin/env python3
"""
Tests for quota-related configuration (Task 2.2).

Validates Env loads defaults, environment overrides, CLI overrides, and
value validation for new quota parameters.
"""

import os
import unittest
from unittest.mock import patch

from artist_bio_gen.config.env import Env, ConfigError


class TestQuotaConfigDefaults(unittest.TestCase):
    def setUp(self):
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
    }, clear=True)
    def test_defaults(self):
        env = Env.load()
        self.assertTrue(env.QUOTA_MONITORING)
        self.assertEqual(env.QUOTA_THRESHOLD, 0.8)
        self.assertIsNone(env.DAILY_REQUEST_LIMIT)
        self.assertEqual(env.PAUSE_DURATION_HOURS, 24)
        self.assertEqual(env.QUOTA_LOG_INTERVAL, 100)


class TestQuotaConfigOverrides(unittest.TestCase):
    def setUp(self):
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "QUOTA_MONITORING": "false",
        "QUOTA_THRESHOLD": "0.9",
        "DAILY_REQUEST_LIMIT": "5000",
        "PAUSE_DURATION_HOURS": "48",
        "QUOTA_LOG_INTERVAL": "250",
    }, clear=True)
    def test_env_overrides(self):
        env = Env.load()
        self.assertFalse(env.QUOTA_MONITORING)
        self.assertEqual(env.QUOTA_THRESHOLD, 0.9)
        self.assertEqual(env.DAILY_REQUEST_LIMIT, 5000)
        self.assertEqual(env.PAUSE_DURATION_HOURS, 48)
        self.assertEqual(env.QUOTA_LOG_INTERVAL, 250)

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
    }, clear=True)
    def test_cli_overrides(self):
        cli = {
            "QUOTA_MONITORING": "false",
            "QUOTA_THRESHOLD": "0.85",
            "DAILY_REQUEST_LIMIT": "2000",
            "PAUSE_DURATION_HOURS": "12",
            "QUOTA_LOG_INTERVAL": "50",
        }
        env = Env.load(cli)
        self.assertFalse(env.QUOTA_MONITORING)
        self.assertEqual(env.QUOTA_THRESHOLD, 0.85)
        self.assertEqual(env.DAILY_REQUEST_LIMIT, 2000)
        self.assertEqual(env.PAUSE_DURATION_HOURS, 12)
        self.assertEqual(env.QUOTA_LOG_INTERVAL, 50)


class TestQuotaConfigValidation(unittest.TestCase):
    def setUp(self):
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "QUOTA_THRESHOLD": "0.05",
    }, clear=True)
    def test_invalid_threshold_raises(self):
        with self.assertRaises(ConfigError):
            Env.load()

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "PAUSE_DURATION_HOURS": "0",
    }, clear=True)
    def test_invalid_pause_duration_low(self):
        with self.assertRaises(ConfigError):
            Env.load()

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "PAUSE_DURATION_HOURS": "100",
    }, clear=True)
    def test_invalid_pause_duration_high(self):
        with self.assertRaises(ConfigError):
            Env.load()

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "DAILY_REQUEST_LIMIT": "0",
    }, clear=True)
    def test_invalid_daily_limit(self):
        with self.assertRaises(ConfigError):
            Env.load()

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://u:p@localhost:5432/db",
        "QUOTA_LOG_INTERVAL": "0",
    }, clear=True)
    def test_invalid_log_interval(self):
        with self.assertRaises(ConfigError):
            Env.load()


if __name__ == "__main__":
    unittest.main()

