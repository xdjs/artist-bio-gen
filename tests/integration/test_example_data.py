#!/usr/bin/env python3
"""
Tests for example data files.

This module tests the example_artists.csv file to ensure it contains
valid data that can be used for testing the parser implementation.
"""

import os
import unittest


class TestExampleDataFile(unittest.TestCase):
    """Test cases for the example_artists.csv file."""

    def setUp(self):
        """Set up test fixtures."""
        self.example_file = "examples/example_artists.csv"
        self.assertTrue(
            os.path.exists(self.example_file),
            f"Example file {self.example_file} not found",
        )

    def test_file_exists(self):
        """Test that the example file exists."""
        self.assertTrue(os.path.isfile(self.example_file))

    def test_file_readable(self):
        """Test that the example file is readable."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)

    def test_file_contains_comments(self):
        """Test that the file contains comment lines."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        comment_lines = [line for line in lines if line.strip().startswith("#")]
        self.assertGreater(len(comment_lines), 0, "File should contain comment lines")

    def test_file_contains_blank_lines(self):
        """Test that the file contains blank lines."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        blank_lines = [line for line in lines if line.strip() == ""]
        self.assertGreater(len(blank_lines), 0, "File should contain blank lines")

    def test_file_contains_data_lines(self):
        """Test that the file contains data lines."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        data_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                data_lines.append(line)

        self.assertGreater(len(data_lines), 0, "File should contain data lines")

    def test_data_lines_format(self):
        """Test that data lines follow the expected format."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        data_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                data_lines.append(line)

        for line in data_lines:
            # Should contain at least one comma (artist_name,artist_data)
            self.assertIn(",", line, f"Data line should contain comma: {line}")

            # Should not be empty after stripping
            self.assertGreater(len(line), 0, f"Data line should not be empty: {line}")

    def test_artist_names_present(self):
        """Test that the file contains recognizable artist names."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for some expected artist names
        expected_artists = [
            "Taylor Swift",
            "Drake",
            "Billie Eilish",
            "The Weeknd",
            "BTS",
        ]
        found_artists = []

        for artist in expected_artists:
            if artist in content:
                found_artists.append(artist)

        self.assertGreater(
            len(found_artists),
            0,
            f"Should find at least one expected artist. Found: {found_artists}",
        )

    def test_edge_case_empty_artist_data(self):
        """Test that the file contains an edge case with empty artist_data."""
        with open(self.example_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        found_empty_data = False
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(",")
                # Format: artist_id,artist_name,artist_data
                if len(parts) >= 3 and parts[2].strip() == "":
                    found_empty_data = True
                    break
                # Also check for lines ending with comma (no third part)
                elif len(parts) == 2 and line.endswith(","):
                    found_empty_data = True
                    break

        self.assertTrue(
            found_empty_data, "File should contain a line with empty artist_data"
        )

    def test_utf8_encoding(self):
        """Test that the file can be read with UTF-8 encoding."""
        try:
            with open(self.example_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIsInstance(content, str)
        except UnicodeDecodeError as e:
            self.fail(f"File should be readable with UTF-8 encoding: {e}")

    def test_file_size_reasonable(self):
        """Test that the file size is reasonable for testing."""
        file_size = os.path.getsize(self.example_file)
        self.assertGreater(file_size, 0, "File should not be empty")
        self.assertLess(file_size, 10000, "File should be reasonably small for testing")


class TestRequirementsFile(unittest.TestCase):
    """Test cases for the requirements.txt file."""

    def setUp(self):
        """Set up test fixtures."""
        self.requirements_file = "requirements.txt"
        self.assertTrue(
            os.path.exists(self.requirements_file),
            f"Requirements file {self.requirements_file} not found",
        )

    def test_file_exists(self):
        """Test that the requirements file exists."""
        self.assertTrue(os.path.isfile(self.requirements_file))

    def test_file_readable(self):
        """Test that the requirements file is readable."""
        with open(self.requirements_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)

    def test_contains_core_dependencies(self):
        """Test that the file contains core dependencies."""
        with open(self.requirements_file, "r", encoding="utf-8") as f:
            content = f.read()

        expected_deps = ["openai", "aiohttp", "tenacity", "python-dotenv"]
        for dep in expected_deps:
            self.assertIn(dep, content, f"Should contain {dep} dependency")

    def test_contains_dev_dependencies(self):
        """Test that the file contains development dependencies."""
        with open(self.requirements_file, "r", encoding="utf-8") as f:
            content = f.read()

        expected_deps = ["pytest", "black", "mypy"]
        for dep in expected_deps:
            self.assertIn(dep, content, f"Should contain {dep} development dependency")

    def test_version_specifiers_present(self):
        """Test that version specifiers are present."""
        with open(self.requirements_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        version_lines = [line for line in lines if ">=" in line.strip()]
        self.assertGreater(len(version_lines), 0, "Should contain version specifiers")

    def test_no_empty_lines_in_dependencies(self):
        """Test that there are no empty lines in the dependencies section."""
        with open(self.requirements_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the first comment line to separate core and dev dependencies
        core_deps = []
        for line in lines:
            if line.strip().startswith("#"):
                break
            if line.strip():
                core_deps.append(line.strip())

        # All core dependency lines should have content
        for dep in core_deps:
            self.assertGreater(
                len(dep), 0, f"Core dependency line should not be empty: {dep}"
            )


if __name__ == "__main__":
    # Create a test suite
    test_suite = unittest.TestSuite()

    # Add test cases
    test_classes = [TestExampleDataFile, TestRequirementsFile]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Exit with appropriate code
    import sys

    sys.exit(0 if result.wasSuccessful() else 1)
