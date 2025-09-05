import unittest
import tempfile
import os
import json
import sys
from unittest.mock import patch, mock_open

# Add the tools directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))

from generate_batch_update import (
    validate_uuid_format,
    has_valid_bio,
    validate_jsonl_entry,
    parse_jsonl_line,
    parse_jsonl_file,
    setup_argument_parser,
    validate_arguments
)


class TestUUIDValidation(unittest.TestCase):
    """Test UUID validation functionality."""
    
    def test_valid_uuid_formats(self):
        """Test that valid UUIDs are accepted."""
        valid_uuids = [
            '123e4567-e89b-12d3-a456-426614174000',
            'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
            '00000000-0000-0000-0000-000000000000',
            'ffffffff-ffff-ffff-ffff-ffffffffffff'
        ]
        
        for uuid_str in valid_uuids:
            with self.subTest(uuid=uuid_str):
                self.assertTrue(validate_uuid_format(uuid_str))
    
    def test_invalid_uuid_formats(self):
        """Test that invalid UUIDs are rejected."""
        invalid_uuids = [
            'not-a-uuid',
            '123e4567-e89b-12d3-a456',  # Too short
            '123e4567-e89b-12d3-a456-426614174000-extra',  # Too long
            '123g4567-e89b-12d3-a456-426614174000',  # Invalid character
            '',
            None,
            123,
            '123e4567_e89b_12d3_a456_426614174000'  # Wrong separators
        ]
        
        for uuid_str in invalid_uuids:
            with self.subTest(uuid=uuid_str):
                self.assertFalse(validate_uuid_format(uuid_str))


class TestBioValidation(unittest.TestCase):
    """Test bio validation functionality."""
    
    def test_valid_bio_entries(self):
        """Test entries with valid bios (no error)."""
        valid_entries = [
            {'error': None},
            {'error': ''},
            {'error': 'null'},
            {}  # No error field
        ]
        
        for entry in valid_entries:
            with self.subTest(entry=entry):
                self.assertTrue(has_valid_bio(entry))
    
    def test_invalid_bio_entries(self):
        """Test entries with invalid bios (has error)."""
        invalid_entries = [
            {'error': 'Some error occurred'},
            {'error': 'Rate limit exceeded'},
            {'error': 'API error'}
        ]
        
        for entry in invalid_entries:
            with self.subTest(entry=entry):
                self.assertFalse(has_valid_bio(entry))


class TestJSONLEntryValidation(unittest.TestCase):
    """Test JSONL entry validation functionality."""
    
    def test_valid_entries(self):
        """Test valid JSONL entries."""
        valid_entries = [
            {
                'artist_id': '123e4567-e89b-12d3-a456-426614174000',
                'bio': 'This is a valid bio text',
                'error': None
            },
            {
                'artist_id': 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
                'bio': 'Another valid bio',
                'error': ''
            },
            {
                'artist_id': '00000000-0000-0000-0000-000000000000',
                'bio': 'Valid bio without error field'
            }
        ]
        
        for entry in valid_entries:
            with self.subTest(entry=entry):
                is_valid, error_msg = validate_jsonl_entry(entry)
                self.assertTrue(is_valid, f"Entry should be valid: {error_msg}")
                self.assertEqual(error_msg, "")
    
    def test_missing_required_fields(self):
        """Test entries missing required fields."""
        invalid_entries = [
            ({}, "Missing required field 'artist_id'"),
            ({'artist_id': '123e4567-e89b-12d3-a456-426614174000'}, "Missing required field 'bio'"),
        ]
        
        for entry, expected_error in invalid_entries:
            with self.subTest(entry=entry):
                is_valid, error_msg = validate_jsonl_entry(entry)
                self.assertFalse(is_valid)
                self.assertEqual(error_msg, expected_error)
    
    def test_invalid_uuid(self):
        """Test entries with invalid UUIDs."""
        entry = {
            'artist_id': 'not-a-uuid',
            'bio': 'Valid bio text'
        }
        
        is_valid, error_msg = validate_jsonl_entry(entry)
        self.assertFalse(is_valid)
        self.assertIn("Invalid UUID format", error_msg)
    
    def test_bio_with_error(self):
        """Test entries with bio errors."""
        entry = {
            'artist_id': '123e4567-e89b-12d3-a456-426614174000',
            'bio': 'Some bio text',
            'error': 'API rate limit exceeded'
        }
        
        is_valid, error_msg = validate_jsonl_entry(entry)
        self.assertFalse(is_valid)
        self.assertIn("Bio has error", error_msg)
    
    def test_empty_bio(self):
        """Test entries with empty bio content."""
        entries = [
            {
                'artist_id': '123e4567-e89b-12d3-a456-426614174000',
                'bio': ''
            },
            {
                'artist_id': '123e4567-e89b-12d3-a456-426614174000',
                'bio': '   '  # Only whitespace
            }
        ]
        
        for entry in entries:
            with self.subTest(entry=entry):
                is_valid, error_msg = validate_jsonl_entry(entry)
                self.assertFalse(is_valid)
                self.assertEqual(error_msg, "Bio content is empty")


class TestJSONLLineParsing(unittest.TestCase):
    """Test JSONL line parsing functionality."""
    
    def test_valid_json_lines(self):
        """Test parsing valid JSON lines."""
        valid_lines = [
            '{"artist_id": "123e4567-e89b-12d3-a456-426614174000", "bio": "Test bio"}',
            '{"name": "test", "value": 123}',
            '{}'
        ]
        
        for line in valid_lines:
            with self.subTest(line=line):
                entry, error_msg = parse_jsonl_line(line, 1)
                self.assertIsNotNone(entry)
                self.assertEqual(error_msg, "")
                self.assertIsInstance(entry, dict)
    
    def test_invalid_json_lines(self):
        """Test parsing invalid JSON lines."""
        invalid_lines = [
            '{"invalid": json}',  # Missing quotes
            '{"incomplete": ',    # Incomplete JSON
            'not json at all',
            '{"trailing": "comma",}'  # Trailing comma
        ]
        
        for line in invalid_lines:
            with self.subTest(line=line):
                entry, error_msg = parse_jsonl_line(line, 1)
                self.assertIsNone(entry)
                self.assertIn("JSON decode error", error_msg)
    
    def test_empty_lines(self):
        """Test parsing empty lines."""
        empty_lines = ['', '   ', '\n', '\t']
        
        for line in empty_lines:
            with self.subTest(line=repr(line)):
                entry, error_msg = parse_jsonl_line(line, 1)
                self.assertIsNone(entry)
                self.assertEqual(error_msg, "")


class TestJSONLFileParsing(unittest.TestCase):
    """Test JSONL file parsing functionality."""
    
    def test_parse_valid_file(self):
        """Test parsing a valid JSONL file."""
        jsonl_content = '''{"artist_id": "123e4567-e89b-12d3-a456-426614174000", "bio": "Bio 1"}
{"artist_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", "bio": "Bio 2"}
{"artist_id": "00000000-0000-0000-0000-000000000000", "bio": "Bio 3"}'''
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            f.write(jsonl_content)
            temp_path = f.name
        
        try:
            valid_entries, invalid_entries, error_messages = parse_jsonl_file(temp_path)
            
            self.assertEqual(len(valid_entries), 3)
            self.assertEqual(len(invalid_entries), 0)
            self.assertEqual(len(error_messages), 0)
            
            # Check that all entries have the expected structure
            for entry in valid_entries:
                self.assertIn('artist_id', entry)
                self.assertIn('bio', entry)
                
        finally:
            os.unlink(temp_path)
    
    def test_parse_mixed_file(self):
        """Test parsing a file with both valid and invalid entries."""
        jsonl_content = '''{"artist_id": "123e4567-e89b-12d3-a456-426614174000", "bio": "Valid bio"}
{"artist_id": "invalid-uuid", "bio": "Bio with bad UUID"}
{"artist_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", "bio": "Valid bio", "error": "Some error"}
invalid json line
{"artist_id": "00000000-0000-0000-0000-000000000000", "bio": "Another valid bio"}'''
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            f.write(jsonl_content)
            temp_path = f.name
        
        try:
            valid_entries, invalid_entries, error_messages = parse_jsonl_file(temp_path)
            
            self.assertEqual(len(valid_entries), 2)  # First and last entries
            self.assertEqual(len(invalid_entries), 2)  # Invalid UUID and error entries
            self.assertEqual(len(error_messages), 3)  # 2 validation errors + 1 JSON error
            
        finally:
            os.unlink(temp_path)
    
    def test_parse_nonexistent_file(self):
        """Test parsing a non-existent file."""
        valid_entries, invalid_entries, error_messages = parse_jsonl_file('/nonexistent/file.jsonl')
        
        self.assertEqual(len(valid_entries), 0)
        self.assertEqual(len(invalid_entries), 0)
        self.assertEqual(len(error_messages), 1)
        self.assertIn("Input file not found", error_messages[0])


class TestArgumentParser(unittest.TestCase):
    """Test command-line argument parsing."""
    
    def test_parser_setup(self):
        """Test that argument parser is set up correctly."""
        parser = setup_argument_parser()
        
        # Test required arguments
        with self.assertRaises(SystemExit):
            parser.parse_args([])  # No arguments should fail
        
        # Test valid arguments
        args = parser.parse_args(['--input', 'test.jsonl'])
        self.assertEqual(args.input, 'test.jsonl')
        self.assertFalse(args.test_mode)
        self.assertEqual(args.output_dir, '.')
        
        # Test all arguments
        args = parser.parse_args(['--input', 'test.jsonl', '--test-mode', '--output-dir', '/tmp'])
        self.assertEqual(args.input, 'test.jsonl')
        self.assertTrue(args.test_mode)
        self.assertEqual(args.output_dir, '/tmp')
    
    def test_argument_validation(self):
        """Test command-line argument validation."""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        # Create a temporary directory for testing
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Test valid arguments
            class MockArgs:
                def __init__(self, input_file, output_dir):
                    self.input = input_file
                    self.output_dir = output_dir
            
            valid_args = MockArgs(temp_file, temp_dir)
            errors = validate_arguments(valid_args)
            self.assertEqual(len(errors), 0)
            
            # Test invalid input file
            invalid_args = MockArgs('/nonexistent/file.jsonl', temp_dir)
            errors = validate_arguments(invalid_args)
            self.assertEqual(len(errors), 1)
            self.assertIn("does not exist", errors[0])
            
            # Test invalid output directory
            invalid_args = MockArgs(temp_file, '/nonexistent/directory')
            errors = validate_arguments(invalid_args)
            self.assertEqual(len(errors), 1)
            self.assertIn("does not exist", errors[0])
            
        finally:
            os.unlink(temp_file)
            os.rmdir(temp_dir)


if __name__ == '__main__':
    unittest.main()