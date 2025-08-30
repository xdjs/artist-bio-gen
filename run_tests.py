#!/usr/bin/env python3
"""
Test runner script for the artist bio generator project.

This script runs all tests and provides a summary of results.
"""

import os
import sys
import unittest
from pathlib import Path


def discover_and_run_tests():
    """Discover and run all tests in the project."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    test_dir = script_dir / 'tests'
    
    # Check if tests directory exists
    if not test_dir.exists():
        print(f"Tests directory not found: {test_dir}")
        return False
    
    # Discover all test files
    loader = unittest.TestLoader()
    start_dir = str(test_dir)
    
    # Find all test files
    test_files = []
    for file in test_dir.glob('test_*.py'):
        test_files.append(file.stem)
    
    print(f"Found test files: {test_files}")
    
    # Add tests directory to Python path for imports
    if str(test_dir) not in sys.path:
        sys.path.insert(0, str(test_dir))
    
    # Load tests from each file
    suite = unittest.TestSuite()
    for test_file in test_files:
        try:
            module_name = test_file
            module = __import__(module_name)
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
            print(f"Loaded tests from {test_file}")
        except ImportError as e:
            print(f"Failed to import {test_file}: {e}")
            continue
    
    # Run the tests
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    print("\n" + "="*70)
    print("RUNNING TESTS")
    print("="*70)
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback}")
    
    success = result.wasSuccessful()
    print(f"\nOverall result: {'PASSED' if success else 'FAILED'}")
    
    return success


def run_specific_test_file(test_file):
    """Run tests from a specific test file."""
    if not test_file.endswith('.py'):
        test_file += '.py'
    
    # Check in tests directory first
    script_dir = Path(__file__).parent
    test_dir = script_dir / 'tests'
    test_file_path = test_dir / test_file
    
    if not test_file_path.exists():
        print(f"Test file {test_file} not found in {test_dir}")
        return False
    
    # Add tests directory to Python path for imports
    if str(test_dir) not in sys.path:
        sys.path.insert(0, str(test_dir))
    
    # Import and run the specific test file
    module_name = test_file[:-3]  # Remove .py extension
    try:
        module = __import__(module_name)
        
        # Create a test suite from the module
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        
        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return result.wasSuccessful()
    except ImportError as e:
        print(f"Failed to import {test_file}: {e}")
        return False


def main():
    """Main entry point for the test runner."""
    if len(sys.argv) > 1:
        # Run specific test file
        test_file = sys.argv[1]
        print(f"Running tests from {test_file}")
        success = run_specific_test_file(test_file)
    else:
        # Run all tests
        print("Running all tests...")
        success = discover_and_run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()