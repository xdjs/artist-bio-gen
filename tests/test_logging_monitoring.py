#!/usr/bin/env python3
"""
Tests for the enhanced logging and monitoring functionality.

This module contains comprehensive tests for the logging and monitoring features
including progress tracking, statistics calculation, and summary reporting.
"""

import os
import sys
import tempfile
import time
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

# Add the current directory to the path so we can import run_artists
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_artists


class TestProcessingStats(unittest.TestCase):
    """Test cases for the ProcessingStats NamedTuple."""
    
    def test_processing_stats_creation(self):
        """Test creating ProcessingStats with all fields."""
        stats = run_artists.ProcessingStats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
            total_duration=10.0,
            avg_time_per_artist=1.0,
            api_calls_per_second=1.0
        )
        
        self.assertEqual(stats.total_artists, 10)
        self.assertEqual(stats.successful_calls, 8)
        self.assertEqual(stats.failed_calls, 2)
        self.assertEqual(stats.skipped_lines, 3)
        self.assertEqual(stats.error_lines, 1)
        self.assertEqual(stats.start_time, 1000.0)
        self.assertEqual(stats.end_time, 1010.0)
        self.assertEqual(stats.total_duration, 10.0)
        self.assertEqual(stats.avg_time_per_artist, 1.0)
        self.assertEqual(stats.api_calls_per_second, 1.0)
    
    def test_processing_stats_immutable(self):
        """Test that ProcessingStats is immutable."""
        stats = run_artists.ProcessingStats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
            total_duration=10.0,
            avg_time_per_artist=1.0,
            api_calls_per_second=1.0
        )
        
        with self.assertRaises(AttributeError):
            stats.total_artists = 20


class TestProgressBar(unittest.TestCase):
    """Test cases for the progress bar functionality."""
    
    def test_progress_bar_empty(self):
        """Test progress bar with no progress."""
        bar = run_artists.create_progress_bar(0, 10)
        self.assertEqual(bar, "[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]")
    
    def test_progress_bar_half(self):
        """Test progress bar at 50%."""
        bar = run_artists.create_progress_bar(5, 10)
        # Should be approximately half filled (15 out of 30 characters)
        filled_chars = bar.count('█')
        self.assertEqual(filled_chars, 15)
    
    def test_progress_bar_full(self):
        """Test progress bar at 100%."""
        bar = run_artists.create_progress_bar(10, 10)
        self.assertEqual(bar, "[██████████████████████████████]")
    
    def test_progress_bar_partial(self):
        """Test progress bar at 33%."""
        bar = run_artists.create_progress_bar(1, 3)
        # Should be approximately 1/3 filled
        filled_chars = bar.count('█')
        self.assertGreater(filled_chars, 0)
        self.assertLess(filled_chars, 30)
    
    def test_progress_bar_zero_total(self):
        """Test progress bar with zero total."""
        bar = run_artists.create_progress_bar(0, 0)
        self.assertEqual(bar, "[                              ]")


class TestStatisticsCalculation(unittest.TestCase):
    """Test cases for statistics calculation."""
    
    def test_calculate_processing_stats_basic(self):
        """Test basic statistics calculation."""
        stats = run_artists.calculate_processing_stats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0
        )
        
        self.assertEqual(stats.total_artists, 10)
        self.assertEqual(stats.successful_calls, 8)
        self.assertEqual(stats.failed_calls, 2)
        self.assertEqual(stats.skipped_lines, 3)
        self.assertEqual(stats.error_lines, 1)
        self.assertEqual(stats.start_time, 1000.0)
        self.assertEqual(stats.end_time, 1010.0)
        self.assertEqual(stats.total_duration, 10.0)
        self.assertEqual(stats.avg_time_per_artist, 1.0)
        self.assertEqual(stats.api_calls_per_second, 1.0)
    
    def test_calculate_processing_stats_zero_duration(self):
        """Test statistics calculation with zero duration."""
        stats = run_artists.calculate_processing_stats(
            total_artists=0,
            successful_calls=0,
            failed_calls=0,
            skipped_lines=0,
            error_lines=0,
            start_time=1000.0,
            end_time=1000.0
        )
        
        self.assertEqual(stats.total_duration, 0.0)
        self.assertEqual(stats.avg_time_per_artist, 0.0)
        self.assertEqual(stats.api_calls_per_second, 0.0)
    
    def test_calculate_processing_stats_zero_artists(self):
        """Test statistics calculation with zero artists."""
        stats = run_artists.calculate_processing_stats(
            total_artists=0,
            successful_calls=0,
            failed_calls=0,
            skipped_lines=0,
            error_lines=0,
            start_time=1000.0,
            end_time=1010.0
        )
        
        self.assertEqual(stats.avg_time_per_artist, 0.0)
        self.assertEqual(stats.api_calls_per_second, 0.0)


class TestLoggingFunctions(unittest.TestCase):
    """Test cases for logging functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('run_artists.logger')
    def test_log_processing_start(self, mock_logger):
        """Test logging processing start."""
        start_time = run_artists.log_processing_start(
            total_artists=10,
            input_file="test.csv",
            prompt_id="test_prompt",
            max_workers=4
        )
        
        # Check that start time was returned
        self.assertIsInstance(start_time, float)
        self.assertGreater(start_time, 0)
        
        # Check that appropriate log messages were called
        mock_logger.info.assert_called()
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Check for key log messages
        self.assertTrue(any("PROCESSING STARTED" in call for call in log_calls))
        self.assertTrue(any("test.csv" in call for call in log_calls))
        self.assertTrue(any("test_prompt" in call for call in log_calls))
        self.assertTrue(any("10" in call for call in log_calls))
        self.assertTrue(any("4" in call for call in log_calls))
    
    @patch('run_artists.logger')
    def test_log_progress_update_success(self, mock_logger):
        """Test logging progress update for successful processing."""
        run_artists.log_progress_update(5, 10, "Taylor Swift", True, 2.5)
        
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        
        # Check for key elements in the log message
        self.assertIn("5/ 10", log_message)  # Note the space padding
        self.assertIn("50.0%", log_message)
        self.assertIn("✅", log_message)
        self.assertIn("Taylor Swift", log_message)
        self.assertIn("SUCCESS", log_message)
        self.assertIn("2.50s", log_message)
    
    @patch('run_artists.logger')
    def test_log_progress_update_failure(self, mock_logger):
        """Test logging progress update for failed processing."""
        run_artists.log_progress_update(3, 10, "Drake", False, 1.2)
        
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        
        # Check for key elements in the log message
        self.assertIn("3/ 10", log_message)  # Note the space padding
        self.assertIn("30.0%", log_message)
        self.assertIn("❌", log_message)
        self.assertIn("Drake", log_message)
        self.assertIn("FAILED", log_message)
        self.assertIn("1.20s", log_message)
    
    @patch('run_artists.logger')
    def test_log_processing_summary(self, mock_logger):
        """Test logging processing summary."""
        stats = run_artists.ProcessingStats(
            total_artists=10,
            successful_calls=8,
            failed_calls=2,
            skipped_lines=3,
            error_lines=1,
            start_time=1000.0,
            end_time=1010.0,
            total_duration=10.0,
            avg_time_per_artist=1.0,
            api_calls_per_second=1.0
        )
        
        run_artists.log_processing_summary(stats)
        
        # Check that multiple log messages were called
        self.assertGreater(mock_logger.info.call_count, 5)
        
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Check for key summary elements
        self.assertTrue(any("PROCESSING SUMMARY" in call for call in log_calls))
        self.assertTrue(any("10" in call for call in log_calls))  # Total artists
        self.assertTrue(any("8" in call for call in log_calls))   # Successful calls
        self.assertTrue(any("2" in call for call in log_calls))   # Failed calls
        self.assertTrue(any("80.0%" in call for call in log_calls))  # Success rate
        self.assertTrue(any("1.00s" in call for call in log_calls))  # Avg time
        self.assertTrue(any("1.00" in call for call in log_calls))   # Calls per second


class TestLoggingConfiguration(unittest.TestCase):
    """Test cases for logging configuration."""
    
    def test_setup_logging_default(self):
        """Test default logging setup."""
        # This is a bit tricky to test since logging is global
        # We'll just ensure the function exists and can be called
        run_artists.setup_logging(verbose=False)
        # If we get here without error, the function works
    
    def test_setup_logging_verbose(self):
        """Test verbose logging setup."""
        run_artists.setup_logging(verbose=True)
        # If we get here without error, the function works


class TestEnhancedMainFunction(unittest.TestCase):
    """Test cases for the enhanced main function with logging."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_argv = sys.argv.copy()
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)
        sys.argv = self.original_argv
    
    def create_temp_file(self, content: str) -> str:
        """Create a temporary file with given content."""
        temp_file = os.path.join(self.temp_dir, "test.csv")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return temp_file
    
    @patch('run_artists.logger')
    @patch('run_artists.create_openai_client')
    def test_main_function_enhanced_logging(self, mock_client, mock_logger):
        """Test that main function uses enhanced logging."""
        content = """550e8400-e29b-41d4-a716-446655440035,Taylor Swift,Pop singer-songwriter
550e8400-e29b-41d4-a716-446655440036,Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        # Mock the OpenAI client and API response
        mock_openai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.output_text = "Generated bio"
        mock_response.id = "response_123"
        mock_response.created_at = 1234567890
        mock_openai_client.responses.create.return_value = mock_response
        mock_client.return_value = mock_openai_client
        
        sys.argv = [
            'run_artists.py',
            '--input-file', temp_file,
            '--prompt-id', 'test_prompt'
        ]
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            run_artists.main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout
        
        # Check that enhanced logging was called
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Should have processing start log
        self.assertTrue(any("PROCESSING STARTED" in call for call in log_calls))
        
        # Should have progress updates
        self.assertTrue(any("✅" in call for call in log_calls))
        
        # Should have processing summary
        self.assertTrue(any("PROCESSING SUMMARY" in call for call in log_calls))
    
    @patch('run_artists.logger')
    def test_main_function_verbose_flag(self, mock_logger):
        """Test that verbose flag is handled correctly."""
        content = """550e8400-e29b-41d4-a716-446655440037,Taylor Swift,Pop singer-songwriter"""
        temp_file = self.create_temp_file(content)
        
        sys.argv = [
            'run_artists.py',
            '--input-file', temp_file,
            '--prompt-id', 'test_prompt',
            '--verbose',
            '--dry-run'
        ]
        
        try:
            run_artists.main()
        except SystemExit:
            pass
        
        # The verbose flag should be processed without error
        # (We can't easily test the actual logging level change without more complex mocking)


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestProcessingStats,
        TestProgressBar,
        TestStatisticsCalculation,
        TestLoggingFunctions,
        TestLoggingConfiguration,
        TestEnhancedMainFunction
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)