# Manual Acceptance Test Plan - Issue #54
## Refactor: Consolidate Error Handling and Response Processing Patterns

**Date**: 2025-09-19
**Issue**: #54
**Purpose**: Validate that the unified ResponseProcessor pipeline works correctly and maintains backward compatibility while eliminating code duplication.

---

## Test Environment Setup

### Prerequisites
1. Python 3.11+ installed
2. Valid OpenAI API key configured in `.env.local`
3. PostgreSQL database (optional, for database tests)
4. Test prompt configured in OpenAI dashboard

### Initial Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create test environment file
cp .env.example .env.local
# Add your OPENAI_API_KEY and OPENAI_PROMPT_ID to .env.local

# 3. Prepare test input file
cat > test_artists.csv << 'EOF'
# Test Artists for Manual Acceptance Testing
11111111-1111-1111-1111-111111111111,The Beatles,British rock band from Liverpool
22222222-2222-2222-2222-222222222222,Miles Davis,American jazz trumpeter and composer
33333333-3333-3333-3333-333333333333,ERROR_TEST,FORCE_ERROR_FOR_TESTING
44444444-4444-4444-4444-444444444444,Bob Dylan,American singer-songwriter
55555555-5555-5555-5555-555555555555,Beyoncé,American singer and performer
EOF
```

---

## Test Scenarios

### Test 1: Basic Pipeline Processing
**Objective**: Verify the ResponseProcessor pipeline handles successful API calls correctly.

**Steps**:
1. Run with a small test file:
   ```bash
   python3 run_artists.py \
     --input-file test_artists.csv \
     --prompt-id <your-prompt-id> \
     --output out_test1.jsonl \
     --max-workers 1
   ```

2. Monitor the console output for:
   - ✅ "🚀 Starting processing:" messages
   - ✅ "✂️ Stripped trailing citations" messages (if applicable)
   - ✅ "✅ Completed processing:" messages with duration
   - ✅ Bio text printed to stdout

3. Verify JSONL output:
   ```bash
   # Check file was created and has content
   test -f out_test1.jsonl && echo "✓ File exists" || echo "✗ File missing"

   # Verify one line per artist (excluding errors)
   wc -l out_test1.jsonl  # Should show 4-5 lines

   # Validate JSON structure
   python3 -c "
   import json
   with open('out_test1.jsonl') as f:
       for i, line in enumerate(f, 1):
           try:
               data = json.loads(line)
               assert 'artist_id' in data
               assert 'response_text' in data
               assert 'created' in data
               print(f'Line {i}: ✓ Valid JSON with required fields')
           except Exception as e:
               print(f'Line {i}: ✗ {e}')
   "
   ```

**Expected Results**:
- ✅ All non-error artists processed successfully
- ✅ JSONL file contains valid JSON lines
- ✅ Each line has required fields
- ✅ Response text is properly cleaned (no trailing citations)

---

### Test 2: Error Handling Through Pipeline
**Objective**: Verify error handling is consistent and errors are properly streamed.

**Steps**:
1. Create a test that will trigger errors:
   ```bash
   # Use an invalid prompt ID to trigger API errors
   python3 run_artists.py \
     --input-file test_artists.csv \
     --prompt-id "invalid-prompt-id-xxx" \
     --output out_test2_errors.jsonl \
     --max-workers 1 2>&1 | tee test2_output.log
   ```

2. Check error handling:
   ```bash
   # Look for error processing in logs
   grep "❌ Failed processing:" test2_output.log
   grep "error" out_test2_errors.jsonl

   # Verify error responses are still streamed to JSONL
   python3 -c "
   import json
   with open('out_test2_errors.jsonl') as f:
       for line in f:
           data = json.loads(line)
           if 'error' in data and data['error']:
               print(f'✓ Error properly recorded: {data[\"artist_name\"][:20]}...')
   "
   ```

**Expected Results**:
- ✅ Errors are logged with "❌ Failed processing:" prefix
- ✅ Error responses are streamed to JSONL file
- ✅ JSONL contains error field for failed requests
- ✅ Pipeline continues processing remaining artists

---

### Test 3: Database Integration
**Objective**: Verify DatabaseUpdateStep works correctly when database is configured.

**Prerequisites**:
- PostgreSQL database configured with `DATABASE_URL` in `.env.local`
- Database has `artists` table with `artist_id` and `bio` columns

**Steps**:
1. Run with database connection:
   ```bash
   # Set DATABASE_URL if not in .env.local
   export DATABASE_URL="postgresql://user:pass@localhost/dbname"

   python3 run_artists.py \
     --input-file test_artists.csv \
     --prompt-id <your-prompt-id> \
     --output out_test3_db.jsonl \
     --max-workers 1
   ```

2. Check database status in output:
   ```bash
   # Look for database operation logs
   grep "💾 Database updated" logs  # Should see for successful updates
   grep "⏭️ Database update skipped" logs  # Should see for existing bios
   grep "DB:" test3_output.log  # Check DB status in completion messages

   # Verify db_status in JSONL
   python3 -c "
   import json
   with open('out_test3_db.jsonl') as f:
       for line in f:
           data = json.loads(line)
           status = data.get('db_status', 'null')
           print(f'{data[\"artist_name\"]}: db_status={status}')
   "
   ```

3. Verify in database:
   ```sql
   -- Check if bios were written
   SELECT artist_id, LEFT(bio, 50) as bio_preview
   FROM artists
   WHERE artist_id IN (
     '11111111-1111-1111-1111-111111111111',
     '22222222-2222-2222-2222-222222222222'
   );
   ```

**Expected Results**:
- ✅ Database connections properly acquired and released
- ✅ db_status field shows "updated", "skipped", or "error"
- ✅ Transaction logging for successful/failed operations
- ✅ Bios appear in database for successful operations

---

### Test 4: Concurrent Processing
**Objective**: Verify pipeline works correctly with multiple workers.

**Steps**:
1. Create larger test file:
   ```bash
   python3 -c "
   import uuid
   for i in range(50):
       print(f'{uuid.uuid4()},Test Artist {i},Description for artist {i}')
   " > test_artists_large.csv
   ```

2. Run with multiple workers:
   ```bash
   python3 run_artists.py \
     --input-file test_artists_large.csv \
     --prompt-id <your-prompt-id> \
     --output out_test4_concurrent.jsonl \
     --max-workers 5 2>&1 | tee test4_output.log
   ```

3. Verify concurrent processing:
   ```bash
   # Check for different worker IDs
   grep -o "W[0-9][0-9]" test4_output.log | sort -u
   # Should see W01, W02, W03, W04, W05

   # Verify all artists processed
   num_input=$(wc -l < test_artists_large.csv)
   num_output=$(wc -l < out_test4_concurrent.jsonl)
   echo "Input: $num_input, Output: $num_output"

   # Check for race conditions in output
   python3 -c "
   import json
   seen = set()
   with open('out_test4_concurrent.jsonl') as f:
       for line in f:
           data = json.loads(line)
           aid = data['artist_id']
           if aid in seen:
               print(f'✗ Duplicate: {aid}')
           seen.add(aid)
   print(f'✓ {len(seen)} unique artists processed')
   "
   ```

**Expected Results**:
- ✅ Multiple worker threads active (W01-W05)
- ✅ All artists processed exactly once
- ✅ No duplicate entries in output
- ✅ No JSON corruption from concurrent writes

---

### Test 5: Quota Monitoring Integration
**Objective**: Verify QuotaUpdateStep properly updates quota metrics.

**Steps**:
1. Run with quota monitoring enabled:
   ```bash
   python3 run_artists.py \
     --input-file test_artists.csv \
     --prompt-id <your-prompt-id> \
     --output out_test5_quota.jsonl \
     --daily-limit 1000 \
     --quota-threshold 0.8 \
     --max-workers 1 2>&1 | tee test5_output.log
   ```

2. Check quota monitoring logs:
   ```bash
   # Look for quota metrics in debug output
   grep "Quota metrics:" test5_output.log
   grep "usage=" test5_output.log

   # Check for pause behavior if threshold reached
   grep "Processing paused due to quota" test5_output.log
   ```

**Expected Results**:
- ✅ Quota metrics logged after each request
- ✅ Usage percentage calculated correctly
- ✅ Pause triggered if threshold exceeded
- ✅ Headers properly extracted and processed

---

### Test 6: Resume Mode with Pipeline
**Objective**: Verify streaming output can be resumed after interruption.

**Steps**:
1. Start processing and interrupt:
   ```bash
   # Start processing large file
   python3 run_artists.py \
     --input-file test_artists_large.csv \
     --prompt-id <your-prompt-id> \
     --output out_test6_resume.jsonl \
     --max-workers 1 &

   # Wait a few seconds then interrupt
   sleep 5 && kill $!
   ```

2. Check partial output:
   ```bash
   wc -l out_test6_resume.jsonl
   # Note the number of lines processed
   ```

3. Resume processing:
   ```bash
   python3 run_artists.py \
     --input-file test_artists_large.csv \
     --prompt-id <your-prompt-id> \
     --output out_test6_resume.jsonl \
     --resume \
     --max-workers 1
   ```

4. Verify completion:
   ```bash
   # Check final count
   wc -l out_test6_resume.jsonl

   # Verify no duplicates
   python3 -c "
   import json
   ids = []
   with open('out_test6_resume.jsonl') as f:
       for line in f:
           ids.append(json.loads(line)['artist_id'])
   print(f'Total: {len(ids)}, Unique: {len(set(ids))}')
   if len(ids) == len(set(ids)):
       print('✓ No duplicates found')
   else:
       print('✗ Duplicates detected!')
   "
   ```

**Expected Results**:
- ✅ Processing resumes from last completed artist
- ✅ No duplicate processing after resume
- ✅ Final output contains all artists
- ✅ JSONL file integrity maintained

---

### Test 7: Pipeline Step Isolation
**Objective**: Verify individual pipeline steps handle failures gracefully.

**Steps**:
1. Test with no OpenAI connection (API failure):
   ```bash
   # Temporarily use invalid API key
   OPENAI_API_KEY="invalid-key-test" python3 run_artists.py \
     --input-file test_artists.csv \
     --prompt-id <your-prompt-id> \
     --output out_test7_api_fail.jsonl \
     --max-workers 1 2>&1 | tee test7_output.log
   ```

2. Verify error handling:
   ```bash
   # Check that errors are properly classified
   grep "ErrorClassification" test7_output.log
   grep "should_retry" test7_output.log

   # Verify error responses still streamed
   test -f out_test7_api_fail.jsonl && echo "✓ Output file created despite errors"
   ```

**Expected Results**:
- ✅ Pipeline handles API failures gracefully
- ✅ Errors are classified correctly
- ✅ Failed responses still streamed to output
- ✅ Clear error messages in logs

---

## Performance Validation

### Compare Processing Times
Run the same dataset with the old and new code (if available):

```bash
# Time the new implementation
time python3 run_artists.py \
  --input-file test_artists.csv \
  --prompt-id <your-prompt-id> \
  --output out_perf_new.jsonl

# Compare file sizes (should be identical structure)
ls -la out_perf_*.jsonl

# Verify output structure unchanged
diff <(head -1 out_perf_new.jsonl | python -m json.tool | sort) \
     <(head -1 out_perf_old.jsonl | python -m json.tool | sort)
```

**Expected Results**:
- ✅ Performance similar or better than before refactoring
- ✅ Output structure unchanged
- ✅ No performance regression

---

## Regression Testing

### Verify Backward Compatibility
1. All existing command-line arguments work:
   ```bash
   python3 run_artists.py --help
   # Verify all documented options still present
   ```

2. Output format unchanged:
   ```bash
   # Compare output structure with previous version
   python3 -c "
   import json
   # Check required fields are present
   with open('out_test1.jsonl') as f:
       data = json.loads(f.readline())
       required = ['artist_id', 'artist_name', 'response_text', 'created', 'prompt_id']
       for field in required:
           assert field in data, f'Missing field: {field}'
       print('✓ All required fields present')
   "
   ```

3. Database operations unchanged:
   ```bash
   # If using database, verify same table structure works
   # No schema changes should be required
   ```

**Expected Results**:
- ✅ All CLI arguments work as documented
- ✅ Output format identical to previous version
- ✅ Database operations unchanged
- ✅ No breaking changes for existing users

---

## Cleanup

After testing:
```bash
# Remove test files
rm -f out_test*.jsonl test*.log test_artists*.csv
rm -f test*_output.log

# Clean up database test data if needed
# DELETE FROM artists WHERE artist_id LIKE '%1111-1111-1111%';
```

---

## Sign-off Checklist

- [ ] **Code Quality**
  - [ ] ~200-300 lines of duplicated code removed
  - [ ] Clear separation of concerns in pipeline steps
  - [ ] Each step independently testable

- [ ] **Functionality**
  - [ ] All tests passing (327 unit tests)
  - [ ] Basic processing works correctly
  - [ ] Error handling consistent across application
  - [ ] Database integration functional
  - [ ] Concurrent processing stable
  - [ ] Quota monitoring operational
  - [ ] Resume mode works correctly

- [ ] **Performance**
  - [ ] No performance regression
  - [ ] Memory usage acceptable
  - [ ] Concurrent processing efficient

- [ ] **Compatibility**
  - [ ] Backward compatible with existing usage
  - [ ] Output format unchanged
  - [ ] All CLI options functional
  - [ ] Database operations unchanged

- [ ] **Documentation**
  - [ ] Code well-commented
  - [ ] Pipeline architecture clear
  - [ ] Test coverage comprehensive

---

## Notes

**Tester**: _________________
**Date**: _________________
**Environment**: _________________
**Issues Found**: _________________

**Sign-off**: ✅ / ❌

**Comments**:
```
[Add any observations, issues, or suggestions here]
```