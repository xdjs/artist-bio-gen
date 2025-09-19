"""
Tests for the Environment Manager.

This module tests the centralized environment configuration system including
precedence handling, validation, and error conditions.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from artist_bio_gen.config.env import Env, ConfigError


class TestEnvManager(unittest.TestCase):
    """Test cases for the Environment Manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing singleton
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        """Clean up after tests."""
        # Clear singleton after each test
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def test_from_mapping_success(self):
        """Test creating Env instance from valid mapping."""
        mapping = {
            "OPENAI_API_KEY": "test_api_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": "test_prompt"
        }

        env = Env.from_mapping(mapping)

        self.assertEqual(env.OPENAI_API_KEY, "test_api_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://test:test@localhost:5432/test")
        self.assertEqual(env.OPENAI_PROMPT_ID, "test_prompt")

    def test_from_mapping_missing_required(self):
        """Test that missing required fields raise ConfigError."""
        # Missing OPENAI_API_KEY
        mapping = {"DATABASE_URL": "postgresql://test:test@localhost:5432/test"}
        with self.assertRaises(ConfigError) as cm:
            Env.from_mapping(mapping)
        self.assertIn("OPENAI_API_KEY", str(cm.exception))

        # Missing DATABASE_URL
        mapping = {"OPENAI_API_KEY": "test_key"}
        with self.assertRaises(ConfigError) as cm:
            Env.from_mapping(mapping)
        self.assertIn("DATABASE_URL", str(cm.exception))

        # Missing both
        mapping = {}
        with self.assertRaises(ConfigError) as cm:
            Env.from_mapping(mapping)
        self.assertIn("OPENAI_API_KEY", str(cm.exception))
        self.assertIn("DATABASE_URL", str(cm.exception))

    def test_from_mapping_optional_fields(self):
        """Test that optional fields can be None."""
        mapping = {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
        }

        env = Env.from_mapping(mapping)

        self.assertEqual(env.OPENAI_API_KEY, "test_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://test:test@localhost:5432/test")
        self.assertIsNone(env.OPENAI_PROMPT_ID)

    def test_to_dict(self):
        """Test converting Env to dictionary."""
        mapping = {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": "test_prompt"
        }

        env = Env.from_mapping(mapping)
        result = env.to_dict()

        expected = {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": "test_prompt"
        }
        self.assertEqual(result, expected)

    def test_mask(self):
        """Test masking sensitive values for safe logging."""
        mapping = {
            "OPENAI_API_KEY": "secret_key",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
            "OPENAI_PROMPT_ID": "prompt_123"
        }

        env = Env.from_mapping(mapping)
        result = env.mask()

        expected = {
            "OPENAI_API_KEY": "***",
            "DATABASE_URL": "***",
            "OPENAI_PROMPT_ID": "prompt_123"  # Not sensitive
        }
        self.assertEqual(result, expected)

    def test_mask_with_none_values(self):
        """Test masking when some values are None."""
        mapping = {
            "OPENAI_API_KEY": "secret_key",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
        }

        env = Env.from_mapping(mapping)
        result = env.mask()

        expected = {
            "OPENAI_API_KEY": "***",
            "DATABASE_URL": "***",
            "OPENAI_PROMPT_ID": None
        }
        self.assertEqual(result, expected)

    def test_quota_config_from_mapping(self):
        """Test quota configuration from mapping."""
        mapping = {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "QUOTA_MONITORING": "false",
            "QUOTA_THRESHOLD": "0.9",
            "DAILY_REQUEST_LIMIT": "1000",
            "PAUSE_DURATION_HOURS": "48",
            "QUOTA_LOG_INTERVAL": "50"
        }

        env = Env.from_mapping(mapping)

        self.assertFalse(env.QUOTA_MONITORING)
        self.assertEqual(env.QUOTA_THRESHOLD, 0.9)
        self.assertEqual(env.DAILY_REQUEST_LIMIT, 1000)
        self.assertEqual(env.PAUSE_DURATION_HOURS, 48)
        self.assertEqual(env.QUOTA_LOG_INTERVAL, 50)


class TestEnvLoading(unittest.TestCase):
    """Test cases for environment loading with precedence."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing singleton
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        """Clean up after tests."""
        # Clear singleton after each test
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    @patch.dict(os.environ, {}, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_load_missing_required_fields(self, mock_dotenv):
        """Test that loading without required fields raises ConfigError."""
        mock_dotenv.return_value = None
        with self.assertRaises(ConfigError) as cm:
            Env.load()

        error_msg = str(cm.exception)
        self.assertIn("OPENAI_API_KEY", error_msg)
        self.assertIn("DATABASE_URL", error_msg)

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "env_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env"
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_load_from_environment(self, mock_dotenv):
        """Test loading from OS environment variables."""
        mock_dotenv.return_value = None
        env = Env.load()

        self.assertEqual(env.OPENAI_API_KEY, "env_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")
        self.assertIsNone(env.OPENAI_PROMPT_ID)

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "env_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
        "OPENAI_PROMPT_ID": "env_prompt"
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_load_all_from_environment(self, mock_dotenv):
        """Test loading all fields from OS environment."""
        mock_dotenv.return_value = None
        env = Env.load()

        self.assertEqual(env.OPENAI_API_KEY, "env_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")
        self.assertEqual(env.OPENAI_PROMPT_ID, "env_prompt")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "env_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env"
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_cli_overrides_environment(self, mock_dotenv):
        """Test that CLI overrides take precedence over environment."""
        mock_dotenv.return_value = None
        cli_overrides = {
            "OPENAI_API_KEY": "cli_key",
            "OPENAI_PROMPT_ID": "cli_prompt"
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "cli_key")  # CLI override
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")  # From env
        self.assertEqual(env.OPENAI_PROMPT_ID, "cli_prompt")  # CLI override

    @patch.dict(os.environ, {}, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_cli_overrides_provide_required(self, mock_dotenv):
        """Test that CLI overrides can provide required fields."""
        # Mock to prevent loading .env.local during tests
        mock_dotenv.return_value = None
        cli_overrides = {
            "OPENAI_API_KEY": "cli_key",
            "DATABASE_URL": "postgresql://cli:cli@localhost:5432/cli"
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "cli_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://cli:cli@localhost:5432/cli")
        self.assertIsNone(env.OPENAI_PROMPT_ID)

    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_whitespace_handling(self, mock_dotenv):
        """Test that whitespace is properly stripped from values."""
        mock_dotenv.return_value = None
        cli_overrides = {
            "OPENAI_API_KEY": "  cli_key  ",
            "DATABASE_URL": "  postgresql://cli:cli@localhost:5432/cli  ",
            "OPENAI_PROMPT_ID": "  cli_prompt  "
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "cli_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://cli:cli@localhost:5432/cli")
        self.assertEqual(env.OPENAI_PROMPT_ID, "cli_prompt")

    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_empty_string_handling(self, mock_dotenv):
        """Test that empty strings are treated as None."""
        mock_dotenv.return_value = None
        cli_overrides = {
            "OPENAI_API_KEY": "valid_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": ""  # Empty string
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "valid_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://test:test@localhost:5432/test")
        self.assertIsNone(env.OPENAI_PROMPT_ID)

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "env_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
        "QUOTA_MONITORING": "false",
        "QUOTA_THRESHOLD": "0.5"
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_quota_config_from_environment(self, mock_dotenv):
        """Test loading quota configuration from environment."""
        mock_dotenv.return_value = None
        env = Env.load()

        self.assertFalse(env.QUOTA_MONITORING)
        self.assertEqual(env.QUOTA_THRESHOLD, 0.5)
        self.assertIsNone(env.DAILY_REQUEST_LIMIT)
        self.assertEqual(env.PAUSE_DURATION_HOURS, 24)  # Default
        self.assertEqual(env.QUOTA_LOG_INTERVAL, 100)  # Default


class TestSingletonBehavior(unittest.TestCase):
    """Test cases for singleton behavior."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing singleton
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        """Clean up after tests."""
        # Clear singleton after each test
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def test_current_before_load_raises_error(self):
        """Test that current() raises error before load() is called."""
        with self.assertRaises(ConfigError) as cm:
            Env.current()

        self.assertIn("not initialized", str(cm.exception))
        self.assertIn("Env.load()", str(cm.exception))

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_load_sets_singleton(self, mock_dotenv):
        """Test that load() sets the singleton instance."""
        mock_dotenv.return_value = None
        env = Env.load()

        # Should be able to get the same instance via current()
        current_env = Env.current()

        self.assertIs(env, current_env)
        self.assertEqual(current_env.OPENAI_API_KEY, "test_key")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "first_key",
        "DATABASE_URL": "postgresql://first:first@localhost:5432/first"
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_subsequent_load_updates_singleton(self, mock_dotenv):
        """Test that subsequent load() calls update the singleton."""
        mock_dotenv.return_value = None
        # First load
        env1 = Env.load()
        self.assertEqual(env1.OPENAI_API_KEY, "first_key")

        # Second load with different values
        cli_overrides = {"OPENAI_API_KEY": "second_key"}
        env2 = Env.load(cli_overrides)

        # Should be different instance with updated values
        self.assertIsNot(env1, env2)
        self.assertEqual(env2.OPENAI_API_KEY, "second_key")

        # current() should return the new instance
        current_env = Env.current()
        self.assertIs(env2, current_env)
        self.assertEqual(current_env.OPENAI_API_KEY, "second_key")


class TestConfigValidation(unittest.TestCase):
    """Test cases for configuration validation."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing singleton
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    def tearDown(self):
        """Clean up after tests."""
        # Clear singleton after each test
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "QUOTA_THRESHOLD": "1.5"  # Invalid - out of range
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_invalid_quota_threshold(self, mock_dotenv):
        """Test that invalid quota threshold raises error."""
        mock_dotenv.return_value = None
        with self.assertRaises(ConfigError) as cm:
            Env.load()

        self.assertIn("QUOTA_THRESHOLD", str(cm.exception))

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "DAILY_REQUEST_LIMIT": "-100"  # Invalid - negative
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_invalid_daily_request_limit(self, mock_dotenv):
        """Test that negative daily request limit raises error."""
        mock_dotenv.return_value = None
        with self.assertRaises(ConfigError) as cm:
            Env.load()

        self.assertIn("DAILY_REQUEST_LIMIT", str(cm.exception))

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "PAUSE_DURATION_HOURS": "100"  # Invalid - out of range
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_invalid_pause_duration(self, mock_dotenv):
        """Test that out of range pause duration raises error."""
        mock_dotenv.return_value = None
        with self.assertRaises(ConfigError) as cm:
            Env.load()

        self.assertIn("PAUSE_DURATION_HOURS", str(cm.exception))

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "QUOTA_MONITORING": "invalid"  # Invalid boolean value
    }, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_invalid_quota_monitoring(self, mock_dotenv):
        """Test that invalid boolean value raises error."""
        mock_dotenv.return_value = None
        with self.assertRaises(ConfigError) as cm:
            Env.load()

        self.assertIn("QUOTA_MONITORING", str(cm.exception))


if __name__ == "__main__":
    unittest.main()