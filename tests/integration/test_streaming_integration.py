#!/usr/bin/env python3
"""
Integration tests for streaming JSONL functionality with large datasets.

These tests validate the complete streaming pipeline including input parsing,
processing coordination, and output generation with large datasets and
interruption scenarios.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path to import helpers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers.streaming import create_streaming_mock

from artist_bio_gen.core.parser import parse_input_file
from artist_bio_gen.core.processor import process_artists_concurrent
from artist_bio_gen.core.output import get_processed_artist_ids, initialize_jsonl_output
from artist_bio_gen.models import ApiResponse, ArtistData


class TestStreamingIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_files = []
        
    def tearDown(self):
        """Clean up temporary files."""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                
    def _create_large_input_file(self, num_artists: int) -> str:
        """Create a large input file with the specified number of artists."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("# Large dataset integration test\n")
            f.write("# This file contains test artists for streaming integration testing\n")
            for i in range(num_artists):
                f.write(f"{i:08d}-1111-1111-1111-111111111111,Integration Artist {i},Integration test data {i}\n")
            input_path = f.name
            
        self.temp_files.append(input_path)
        return input_path
        
    def _create_mock_openai_client(self):
        """Create a mock OpenAI client for testing."""
        mock_client = MagicMock()
        return mock_client
        
    def _create_mock_api_response(self, artist: ArtistData, success: bool = True) -> tuple:
        """Create a mock API response for testing."""
        if success:
            response = ApiResponse(
                artist_id=artist.artist_id,
                artist_name=artist.name,
                artist_data=artist.data,
                response_text=f"Mock bio response for {artist.name}",
                response_id=f"mock_resp_{artist.artist_id}",
                created=int(time.time()),
                db_status="updated",
            )
            duration = 0.1
        else:
            response = ApiResponse(
                artist_id=artist.artist_id,
                artist_name=artist.name,
                artist_data=artist.data,
                response_text="",
                response_id="",
                created=0,
                db_status="null",
                error="Mock API error"
            )
            duration = 0.05
            
        return response, duration
        
    def test_large_dataset_streaming_integration(self):
        """Test streaming integration with large dataset (1000+ artists)."""
        num_artists = 1000
        input_path = self._create_large_input_file(num_artists)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            output_path = f.name
        self.temp_files.append(output_path)
        
        # Parse the large input file
        start_time = time.time()
        parse_result = parse_input_file(input_path)
        parse_duration = time.time() - start_time
        
        # Validate parsing performance
        self.assertEqual(len(parse_result.artists), num_artists)
        self.assertLess(parse_duration, 5.0, f"Parsing took too long: {parse_duration:.2f}s")
        
        # Mock the API call to simulate successful processing
        def mock_call_openai_api(client, artist, prompt_id, version, worker_id, db_connection, skip_existing, test_mode, quota_monitor=None, pause_controller=None, output_path=None):
            return self._create_mock_api_response(artist, success=True)
            
        mock_client = self._create_mock_openai_client()
        
        # Test streaming processing with large dataset
        start_time = time.time()
        with patch('artist_bio_gen.core.orchestrator.call_openai_api', side_effect=mock_call_openai_api):
            successful_calls, failed_calls = process_artists_concurrent(
                artists=parse_result.artists,
                client=mock_client,
                prompt_id="integration_test",
                version="v1",
                max_workers=4,
                output_path=output_path,
                db_pool=None,
                test_mode=False,
                resume_mode=False
            )
        processing_duration = time.time() - start_time
        
        # Validate processing results
        self.assertEqual(successful_calls, num_artists)
        self.assertEqual(failed_calls, 0)
        self.assertLess(processing_duration, 30.0, f"Processing took too long: {processing_duration:.2f}s")
        
        # Validate output file integrity
        with open(output_path, 'r') as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), num_artists)
        
        # Validate each line is valid JSON and contains expected data
        processed_ids = set()
        for i, line in enumerate(lines):
            record = json.loads(line.strip())
            
            # Check required fields
            self.assertIn("artist_id", record)
            self.assertIn("artist_name", record)
            self.assertIn("response_text", record)
            
            # Verify no duplicates
            artist_id = record["artist_id"]
            self.assertNotIn(artist_id, processed_ids, f"Duplicate artist_id: {artist_id}")
            processed_ids.add(artist_id)
            
        # Validate that resume functionality can read the output correctly
        resume_processed_ids = get_processed_artist_ids(output_path)
        self.assertEqual(len(resume_processed_ids), num_artists)
        self.assertEqual(resume_processed_ids, processed_ids)
        
    def test_streaming_with_mixed_success_failure(self):
        """Test streaming integration with mixed success and failure responses."""
        num_artists = 100
        failure_rate = 0.2  # 20% failure rate
        input_path = self._create_large_input_file(num_artists)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            output_path = f.name
        self.temp_files.append(output_path)
        
        parse_result = parse_input_file(input_path)
        
        # Mock API call with mixed success/failure
        call_count = 0
        def mock_call_openai_api_mixed(client, artist, prompt_id, version, worker_id, db_connection, skip_existing, test_mode, quota_monitor=None, pause_controller=None, output_path=None):
            nonlocal call_count
            call_count += 1
            # Fail every 5th call (20% failure rate)
            success = (call_count % 5) != 0
            return self._create_mock_api_response(artist, success=success)

        mock_client = self._create_mock_openai_client()

        with patch('artist_bio_gen.core.orchestrator.call_openai_api', side_effect=mock_call_openai_api_mixed):
            successful_calls, failed_calls = process_artists_concurrent(
                artists=parse_result.artists,
                client=mock_client,
                prompt_id="mixed_test",
                version="v1",
                max_workers=2,
                output_path=output_path,
                db_pool=None,
                test_mode=False,
                resume_mode=False
            )
            
        # Validate mixed results
        expected_failures = num_artists // 5  # Every 5th call fails
        expected_successes = num_artists - expected_failures
        
        self.assertEqual(successful_calls, expected_successes)
        self.assertEqual(failed_calls, expected_failures)
        
        # Validate that all responses (success and failure) are written to output
        with open(output_path, 'r') as f:
            lines = f.readlines()
        self.assertEqual(len(lines), num_artists)
        
        # Count successful vs failed entries in output
        success_count = 0
        failure_count = 0
        
        for line in lines:
            record = json.loads(line.strip())
            if record.get("error"):
                failure_count += 1
            else:
                success_count += 1
                
        self.assertEqual(success_count, expected_successes)
        self.assertEqual(failure_count, expected_failures)
        
        # Resume functionality should only count successful entries
        resume_processed_ids = get_processed_artist_ids(output_path)
        self.assertEqual(len(resume_processed_ids), expected_successes)
        
    def test_resume_integration_with_large_dataset(self):
        """Test resume functionality integration with large dataset."""
        num_artists = 500
        resume_point = 200  # Resume after processing 200 artists
        
        input_path = self._create_large_input_file(num_artists)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            output_path = f.name
        self.temp_files.append(output_path)
        
        parse_result = parse_input_file(input_path)
        
        # Mock API call that tracks processing
        processed_count = 0
        def mock_call_openai_api_counting(client, artist, prompt_id, version, worker_id, db_connection, skip_existing, test_mode, quota_monitor=None, pause_controller=None, output_path=None):
            nonlocal processed_count
            processed_count += 1
            return self._create_mock_api_response(artist, success=True)
            
        mock_client = self._create_mock_openai_client()
        
        # First processing run - process only first portion
        first_batch = parse_result.artists[:resume_point]

        with patch('artist_bio_gen.core.orchestrator.call_openai_api', side_effect=mock_call_openai_api_counting):
            successful_calls_1, failed_calls_1 = process_artists_concurrent(
                artists=first_batch,
                client=mock_client,
                prompt_id="resume_test",
                version="v1",
                max_workers=2,
                output_path=output_path,
                db_pool=None,
                test_mode=False,
                resume_mode=False
            )
            
        # Validate first batch results
        self.assertEqual(successful_calls_1, resume_point)
        self.assertEqual(failed_calls_1, 0)
        
        # Check output file has correct number of entries
        with open(output_path, 'r') as f:
            lines_after_first = f.readlines()
        self.assertEqual(len(lines_after_first), resume_point)
        
        # Test resume functionality - parse with skip list
        processed_ids = get_processed_artist_ids(output_path)
        self.assertEqual(len(processed_ids), resume_point)
        
        # Parse input with skip list (simulating resume)
        parse_result_resume = parse_input_file(input_path, skip_processed_ids=processed_ids)
        expected_remaining = num_artists - resume_point
        self.assertEqual(len(parse_result_resume.artists), expected_remaining)
        
        # Reset counter for second run
        processed_count = 0

        # Second processing run - process remaining artists in resume mode
        with patch('artist_bio_gen.core.orchestrator.call_openai_api', side_effect=mock_call_openai_api_counting):
            successful_calls_2, failed_calls_2 = process_artists_concurrent(
                artists=parse_result_resume.artists,
                client=mock_client,
                prompt_id="resume_test",
                version="v1",
                max_workers=2,
                output_path=output_path,
                db_pool=None,
                test_mode=False,
                resume_mode=True  # Resume mode - append to existing file
            )
            
        # Validate second batch results
        self.assertEqual(successful_calls_2, expected_remaining)
        self.assertEqual(failed_calls_2, 0)
        
        # Check final output file has all entries
        with open(output_path, 'r') as f:
            final_lines = f.readlines()
        self.assertEqual(len(final_lines), num_artists)
        
        # Validate all artist IDs are present and unique
        final_processed_ids = get_processed_artist_ids(output_path)
        self.assertEqual(len(final_processed_ids), num_artists)
        
        # Verify no duplicates by checking that we have exactly the expected artist IDs
        expected_ids = {f"{i:08d}-1111-1111-1111-111111111111" for i in range(num_artists)}
        self.assertEqual(final_processed_ids, expected_ids)
        
    def test_concurrent_streaming_consistency(self):
        """Test that concurrent streaming maintains consistency."""
        num_artists = 200
        max_workers = 8  # High concurrency
        
        input_path = self._create_large_input_file(num_artists)
        
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            output_path = f.name
        self.temp_files.append(output_path)
        
        parse_result = parse_input_file(input_path)
        
        def mock_call_openai_api_concurrent(client, artist, prompt_id, version, worker_id, db_connection, skip_existing, test_mode, quota_monitor=None, pause_controller=None, output_path=None):
            # Add small random delay to increase chance of race conditions
            time.sleep(0.001)
            return self._create_mock_api_response(artist, success=True)
        mock_client = self._create_mock_openai_client()

        with patch('artist_bio_gen.core.orchestrator.call_openai_api', side_effect=mock_call_openai_api_concurrent):
            successful_calls, failed_calls = process_artists_concurrent(
                artists=parse_result.artists,
                client=mock_client,
                prompt_id="concurrent_test",
                version="v1",
                max_workers=max_workers,
                output_path=output_path,
                db_pool=None,
                test_mode=False,
                resume_mode=False
            )
            
        # Validate concurrent processing results
        self.assertEqual(successful_calls, num_artists)
        self.assertEqual(failed_calls, 0)
        
        # Validate output file integrity under high concurrency
        with open(output_path, 'r') as f:
            lines = f.readlines()
        self.assertEqual(len(lines), num_artists)
        
        # Validate each line is valid JSON and no corruption occurred
        artist_ids = set()
        for line in lines:
            record = json.loads(line.strip())  # This will fail if JSON is corrupted
            
            artist_id = record["artist_id"]
            self.assertNotIn(artist_id, artist_ids, f"Duplicate artist_id from race condition: {artist_id}")
            artist_ids.add(artist_id)
            
        # Verify we have exactly the expected number of unique entries
        self.assertEqual(len(artist_ids), num_artists)


if __name__ == "__main__":
    unittest.main()