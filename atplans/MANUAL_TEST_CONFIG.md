# Manual Acceptance Testing for Configuration Refactoring

## Overview
This document provides manual testing procedures to verify the configuration management refactoring (Issue #55).

## Automated Test Script
Run the automated acceptance test first:
```bash
python test_config_refactor.py
```

## Manual Testing Procedures

### 1. Verify Removed Features

#### Test: OPENAI_ORG_ID Removal
```bash
# This should NOT show --openai-org-id
python run_artists.py --help | grep "org-id"

# Expected: No output (option removed)
```

#### Test: Duplicate --openai-prompt-id Removal
```bash
# Should only show --prompt-id, not --openai-prompt-id
python run_artists.py --help | grep "prompt-id"

# Expected: Only --prompt-id appears
```

### 2. Test Configuration Precedence

#### Test: CLI > Environment > .env.local > Defaults

1. **Create test .env.local file:**
```bash
cat > .env.local.test << EOF
OPENAI_API_KEY=dotenv_key
DATABASE_URL=postgresql://dotenv:dotenv@localhost:5432/dotenv
QUOTA_THRESHOLD=0.3
EOF
```

2. **Test with environment variable:**
```bash
# Set env var (should override .env.local)
export QUOTA_THRESHOLD=0.5

# Run with CLI (should override env)
python run_artists.py --input-file test.csv \
  --quota-threshold 0.9 \
  --dry-run

# Check logs to verify quota_threshold=0.9 was used
```

3. **Clean up:**
```bash
unset QUOTA_THRESHOLD
rm .env.local.test
```

### 3. Test Validation Rules

#### Test: Quota Threshold Range
```bash
# Should fail (> 1.0)
python run_artists.py --input-file test.csv \
  --openai-api-key test \
  --db-url postgresql://test:test@localhost:5432/test \
  --prompt-id test \
  --quota-threshold 1.5 \
  --dry-run

# Expected: Error message about quota threshold range

# Should succeed (valid range)
python run_artists.py --input-file test.csv \
  --openai-api-key test \
  --db-url postgresql://test:test@localhost:5432/test \
  --prompt-id test \
  --quota-threshold 0.5 \
  --dry-run
```

#### Test: Daily Request Limit
```bash
# Should fail (negative)
python run_artists.py --input-file test.csv \
  --openai-api-key test \
  --db-url postgresql://test:test@localhost:5432/test \
  --prompt-id test \
  --daily-limit -100 \
  --dry-run

# Expected: Error about positive integer requirement
```

#### Test: Pause Duration Range
```bash
# Should fail (> 72 hours)
python run_artists.py --input-file test.csv \
  --openai-api-key test \
  --db-url postgresql://test:test@localhost:5432/test \
  --prompt-id test \
  --pause-duration 100 \
  --dry-run

# Expected: Error about 1-72 hour range
```

### 4. Test Empty String Handling

#### Test: Empty String as None
```bash
# Empty prompt-id should be treated as None
python run_artists.py --input-file test.csv \
  --openai-api-key test \
  --db-url postgresql://test:test@localhost:5432/test \
  --prompt-id "" \
  --dry-run

# Expected: Should work in dry-run, or error that prompt-id is required
```

#### Test: Whitespace Trimming
```bash
# Whitespace should be trimmed
python run_artists.py --input-file test.csv \
  --openai-api-key "  test_key  " \
  --db-url "  postgresql://test:test@localhost:5432/test  " \
  --prompt-id "  test_prompt  " \
  --dry-run

# Expected: Should work with trimmed values
```

### 5. Test Boolean Configuration

#### Test: Quota Monitoring Boolean
```bash
# Test valid boolean values
for value in true false; do
  python run_artists.py --input-file test.csv \
    --openai-api-key test \
    --db-url postgresql://test:test@localhost:5432/test \
    --prompt-id test \
    --quota-monitoring $value \
    --dry-run
  echo "quota-monitoring=$value: exit code $?"
done

# Expected: Both should succeed
```

#### Test: Invalid Boolean
```bash
# Through environment variable
export QUOTA_MONITORING=invalid
python run_artists.py --input-file test.csv \
  --openai-api-key test \
  --db-url postgresql://test:test@localhost:5432/test \
  --prompt-id test \
  --dry-run

# Expected: Error about invalid boolean value
unset QUOTA_MONITORING
```

### 6. Test Type Conversion

#### Test: Automatic Type Conversion
```bash
# Create a test to verify types are properly converted
python -c "
from artist_bio_gen.config.loader import ConfigLoader
from artist_bio_gen.config.schema import ConfigSchema
from argparse import Namespace

# Simulate CLI args
args = Namespace(
    quota_threshold=0.5,  # Should remain float
    daily_limit=1000,     # Should remain int
    pause_duration=24,    # Should remain int
    quota_monitoring='true',  # Should convert to bool
    openai_api_key='test',
    db_url='postgresql://test:test@localhost:5432/test',
    prompt_id='test'
)

config = ConfigLoader.load(schema=ConfigSchema, cli_args=args)

print(f'quota_threshold type: {type(config.quota_threshold).__name__} = {config.quota_threshold}')
print(f'daily_limit type: {type(config.daily_request_limit).__name__} = {config.daily_request_limit}')
print(f'pause_duration type: {type(config.pause_duration_hours).__name__} = {config.pause_duration_hours}')
print(f'quota_monitoring type: {type(config.quota_monitoring).__name__} = {config.quota_monitoring}')
"

# Expected output:
# quota_threshold type: float = 0.5
# daily_limit type: int = 1000
# pause_duration type: int = 24
# quota_monitoring type: bool = True
```

### 7. Integration Test with Real Workflow

#### Test: Complete Workflow
1. **Create test input file:**
```bash
cat > test_artists.csv << EOF
550e8400-e29b-41d4-a716-446655440001,Test Artist 1,Biography data for artist 1
550e8400-e29b-41d4-a716-446655440002,Test Artist 2,Biography data for artist 2
EOF
```

2. **Run with full configuration:**
```bash
python run_artists.py \
  --input-file test_artists.csv \
  --openai-api-key $OPENAI_API_KEY \
  --db-url $DATABASE_URL \
  --prompt-id $OPENAI_PROMPT_ID \
  --quota-threshold 0.8 \
  --quota-monitoring true \
  --daily-limit 5000 \
  --pause-duration 24 \
  --quota-log-interval 50 \
  --max-workers 2 \
  --dry-run

# Expected: Should show dry run output with 2 artist payloads
```

3. **Clean up:**
```bash
rm test_artists.csv
```

## Performance Verification

### Code Reduction Check
```bash
# Compare old vs new line counts
echo "Parser module:"
wc -l artist_bio_gen/cli/parser.py
echo "(Was ~144 lines, now ~18 lines)"

echo -e "\nConfig module:"
wc -l artist_bio_gen/config/*.py
echo "(Total config code reduced by ~260 lines)"
```

## Expected Test Results

✅ **All tests should pass with:**
- No references to OPENAI_ORG_ID
- No duplicate --openai-prompt-id argument
- Proper configuration precedence (CLI > ENV > .env.local)
- Validation errors for out-of-range values
- Correct type conversion
- Empty strings treated as None
- Whitespace properly trimmed

## Troubleshooting

If tests fail:

1. **Check for .env.local file:**
   ```bash
   ls -la .env.local
   ```
   This file may provide values that affect tests.

2. **Check environment variables:**
   ```bash
   env | grep -E "(OPENAI|DATABASE|QUOTA|DAILY|PAUSE)"
   ```

3. **Run unit tests:**
   ```bash
   python -m pytest tests/config/ -v
   ```

4. **Check imports:**
   ```bash
   python -c "from artist_bio_gen.config import ConfigSchema, ConfigLoader"
   ```

## Summary

The refactored configuration system should:
1. ✅ Remove ~260 lines of boilerplate code
2. ✅ Provide single source of truth (schema)
3. ✅ Generate CLI automatically from schema
4. ✅ Validate with clear error messages
5. ✅ Maintain backward compatibility
6. ✅ Handle edge cases (empty strings, whitespace)