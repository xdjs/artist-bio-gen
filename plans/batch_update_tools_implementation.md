# Batch Update Tools Implementation Plan

## Overview
Create tools to generate and execute batch SQL update files from JSONL output, enabling efficient bulk database updates via PostgreSQL COPY operations.

## Requirements Summary
- **Input**: JSONL file in `out.jsonl` format  
- **Output**: Timestamped SQL batch file + CSV data file + skipped entries JSONL
- **Method**: PostgreSQL COPY with temporary table (Option 2)
- **Batch Size**: 1000 records per transaction
- **Error Handling**: Skip invalid entries, log duplicates, continue processing
- **Table Support**: `artists` (default) or `test_artists` (via `--test-mode`)
- **Shell Integration**: Automated SQL file execution

## Phase 1: Python Batch Generator Script
**Priority: High | Estimated Time: 4-5 hours**

### Task 1.1: Create Project Structure
- ✅ Create `tools/` directory at project root
- ✅ Create `tools/__init__.py` (empty file for Python module support)
- ✅ Plan file structure and imports

### Task 1.2: Implement Core JSONL Parser
**File**: `tools/generate_batch_update.py`

**Subtasks**:
- ✅ Create command-line argument parser
  ```python
  --input <jsonl_file>     # Required: input JSONL file path
  --test-mode              # Optional: use test_artists table
  --output-dir <dir>       # Optional: output directory (default: cwd)
  ```
- ✅ Implement JSONL line-by-line parser
- ✅ Add error handling for malformed JSON lines
- ✅ Create data validation functions:
  - `validate_uuid_format(artist_id)` 
  - `validate_jsonl_entry(entry)`
  - `has_valid_bio(entry)` (checks error field is null/empty)

### Task 1.3: Implement Duplicate Detection
**Subtasks**:
- ✅ Create `artist_id` tracking set for duplicates
- ✅ Process entries in order, detect duplicates
- ✅ Move ALL occurrences of duplicated `artist_id` to skipped file
- ✅ Log duplicate detection with counts

### Task 1.4: Implement File Generation System
**Subtasks**:
- ✅ Create timestamp generation function: `YYYYMMDD_HHMMSS` format
- ✅ Generate three output files:
  - `batch_update_{timestamp}.sql` - Main SQL script
  - `batch_update_{timestamp}.csv` - CSV data for COPY
  - `batch_update_skipped_{timestamp}.jsonl` - Invalid entries
- ✅ Implement CSV writer with UTF-8 support and proper escaping
- ✅ Handle bio text with quotes, newlines, special characters

### Task 1.5: Implement SQL Script Generation
**Subtasks**:
- ✅ Generate SQL header with error handling:
  ```sql
  \set ON_ERROR_STOP on
  \echo 'Starting batch bio update...'
  ```
- ✅ Create transaction structure with batched processing:
  ```sql
  BEGIN;
  CREATE TEMP TABLE temp_bio_updates (id UUID, bio TEXT);
  \copy temp_bio_updates FROM 'batch_update_{timestamp}.csv' WITH CSV HEADER;
  ```
- ✅ Generate batched UPDATE statements (1000 records per batch):
  ```sql
  \echo 'Processing batch 1/N (records 1-1000)...'
  WITH batch AS (SELECT * FROM temp_bio_updates ORDER BY id LIMIT 1000 OFFSET 0)
  UPDATE {table_name} SET bio = batch.bio, updated_at = CURRENT_TIMESTAMP
  FROM batch WHERE {table_name}.id = batch.id;
  ```
- ✅ Add cleanup and summary:
  ```sql
  SELECT COUNT(*) as total_processed FROM temp_bio_updates;
  DROP TABLE temp_bio_updates;
  COMMIT;
  \echo 'Batch update completed successfully!'
  ```
- ✅ Support both `artists` and `test_artists` table names

### Task 1.6: Implement Logging and Statistics
**Subtasks**:
- ✅ Track processing statistics:
  - ✅ Total lines processed
  - ✅ Valid entries processed  
  - ✅ Invalid entries skipped
  - ✅ Duplicate entries detected
  - ✅ Total batches generated
- ✅ Print summary report to stdout
- ✅ Include file paths in summary

### Task 1.7: Error Handling and Validation
**Subtasks**:
- ✅ Validate input file exists and is readable
- ✅ Validate output directory exists and is writable
- ✅ Handle file I/O errors gracefully
- ✅ Ensure atomic file operations (write to temp files first)
- ✅ Add comprehensive error messages with line numbers

## Phase 2: Shell Script for SQL Execution
**Priority: High | Estimated Time: 2-3 hours**

### Task 2.1: Create Shell Script Structure ✅
**File**: `tools/run_batch_update.sh`

**Subtasks**:
- ✅ Create executable shell script with proper shebang
- ✅ Implement argument parsing:
  ```bash
  run_batch_update.sh [directory]  # Optional: directory to scan (default: cwd)
  ```
- ✅ Add help text and usage information

### Task 2.2: Implement SQL File Discovery ✅
**Subtasks**:
- ✅ Scan directory for files matching `batch_update_*.sql`
- ✅ Sort files by timestamp (process oldest first)
- ✅ Skip files that don't match expected naming pattern
- ✅ Display found files before processing

### Task 2.3: Implement Database Connection Management ✅
**Subtasks**:
- ✅ Read database connection parameters from environment:
  ```bash
  DATABASE_URL (PostgreSQL connection URL format)
  ```
- ✅ Validate required environment variable is present
- ✅ Test database connectivity before processing files
- ✅ Use `psql` command for SQL execution

### Task 2.4: Implement File Execution Logic ✅
**Subtasks**:
- ✅ Process each SQL file in chronological order
- ✅ Execute with `psql` and capture output to stdout
- ✅ Handle execution errors appropriately:
  - Continue with next file on error
  - Log error details to stdout
  - Track success/failure counts
- ✅ Move successfully processed files to `processed/` subdirectory
- ✅ Leave failed files in place for manual review

### Task 2.5: Implement Progress Reporting
**Subtasks**:
- Display file being processed
- Show progress through multiple files
- Display execution time for each file
- Print summary statistics at completion

### Task 2.6: Add Safety and Validation Features
**Subtasks**:
- Verify CSV data files exist before executing SQL
- Check that SQL files are valid (basic syntax check)
- Ensure proper file permissions
- Create backup/processed directory structure

## Phase 3: Integration and Documentation
**Priority: Medium | Estimated Time: 1-2 hours**

### Task 3.1: Create Documentation
**Subtasks**:
- Add `tools/README.md` with usage instructions
- Document workflow: generate → execute → cleanup
- Provide example usage scenarios
- Document required environment variables
- Add troubleshooting section

### Task 3.2: Add Example Files and Tests
**Subtasks**:
- Create sample input JSONL file for testing
- Generate example output files for reference
- Test with both `artists` and `test_artists` modes
- Validate handling of edge cases:
  - Empty JSONL file
  - All invalid entries
  - Very large files (10k+ entries)
  - Unicode/special characters in bio text

### Task 3.3: Update Project Documentation
**Subtasks**:
- Update main `README.md` to mention batch tools
- Add section to `AGENTS.md` about tool usage
- Update `.gitignore` for generated files:
  ```
  tools/batch_update_*.sql
  tools/batch_update_*.csv
  tools/batch_update_skipped_*.jsonl
  tools/processed/
  ```

## Phase 4: Testing and Validation
**Priority: High | Estimated Time: 2-3 hours**

### Task 4.1: Unit Testing (Python Script)
**Subtasks**:
- Test JSONL parsing with various input formats
- Test UUID validation with valid/invalid UUIDs
- Test duplicate detection logic
- Test CSV generation with special characters
- Test SQL generation for both table modes
- Test error handling for malformed input

### Task 4.2: Integration Testing
**Subtasks**:
- End-to-end test: generate JSONL → create batch → execute SQL
- Test with realistic data volume (1000+ records)
- Test with `test_artists` table in database
- Validate database state after batch updates
- Test shell script with multiple SQL files

### Task 4.3: Error Scenario Testing
**Subtasks**:
- Test behavior with missing CSV files
- Test database connection failures
- Test interrupted executions
- Test file permission issues
- Test malformed SQL files

## File Structure After Implementation

```
tools/
├── __init__.py                                    # Empty file for module support
├── generate_batch_update.py                       # Main batch generator script
├── run_batch_update.sh                           # SQL execution shell script
├── README.md                                      # Tool documentation
├── processed/                                     # Processed SQL files (created by shell script)
└── examples/                                      # Example files for testing
    ├── sample_input.jsonl
    ├── sample_output.sql
    └── sample_output.csv
```

## Expected Generated Files

```bash
# Generated by Python script
batch_update_20250105_143022.sql                  # SQL script with batched updates  
batch_update_20250105_143022.csv                  # CSV data for COPY command
batch_update_skipped_20250105_143022.jsonl        # Invalid/duplicate entries

# Created by shell script  
processed/batch_update_20250105_143022.sql        # Moved after successful execution
processed/batch_update_20250105_143022.csv        # Corresponding CSV file
```

## Success Criteria

- Python script successfully parses JSONL and generates valid SQL batch files
- Shell script executes SQL files reliably with proper error handling
- Handles edge cases: duplicates, invalid data, large files, special characters
- Provides clear feedback and logging throughout process
- Integrates cleanly with existing project structure
- Documentation is complete and examples work as described

## Performance Targets

- **Processing Speed**: Handle 10,000+ JSONL entries in under 30 seconds
- **SQL Execution**: Batch updates of 10,000 records in under 2 minutes  
- **Memory Usage**: Process files larger than available RAM (streaming approach)
- **Reliability**: 99%+ success rate for valid input data