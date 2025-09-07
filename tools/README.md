# Batch Update Tools

Automated tools for processing artist bio data from JSONL files and executing batch database updates.

## Overview

The batch update system provides a complete workflow for:
1. **Parsing JSONL data** with validation and duplicate detection
2. **Generating SQL batch files** with CSV data for PostgreSQL
3. **Executing database updates** with comprehensive error handling and progress reporting

## Tools

### 1. `generate_batch_update.py` - JSONL to SQL Converter

Processes JSONL files containing artist bio data and generates PostgreSQL batch update files.

**Features:**
- Field name mapping: `response_text` → `bio` 
- UUID validation and duplicate detection
- Error handling with detailed reporting
- Atomic file operations with comprehensive statistics

### 2. `run_batch_update.sh` - SQL Execution Engine

Discovers and executes batch update SQL files with full error handling and file management.

**Features:**
- Chronological file processing (oldest first)
- Database connectivity validation
- Progress reporting with execution timing
- Automatic file management (moves processed files to `processed/` directory)

## Installation & Setup

### Prerequisites

- **Python 3.7+** with standard library
- **PostgreSQL client** (`psql` command available)
- **Database access** via connection URL

### Environment Configuration

Set up your environment variables in `.env.local`:

```bash
# Database Connection (Required)
DATABASE_URL=postgresql://username:password@host:port/database

# Example
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
```

Load environment variables:
```bash
# Option 1: Export for current session
source .env.local

# Option 2: Export for subprocess (recommended)
set -a; source .env.local; set +a
```

## Usage

### Basic Workflow

```bash
# 1. Generate batch files from JSONL
python3 tools/generate_batch_update.py --input your_data.jsonl

# 2. Execute SQL updates
./tools/run_batch_update.sh

# 3. Review results in processed/ directory
ls -la processed/
```

### Production Mode (Default)

Updates the `artists` table:

```bash
# Generate for production
python3 tools/generate_batch_update.py --input out.jsonl

# Execute against production database
./tools/run_batch_update.sh
```

### Test Mode

Updates the `test_artists` table:

```bash
# Generate for testing
python3 tools/generate_batch_update.py --input out.jsonl --test-mode

# Execute (automatically detects test mode from SQL files)
./tools/run_batch_update.sh
```

### Custom Output Directory

```bash
# Generate files in custom location
python3 tools/generate_batch_update.py --input data.jsonl --output-dir /path/to/output

# Execute from custom directory
./tools/run_batch_update.sh /path/to/output
```

## Input Format

### JSONL Structure

Each line must contain a valid JSON object with:

```json
{
  "artist_id": "550e8400-e29b-41d4-a716-446655440001",
  "response_text": "Artist biography content here...",
  "error": null
}
```

**Required Fields:**
- `artist_id`: Valid UUID v4 format
- `response_text`: Non-empty artist biography text
- `error`: Must be `null` or empty string for valid entries

### Validation Rules

- ✅ **Valid UUID**: Proper UUID v4 format
- ✅ **Non-empty content**: `response_text` must contain actual content
- ✅ **No errors**: `error` field must be `null` or empty
- ✅ **Unique IDs**: Duplicate `artist_id` values are automatically excluded

## Output Files

### Generated Files

**Success Case:**
- `batch_update_YYYYMMDD_HHMMSS.csv` - Data for database import
- `batch_update_YYYYMMDD_HHMMSS.sql` - PostgreSQL execution script

**Mixed Results:**  
- `batch_update_YYYYMMDD_HHMMSS.csv` - Valid entries only
- `batch_update_YYYYMMDD_HHMMSS.sql` - SQL script for valid entries
- `batch_update_skipped_YYYYMMDD_HHMMSS.jsonl` - Invalid/duplicate entries

### After Execution

- `processed/` - Successfully processed files moved here
- `batch_update_skipped_*.jsonl` - Failed entries remain for review

## Command Reference

### generate_batch_update.py

```bash
python3 tools/generate_batch_update.py [OPTIONS]

Required:
  --input INPUT_FILE          JSONL file with artist data

Optional:
  --output-dir OUTPUT_DIR     Output directory (default: current directory)
  --test-mode                 Target test_artists table instead of artists
  --help                      Show help message

Examples:
  python3 tools/generate_batch_update.py --input out.jsonl
  python3 tools/generate_batch_update.py --input data.jsonl --test-mode
  python3 tools/generate_batch_update.py --input data.jsonl --output-dir ./batches
```

### run_batch_update.sh

```bash
./tools/run_batch_update.sh [DIRECTORY]

Arguments:
  DIRECTORY                   Directory to scan for SQL files (default: current)

Environment:
  DATABASE_URL               PostgreSQL connection URL (required)

Examples:
  ./tools/run_batch_update.sh
  ./tools/run_batch_update.sh /path/to/batch/files
  
  # With environment
  DATABASE_URL="postgresql://..." ./tools/run_batch_update.sh
```

## Example Scenarios

### Scenario 1: Standard Production Update

```bash
# You have artist bio data in out.jsonl
python3 tools/generate_batch_update.py --input out.jsonl

# Output:
# ✅ batch_update_20241201_143022.csv (1.2MB, 500 records)  
# ✅ batch_update_20241201_143022.sql (2KB)
# ✅ Success rate: 95.2% (500/525 entries processed)

# Execute the updates
source .env.local
./tools/run_batch_update.sh

# Output:
# ✅ Database connection successful
# ✅ Executing: batch_update_20241201_143022.sql
# ✅ Completed successfully (12s)
# ✅ Files processed successfully: 1
```

### Scenario 2: Test Environment Validation

```bash
# Test your changes safely
python3 tools/generate_batch_update.py --input new_data.jsonl --test-mode

# Verify results before production
./tools/run_batch_update.sh

# Check test_artists table for expected changes
```

### Scenario 3: Handling Mixed Data

```bash
python3 tools/generate_batch_update.py --input mixed_data.jsonl

# Output shows issues:
# ⚠️ Success rate: 60.0% (150/250 entries processed)
# ⚠️ Skipped entries: 100 (see batch_update_skipped_*.jsonl)

# Execute valid entries
./tools/run_batch_update.sh

# Review failed entries
cat batch_update_skipped_*.jsonl
```

## Troubleshooting

### Common Issues

**"DATABASE_URL environment variable is required"**
```bash
# Solution: Set the environment variable
export DATABASE_URL="postgresql://user:pass@host:port/db"
# Or load from file
source .env.local
```

**"No SQL batch files found"**
```bash
# Solution: Generate files first or check directory
python3 tools/generate_batch_update.py --input your_data.jsonl
```

**"Required CSV file not found"**
```bash
# Solution: Don't move/delete CSV files before SQL execution
# Both .csv and .sql files must be present together
```

**"Failed to connect to database"**
```bash
# Solution: Verify DATABASE_URL format and database accessibility
psql "$DATABASE_URL" -c "SELECT 1"
```

### File Naming Convention

Files use timestamp format: `batch_update_YYYYMMDD_HHMMSS.ext`

- Allows chronological processing (oldest first)
- Prevents filename conflicts  
- Makes it easy to track processing order

### Performance Notes

- **Batch size**: 1000 records per batch (configurable in SQL script)
- **Processing speed**: ~100 records/second typical
- **Memory usage**: Minimal (streaming processing)
- **Database locks**: Temporary table approach minimizes locking

## Safety Features

- **Atomic operations**: Temp files prevent corruption
- **Transaction safety**: All updates wrapped in BEGIN/COMMIT
- **Backup strategy**: Original files preserved until successful execution
- **Validation**: Pre-execution checks for required files and connectivity
- **Error isolation**: Failed files don't block successful processing

## Integration

### With CI/CD Pipelines

```bash
# In your deployment script
python3 tools/generate_batch_update.py --input "$JSONL_FILE"
./tools/run_batch_update.sh
```

### With Cron Jobs

```bash
# Daily batch processing
0 2 * * * cd /path/to/project && ./tools/run_batch_update.sh
```

### With Monitoring

The tools provide detailed output suitable for log aggregation:
- Processing statistics
- Execution timing
- Error details with context
- File-level success/failure tracking