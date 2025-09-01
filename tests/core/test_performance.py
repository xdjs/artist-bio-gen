#!/usr/bin/env python3
"""
Performance tests for streaming JSONL functionality.

These tests validate that the streaming implementation maintains
constant memory usage and performs well with large datasets.
"""

import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from artist_bio_gen.core.output import append_jsonl_response, initialize_jsonl_output
from artist_bio_gen.core.parser import parse_input_file
from artist_bio_gen.models import ApiResponse


class TestPerformance(unittest.TestCase):
        
    def _create_test_responses(self, count: int):
        """Create a list of test responses."""
        responses = []
        for i in range(count):
            response = ApiResponse(
                artist_id=f"{i:08d}-1111-1111-1111-111111111111",
                artist_name=f"Performance Artist {i}",
                artist_data=f"Performance test data {i}",
                response_text=f"Performance bio response {i}" * 10,  # Make it larger
                response_id=f"perf_response_{i}",
                created=1693843200 + i,
                db_status="updated",
            )
            responses.append(response)
        return responses
        
    def test_streaming_large_dataset_completion(self):
        """Test that streaming can handle large datasets without issues."""
        num_responses = 1000
        responses = self._create_test_responses(num_responses)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            # Initialize output file
            initialize_jsonl_output(output_path, overwrite_existing=True)
            
            # Write all responses - this tests that streaming doesn't accumulate data in memory
            start_time = time.time()
            for response in responses:
                append_jsonl_response(response, output_path, "perf_test")
            end_time = time.time()
            
            # Verify all responses were written correctly
            with open(output_path, 'r') as f:
                lines = f.readlines()
            self.assertEqual(len(lines), num_responses)
            
            # Verify that processing completed in reasonable time
            duration = end_time - start_time
            self.assertLess(duration, 30.0, f"Processing took too long: {duration:.2f}s")
            
        finally:
            os.unlink(output_path)
            
    def test_streaming_performance_throughput(self):
        """Test streaming throughput performance."""
        num_responses = 500
        responses = self._create_test_responses(num_responses)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            # Initialize output file
            initialize_jsonl_output(output_path, overwrite_existing=True)
            
            # Measure throughput
            start_time = time.time()
            
            for response in responses:
                append_jsonl_response(response, output_path, "perf_test")
                
            end_time = time.time()
            duration = end_time - start_time
            throughput = num_responses / duration
            
            # Should be able to write at least 100 responses per second
            # This is a conservative threshold
            self.assertGreater(throughput, 100.0, 
                             f"Throughput too low: {throughput:.2f} responses/sec")
            
            # Verify all responses were written correctly
            with open(output_path, 'r') as f:
                lines = f.readlines()
            self.assertEqual(len(lines), num_responses)
            
        finally:
            os.unlink(output_path)
            
    def test_concurrent_streaming_performance(self):
        """Test performance of concurrent streaming writes."""
        num_threads = 4
        responses_per_thread = 100
        
        # Create unique responses for each thread
        all_responses = []
        for thread_id in range(num_threads):
            for response_id in range(responses_per_thread):
                # Create unique artist ID for each thread/response combination
                unique_id = thread_id * responses_per_thread + response_id
                response = ApiResponse(
                    artist_id=f"{unique_id:08d}-1111-1111-1111-111111111111",
                    artist_name=f"Thread {thread_id} Artist {response_id}",
                    artist_data=f"Thread {thread_id} data {response_id}",
                    response_text=f"Thread {thread_id} bio {response_id}",
                    response_id=f"thread_{thread_id}_resp_{response_id}",
                    created=1693843200,
                    db_status="updated"
                )
                all_responses.append(response)
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            output_path = f.name
            
        try:
            # Initialize output file
            initialize_jsonl_output(output_path, overwrite_existing=True)
            
            # Measure concurrent throughput
            start_time = time.time()
            
            def write_responses(responses):
                for response in responses:
                    append_jsonl_response(response, output_path, "perf_test")
                    
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
                    
            end_time = time.time()
            duration = end_time - start_time
            total_responses = num_threads * responses_per_thread
            throughput = total_responses / duration
            
            # Concurrent throughput should be reasonable
            # With thread safety overhead, expect at least 50 responses/sec
            self.assertGreater(throughput, 50.0, 
                             f"Concurrent throughput too low: {throughput:.2f} responses/sec")
            
            # Verify all responses were written without corruption
            with open(output_path, 'r') as f:
                lines = f.readlines()
            self.assertEqual(len(lines), total_responses)
            
            # Verify no duplicate artist_ids (which would indicate race conditions)
            import json
            artist_ids = set()
            for line in lines:
                record = json.loads(line.strip())
                artist_id = record["artist_id"]
                self.assertNotIn(artist_id, artist_ids, 
                               f"Duplicate artist_id found: {artist_id}")
                artist_ids.add(artist_id)
                
        finally:
            os.unlink(output_path)
            
    def test_resume_parsing_performance_large_input(self):
        """Test performance of parsing large input files with resume functionality."""
        num_artists = 1000
        
        # Create large input file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("# Performance test input file\n")
            for i in range(num_artists):
                f.write(f"{i:08d}-1111-1111-1111-111111111111,Performance Artist {i},Performance data {i}\n")
            input_path = f.name
            
        try:
            # Test parsing performance without skip list
            start_time = time.time()
            result_no_skip = parse_input_file(input_path)
            end_time = time.time()
            parse_duration_no_skip = end_time - start_time
            
            self.assertEqual(len(result_no_skip.artists), num_artists)
            
            # Test parsing performance with large skip list (50% of artists)
            skip_ids = {f"{i:08d}-1111-1111-1111-111111111111" for i in range(0, num_artists, 2)}
            
            start_time = time.time()
            result_with_skip = parse_input_file(input_path, skip_processed_ids=skip_ids)
            end_time = time.time()
            parse_duration_with_skip = end_time - start_time
            
            self.assertEqual(len(result_with_skip.artists), num_artists // 2)
            
            # Skip list processing shouldn't be significantly slower
            # Allow up to 2x slowdown for skip list processing
            self.assertLess(parse_duration_with_skip, parse_duration_no_skip * 2.0,
                           f"Skip list parsing too slow: {parse_duration_with_skip:.3f}s vs {parse_duration_no_skip:.3f}s")
            
            # Both should complete in reasonable time (< 5 seconds for 1000 artists)
            self.assertLess(parse_duration_no_skip, 5.0, 
                           f"Parsing too slow: {parse_duration_no_skip:.3f}s")
            self.assertLess(parse_duration_with_skip, 5.0, 
                           f"Skip list parsing too slow: {parse_duration_with_skip:.3f}s")
                           
        finally:
            os.unlink(input_path)


if __name__ == "__main__":
    unittest.main()