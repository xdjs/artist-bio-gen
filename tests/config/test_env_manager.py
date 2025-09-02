"""
Tests for the Environment Manager.

This module tests the centralized environment configuration system including
precedence handling, validation, and error conditions.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, mock_open

from artist_bio_gen.config.env import Env, ConfigError, _load_from_dotenv_file


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
            "OPENAI_PROMPT_ID": "test_prompt",
            "OPENAI_ORG_ID": "test_org",
        }

        env = Env.from_mapping(mapping)

        self.assertEqual(env.OPENAI_API_KEY, "test_api_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://test:test@localhost:5432/test")
        self.assertEqual(env.OPENAI_PROMPT_ID, "test_prompt")
        self.assertEqual(env.OPENAI_ORG_ID, "test_org")

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
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        }

        env = Env.from_mapping(mapping)

        self.assertEqual(env.OPENAI_API_KEY, "test_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://test:test@localhost:5432/test")
        self.assertIsNone(env.OPENAI_PROMPT_ID)
        self.assertIsNone(env.OPENAI_ORG_ID)

    def test_to_dict(self):
        """Test converting Env to dictionary."""
        mapping = {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": "test_prompt",
        }

        env = Env.from_mapping(mapping)
        result = env.to_dict()

        expected = {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": "test_prompt",
            "OPENAI_ORG_ID": None,
            "OPENAI_RPM": 500,
            "OPENAI_TPM": 200000,
            "OPENAI_TPD": 2000000,
        }
        self.assertEqual(result, expected)

    def test_mask(self):
        """Test masking sensitive values for safe logging."""
        mapping = {
            "OPENAI_API_KEY": "secret_key",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
            "OPENAI_PROMPT_ID": "prompt_123",
            "OPENAI_ORG_ID": "org_456",
        }

        env = Env.from_mapping(mapping)
        result = env.mask()

        expected = {
            "OPENAI_API_KEY": "***",
            "DATABASE_URL": "***",
            "OPENAI_PROMPT_ID": "prompt_123",  # Not sensitive
            "OPENAI_ORG_ID": "org_456",  # Not sensitive
            "OPENAI_RPM": 500,
            "OPENAI_TPM": 200000,
            "OPENAI_TPD": 2000000,
        }
        self.assertEqual(result, expected)

    def test_mask_with_none_values(self):
        """Test masking when some values are None."""
        mapping = {
            "OPENAI_API_KEY": "secret_key",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db",
        }

        env = Env.from_mapping(mapping)
        result = env.mask()

        expected = {
            "OPENAI_API_KEY": "***",
            "DATABASE_URL": "***",
            "OPENAI_PROMPT_ID": None,
            "OPENAI_ORG_ID": None,
            "OPENAI_RPM": 500,
            "OPENAI_TPM": 200000,
            "OPENAI_TPD": 2000000,
        }
        self.assertEqual(result, expected)


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
    @patch("artist_bio_gen.config.env._load_from_dotenv_file")
    def test_load_missing_required_fields(self, mock_dotenv):
        """Test that loading without required fields raises ConfigError."""
        with self.assertRaises(ConfigError) as cm:
            Env.load()

        error_msg = str(cm.exception)
        self.assertIn("OPENAI_API_KEY", error_msg)
        self.assertIn("DATABASE_URL", error_msg)

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "env_key",
            "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
        },
        clear=True,
    )
    @patch("artist_bio_gen.config.env._load_from_dotenv_file")
    def test_load_from_environment(self, mock_dotenv):
        """Test loading from OS environment variables."""
        env = Env.load()

        self.assertEqual(env.OPENAI_API_KEY, "env_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")
        self.assertIsNone(env.OPENAI_PROMPT_ID)
        self.assertIsNone(env.OPENAI_ORG_ID)

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "env_key",
            "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
            "OPENAI_PROMPT_ID": "env_prompt",
            "OPENAI_ORG_ID": "env_org",
        },
        clear=True,
    )
    def test_load_all_from_environment(self):
        """Test loading all fields from OS environment."""
        env = Env.load()

        self.assertEqual(env.OPENAI_API_KEY, "env_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")
        self.assertEqual(env.OPENAI_PROMPT_ID, "env_prompt")
        self.assertEqual(env.OPENAI_ORG_ID, "env_org")

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "env_key",
            "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
        },
        clear=True,
    )
    def test_cli_overrides_environment(self):
        """Test that CLI overrides take precedence over environment."""
        cli_overrides = {"OPENAI_API_KEY": "cli_key", "OPENAI_PROMPT_ID": "cli_prompt"}

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "cli_key")  # CLI override
        self.assertEqual(
            env.DATABASE_URL, "postgresql://env:env@localhost:5432/env"
        )  # From env
        self.assertEqual(env.OPENAI_PROMPT_ID, "cli_prompt")  # CLI override
        self.assertIsNone(env.OPENAI_ORG_ID)

    @patch.dict(os.environ, {}, clear=True)
    @patch("artist_bio_gen.config.env._load_from_dotenv_file")
    def test_cli_overrides_provide_required(self, mock_dotenv):
        """Test that CLI overrides can provide required fields."""
        cli_overrides = {
            "OPENAI_API_KEY": "cli_key",
            "DATABASE_URL": "postgresql://cli:cli@localhost:5432/cli",
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "cli_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://cli:cli@localhost:5432/cli")
        self.assertIsNone(env.OPENAI_PROMPT_ID)
        self.assertIsNone(env.OPENAI_ORG_ID)

    def test_whitespace_handling(self):
        """Test that whitespace is properly stripped from values."""
        cli_overrides = {
            "OPENAI_API_KEY": "  cli_key  ",
            "DATABASE_URL": "  postgresql://cli:cli@localhost:5432/cli  ",
            "OPENAI_PROMPT_ID": "  cli_prompt  ",
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "cli_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://cli:cli@localhost:5432/cli")
        self.assertEqual(env.OPENAI_PROMPT_ID, "cli_prompt")

    def test_empty_string_handling(self):
        """Test that empty strings are treated as None."""
        cli_overrides = {
            "OPENAI_API_KEY": "valid_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "OPENAI_PROMPT_ID": "",  # Empty string
            "OPENAI_ORG_ID": "   ",  # Whitespace only
        }

        env = Env.load(cli_overrides)

        self.assertEqual(env.OPENAI_API_KEY, "valid_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://test:test@localhost:5432/test")
        self.assertIsNone(env.OPENAI_PROMPT_ID)
        self.assertIsNone(env.OPENAI_ORG_ID)


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

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        },
        clear=True,
    )
    def test_load_sets_singleton(self):
        """Test that load() sets the singleton instance."""
        env = Env.load()

        # Should be able to get the same instance via current()
        current_env = Env.current()

        self.assertIs(env, current_env)
        self.assertEqual(current_env.OPENAI_API_KEY, "test_key")

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "first_key",
            "DATABASE_URL": "postgresql://first:first@localhost:5432/first",
        },
        clear=True,
    )
    def test_subsequent_load_updates_singleton(self):
        """Test that subsequent load() calls update the singleton."""
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


class TestDotenvFileLoading(unittest.TestCase):
    """Test cases for .env.local file loading."""

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

    @patch("os.path.exists")
    @patch("builtins.__import__")
    def test_dotenv_file_loading_success(self, mock_import, mock_exists):
        """Test successful .env.local file loading."""
        mock_exists.return_value = True

        # Mock the dotenv module and load_dotenv function
        mock_dotenv_module = unittest.mock.MagicMock()
        mock_load_dotenv = unittest.mock.MagicMock()
        mock_dotenv_module.load_dotenv = mock_load_dotenv

        def side_effect(name, *args, **kwargs):
            if name == "dotenv":
                return mock_dotenv_module
            return unittest.mock.DEFAULT

        mock_import.side_effect = side_effect
        values = {}

        _load_from_dotenv_file(values)

        mock_exists.assert_called_once_with(".env.local")
        mock_load_dotenv.assert_called_once_with(".env.local", override=False)

    @patch("os.path.exists")
    @patch("builtins.__import__")
    def test_dotenv_file_not_exists(self, mock_import, mock_exists):
        """Test behavior when .env.local file doesn't exist."""
        mock_exists.return_value = False

        # Mock the dotenv module
        mock_dotenv_module = unittest.mock.MagicMock()
        mock_load_dotenv = unittest.mock.MagicMock()
        mock_dotenv_module.load_dotenv = mock_load_dotenv

        def side_effect(name, *args, **kwargs):
            if name == "dotenv":
                return mock_dotenv_module
            return unittest.mock.DEFAULT

        mock_import.side_effect = side_effect
        values = {}

        _load_from_dotenv_file(values)

        mock_exists.assert_called_once_with(".env.local")
        mock_load_dotenv.assert_not_called()

    @patch("builtins.__import__")
    def test_dotenv_import_error_handling(self, mock_import):
        """Test graceful handling when python-dotenv is not available."""

        def side_effect(name, *args, **kwargs):
            if name == "dotenv":
                raise ImportError("No module named 'dotenv'")
            return unittest.mock.DEFAULT

        mock_import.side_effect = side_effect
        values = {}

        # Should not raise exception
        _load_from_dotenv_file(values)


if __name__ == "__main__":
    unittest.main()
