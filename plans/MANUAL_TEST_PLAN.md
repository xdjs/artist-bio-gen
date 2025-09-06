# Manual Acceptance Test Plan - Batch Update Tools

## Purpose

This test plan provides AI-executable acceptance tests for the batch update tools. Each test includes precise commands, expected outputs, and programmatically verifiable success criteria.

## Prerequisites

### Environment Setup
```bash
# 1. Verify working directory
pwd
# Expected: /path/to/artist-bio-gen

# 2. Verify Python availability
python3 --version
# Expected: Python 3.7+ output

# 3. Verify PostgreSQL client
which psql
# Expected: /path/to/psql

# 4. Load environment variables
set -a; source .env.local; set +a

# 5. Verify DATABASE_URL is set
echo ${DATABASE_URL:0:20}...
# Expected: postgresql://...
```

### Clean State Setup
```bash
# Remove any existing batch files
rm -f batch_update_*.sql batch_update_*.csv batch_update_skipped_*.jsonl
rm -rf processed/

# Verify clean state
ls batch_update_* 2>/dev/null || echo "CLEAN_STATE_VERIFIED"
# Expected: CLEAN_STATE_VERIFIED
```

## Test Suite

### Test 1: Basic Workflow - Valid Data Only

**Objective**: Verify end-to-end workflow with 100% valid data

**Setup**:
```bash
cat > test1_input.jsonl << 'EOF'
{"artist_id": "550e8400-e29b-41d4-a716-446655440001", "response_text": "The Beatles were an English rock band formed in Liverpool in 1960.", "error": null}
{"artist_id": "550e8400-e29b-41d4-a716-446655440002", "response_text": "Bob Dylan is an American singer-songwriter and Nobel Prize winner.", "error": null}
EOF
```

**Execution**:
```bash
# Generate batch files
python3 tools/generate_batch_update.py --input test1_input.jsonl --test-mode
```

**Success Criteria**:
- Exit code: 0
- Output contains: "Processing success rate: 100.0%"
- Output contains: "Files created:"
- Files exist: `batch_update_*.csv` and `batch_update_*.sql`
- No skipped file created

**Validation**:
```bash
# Verify CSV content
head -3 batch_update_*.csv | grep -E "^\"id\",\"bio\"$|^\"550e8400"
# Expected: 3 lines (header + 2 data rows)

# Verify SQL targets test_artists
grep "UPDATE test_artists" batch_update_*.sql
# Expected: UPDATE test_artists SET bio = batch.bio...

# Execute SQL
./tools/run_batch_update.sh
```

**SQL Execution Success Criteria**:
- Exit code: 0
- Output contains: "Database connection successful ✓"
- Output contains: "✓ Completed successfully"
- Output contains: "Files processed successfully: 1"
- Files moved to `processed/` directory

**Cleanup**:
```bash
rm -f test1_input.jsonl batch_update_*.* && rm -rf processed/
```

---

### Test 2: Mixed Data Validation

**Objective**: Verify handling of valid, invalid, and duplicate entries

**Setup**:
```bash
cat > test2_input.jsonl << 'EOF'
{"artist_id": "550e8400-e29b-41d4-a716-446655440001", "response_text": "Valid artist bio", "error": null}
{"artist_id": "invalid-uuid", "response_text": "Invalid UUID format", "error": null}
{"artist_id": "550e8400-e29b-41d4-a716-446655440002", "response_text": "Bio with error", "error": "API timeout"}
{"artist_id": "550e8400-e29b-41d4-a716-446655440003", "response_text": "", "error": null}
{"artist_id": "550e8400-e29b-41d4-a716-446655440001", "response_text": "Duplicate ID", "error": null}
EOF
```

**Execution**:
```bash
python3 tools/generate_batch_update.py --input test2_input.jsonl --test-mode
```

**Success Criteria**:
- Exit code: 0
- Output contains: "Valid entries: 1"
- Output contains: "Invalid entries: 2" 
- Output contains: "Duplicate entries: 2"
- Output contains: "Processing success rate: 20.0%"
- Files exist: `batch_update_*.csv`, `batch_update_*.sql`, `batch_update_skipped_*.jsonl`

**Validation**:
```bash
# Verify only 1 valid entry in CSV
wc -l batch_update_*.csv | awk '{print $1-1}'
# Expected: 1

# Verify 4 skipped entries
wc -l batch_update_skipped_*.jsonl | awk '{print $1}'
# Expected: 4

# Execute and verify
./tools/run_batch_update.sh
# Should succeed with 1 file processed
```

**Cleanup**:
```bash
rm -f test2_input.jsonl batch_update_*.* && rm -rf processed/
```

---

### Test 3: Empty Input Handling

**Objective**: Verify graceful handling of empty input

**Setup**:
```bash
touch test3_empty.jsonl
```

**Execution**:
```bash
python3 tools/generate_batch_update.py --input test3_empty.jsonl --test-mode
```

**Success Criteria**:
- Exit code: 0
- Output contains: "Total lines processed: 0"
- Output contains: "Valid entries: 0"
- Output contains: "Processing success rate: 0.0% (0/0)"
- No output files created

**Validation**:
```bash
# Verify no files created
ls batch_update_* 2>/dev/null && echo "UNEXPECTED_FILES" || echo "NO_FILES_CONFIRMED"
# Expected: NO_FILES_CONFIRMED

# Verify shell script handles no files
./tools/run_batch_update.sh
# Expected: "No SQL batch files found matching pattern"
```

**Cleanup**:
```bash
rm -f test3_empty.jsonl
```

---

### Test 4: Special Characters and Unicode

**Objective**: Verify proper handling of special characters in bio content

**Setup**:
```bash
cat > test4_unicode.jsonl << 'EOF'
{"artist_id": "550e8400-e29b-41d4-a716-446655440001", "response_text": "Artist with \"quotes\" and, commas in bio", "error": null}
{"artist_id": "550e8400-e29b-41d4-a716-446655440002", "response_text": "Unicode artist: café 音楽 🎵 émojis", "error": null}
{"artist_id": "550e8400-e29b-41d4-a716-446655440003", "response_text": "Newlines\nand\ttabs\nin\rcontent", "error": null}
EOF
```

**Execution**:
```bash
python3 tools/generate_batch_update.py --input test4_unicode.jsonl --test-mode
```

**Success Criteria**:
- Exit code: 0
- Output contains: "Processing success rate: 100.0%"
- CSV file properly escapes special characters

**Validation**:
```bash
# Verify CSV escaping
grep '""quotes""' batch_update_*.csv
# Expected: Match found (quotes properly doubled)

# Verify Unicode preservation
grep 'café' batch_update_*.csv
# Expected: Match found (Unicode preserved)

# Execute SQL
./tools/run_batch_update.sh
```

**Cleanup**:
```bash
rm -f test4_unicode.jsonl batch_update_*.* && rm -rf processed/
```

---

### Test 5: Production vs Test Mode

**Objective**: Verify correct table targeting in different modes

**Setup**:
```bash
cat > test5_mode.jsonl << 'EOF'
{"artist_id": "550e8400-e29b-41d4-a716-446655440001", "response_text": "Mode test artist", "error": null}
EOF
```

**Test 5a: Production Mode**:
```bash
python3 tools/generate_batch_update.py --input test5_mode.jsonl
# No --test-mode flag
```

**Success Criteria**:
- Output contains: "Target table: artists"
- SQL file contains: "UPDATE artists SET"

**Validation**:
```bash
grep "UPDATE artists" batch_update_*.sql
# Expected: Match found

# Clean up
rm -f batch_update_*.*
```

**Test 5b: Test Mode**:
```bash
python3 tools/generate_batch_update.py --input test5_mode.jsonl --test-mode
```

**Success Criteria**:
- Output contains: "Target table: test_artists"  
- SQL file contains: "UPDATE test_artists SET"

**Validation**:
```bash
grep "UPDATE test_artists" batch_update_*.sql
# Expected: Match found
```

**Cleanup**:
```bash
rm -f test5_mode.jsonl batch_update_*.* && rm -rf processed/
```

---

### Test 6: Error Conditions

**Objective**: Verify proper error handling for various failure scenarios

**Test 6a: Missing Input File**:
```bash
python3 tools/generate_batch_update.py --input nonexistent.jsonl
```

**Success Criteria**:
- Exit code: 1
- Output contains error message about file not found

**Test 6b: Missing DATABASE_URL**:
```bash
unset DATABASE_URL
./tools/run_batch_update.sh
```

**Success Criteria**:
- Exit code: 1  
- Output contains: "DATABASE_URL environment variable is required"

**Test 6c: Invalid DATABASE_URL**:
```bash
DATABASE_URL="postgresql://invalid:invalid@invalid:5432/invalid" ./tools/run_batch_update.sh
```

**Success Criteria**:
- Exit code: 1
- Output contains: "Failed to connect to database"

**Restoration**:
```bash
set -a; source .env.local; set +a
```

---

### Test 7: File Management Verification

**Objective**: Verify proper file movement and directory creation

**Setup**:
```bash
cat > test7_files.jsonl << 'EOF'
{"artist_id": "550e8400-e29b-41d4-a716-446655440001", "response_text": "File management test", "error": null}
EOF

python3 tools/generate_batch_update.py --input test7_files.jsonl --test-mode
```

**Execution**:
```bash
# Record initial files
ls -1 batch_update_*.* > initial_files.txt

# Execute
./tools/run_batch_update.sh

# Verify processed directory created
ls -ld processed/
# Expected: Directory exists

# Verify files moved
ls -1 processed/batch_update_*.* > moved_files.txt
```

**Success Criteria**:
- `processed/` directory exists
- CSV and SQL files moved to `processed/`
- No `batch_update_*.csv` or `batch_update_*.sql` in working directory
- Any skipped files remain in working directory

**Validation**:
```bash
# Verify working directory clean of processed files
ls batch_update_*.sql batch_update_*.csv 2>/dev/null && echo "ERROR: Files not moved" || echo "SUCCESS: Files moved"
# Expected: SUCCESS: Files moved

# Verify processed directory contains files
find processed/ -name "batch_update_*" | wc -l
# Expected: 2 (CSV and SQL files)
```

**Cleanup**:
```bash
rm -f test7_files.jsonl initial_files.txt moved_files.txt batch_update_*.* 
rm -rf processed/
```

---

### Test 8: Large Dataset Performance

**Objective**: Verify handling of larger datasets (100+ entries)

**Setup**:
```bash
# Generate 100 valid entries
for i in {1..100}; do
    uuid=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
    echo "{\"artist_id\": \"$uuid\", \"response_text\": \"Test artist bio number $i with some content to make it realistic.\", \"error\": null}"
done > test8_large.jsonl
```

**Execution**:
```bash
python3 tools/generate_batch_update.py --input test8_large.jsonl --test-mode
```

**Success Criteria**:
- Exit code: 0
- Output contains: "Valid entries: 100"
- Output contains: "Processing success rate: 100.0%"
- CSV file contains 101 lines (header + 100 data rows)

**Validation**:
```bash
# Verify CSV row count
wc -l batch_update_*.csv | awk '{print $1}'
# Expected: 101

# Execute with timing
time ./tools/run_batch_update.sh
# Should complete successfully
```

**Cleanup**:
```bash
rm -f test8_large.jsonl batch_update_*.* && rm -rf processed/
```

---

## Automated Test Execution

### Full Test Suite Runner

```bash
#!/bin/bash
# Run all acceptance tests

set -e
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    echo "=== Running $test_name ==="
    
    if eval "$2"; then
        echo "✅ $test_name PASSED"
        ((TESTS_PASSED++))
    else
        echo "❌ $test_name FAILED"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Environment setup
set -a; source .env.local; set +a

# Run tests
run_test "Test 1: Basic Workflow" "test1_basic_workflow"
run_test "Test 2: Mixed Data" "test2_mixed_data"  
run_test "Test 3: Empty Input" "test3_empty_input"
run_test "Test 4: Special Characters" "test4_special_chars"
run_test "Test 5: Production vs Test Mode" "test5_modes"
run_test "Test 6: Error Conditions" "test6_error_conditions"
run_test "Test 7: File Management" "test7_file_management"
run_test "Test 8: Large Dataset" "test8_large_dataset"

# Summary
echo "=== TEST SUMMARY ==="
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo "Total: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED"
    exit 0
else
    echo "💥 SOME TESTS FAILED"
    exit 1
fi
```

## AI Agent Execution Guidelines

### Success Detection Patterns

**For generate_batch_update.py**:
- Success: Exit code 0 AND "Processing success rate: X%" in output
- Expected files: Look for "Files created:" section in output
- Validation: Use `wc -l`, `grep`, and file existence checks

**For run_batch_update.sh**:
- Success: Exit code 0 AND "All files processed successfully!" in output  
- Database: Look for "Database connection successful ✓"
- File movement: Check `processed/` directory contents vs working directory

### Error Detection Patterns

**Common failure indicators**:
- Exit codes: 1 (expected for error tests, unexpected for success tests)
- Missing files when expected
- Unexpected files when not expected  
- Wrong content in generated files
- Database connection failures

### Validation Commands

**File content verification**:
```bash
# CSV structure
head -1 file.csv | grep '^"id","bio"$'

# SQL table targeting
grep -E "UPDATE (test_)?artists SET" file.sql

# Row counting
wc -l < file.csv

# Content matching
grep -F "expected_string" file.txt
```

**State verification**:
```bash
# Clean state
ls batch_update_* 2>/dev/null || echo "CLEAN"

# File movement
ls processed/ | wc -l

# Directory existence  
test -d processed/ && echo "EXISTS"
```

## Exit Codes

- **0**: Test passed completely
- **1**: Test failed - validation criteria not met
- **2**: Test error - unable to execute test steps
- **3**: Environment error - prerequisites not met

## Notes for AI Agents

1. **Execute commands exactly as written** - paths and options matter
2. **Check exit codes** before proceeding to validation steps
3. **Use exact string matching** for output validation where specified
4. **Clean up after each test** to prevent state contamination
5. **Verify prerequisites** before starting test execution
6. **Log all command outputs** for debugging failed tests
7. **Stop on first failure** unless running the full suite
8. **Report specific failure points** with actual vs expected results