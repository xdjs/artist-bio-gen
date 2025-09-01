#!/usr/bin/env python3
"""
Tests for streaming JSONL output functionality.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from artist_bio_gen.core.output import (
    append_jsonl_response, 
    initialize_jsonl_output,
    get_processed_artist_ids,
    _create_jsonl_record
)
from artist_bio_gen.models import ApiResponse


class TestStreamingOutput(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_response = ApiResponse(
            artist_id="11111111-1111-1111-1111-111111111111",
            artist_name="Test Artist",
            artist_data="Test data",
            response_text="Test bio response",
            response_id="response_123",
            created=1693843200,
            db_status="updated",
        )
        
    def test_initialize_jsonl_output_new_file(self):
        """Test initializing a new JSONL output file."""
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            output_path = f.name
        
        # Delete the file so we can test creation
        os.unlink(output_path)
        
        try:
            initialize_jsonl_output(output_path, overwrite_existing=True)
            
            # File should exist and be empty
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, 'r') as f:
                content = f.read()
                self.assertEqual(content, "")
                
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
                
    def test_initialize_jsonl_output_overwrite_existing(self):
        """Test overwriting an existing JSONL file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("existing content\n")
            output_path = f.name
            
        try:
            initialize_jsonl_output(output_path, overwrite_existing=True)
            
            # File should be empty after overwrite
            with open(output_path, 'r') as f:
                content = f.read()
                self.assertEqual(content, "")
                
        finally:
            os.unlink(output_path)
            
    def test_initialize_jsonl_output_preserve_existing(self):
        """Test preserving an existing JSONL file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("existing content\n")
            output_path = f.name
            
        try:
            initialize_jsonl_output(output_path, overwrite_existing=False)
            
            # File should preserve existing content
            with open(output_path, 'r') as f:
                content = f.read()
                self.assertEqual(content, "existing content\n")
                
        finally:
            os.unlink(output_path)
            
    def test_append_jsonl_response_single(self):
        """Test appending a single response to JSONL file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            append_jsonl_response(
                self.test_response, 
                output_path, 
                "prompt_123", 
                "v1"
            )
            
            # Verify the content
            with open(output_path, 'r') as f:
                line = f.readline().strip()
                record = json.loads(line)
                
                self.assertEqual(record["artist_id"], self.test_response.artist_id)
                self.assertEqual(record["artist_name"], self.test_response.artist_name)
                self.assertEqual(record["response_text"], self.test_response.response_text)
                self.assertEqual(record["request"]["prompt_id"], "prompt_123")
                self.assertEqual(record["request"]["version"], "v1")
                
        finally:
            os.unlink(output_path)
            
    def test_append_jsonl_response_multiple(self):
        """Test appending multiple responses to JSONL file."""
        responses = [
            ApiResponse(
                artist_id=f"1111111{i}-1111-1111-1111-111111111111",
                artist_name=f"Test Artist {i}",
                artist_data=f"Test data {i}",
                response_text=f"Test bio {i}",
                response_id=f"response_{i}",
                created=1693843200 + i,
                db_status="updated"
            )
            for i in range(3)
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            # Append all responses
            for response in responses:
                append_jsonl_response(response, output_path, "prompt_123")
                
            # Verify all responses were written
            with open(output_path, 'r') as f:
                lines = f.readlines()
                
            self.assertEqual(len(lines), 3)
            
            for i, line in enumerate(lines):
                record = json.loads(line.strip())
                self.assertEqual(record["artist_name"], f"Test Artist {i}")
                self.assertEqual(record["response_text"], f"Test bio {i}")
                
        finally:
            os.unlink(output_path)
            
    def test_concurrent_append_safety(self):
        """Test thread safety of concurrent JSONL appends."""
        num_threads = 5
        responses_per_thread = 10
        
        # Create responses for each thread
        all_responses = []
        for thread_id in range(num_threads):
            for response_id in range(responses_per_thread):
                response = ApiResponse(
                    artist_id=f"{thread_id:04d}{response_id:04d}-1111-1111-1111-111111111111",
                    artist_name=f"Artist T{thread_id}R{response_id}",
                    artist_data=f"Data T{thread_id}R{response_id}",
                    response_text=f"Bio T{thread_id}R{response_id}",
                    response_id=f"resp_T{thread_id}R{response_id}",
                    created=1693843200,
                    db_status="updated"
                )
                all_responses.append(response)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            # Write all responses concurrently
            def write_responses(responses):
                for response in responses:
                    append_jsonl_response(response, output_path, "prompt_123")
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
                    
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Split responses among threads
                futures = []
                for i in range(num_threads):
                    start_idx = i * responses_per_thread
                    end_idx = start_idx + responses_per_thread
                    thread_responses = all_responses[start_idx:end_idx]
                    futures.append(executor.submit(write_responses, thread_responses))
                    
                # Wait for all threads to complete
                for future in futures:
                    future.result()
                    
            # Verify all responses were written correctly
            with open(output_path, 'r') as f:
                lines = f.readlines()
                
            self.assertEqual(len(lines), num_threads * responses_per_thread)
            
            # Verify each line is valid JSON
            written_artist_ids = set()
            for line in lines:
                record = json.loads(line.strip())
                self.assertIn("artist_id", record)
                self.assertIn("artist_name", record)
                written_artist_ids.add(record["artist_id"])
                
            # Verify no duplicates or missing entries
            expected_ids = {r.artist_id for r in all_responses}
            self.assertEqual(written_artist_ids, expected_ids)
            
        finally:
            os.unlink(output_path)
            
    def test_append_with_error_response(self):
        """Test appending responses that contain errors."""
        error_response = ApiResponse(
            artist_id="22222222-2222-2222-2222-222222222222",
            artist_name="Failed Artist",
            artist_data="Test data",
            response_text="",
            response_id="",
            created=0,
            error="API call failed"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            append_jsonl_response(error_response, output_path, "prompt_123")
            
            with open(output_path, 'r') as f:
                line = f.readline().strip()
                record = json.loads(line)
                
                self.assertEqual(record["artist_id"], error_response.artist_id)
                self.assertEqual(record["error"], "API call failed")
                self.assertEqual(record["response_text"], "")
                
        finally:
            os.unlink(output_path)
            
    def test_append_creates_directory(self):
        """Test that append creates parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a nested path that doesn't exist
            output_path = os.path.join(temp_dir, "subdir", "output.jsonl")
            
            # Directory should not exist yet
            self.assertFalse(os.path.exists(os.path.dirname(output_path)))
            
            append_jsonl_response(self.test_response, output_path, "prompt_123")
            
            # Directory and file should now exist
            self.assertTrue(os.path.exists(os.path.dirname(output_path)))
            self.assertTrue(os.path.exists(output_path))
            
    def test_create_jsonl_record_structure(self):
        """Test the structure of created JSONL records."""
        record = _create_jsonl_record(self.test_response, "prompt_123", "v1")
        
        # Verify all required fields are present
        required_fields = [
            "artist_id", "artist_name", "artist_data", "response_text",
            "response_id", "created", "db_status", "error", "request"
        ]
        for field in required_fields:
            self.assertIn(field, record)
        
        # Verify nested request structure
        self.assertIn("prompt_id", record["request"])
        self.assertIn("version", record["request"])
        self.assertIn("variables", record["request"])
            
        # Verify field values
        self.assertEqual(record["artist_id"], self.test_response.artist_id)
        self.assertEqual(record["artist_name"], self.test_response.artist_name)
        self.assertEqual(record["request"]["prompt_id"], "prompt_123")
        self.assertEqual(record["request"]["version"], "v1")
        
    def test_create_jsonl_record_no_version(self):
        """Test creating JSONL record without version."""
        record = _create_jsonl_record(self.test_response, "prompt_123", None)
        
        self.assertNotIn("version", record["request"])
        self.assertEqual(record["request"]["prompt_id"], "prompt_123")
        
    def test_streaming_integration_with_resume(self):
        """Test streaming output integration with resume functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            # Write some responses
            responses = [
                ApiResponse(
                    artist_id=f"3333333{i}-3333-3333-3333-333333333333",
                    artist_name=f"Resume Artist {i}",
                    artist_data="Test data",
                    response_text=f"Bio {i}",
                    response_id=f"resp_{i}",
                    created=1693843200,
                    db_status="updated"
                )
                for i in range(3)
            ]
            
            # Write first two responses
            for response in responses[:2]:
                append_jsonl_response(response, output_path, "prompt_123")
                
            # Use resume functionality to read processed IDs
            processed_ids = get_processed_artist_ids(output_path)
            
            # Should find the first two
            self.assertEqual(len(processed_ids), 2)
            self.assertIn(responses[0].artist_id, processed_ids)
            self.assertIn(responses[1].artist_id, processed_ids)
            self.assertNotIn(responses[2].artist_id, processed_ids)
            
            # Append the third response (simulating resume)
            append_jsonl_response(responses[2], output_path, "prompt_123")
            
            # Verify all three are now present
            processed_ids = get_processed_artist_ids(output_path)
            self.assertEqual(len(processed_ids), 3)
            for response in responses:
                self.assertIn(response.artist_id, processed_ids)
                
        finally:
            os.unlink(output_path)


if __name__ == "__main__":
    unittest.main()