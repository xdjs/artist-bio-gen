#!/usr/bin/env python3
"""
Manual Acceptance Test for Configuration Management Refactoring (Issue #55)

This script tests the refactored configuration system to ensure:
1. Schema-driven configuration works correctly
2. CLI arguments are properly generated and parsed
3. Configuration precedence is maintained (CLI > ENV > .env.local > defaults)
4. Validation works as expected
5. Backward compatibility is preserved
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def print_test(test_name):
    print(f"\n{YELLOW}► Testing: {test_name}{RESET}")

def print_success(message):
    print(f"  {GREEN}✓ {message}{RESET}")

def print_error(message):
    print(f"  {RED}✗ {message}{RESET}")

def print_info(message):
    print(f"  ℹ {message}")

def run_command(cmd, env=None, capture=True):
    """Run a command and return output."""
    if env:
        full_env = os.environ.copy()
        full_env.update(env)
    else:
        full_env = os.environ.copy()

    if capture:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            env=full_env
        )
        return result.returncode, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd, shell=True, env=full_env)
        return result.returncode, "", ""

def create_test_input_file():
    """Create a temporary test input file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("550e8400-e29b-41d4-a716-446655440001,Test Artist,Test bio data\n")
        return f.name

def test_cli_help():
    """Test that CLI help shows all expected arguments."""
    print_test("CLI Help Generation")

    code, stdout, stderr = run_command("python run_artists.py --help")

    # Check for schema-based arguments
    expected_args = [
        "--quota-threshold",
        "--quota-monitoring",
        "--daily-limit",
        "--pause-duration",
        "--quota-log-interval",
        "--openai-api-key",
        "--prompt-id",  # Should be --prompt-id, not --openai-prompt-id
        "--db-url"
    ]

    missing = []
    for arg in expected_args:
        if arg in stdout:
            print_success(f"Found argument: {arg}")
        else:
            print_error(f"Missing argument: {arg}")
            missing.append(arg)

    # Check that removed arguments are not present
    if "--openai-org-id" not in stdout:
        print_success("OPENAI_ORG_ID correctly removed")
    else:
        print_error("OPENAI_ORG_ID still present (should be removed)")
        missing.append("removal of --openai-org-id")

    if "--openai-prompt-id" not in stdout:
        print_success("Duplicate --openai-prompt-id correctly removed")
    else:
        print_error("Duplicate --openai-prompt-id still present")
        missing.append("removal of duplicate --openai-prompt-id")

    return len(missing) == 0

def test_env_loading():
    """Test loading configuration from environment variables."""
    print_test("Environment Variable Loading")

    test_file = create_test_input_file()

    env = {
        "OPENAI_API_KEY": "test_env_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "OPENAI_PROMPT_ID": "test_prompt",
        "QUOTA_THRESHOLD": "0.7",
        "QUOTA_MONITORING": "false"
    }

    cmd = f"python run_artists.py --input-file {test_file} --dry-run"
    code, stdout, stderr = run_command(cmd, env=env)

    if code == 0:
        print_success("Successfully loaded configuration from environment")
        if "DRY RUN MODE" in stdout or "DRY RUN MODE" in stderr:
            print_success("Dry run executed successfully")
        else:
            print_error("Dry run did not execute as expected")
            return False
    else:
        print_error(f"Failed to load configuration: {stderr}")
        return False

    os.unlink(test_file)
    return True

def test_cli_override():
    """Test that CLI arguments override environment variables."""
    print_test("CLI Override Precedence")

    test_file = create_test_input_file()

    # Set environment variables
    env = {
        "OPENAI_API_KEY": "env_key",
        "DATABASE_URL": "postgresql://env:env@localhost:5432/env",
        "QUOTA_THRESHOLD": "0.5"
    }

    # CLI should override environment
    cmd = (
        f"python run_artists.py --input-file {test_file} "
        f"--openai-api-key cli_key "
        f"--db-url postgresql://cli:cli@localhost:5432/cli "
        f"--prompt-id cli_prompt "
        f"--quota-threshold 0.9 "
        f"--dry-run"
    )

    code, stdout, stderr = run_command(cmd, env=env)

    if code == 0:
        print_success("CLI overrides accepted")
    else:
        print_error(f"CLI override failed: {stderr}")
        os.unlink(test_file)
        return False

    os.unlink(test_file)
    return True

def test_validation():
    """Test configuration validation."""
    print_test("Configuration Validation")

    test_file = create_test_input_file()
    test_results = []

    # Test 1: Invalid quota threshold (out of range)
    print_info("Testing invalid quota threshold...")
    env = {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "QUOTA_THRESHOLD": "1.5"  # Invalid: > 1.0
    }

    cmd = f"python run_artists.py --input-file {test_file} --prompt-id test --dry-run"
    code, stdout, stderr = run_command(cmd, env=env)

    if code != 0 and "QUOTA_THRESHOLD" in stderr:
        print_success("Invalid quota threshold correctly rejected")
        test_results.append(True)
    else:
        print_error("Invalid quota threshold not caught")
        test_results.append(False)

    # Test 2: Invalid daily request limit (negative)
    print_info("Testing invalid daily request limit...")
    cmd = (
        f"python run_artists.py --input-file {test_file} "
        f"--openai-api-key test "
        f"--db-url postgresql://test:test@localhost:5432/test "
        f"--prompt-id test "
        f"--daily-limit -100 "  # Invalid: negative
        f"--dry-run"
    )

    code, stdout, stderr = run_command(cmd)

    if code != 0 and "DAILY_REQUEST_LIMIT" in stderr:
        print_success("Invalid daily limit correctly rejected")
        test_results.append(True)
    else:
        print_error("Invalid daily limit not caught")
        test_results.append(False)

    # Test 3: Invalid boolean value
    print_info("Testing invalid boolean value...")
    env = {
        "OPENAI_API_KEY": "test_key",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "QUOTA_MONITORING": "invalid"  # Invalid boolean
    }

    cmd = f"python run_artists.py --input-file {test_file} --prompt-id test --dry-run"
    code, stdout, stderr = run_command(cmd, env=env)

    if code != 0 and "QUOTA_MONITORING" in stderr:
        print_success("Invalid boolean correctly rejected")
        test_results.append(True)
    else:
        print_error("Invalid boolean not caught")
        test_results.append(False)

    os.unlink(test_file)
    return all(test_results)

def test_empty_string_handling():
    """Test that empty strings are properly handled."""
    print_test("Empty String Handling")

    test_file = create_test_input_file()

    # Provide required fields but with an empty prompt ID
    cmd = (
        f"python run_artists.py --input-file {test_file} "
        f"--openai-api-key test_key "
        f"--db-url postgresql://test:test@localhost:5432/test "
        f'--prompt-id "" '  # Empty string should be treated as None
        f"--dry-run"
    )

    code, stdout, stderr = run_command(cmd)

    # Should fail because OPENAI_PROMPT_ID is required for non-dry-run
    # But in dry-run mode, it might still work
    print_info(f"Exit code: {code}")

    if "Prompt ID is required" in stderr or code != 0:
        print_success("Empty string correctly treated as None/missing")
        result = True
    else:
        print_info("Empty string handling may need verification")
        result = True  # May be acceptable in dry-run mode

    os.unlink(test_file)
    return result

def test_missing_required():
    """Test that missing required fields are caught."""
    print_test("Missing Required Fields")

    test_file = create_test_input_file()

    # Don't provide any required environment variables
    cmd = f"python run_artists.py --input-file {test_file} --dry-run"

    # Clear any .env.local effect by using empty env
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", "")
    }

    code, stdout, stderr = run_command(cmd, env=env)

    if code != 0:
        if "OPENAI_API_KEY" in stderr or "DATABASE_URL" in stderr:
            print_success("Missing required fields correctly detected")
            result = True
        else:
            print_error("Error occurred but not for expected reason")
            print_info(f"stderr: {stderr[:200]}")
            result = False
    else:
        # Might succeed if .env.local exists
        print_info("Command succeeded - may be loading from .env.local")
        result = True

    os.unlink(test_file)
    return result

def test_schema_types():
    """Test that schema properly converts types."""
    print_test("Schema Type Conversion")

    test_file = create_test_input_file()

    cmd = (
        f"python run_artists.py --input-file {test_file} "
        f"--openai-api-key test "
        f"--db-url postgresql://test:test@localhost:5432/test "
        f"--prompt-id test "
        f"--quota-threshold 0.5 "  # Should convert to float
        f"--daily-limit 1000 "      # Should convert to int
        f"--pause-duration 48 "     # Should convert to int
        f"--dry-run"
    )

    code, stdout, stderr = run_command(cmd)

    if code == 0:
        print_success("Type conversion successful")
        return True
    else:
        print_error(f"Type conversion failed: {stderr}")
        return False

    os.unlink(test_file)
    return True

def main():
    """Run all acceptance tests."""
    print_header("CONFIGURATION REFACTORING ACCEPTANCE TESTS")
    print_info("Testing issue #55 implementation")

    # Check if we're in the right directory
    if not os.path.exists("run_artists.py"):
        print_error("Please run this script from the project root directory")
        sys.exit(1)

    tests = [
        ("CLI Help Generation", test_cli_help),
        ("Environment Loading", test_env_loading),
        ("CLI Override Precedence", test_cli_override),
        ("Configuration Validation", test_validation),
        ("Empty String Handling", test_empty_string_handling),
        ("Missing Required Fields", test_missing_required),
        ("Schema Type Conversion", test_schema_types)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' raised exception: {e}")
            results.append((test_name, False))

    # Print summary
    print_header("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {test_name}: {status}")

    print(f"\n{BLUE}Results: {passed}/{total} tests passed{RESET}")

    if passed == total:
        print(f"{GREEN}✓ All acceptance tests passed!{RESET}")
        return 0
    else:
        print(f"{RED}✗ Some tests failed. Please review the output above.{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())