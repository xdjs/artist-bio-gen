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

# Import models from their new location
from artist_bio_gen.models import (
    ArtistData,
    ParseResult,
)

# Import core parsing function
from artist_bio_gen.core import (
    parse_input_file,
)

# Import CLI main function
from artist_bio_gen.cli import (
    main,
)


class TestArtistData(unittest.TestCase):
    """Test cases for the ArtistData NamedTuple."""
    
    def test_artist_data_creation(self):
        """Test creating ArtistData with name only."""
        artist = ArtistData(artist_id="550e8400-e29b-41d4-a716-446655440000", name="Taylor Swift")
        self.assertEqual(artist.artist_id, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(artist.name, "Taylor Swift")
        self.assertIsNone(artist.data)
    
    def test_artist_data_with_data(self):
        """Test creating ArtistData with name and data."""
        artist = ArtistData(
            artist_id="550e8400-e29b-41d4-a716-446655440001",
            name="Taylor Swift",
            data="Pop singer-songwriter"
        )
        self.assertEqual(artist.artist_id, "550e8400-e29b-41d4-a716-446655440001")
        self.assertEqual(artist.name, "Taylor Swift")
        self.assertEqual(artist.data, "Pop singer-songwriter")
    
    def test_artist_data_immutable(self):
        """Test that ArtistData is immutable."""
        artist = ArtistData(artist_id="550e8400-e29b-41d4-a716-446655440002", name="Taylor Swift")
        with self.assertRaises(AttributeError):
            artist.name = "Drake"


class TestParseResult(unittest.TestCase):
    """Test cases for the ParseResult NamedTuple."""
    
    def test_parse_result_creation(self):
        """Test creating ParseResult."""
        artists = [
            ArtistData(artist_id="550e8400-e29b-41d4-a716-446655440003", name="Artist 1"),
            ArtistData(artist_id="550e8400-e29b-41d4-a716-446655440004", name="Artist 2")
        ]
        result = ParseResult(
            artists=artists,
            skipped_lines=3,
            error_lines=1
        )
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 3)
        self.assertEqual(result.error_lines, 1)
    
    def test_parse_result_immutable(self):
        """Test that ParseResult is immutable."""
        result = ParseResult(artists=[], skipped_lines=0, error_lines=0)
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
        content = """550e8400-e29b-41d4-a716-446655440010,Taylor Swift,Pop singer-songwriter
550e8400-e29b-41d4-a716-446655440011,Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440010")
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].artist_id, "550e8400-e29b-41d4-a716-446655440011")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper")
        self.assertEqual(result.skipped_lines, 0)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_with_comments(self):
        """Test parsing a file with comment lines."""
        content = """# This is a comment
550e8400-e29b-41d4-a716-446655440019,Taylor Swift,Pop singer-songwriter
# Another comment
550e8400-e29b-41d4-a716-446655440020,Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 2)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_with_blank_lines(self):
        """Test parsing a file with blank lines."""
        content = """550e8400-e29b-41d4-a716-446655440021,Taylor Swift,Pop singer-songwriter

550e8400-e29b-41d4-a716-446655440022,Drake,Canadian rapper

"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 2)  # 2 blank lines (trailing blank line is stripped)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_with_optional_data(self):
        """Test parsing a file where some artists have no additional data."""
        content = """550e8400-e29b-41d4-a716-446655440012,Taylor Swift,Pop singer-songwriter
550e8400-e29b-41d4-a716-446655440013,Drake,
550e8400-e29b-41d4-a716-446655440014,Billie Eilish,Alternative pop artist"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 3)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440012")
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].artist_id, "550e8400-e29b-41d4-a716-446655440013")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertIsNone(result.artists[1].data)
        self.assertEqual(result.artists[2].artist_id, "550e8400-e29b-41d4-a716-446655440014")
        self.assertEqual(result.artists[2].name, "Billie Eilish")
        self.assertEqual(result.artists[2].data, "Alternative pop artist")
    
    def test_parse_file_with_whitespace(self):
        """Test parsing a file with whitespace that should be trimmed."""
        content = """  550e8400-e29b-41d4-a716-446655440015  ,  Taylor Swift  ,  Pop singer-songwriter  
  550e8400-e29b-41d4-a716-446655440016  ,  Drake  ,  Canadian rapper  """
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440015")
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].artist_id, "550e8400-e29b-41d4-a716-446655440016")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper")
    
    def test_parse_file_with_empty_artist_name(self):
        """Test parsing a file with empty artist names."""
        content = """550e8400-e29b-41d4-a716-446655440023,Taylor Swift,Pop singer-songwriter
,Empty artist name
550e8400-e29b-41d4-a716-446655440024,Drake,Canadian rapper"""
        temp_file = self.create_temp_file(content)
        
        with patch('artist_bio_gen.core.parser.logger') as mock_logger:
            result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)  # Only 2 valid artists
        self.assertEqual(result.error_lines, 1)
        # Check that warning was logged
        mock_logger.warning.assert_called()
    
    def test_parse_file_with_commas_in_data(self):
        """Test parsing a file where artist data contains commas."""
        content = """550e8400-e29b-41d4-a716-446655440025,Taylor Swift,"Pop singer-songwriter, known for autobiographical lyrics"
550e8400-e29b-41d4-a716-446655440026,Drake,"Canadian rapper, singer, and producer\""""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, 'Pop singer-songwriter, known for autobiographical lyrics')
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper, singer, and producer")
    
    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        temp_file = self.create_temp_file("")
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 0)
        self.assertEqual(result.skipped_lines, 0)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_only_comments(self):
        """Test parsing a file with only comments and blank lines."""
        content = """# This is a comment

# Another comment

"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 0)
        self.assertEqual(result.skipped_lines, 4)  # 2 comments + 2 blank lines (trailing blank line is stripped)
        self.assertEqual(result.error_lines, 0)
    
    def test_parse_file_not_found(self):
        """Test parsing a non-existent file."""
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.csv")
        
        with self.assertRaises(FileNotFoundError):
            parse_input_file(non_existent_file)
    
    def test_parse_file_encoding_error(self):
        """Test parsing a file with invalid encoding."""
        temp_file = os.path.join(self.temp_dir, "test.csv")
        # Write binary data that's not valid UTF-8
        with open(temp_file, 'wb') as f:
            f.write(b'\xff\xfe\x00\x00')  # Invalid UTF-8
        
        with self.assertRaises(UnicodeDecodeError):
            parse_input_file(temp_file)
    
    def test_parse_file_utf8_support(self):
        """Test parsing a file with UTF-8 characters."""
        content = """550e8400-e29b-41d4-a716-446655440032,Björk,Icelandic singer-songwriter
550e8400-e29b-41d4-a716-446655440033,Sigur Rós,Icelandic post-rock band
"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440032")
        self.assertEqual(result.artists[0].name, "Björk")
        self.assertEqual(result.artists[0].data, "Icelandic singer-songwriter")
        self.assertEqual(result.artists[1].artist_id, "550e8400-e29b-41d4-a716-446655440033")
        self.assertEqual(result.artists[1].name, "Sigur Rós")
        self.assertEqual(result.artists[1].data, "Icelandic post-rock band")
    
    def test_parse_file_logging(self):
        """Test that parsing logs appropriate messages."""
        content = """# Comment
550e8400-e29b-41d4-a716-446655440027,Taylor Swift,Pop singer-songwriter

550e8400-e29b-41d4-a716-446655440028,Drake,Canadian rapper
,Empty name"""
        temp_file = self.create_temp_file(content)
        
        with patch('artist_bio_gen.core.parser.logger') as mock_logger:
            result = parse_input_file(temp_file)
        
        # Check that appropriate log messages were called
        mock_logger.info.assert_called()
        mock_logger.warning.assert_called()
        
        # Verify the result
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.skipped_lines, 2)  # 1 comment + 1 blank line
        self.assertEqual(result.error_lines, 1)    # 1 empty name
    
    def test_parse_file_with_tabs_and_spaces(self):
        """Test parsing a file with various whitespace characters."""
        content = """550e8400-e29b-41d4-a716-446655440017,Taylor Swift\t,Pop singer-songwriter
  550e8400-e29b-41d4-a716-446655440018  ,  Drake  ,  Canadian rapper  """
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 2)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440017")
        self.assertEqual(result.artists[0].name, "Taylor Swift")
        self.assertEqual(result.artists[0].data, "Pop singer-songwriter")
        self.assertEqual(result.artists[1].artist_id, "550e8400-e29b-41d4-a716-446655440018")
        self.assertEqual(result.artists[1].name, "Drake")
        self.assertEqual(result.artists[1].data, "Canadian rapper")
    
    def test_parse_file_single_artist_no_data(self):
        """Test parsing a file with a single artist and no data field."""
        content = """550e8400-e29b-41d4-a716-446655440034,Taylor Swift"""
        temp_file = self.create_temp_file(content)
        
        result = parse_input_file(temp_file)
        
        self.assertEqual(len(result.artists), 1)
        self.assertEqual(result.artists[0].artist_id, "550e8400-e29b-41d4-a716-446655440034")
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
    
    @patch('artist_bio_gen.core.parser.logger')
    def test_main_function_dry_run(self, mock_logger):
        """Test main function with dry run mode."""
        content = """550e8400-e29b-41d4-a716-446655440029,Taylor Swift,Pop singer-songwriter
550e8400-e29b-41d4-a716-446655440030,Drake,Canadian rapper
550e8400-e29b-41d4-a716-446655440031,Billie Eilish,Alternative pop artist"""
        temp_file = self.create_temp_file(content)
        
        sys.argv = ['py', '--input-file', temp_file, '--prompt-id', 'test_prompt', '--dry-run']
        
        # Capture stdout
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            main()
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
    
    @patch('artist_bio_gen.core.parser.logger')
    def test_main_function_no_artists(self, mock_logger):
        """Test main function with file containing no valid artists."""
        content = """# Only comments
# No valid data"""
        temp_file = self.create_temp_file(content)
        
        sys.argv = ['py', '--input-file', temp_file, '--prompt-id', 'test_prompt']
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
        self.assertEqual(cm.exception.code, 1)
        mock_logger.error.assert_called()
    
    @patch('artist_bio_gen.core.parser.logger')
    def test_main_function_file_not_found(self, mock_logger):
        """Test main function with non-existent file."""
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.csv")
        
        sys.argv = ['py', '--input-file', non_existent_file, '--prompt-id', 'test_prompt']
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
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