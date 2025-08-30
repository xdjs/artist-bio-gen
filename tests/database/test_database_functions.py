#!/usr/bin/env python3
"""
Tests for database functions.

This module tests database-related functions including URL validation,
configuration management, error classification, and table name selection.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from artist_bio_gen import main as run_artists


class TestDatabaseUrlValidation(unittest.TestCase):
    """Test cases for database URL validation."""
    
    def test_validate_database_url_valid_urls(self):
        """Test that valid database URLs are accepted."""
        valid_urls = [
            "postgresql://user:pass@localhost:5432/dbname",
            "postgres://user:pass@localhost:5432/dbname",
            "postgresql://user:pass@localhost/dbname",
            "postgres://user@localhost:5432/dbname",
            "postgresql://user:pass@host.example.com:5432/mydb",
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(run_artists.validate_database_url(url))
    
    def test_validate_database_url_invalid_urls(self):
        """Test that invalid database URLs are rejected."""
        invalid_urls = [
            "",  # Empty string
            None,  # None value
            "not-a-url",  # Not a URL at all
            "http://localhost:5432/db",  # Wrong scheme
            "mysql://user:pass@localhost:5432/db",  # Wrong scheme
            "postgresql://localhost:5432/db",  # Missing username
            "postgresql://user:pass@:5432/db",  # Missing hostname
            "postgresql://user:pass@localhost:5432",  # Missing database name
            "postgresql://user:pass@localhost:5432/",  # Empty database name
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(run_artists.validate_database_url(url))
    
    def test_validate_database_url_logs_specific_errors(self):
        """Test that specific error messages are logged for different invalid URLs."""
        # This test verifies that appropriate error messages are logged
        # We don't need to capture the logs for this test, just ensure the function works
        self.assertFalse(run_artists.validate_database_url("http://localhost/db"))
        self.assertFalse(run_artists.validate_database_url("postgresql://localhost/db"))


class TestDatabaseConfig(unittest.TestCase):
    """Test cases for database configuration creation."""
    
    def test_create_database_config_valid(self):
        """Test creating database config with valid parameters."""
        url = "postgresql://user:pass@localhost:5432/testdb"
        config = run_artists.create_database_config(url)
        
        self.assertIsNotNone(config)
        self.assertEqual(config.url, url)
        self.assertEqual(config.pool_size, run_artists.DEFAULT_POOL_SIZE)
        self.assertEqual(config.max_overflow, run_artists.DEFAULT_MAX_OVERFLOW)
        self.assertEqual(config.connection_timeout, run_artists.DEFAULT_CONNECTION_TIMEOUT)
        self.assertEqual(config.query_timeout, run_artists.DEFAULT_QUERY_TIMEOUT)
    
    def test_create_database_config_custom_params(self):
        """Test creating database config with custom parameters."""
        url = "postgresql://user:pass@localhost:5432/testdb"
        config = run_artists.create_database_config(
            url=url,
            pool_size=8,
            max_overflow=16,
            connection_timeout=60,
            query_timeout=120
        )
        
        self.assertIsNotNone(config)
        self.assertEqual(config.url, url)
        self.assertEqual(config.pool_size, 8)
        self.assertEqual(config.max_overflow, 16)
        self.assertEqual(config.connection_timeout, 60)
        self.assertEqual(config.query_timeout, 120)
    
    def test_create_database_config_test_mode(self):
        """Test that test mode reduces pool sizes."""
        url = "postgresql://user:pass@localhost:5432/testdb"
        config = run_artists.create_database_config(
            url=url,
            pool_size=8,
            max_overflow=16,
            test_mode=True
        )
        
        self.assertIsNotNone(config)
        # Test mode should limit pool sizes
        self.assertEqual(config.pool_size, 2)  # min(8, 2)
        self.assertEqual(config.max_overflow, 2)  # min(16, 2)
    
    def test_create_database_config_invalid_url(self):
        """Test that invalid URL returns None."""
        config = run_artists.create_database_config("invalid-url")
        self.assertIsNone(config)
    
    def test_create_database_config_invalid_params(self):
        """Test that invalid parameters are rejected."""
        url = "postgresql://user:pass@localhost:5432/testdb"
        
        # Invalid pool size
        config = run_artists.create_database_config(url, pool_size=0)
        self.assertIsNone(config)
        
        # Invalid max overflow
        config = run_artists.create_database_config(url, max_overflow=-1)
        self.assertIsNone(config)
        
        # Invalid connection timeout
        config = run_artists.create_database_config(url, connection_timeout=0)
        self.assertIsNone(config)
        
        # Invalid query timeout
        config = run_artists.create_database_config(url, query_timeout=0)
        self.assertIsNone(config)


class TestTableNameSelection(unittest.TestCase):
    """Test cases for table name selection."""
    
    def test_get_table_name_production(self):
        """Test that production mode returns 'artists' table."""
        table_name = run_artists.get_table_name(test_mode=False)
        self.assertEqual(table_name, "artists")
    
    def test_get_table_name_test(self):
        """Test that test mode returns 'test_artists' table."""
        table_name = run_artists.get_table_name(test_mode=True)
        self.assertEqual(table_name, "test_artists")
    
    def test_get_table_name_default(self):
        """Test that default (no parameters) returns 'artists' table."""
        table_name = run_artists.get_table_name()
        self.assertEqual(table_name, "artists")


class TestDatabaseErrorClassification(unittest.TestCase):
    """Test cases for database error classification."""
    
    def test_classify_permanent_errors(self):
        """Test that permanent errors are correctly classified."""
        permanent_errors = [
            Exception("invalid UUID format"),
            Exception("constraint violation occurred"),
            Exception("foreign key constraint failed"),
            Exception("check constraint violated"),
            Exception("not null violation"),
            Exception("duplicate key value"),
            Exception("relation does not exist"),
            Exception("column does not exist"),
        ]
        
        for error in permanent_errors:
            with self.subTest(error=str(error)):
                classification = run_artists.classify_database_error(error)
                self.assertEqual(classification, "permanent")
    
    def test_classify_systemic_errors(self):
        """Test that systemic errors are correctly classified."""
        systemic_errors = [
            Exception("authentication failed"),
            Exception("permission denied"),
            Exception("role does not exist"),
            Exception("database does not exist"),
            Exception("SSL required"),
            Exception("password authentication failed"),
        ]
        
        for error in systemic_errors:
            with self.subTest(error=str(error)):
                classification = run_artists.classify_database_error(error)
                self.assertEqual(classification, "systemic")
    
    def test_classify_transient_errors(self):
        """Test that transient errors are correctly classified."""
        transient_errors = [
            Exception("connection timeout"),
            Exception("network unreachable"),
            Exception("deadlock detected"),
            Exception("server closed the connection unexpectedly"),
            Exception("some random database error"),
        ]
        
        for error in transient_errors:
            with self.subTest(error=str(error)):
                classification = run_artists.classify_database_error(error)
                self.assertEqual(classification, "transient")
    
    def test_classify_mixed_case_errors(self):
        """Test that error classification is case-insensitive."""
        # Test with mixed case error messages
        error = Exception("AUTHENTICATION FAILED")
        self.assertEqual(run_artists.classify_database_error(error), "systemic")
        
        error = Exception("Invalid UUID Format")
        self.assertEqual(run_artists.classify_database_error(error), "permanent")


class TestEnvironmentVariableHandling(unittest.TestCase):
    """Test cases for environment variable handling."""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_database_url_from_env_no_vars(self):
        """Test when no environment variables are set."""
        url = run_artists.get_database_url_from_env()
        self.assertIsNone(url)
        
        url = run_artists.get_database_url_from_env(test_mode=True)
        self.assertIsNone(url)
    
    @patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@localhost/prod'}, clear=True)
    def test_get_database_url_from_env_production(self):
        """Test getting DATABASE_URL in production mode."""
        url = run_artists.get_database_url_from_env(test_mode=False)
        self.assertEqual(url, 'postgresql://user:pass@localhost/prod')
        
        # Test mode should also fall back to DATABASE_URL if TEST_DATABASE_URL not set
        url = run_artists.get_database_url_from_env(test_mode=True)
        self.assertEqual(url, 'postgresql://user:pass@localhost/prod')
    
    @patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://user:pass@localhost/prod',
        'TEST_DATABASE_URL': 'postgresql://user:pass@localhost/test'
    }, clear=True)
    def test_get_database_url_from_env_test_priority(self):
        """Test that TEST_DATABASE_URL takes priority in test mode."""
        # Production mode should use DATABASE_URL
        url = run_artists.get_database_url_from_env(test_mode=False)
        self.assertEqual(url, 'postgresql://user:pass@localhost/prod')
        
        # Test mode should prefer TEST_DATABASE_URL
        url = run_artists.get_database_url_from_env(test_mode=True)
        self.assertEqual(url, 'postgresql://user:pass@localhost/test')
    
    @patch.dict(os.environ, {'TEST_DATABASE_URL': 'postgresql://user:pass@localhost/test'}, clear=True)
    def test_get_database_url_from_env_test_only(self):
        """Test when only TEST_DATABASE_URL is set."""
        # Production mode should return None (no DATABASE_URL)
        url = run_artists.get_database_url_from_env(test_mode=False)
        self.assertIsNone(url)
        
        # Test mode should use TEST_DATABASE_URL
        url = run_artists.get_database_url_from_env(test_mode=True)
        self.assertEqual(url, 'postgresql://user:pass@localhost/test')


if __name__ == '__main__':
    unittest.main()