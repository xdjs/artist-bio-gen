"""
Integration tests for environment variable handling.

This module tests the complete environment configuration flow including
CLI integration, main function execution, and end-to-end behavior.
"""

import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from artist_bio_gen.cli import main
from artist_bio_gen.config import Env


class TestEnvironmentIntegration(unittest.TestCase):
    """Integration tests for environment variable handling."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing singleton
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None
        
        # Create temp directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after tests."""
        # Clear singleton after each test
        import artist_bio_gen.config.env as env_module
        env_module._ENV = None
        
        # Restore original argv
        sys.argv = self.original_argv
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_file(self, content: str) -> str:
        """Create a test CSV file with given content."""
        test_file = os.path.join(self.temp_dir, "test.csv")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(content)
        return test_file

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "env_api_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
        "OPENAI_PROMPT_ID": "env_prompt"
    }, clear=True)
    def test_environment_variables_used_in_dry_run(self):
        """Test that environment variables are properly loaded and used in dry run."""
        test_content = "550e8400-e29b-41d4-a716-446655440001,Test Artist,Test Data"
        test_file = self.create_test_file(test_content)
        
        # Set up CLI arguments for dry run
        sys.argv = [
            "artist_bio_gen",
            "--input-file", test_file,
            "--dry-run"
        ]
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout
        
        output = captured_output.getvalue()
        
        # Should see dry run output (logging goes to stderr, JSON to stdout)
        self.assertIn("Test Artist", output)
        
        # Environment should be loaded correctly
        env = Env.current()
        self.assertEqual(env.OPENAI_API_KEY, "env_api_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")
        self.assertEqual(env.OPENAI_PROMPT_ID, "env_prompt")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "env_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env"
    }, clear=True)
    def test_cli_overrides_environment_integration(self):
        """Test that CLI arguments override environment variables in full integration."""
        test_content = "550e8400-e29b-41d4-a716-446655440001,CLI Test,CLI Data"
        test_file = self.create_test_file(test_content)
        
        # Set up CLI arguments with overrides
        sys.argv = [
            "artist_bio_gen",
            "--input-file", test_file,
            "--openai-api-key", "cli_api_key",
            "--prompt-id", "cli_prompt",
            "--dry-run"
        ]
        
        try:
            main()
        except SystemExit:
            pass
        
        # Environment should reflect CLI overrides
        env = Env.current()
        self.assertEqual(env.OPENAI_API_KEY, "cli_api_key")  # CLI override
        self.assertEqual(env.DATABASE_URL, "postgresql://env:env@localhost:5432/env")  # From env
        self.assertEqual(env.OPENAI_PROMPT_ID, "cli_prompt")  # CLI override

    @patch.dict(os.environ, {}, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_missing_required_config_error_integration(self, mock_dotenv):
        """Test that missing required configuration produces proper error in main()."""
        mock_dotenv.return_value = None
        test_content = "550e8400-e29b-41d4-a716-446655440001,Error Test,Error Data"
        test_file = self.create_test_file(test_content)
        
        # Set up CLI arguments without required environment variables
        sys.argv = [
            "artist_bio_gen",
            "--input-file", test_file,
            "--dry-run"
        ]
        
        # Should exit with configuration error
        with self.assertRaises(SystemExit) as cm:
            main()
        
        # Should exit with config error code (3)
        self.assertEqual(cm.exception.code, 3)

    @patch.dict(os.environ, {}, clear=True)
    @patch('artist_bio_gen.config.loader._load_from_dotenv_file')
    def test_cli_provides_all_required_config(self, mock_dotenv):
        """Test that CLI can provide all required configuration."""
        mock_dotenv.return_value = None
        test_content = "550e8400-e29b-41d4-a716-446655440001,CLI Complete,CLI Complete Data"
        test_file = self.create_test_file(test_content)
        
        # Set up CLI arguments with all required config
        sys.argv = [
            "artist_bio_gen",
            "--input-file", test_file,
            "--openai-api-key", "cli_complete_key",
            "--db-url", "postgresql://cli:cli@localhost:5432/cli",
            "--prompt-id", "cli_complete_prompt",
            "--dry-run"
        ]
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout
        
        output = captured_output.getvalue()
        
        # Should complete successfully (check for JSON output instead of logs)
        self.assertIn("CLI Complete", output)
        
        # Environment should have CLI values
        env = Env.current()
        self.assertEqual(env.OPENAI_API_KEY, "cli_complete_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://cli:cli@localhost:5432/cli")
        self.assertEqual(env.OPENAI_PROMPT_ID, "cli_complete_prompt")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "   whitespace_key   ",
        "DATABASE_URL": "  postgresql://ws:ws@localhost:5432/ws  "
    }, clear=True)
    def test_whitespace_handling_integration(self):
        """Test that whitespace is properly handled in full integration."""
        test_content = "550e8400-e29b-41d4-a716-446655440001,Whitespace Test,WS Data"
        test_file = self.create_test_file(test_content)
        
        sys.argv = [
            "artist_bio_gen",
            "--input-file", test_file,
            "--prompt-id", "  ws_prompt  ",
            "--dry-run"
        ]
        
        try:
            main()
        except SystemExit:
            pass
        
        # Environment should have trimmed values
        env = Env.current()
        self.assertEqual(env.OPENAI_API_KEY, "whitespace_key")
        self.assertEqual(env.DATABASE_URL, "postgresql://ws:ws@localhost:5432/ws")
        self.assertEqual(env.OPENAI_PROMPT_ID, "ws_prompt")

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
    }, clear=True)
    def test_help_flag_works_with_env_system(self):
        """Test that help flag works even with new environment system."""
        sys.argv = ["artist_bio_gen", "--help"]
        
        # Should exit successfully with help
        with self.assertRaises(SystemExit) as cm:
            main()
        
        # Help should exit with code 0
        self.assertEqual(cm.exception.code, 0)


# NOTE: .env.local file loading is comprehensively tested in tests/config/test_env_manager.py
# Integration testing for dotenv functionality is complex due to import mocking requirements
# The unit tests provide complete coverage of this functionality


if __name__ == "__main__":
    unittest.main()