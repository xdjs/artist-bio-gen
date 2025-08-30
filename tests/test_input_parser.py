#!/usr/bin/env python3
"""
Tests for the input file parser functionality.

This module contains comprehensive tests for the parse_input_file function
and related data structures.
"""

import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

# Add the current directory to the path so we can import run_artists
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_artists


class TestArtistData(unittest.TestCase):
    """Test cases for the ArtistData NamedTuple."""
    
    def test_artist_data_creation(self):
        """Test creating ArtistData with artist_id and name only."""
        artist = run_artists.ArtistData(
            artist_id="550e8400-e29b-41d4-a716-446655440000",
            name="Taylor Swift"
        )
        self.assertEqual(artist.artist_id, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(artist.name, "Taylor Swift")
        self.assertIsNone(artist.data)
    
    def test_artist_data_with_data(self):
        """Test creating ArtistData with artist_id, name and data."""
        artist = run_artists.ArtistData(
            artist_id="550e8400-e29b-41d4-a716-446655440000",
            name="Taylor Swift",
            data="Pop singer-songwriter"
        )
        self.assertEqual(artist.artist_id, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(artist.name, "Taylor Swift")
        self.assertEqual(artist.data, "Pop singer-songwriter")
    
    def test_artist_data_immutable(self):
        """Test that ArtistData is immutable."""
        artist = run_artists.ArtistData(
            artist_id="550e8400-e29b-41d4-a716-446655440000",
            name="Taylor Swift"
        )
        with self.assertRaises(AttributeError):
            artist.name = "Drake"


class TestParseResult(unittest.TestCase):
    """Test cases for the ParseResult NamedTuple."""
    
    def test_parse_result_creation(self):
        """Test creating ParseResult."""
        artists = [
            run_artists.ArtistData(artist_id="11111111-1111-1111-1111-111111111111", name="Artist 1"),
            run_artists.ArtistData(artist_id="22222222-2222-2222-2222-222222222222", name="Artist 2")
        ]
        result = run_artists.ParseResult(
            artists=artists,
            skipped_lines=3,
            error_lines=1
        )
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 3)
        self.assertEqual(result.error_lines, 1)
    
    def test_parse_result_immutable(self):
        """Test that ParseResult is immutable."""
        result = run_artists.ParseResult(artists=[], skipped_lines=0, error_lines=0)
        with self.assertRaises(AttributeError):
            result.skipped_lines = 5


class TestParseInputFile(unittest.TestCase):
    """Test cases for the parse_input_file function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_temp_file(self, content: str) -> str:
        """Create a temporary file with given content."""
        temp_file = os.path.join(self.temp_dir, "test.csv")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return temp_file
    
    def test_parse_simple_file(self):
        """Test parsing a simple file with valid data."""
        content = """550e8400-e29b-41d4-a716-446655440000,Taylor Swift,Pop singer-songwriter
11111111-1111-1111-1111-111111111111,Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].artist_id, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper")
        self.assertEqual(result.skipped_lines, 0)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_with_comments(self):
        """Test parsing a file with comment lines."""
        content = """# This is a comment
550e8400-e29b-41d4-a716-446655440000,Taylor Swift,Pop singer-songwriter
# Another comment
11111111-1111-1111-1111-111111111111,Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 2)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_with_blank_lines(self):
        """Test parsing a file with blank lines."""
        content = """Taylor Swift,Pop singer-songwriter

Drake,Canadian rapper

"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 2)  # 2 blank lines (trailing blank line is stripped)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_with_optional_data(self):
        """Test parsing a file where some artists have no additional data."""
        content = """Taylor Swift,Pop singer-songwriter
Drake,
Billie Eilish,Alternative pop artist"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 3)
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertIsNone(result.artists[1].data)
        self.assertEqual(result.artists[2].name, "Billie Eilish")
        self.assertEqual(result.artists[2].data, "Alternative pop artist")
    
    def test_parse_file_with_whitespace(self):
        """Test parsing a file with whitespace that should be trimmed."""
        content = """  Taylor Swift  ,  Pop singer-songwriter  
  Drake  ,  Canadian rapper  """
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper")
    
    def test_parse_file_with_empty_artist_name(self):
        """Test parsing a file with empty artist names."""
        content = """Taylor Swift,Pop singer-songwriter
,Empty artist name
Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        with patch('run_artists.logger') as mock_logger:
            result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)  # Only 2 valid artists
        self.assertEqual(result.error_lines, 1)
        # Check that warning was logged
        mock_logger.warning.assert_called()
    
    def test_parse_file_with_commas_in_data(self):
        """Test parsing a file where artist data contains commas."""
        content = """Taylor Swift,"Pop singer-songwriter, known for autobiographical lyrics"
Drake,Canadian rapper, singer, and producer"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, '"Pop singer-songwriter, known for autobiographical lyrics"')
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper, singer, and producer")
    
    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        temp_file = self.create_temp_file("")
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 0)
        self.assertEqual(result.skipped_lines, 0)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_only_comments(self):
        """Test parsing a file with only comments and blank lines."""
        content = """# This is a comment

# Another comment

"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 0)
        self.assertEqual(result.skipped_lines, 4)  # 2 comments + 2 blank lines (trailing blank line is stripped)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_not_found(self):
        """Test parsing a non-existent file."""
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.csv")
        
        with self.assertRaises(FileNotFoundError):
            run_artists.parse_input_file(non_existent_file)
    
    def test_parse_file_encoding_error(self):
        """Test parsing a file with invalid encoding."""
        temp_file = os.path.join(self.temp_dir, "test.csv")
        # Write binary data that's not valid UTF-8
        with open(temp_file, 'wb') as f:
            f.write(b'\xff\xfe\x00\x00')  # Invalid UTF-8
        
        with self.assertRaises(UnicodeDecodeError):
            run_artists.parse_input_file(temp_file)
    
    def test_parse_file_utf8_support(self):
        """Test parsing a file with UTF-8 characters."""
        content = """Björk,Icelandic singer-songwriter
Sigur Rós,Icelandic post-rock band
"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].name, "Björk")
        self.assertEqual(result.artists[0].data, "Icelandic singer-songwriter")
        self.assertEqual(result.artists[1].name, "Sigur Rós")
        self.assertEqual(result.artists[1].data, "Icelandic post-rock band")
    
    def test_parse_file_logging(self):
        """Test that parsing logs appropriate messages."""
        content = """# Comment
Taylor Swift,Pop singer-songwriter

Drake,Canadian rapper
,Empty name"""
        temp_file = self.create_temp_file(content)
        
        with patch('run_artists.logger') as mock_logger:
            result = run_artists.parse_input_file(temp_file)
        
        # Check that appropriate log messages were called
        mock_logger.info.assert_called()
        mock_logger.warning.assert_called()
        
        # Verify the result
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 2)  # 1 comment + 1 blank line
        self.assertEqual(result.error_lines, 1)    # 1 empty name
    
    def test_parse_file_with_tabs_and_spaces(self):
        """Test parsing a file with various whitespace characters."""
        content = """Taylor Swift\t,Pop singer-songwriter
  Drake  ,  Canadian rapper  """
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper")
    
    def test_parse_file_single_artist_no_data(self):
        """Test parsing a file with a single artist and no data field."""
        content = """Taylor Swift"""
        temp_file = self.create_temp_file(content)
        
        result = run_artists.parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 1)
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertIsNone(result.artists[0].data)


class TestMainFunctionWithParser(unittest.TestCase):
    """Test cases for main function integration with parser."""
    
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
    def test_main_function_dry_run(self, mock_logger):
        """Test main function with dry run mode."""
        content = """Taylor Swift,Pop singer-songwriter
Drake,Canadian rapper
Billie Eilish,Alternative pop artist"""
        temp_file = self.create_temp_file(content)
        
        sys.argv = ['run_artists.py', '--input-file', temp_file, '--prompt-id', 'test_prompt', '--dry-run']
        
        # Capture stdout
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            run_artists.main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout
        
        output = captured_output.getvalue()
        
        # Check that dry run output was printed
        self.assertIn("Taylor Swift", output)
        self.assertIn("Pop singer-songwriter", output)
        self.assertIn("Drake", output)
        self.assertIn("Canadian rapper", output)
        
        # Check that logging was called
        mock_logger.info.assert_called()
    
    @patch('run_artists.logger')
    def test_main_function_no_artists(self, mock_logger):
        """Test main function with file containing no valid artists."""
        content = """# Only comments
# No valid data"""
        temp_file = self.create_temp_file(content)
        
        sys.argv = ['run_artists.py', '--input-file', temp_file, '--prompt-id', 'test_prompt']
        
        with self.assertRaises(SystemExit) as cm:
            run_artists.main()
        
        self.assertEqual(cm.exception.code, 1)
        mock_logger.error.assert_called()
    
    @patch('run_artists.logger')
    def test_main_function_file_not_found(self, mock_logger):
        """Test main function with non-existent file."""
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.csv")
        
        sys.argv = ['run_artists.py', '--input-file', non_existent_file, '--prompt-id', 'test_prompt']
        
        with self.assertRaises(SystemExit) as cm:
            run_artists.main()
        
        self.assertEqual(cm.exception.code, 1)
        mock_logger.error.assert_called()


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestArtistData,
        TestParseResult,
        TestParseInputFile,
        TestMainFunctionWithParser
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)