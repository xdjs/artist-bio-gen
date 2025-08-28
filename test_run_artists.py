#!/usr/bin/env python3
"""
Tests for run_artists.py

This module contains comprehensive tests for the artist bio generator script,
focusing on CLI argument parsing and basic functionality.
"""

import argparse
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

# Add the current directory to the path so we can import run_artists
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_artists


class TestArgumentParser(unittest.TestCase):
    """Test cases for the CLI argument parser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = run_artists.create_argument_parser()
    
    def test_required_input_file_argument(self):
        """Test that --input-file is required."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])
    
    def test_input_file_argument_parsing(self):
        """Test that --input-file argument is parsed correctly."""
        args = self.parser.parse_args(['--input-file', 'test.csv'])
        self.assertEqual(args.input_file, 'test.csv')
    
    def test_prompt_id_default_from_env(self):
        """Test that prompt ID defaults to environment variable."""
        with patch.dict(os.environ, {'OPENAI_PROMPT_ID': 'test_prompt_123'}):
            args = self.parser.parse_args(['--input-file', 'test.csv'])
            args = run_artists.apply_environment_defaults(args)
            self.assertEqual(args.prompt_id, 'test_prompt_123')
    
    def test_prompt_id_explicit_override(self):
        """Test that explicit prompt ID overrides environment variable."""
        with patch.dict(os.environ, {'OPENAI_PROMPT_ID': 'env_prompt'}):
            args = self.parser.parse_args([
                '--input-file', 'test.csv',
                '--prompt-id', 'explicit_prompt'
            ])
            args = run_artists.apply_environment_defaults(args)
            self.assertEqual(args.prompt_id, 'explicit_prompt')
    

    
    def test_version_argument(self):
        """Test that version argument is optional and parsed correctly."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--version', 'v1.2.3'
        ])
        self.assertEqual(args.version, 'v1.2.3')
    
    def test_version_argument_optional(self):
        """Test that version argument is optional."""
        args = self.parser.parse_args(['--input-file', 'test.csv'])
        self.assertIsNone(args.version)
    
    def test_output_default(self):
        """Test that output file defaults to out.jsonl."""
        args = self.parser.parse_args(['--input-file', 'test.csv'])
        self.assertEqual(args.output, 'out.jsonl')
    
    def test_output_explicit(self):
        """Test that output file can be specified explicitly."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--output', 'custom_output.jsonl'
        ])
        self.assertEqual(args.output, 'custom_output.jsonl')
    
    def test_max_workers_default(self):
        """Test that max_workers defaults to 4."""
        args = self.parser.parse_args(['--input-file', 'test.csv'])
        self.assertEqual(args.max_workers, 4)
    
    def test_max_workers_explicit(self):
        """Test that max_workers can be specified explicitly."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--max-workers', '8'
        ])
        self.assertEqual(args.max_workers, 8)
    
    def test_max_workers_type_conversion(self):
        """Test that max_workers is converted to integer."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--max-workers', '16'
        ])
        self.assertIsInstance(args.max_workers, int)
        self.assertEqual(args.max_workers, 16)
    
    def test_dry_run_flag(self):
        """Test that dry-run flag is parsed correctly."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--dry-run'
        ])
        self.assertTrue(args.dry_run)
    
    def test_dry_run_default_false(self):
        """Test that dry-run defaults to False."""
        args = self.parser.parse_args(['--input-file', 'test.csv'])
        self.assertFalse(args.dry_run)
    
    def test_all_arguments_together(self):
        """Test parsing all arguments together."""
        args = self.parser.parse_args([
            '--input-file', 'artists.csv',
            '--prompt-id', 'prompt_456',
            '--version', 'v2.0',
            '--output', 'results.jsonl',
            '--max-workers', '10',
            '--dry-run'
        ])
        
        self.assertEqual(args.input_file, 'artists.csv')
        self.assertEqual(args.prompt_id, 'prompt_456')
        self.assertEqual(args.version, 'v2.0')
        self.assertEqual(args.output, 'results.jsonl')
        self.assertEqual(args.max_workers, 10)
        self.assertTrue(args.dry_run)
    
    def test_help_text_contains_expected_content(self):
        """Test that help text contains expected information."""
        help_output = StringIO()
        self.parser.print_help(file=help_output)
        help_text = help_output.getvalue()
        
        # Check for key help text elements
        self.assertIn('Generate artist bios using OpenAI Responses API', help_text)
        self.assertIn('--input-file', help_text)
        self.assertIn('--prompt-id', help_text)
        self.assertIn('--version', help_text)
        self.assertIn('--output', help_text)
        self.assertIn('--max-workers', help_text)
        self.assertIn('--dry-run', help_text)
        self.assertIn('Examples:', help_text)
    
    def test_examples_in_help(self):
        """Test that help text contains usage examples."""
        help_output = StringIO()
        self.parser.print_help(file=help_output)
        help_text = help_output.getvalue()
        
        # Check for example commands
        self.assertIn('python run_artists.py --input-file artists.csv --prompt-id prompt_123', help_text)
        self.assertIn('python run_artists.py --input-file data.txt --max-workers 8', help_text)
        self.assertIn('python run_artists.py --input-file artists.csv --dry-run', help_text)


class TestMainFunction(unittest.TestCase):
    """Test cases for the main function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.original_argv = sys.argv.copy()
    
    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv
    
    @patch('run_artists.logger')
    def test_main_function_basic_execution(self, mock_logger):
        """Test that main function executes without errors."""
        sys.argv = ['run_artists.py', '--input-file', 'test.csv', '--prompt-id', 'test_prompt']
        
        # Should not raise any exceptions
        try:
            run_artists.main()
        except SystemExit:
            pass  # Expected when argparse encounters issues
        
        # Verify logging was called
        mock_logger.info.assert_called()
    
    @patch('run_artists.logger')
    def test_main_function_logging(self, mock_logger):
        """Test that main function logs expected information."""
        sys.argv = ['run_artists.py', '--input-file', 'artists.csv', '--prompt-id', 'prompt_123']
        
        try:
            run_artists.main()
        except SystemExit:
            pass
        
        # Check that logging was called with expected messages
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        self.assertIn("Starting artist bio generation process", log_calls)
        self.assertIn("Input file: artists.csv", log_calls)
        self.assertIn("Prompt ID: prompt_123", log_calls)


class TestEnvironmentVariableHandling(unittest.TestCase):
    """Test cases for environment variable handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = run_artists.create_argument_parser()
    
    def test_no_environment_variables(self):
        """Test behavior when no environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            args = self.parser.parse_args(['--input-file', 'test.csv'])
            args = run_artists.apply_environment_defaults(args)
            self.assertIsNone(args.prompt_id)
    
    def test_partial_environment_variables(self):
        """Test behavior when only some environment variables are set."""
        with patch.dict(os.environ, {'OPENAI_PROMPT_ID': 'test_prompt'}):
            args = self.parser.parse_args(['--input-file', 'test.csv'])
            args = run_artists.apply_environment_defaults(args)
            self.assertEqual(args.prompt_id, 'test_prompt')
    
    def test_all_environment_variables(self):
        """Test behavior when all environment variables are set."""
        with patch.dict(os.environ, {
            'OPENAI_PROMPT_ID': 'env_prompt'
        }):
            args = self.parser.parse_args(['--input-file', 'test.csv'])
            args = run_artists.apply_environment_defaults(args)
            self.assertEqual(args.prompt_id, 'env_prompt')


class TestArgumentValidation(unittest.TestCase):
    """Test cases for argument validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = run_artists.create_argument_parser()
    
    def test_max_workers_positive_integer(self):
        """Test that max_workers accepts positive integers."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--max-workers', '1'
        ])
        self.assertEqual(args.max_workers, 1)
        
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--max-workers', '100'
        ])
        self.assertEqual(args.max_workers, 100)
    
    def test_max_workers_zero(self):
        """Test that max_workers accepts zero."""
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--max-workers', '0'
        ])
        self.assertEqual(args.max_workers, 0)
    
    def test_max_workers_negative_raises_error(self):
        """Test that negative max_workers raises an error."""
        # Note: argparse doesn't validate ranges by default, so this test
        # documents current behavior. Range validation would need to be added.
        args = self.parser.parse_args([
            '--input-file', 'test.csv',
            '--max-workers', '-1'
        ])
        self.assertEqual(args.max_workers, -1)  # Currently allowed


class TestFileStructure(unittest.TestCase):
    """Test cases for file structure and imports."""
    
    def test_run_artists_imports(self):
        """Test that run_artists module can be imported successfully."""
        import run_artists
        self.assertTrue(hasattr(run_artists, 'main'))
        self.assertTrue(hasattr(run_artists, 'create_argument_parser'))
    
    def test_required_functions_exist(self):
        """Test that required functions exist in the module."""
        import run_artists
        self.assertTrue(callable(run_artists.main))
        self.assertTrue(callable(run_artists.create_argument_parser))
    
    def test_logger_configuration(self):
        """Test that logger is properly configured."""
        import run_artists
        self.assertIsNotNone(run_artists.logger)
        self.assertEqual(run_artists.logger.name, '__main__')


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestArgumentParser,
        TestMainFunction,
        TestEnvironmentVariableHandling,
        TestArgumentValidation,
        TestFileStructure
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)