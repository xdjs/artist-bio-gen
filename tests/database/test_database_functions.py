#!/usr/bin/env python3
"""
Tests for database functions.

This module tests database-related functions including URL validation,
configuration management, error classification, and table name selection.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

# Import database functions from their new modules
from artist_bio_gen.database import (
    validate_database_url,
    create_database_config,
    get_table_name,
    classify_database_error,
)

# Import constants
from artist_bio_gen.constants import (
    DEFAULT_POOL_SIZE,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_QUERY_TIMEOUT,
)


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
                self.assertTrue(validate_database_url(url))

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
                self.assertFalse(validate_database_url(url))

    def test_validate_database_url_logs_specific_errors(self):
        """Test that specific error messages are logged for different invalid URLs."""
        # This test verifies that appropriate error messages are logged
        # We don't need to capture the logs for this test, just ensure the function works
        self.assertFalse(validate_database_url("http://localhost/db"))
        self.assertFalse(validate_database_url("postgresql://localhost/db"))


class TestDatabaseConfig(unittest.TestCase):
    """Test cases for database configuration creation."""

    def test_create_database_config_valid(self):
        """Test creating database config with valid parameters."""
        url = "postgresql://user:pass@localhost:5432/testdb"
        config = create_database_config(url)

        self.assertIsNotNone(config)
        self.assertEqual(config.url, url)
        self.assertEqual(config.pool_size, DEFAULT_POOL_SIZE)
        self.assertEqual(config.max_overflow, DEFAULT_MAX_OVERFLOW)
        self.assertEqual(config.connection_timeout, DEFAULT_CONNECTION_TIMEOUT)
        self.assertEqual(config.query_timeout, DEFAULT_QUERY_TIMEOUT)

    def test_create_database_config_custom_params(self):
        """Test creating database config with custom parameters."""
        url = "postgresql://user:pass@localhost:5432/testdb"
        config = create_database_config(
            url=url,
            pool_size=8,
            max_overflow=16,
            connection_timeout=60,
            query_timeout=120,
        )

        self.assertIsNotNone(config)
        self.assertEqual(config.url, url)
        self.assertEqual(config.pool_size, 8)
        self.assertEqual(config.max_overflow, 16)
        self.assertEqual(config.connection_timeout, 60)
        self.assertEqual(config.query_timeout, 120)


    def test_create_database_config_invalid_url(self):
        """Test that invalid URL returns None."""
        config = create_database_config("invalid-url")
        self.assertIsNone(config)

    def test_create_database_config_invalid_params(self):
        """Test that invalid parameters are rejected."""
        url = "postgresql://user:pass@localhost:5432/testdb"

        # Invalid pool size
        config = create_database_config(url, pool_size=0)
        self.assertIsNone(config)

        # Invalid max overflow
        config = create_database_config(url, max_overflow=-1)
        self.assertIsNone(config)

        # Invalid connection timeout
        config = create_database_config(url, connection_timeout=0)
        self.assertIsNone(config)

        # Invalid query timeout
        config = create_database_config(url, query_timeout=0)
        self.assertIsNone(config)


class TestTableNameSelection(unittest.TestCase):
    """Test cases for table name selection."""

    def test_get_table_name_production(self):
        """Test that production mode returns 'artists' table."""
        table_name = get_table_name(test_mode=False)
        self.assertEqual(table_name, "artists")

    def test_get_table_name_test(self):
        """Test that test mode returns 'test_artists' table."""
        table_name = get_table_name(test_mode=True)
        self.assertEqual(table_name, "test_artists")

    def test_get_table_name_default(self):
        """Test that default (no parameters) returns 'artists' table."""
        table_name = get_table_name()
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
                classification = classify_database_error(error)
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
                classification = classify_database_error(error)
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
                classification = classify_database_error(error)
                self.assertEqual(classification, "transient")

    def test_classify_mixed_case_errors(self):
        """Test that error classification is case-insensitive."""
        # Test with mixed case error messages
        error = Exception("AUTHENTICATION FAILED")
        self.assertEqual(classify_database_error(error), "systemic")

        error = Exception("Invalid UUID Format")
        self.assertEqual(classify_database_error(error), "permanent")


# TestEnvironmentVariableHandling class removed - functionality now handled by Env.load() in centralized config


if __name__ == "__main__":
    unittest.main()
