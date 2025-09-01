#!/usr/bin/env python3
"""
Tests for resume functionality including JSONL reading and input filtering.
"""

import json
import tempfile
import unittest
import os
from unittest.mock import patch

from artist_bio_gen.core.output import get_processed_artist_ids
from artist_bio_gen.core.parser import parse_input_file
from artist_bio_gen.models import ArtistData


class TestResumeFunctionality(unittest.TestCase):
    
    def test_get_processed_artist_ids_empty_file(self):
        """Test reading processed IDs from non-existent file."""
        non_existent_path = "/tmp/does_not_exist.jsonl"
        processed_ids = get_processed_artist_ids(non_existent_path)
        self.assertEqual(len(processed_ids), 0)
        self.assertIsInstance(processed_ids, set)
        
    def test_get_processed_artist_ids_successful_entries(self):
        """Test reading processed IDs from JSONL with successful entries."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # Write successful entries
            f.write(json.dumps({
                "artist_id": "11111111-1111-1111-1111-111111111111",
                "artist_name": "Test Artist 1",
                "response_text": "Bio for artist 1"
            }) + "\n")
            f.write(json.dumps({
                "artist_id": "22222222-2222-2222-2222-222222222222", 
                "artist_name": "Test Artist 2",
                "response_text": "Bio for artist 2"
            }) + "\n")
            f.write(json.dumps({
                "artist_id": "33333333-3333-3333-3333-333333333333",
                "artist_name": "Test Artist 3", 
                "response_text": "Bio for artist 3",
                "error": "Some error"  # This should be skipped
            }) + "\n")
            jsonl_path = f.name
            
        try:
            processed_ids = get_processed_artist_ids(jsonl_path)
            
            # Should only include successful entries (no error)
            self.assertEqual(len(processed_ids), 2)
            self.assertIn("11111111-1111-1111-1111-111111111111", processed_ids)
            self.assertIn("22222222-2222-2222-2222-222222222222", processed_ids)
            self.assertNotIn("33333333-3333-3333-3333-333333333333", processed_ids)
            
        finally:
            os.unlink(jsonl_path)
            
    def test_get_processed_artist_ids_invalid_json(self):
        """Test handling of invalid JSON lines."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # Write one valid and one invalid entry
            f.write(json.dumps({
                "artist_id": "11111111-1111-1111-1111-111111111111",
                "artist_name": "Test Artist 1",
                "response_text": "Bio for artist 1"
            }) + "\n")
            f.write("invalid json line\n")  # This should be skipped
            f.write(json.dumps({
                "artist_id": "22222222-2222-2222-2222-222222222222",
                "artist_name": "Test Artist 2", 
                "response_text": "Bio for artist 2"
            }) + "\n")
            jsonl_path = f.name
            
        try:
            with patch('artist_bio_gen.core.output.logger') as mock_logger:
                processed_ids = get_processed_artist_ids(jsonl_path)
                
                # Should include valid entries and warn about invalid
                self.assertEqual(len(processed_ids), 2)
                self.assertIn("11111111-1111-1111-1111-111111111111", processed_ids)
                self.assertIn("22222222-2222-2222-2222-222222222222", processed_ids)
                
                # Should have logged warning about invalid JSON
                mock_logger.warning.assert_called()
                
        finally:
            os.unlink(jsonl_path)
            
    def test_parse_input_file_with_skip_processed(self):
        """Test input parsing with skip processed IDs."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("# Test artists for resume functionality\n")
            f.write("11111111-1111-1111-1111-111111111111,Artist One,Pop singer\n")
            f.write("22222222-2222-2222-2222-222222222222,Artist Two,Rock band\n")
            f.write("33333333-3333-3333-3333-333333333333,Artist Three,Jazz musician\n")
            input_path = f.name
            
        try:
            # Test without skip list - should get all 3 artists
            result_no_skip = parse_input_file(input_path)
            self.assertEqual(len(result_no_skip.artists), 3)
            
            # Test with skip list - should skip first two artists
            skip_ids = {
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222"
            }
            result_with_skip = parse_input_file(input_path, skip_processed_ids=skip_ids)
            
            # Should only get the third artist
            self.assertEqual(len(result_with_skip.artists), 1)
            self.assertEqual(result_with_skip.artists[0].artist_id, "33333333-3333-3333-3333-333333333333")
            self.assertEqual(result_with_skip.artists[0].name, "Artist Three")
            
        finally:
            os.unlink(input_path)
            
    def test_parse_input_file_all_artists_processed(self):
        """Test input parsing when all artists are already processed."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("11111111-1111-1111-1111-111111111111,Artist One,Pop singer\n")
            f.write("22222222-2222-2222-2222-222222222222,Artist Two,Rock band\n")
            input_path = f.name
            
        try:
            # Skip all artists
            skip_ids = {
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222"
            }
            result = parse_input_file(input_path, skip_processed_ids=skip_ids)
            
            # Should get no artists
            self.assertEqual(len(result.artists), 0)
            
        finally:
            os.unlink(input_path)


if __name__ == "__main__":
    unittest.main()