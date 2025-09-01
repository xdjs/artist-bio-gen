#!/usr/bin/env python3
"""
Tests for transaction-level logging functionality.
"""

import json
import logging
import time
import unittest
from unittest.mock import MagicMock

from artist_bio_gen.utils.logging import log_transaction_success, log_transaction_failure


class TestTransactionLogging(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = MagicMock(spec=logging.Logger)
        
    def test_log_transaction_success(self):
        """Test that transaction success logging creates structured records."""
        test_timestamp = time.time()
        
        log_transaction_success(
            artist_id="test-artist-123",
            artist_name="Test Artist",
            worker_id="W01",
            processing_duration=2.5,
            db_status="updated",
            response_id="response-456", 
            timestamp=test_timestamp,
            logger=self.mock_logger
        )
        
        # Verify that logger.info was called
        self.mock_logger.info.assert_called_once()
        
        # Parse the logged message
        call_args = self.mock_logger.info.call_args[0][0]
        self.assertTrue(call_args.startswith("TRANSACTION: "))
        
        json_data = call_args[13:]  # Remove "TRANSACTION: " prefix
        record = json.loads(json_data)
        
        # Verify record structure and content
        self.assertEqual(record["event_type"], "database_transaction")
        self.assertEqual(record["artist_id"], "test-artist-123")
        self.assertEqual(record["artist_name"], "Test Artist")
        self.assertEqual(record["worker_id"], "W01")
        self.assertEqual(record["processing_duration_seconds"], 2.5)
        self.assertEqual(record["db_status"], "updated")
        self.assertEqual(record["response_id"], "response-456")
        self.assertEqual(record["timestamp"], test_timestamp)
        self.assertEqual(record["success"], True)
        
    def test_log_transaction_success_skipped(self):
        """Test transaction success logging for skipped database operations."""
        log_transaction_success(
            artist_id="skip-artist-789",
            artist_name="Skip Artist",
            worker_id="W02",
            processing_duration=1.0,
            db_status="skipped",
            response_id="response-789",
            logger=self.mock_logger
        )
        
        call_args = self.mock_logger.info.call_args[0][0]
        json_data = call_args[13:]  # Remove "TRANSACTION: " prefix
        record = json.loads(json_data)
        
        # Skipped operations should be marked as successful completion
        self.assertEqual(record["success"], False)  # Only "updated" is marked as success
        self.assertEqual(record["db_status"], "skipped")
        
    def test_log_transaction_failure(self):
        """Test that transaction failure logging creates structured records."""
        test_timestamp = time.time()
        
        log_transaction_failure(
            artist_id="fail-artist-456",
            artist_name="Fail Artist", 
            worker_id="W03",
            processing_duration=1.5,
            error_message="Database connection failed",
            timestamp=test_timestamp,
            logger=self.mock_logger
        )
        
        # Verify that logger.warning was called
        self.mock_logger.warning.assert_called_once()
        
        # Parse the logged message
        call_args = self.mock_logger.warning.call_args[0][0]
        self.assertTrue(call_args.startswith("TRANSACTION_FAILURE: "))
        
        json_data = call_args[21:]  # Remove "TRANSACTION_FAILURE: " prefix
        record = json.loads(json_data)
        
        # Verify record structure and content
        self.assertEqual(record["event_type"], "transaction_failure")
        self.assertEqual(record["artist_id"], "fail-artist-456")
        self.assertEqual(record["artist_name"], "Fail Artist")
        self.assertEqual(record["worker_id"], "W03")
        self.assertEqual(record["processing_duration_seconds"], 1.5)
        self.assertEqual(record["error_message"], "Database connection failed")
        self.assertEqual(record["timestamp"], test_timestamp)
        self.assertEqual(record["success"], False)
        
    def test_default_timestamp_and_logger(self):
        """Test that functions work with default timestamp and logger."""
        # This test verifies the functions don't crash when using defaults
        # We can't easily test the exact timestamp/logger behavior in unit tests
        
        # Should not raise an exception
        log_transaction_success(
            artist_id="default-test",
            artist_name="Default Test",
            worker_id="W99",
            processing_duration=0.1,
            db_status="updated",
            response_id="default-response"
        )
        
        log_transaction_failure(
            artist_id="default-fail",
            artist_name="Default Fail",
            worker_id="W99",
            processing_duration=0.1,
            error_message="Test error"
        )
        
        # If we get here without exceptions, the defaults work
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()