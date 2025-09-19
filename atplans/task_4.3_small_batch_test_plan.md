# Task 4.3: Small Batch Testing Plan

## Overview
This document provides a detailed manual test plan for validating the rate limiting and quota management system with a small batch of 100 artists. This test should be performed in a controlled environment before deploying to production.

## Prerequisites

### Environment Setup
- [ ] Python 3.8+ environment with all dependencies installed
- [ ] Valid OpenAI API key configured in environment
- [ ] Access to test database (or test mode enabled)
- [ ] Sufficient API quota for ~100-150 API calls
- [ ] Log monitoring setup (terminal or log aggregator)

### Data Preparation
- [ ] Prepare test dataset with 100 artists in CSV format
- [ ] Ensure artist data has variety (different text lengths, special characters)
- [ ] Backup any existing output files

## Test Execution Plan

### Phase 1: Basic Functionality Test (10 Artists)

#### 1.1 Initial Smoke Test
```bash
# Start with minimal batch to verify setup
python -m artist_bio_gen.main \
  --input data/test_artists_10.csv \
  --prompt-id <your_prompt_id> \
  --max-workers 2 \
  --output output/test_phase1.jsonl \
  --quota-monitoring \
  --quota-threshold 0.8 \
  --daily-limit 1000 \
  --verbose
```

**Verification Points:**
- [ ] Script starts without errors
- [ ] Quota monitoring initialization logged
- [ ] Artists processed successfully
- [ ] Output file created with valid JSON lines
- [ ] No unexpected errors in logs

#### 1.2 Log Verification
Check for these log messages:
```
INFO: QuotaMonitor initialized: daily_limit=1000, threshold=0.8
DEBUG: Parsed quota status: X/5000 requests, Y/4000000 tokens
INFO: [W01] Processed artist 1/10: "Artist Name"
INFO: Quota metrics: X requests used today (X% of daily limit)
```

### Phase 2: Quota Threshold Testing (30 Artists)

#### 2.1 Low Threshold Test
```bash
# Set low thresholds to trigger pause behavior
python -m artist_bio_gen.main \
  --input data/test_artists_30.csv \
  --prompt-id <your_prompt_id> \
  --max-workers 4 \
  --output output/test_phase2.jsonl \
  --quota-monitoring \
  --quota-threshold 0.2 \
  --daily-limit 50 \
  --pause-duration 0.1 \
  --verbose
```

**Expected Behavior:**
- [ ] Processing starts normally
- [ ] After ~10 artists, quota threshold warning appears
- [ ] At 20% of limit (10 requests), pause triggered
- [ ] Clear pause message logged with reason
- [ ] Processing resumes after pause duration
- [ ] All 30 artists eventually processed

#### 2.2 Pause/Resume Verification
Monitor for these events:
```
WARNING: Quota usage at 60% (30/50 requests)
WARNING: PAUSED: Daily quota 80.0% used (limit: 50) - Will resume at [timestamp]
INFO: RESUMED: Auto-resume time reached
```

### Phase 3: Full Batch Test (100 Artists)

#### 3.1 Production-Like Configuration
```bash
# Run with production-like settings
python -m artist_bio_gen.main \
  --input data/test_artists_100.csv \
  --prompt-id <your_prompt_id> \
  --max-workers 8 \
  --output output/test_phase3.jsonl \
  --quota-monitoring \
  --quota-threshold 0.8 \
  --daily-limit 500 \
  --verbose \
  --resume  # Enable resume mode for safety
```

**Performance Metrics to Track:**
- [ ] Start time: ________________
- [ ] End time: ________________
- [ ] Total duration: ________________
- [ ] Average time per artist: ________________
- [ ] Number of pauses triggered: ________________
- [ ] Total pause duration: ________________

#### 3.2 Progress Monitoring
Every 10 artists, verify:
- [ ] Progress percentage updates correctly
- [ ] Memory usage remains stable
- [ ] No accumulating errors
- [ ] Output file growing as expected

### Phase 4: Error Recovery Testing

#### 4.1 Interrupt and Resume Test
1. Start processing 100 artists
2. After ~50 artists, interrupt with Ctrl+C
3. Verify state saved properly
4. Resume processing:
```bash
python -m artist_bio_gen.main \
  --input data/test_artists_100.csv \
  --prompt-id <your_prompt_id> \
  --max-workers 8 \
  --output output/test_phase4.jsonl \
  --quota-monitoring \
  --resume
```

**Verification:**
- [ ] Resume starts from last completed artist
- [ ] No duplicate processing
- [ ] Quota state restored correctly
- [ ] Final output has all 100 artists

#### 4.2 API Error Simulation
If possible, test with rate limit errors:
1. Set very high concurrency (--max-workers 20)
2. Process 50 artists rapidly
3. Observe rate limit handling:
   - [ ] 429 errors trigger exponential backoff
   - [ ] Retry logic works correctly
   - [ ] No data loss during retries

### Phase 5: Configuration Validation

#### 5.1 Parameter Boundary Testing
Test edge cases for configuration:

| Parameter | Test Value | Expected Result |
|-----------|------------|-----------------|
| quota-threshold | 0.1 | Very early pause |
| quota-threshold | 1.0 | Never pause (until hard limit) |
| daily-limit | 10 | Pause after ~8 requests |
| daily-limit | None | No daily limit enforcement |
| max-workers | 1 | Sequential processing |
| max-workers | 16 | High concurrency handling |

#### 5.2 Environment Variable Testing
```bash
# Test environment variable configuration
export QUOTA_MONITORING=true
export QUOTA_THRESHOLD=0.7
export DAILY_REQUEST_LIMIT=200
export PAUSE_DURATION_HOURS=0.5
export QUOTA_LOG_INTERVAL=10

python -m artist_bio_gen.main \
  --input data/test_artists_20.csv \
  --prompt-id <your_prompt_id> \
  --output output/test_env_vars.jsonl
```

Verify:
- [ ] Environment variables properly loaded
- [ ] CLI args override environment variables
- [ ] Default values used for unset variables

## Test Results Documentation

### Success Criteria Checklist
- [ ] All 100 test artists processed successfully
- [ ] Output file contains valid JSON for all artists
- [ ] Quota monitoring logs show expected patterns
- [ ] Pause/resume triggered and recovered correctly
- [ ] No data loss or corruption
- [ ] Performance within acceptable ranges (<2s per artist average)
- [ ] Memory usage stable (no leaks)
- [ ] Error handling works as expected
- [ ] Configuration parameters behave correctly

### Metrics to Record

| Metric | Target | Actual | Pass/Fail |
|--------|--------|--------|-----------|
| Success Rate | 100% | ___% | ⬜ |
| Avg Time/Artist | <2s | ___s | ⬜ |
| Total Duration | <5min | ___min | ⬜ |
| Memory Peak | <500MB | ___MB | ⬜ |
| Error Rate | <1% | ___% | ⬜ |
| Pause Accuracy | ±5% of threshold | ___% | ⬜ |

### Issue Log

Document any issues encountered:

| Issue # | Description | Severity | Resolution |
|---------|-------------|----------|------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

## Post-Test Validation

### Data Quality Checks
1. **Output Validation**
   ```python
   # Verify output file integrity
   import json

   with open('output/test_phase3.jsonl', 'r') as f:
       lines = f.readlines()
       assert len(lines) == 100, f"Expected 100, got {len(lines)}"

       for i, line in enumerate(lines):
           data = json.loads(line)
           assert 'artist_id' in data
           assert 'response_text' in data
           assert len(data['response_text']) > 50
   ```

2. **Duplicate Check**
   ```python
   # Ensure no duplicate processing
   artist_ids = [json.loads(line)['artist_id'] for line in lines]
   assert len(artist_ids) == len(set(artist_ids)), "Duplicates found!"
   ```

### Log Analysis
1. **Quota Event Summary**
   ```bash
   # Count quota-related log entries
   grep "quota" test_run.log | wc -l
   grep "PAUSED" test_run.log | wc -l
   grep "RESUMED" test_run.log | wc -l
   grep "Rate limit" test_run.log | wc -l
   ```

2. **Error Summary**
   ```bash
   # Check for errors and warnings
   grep "ERROR" test_run.log | head -20
   grep "WARNING" test_run.log | grep -v "quota" | head -20
   ```

### Performance Analysis
1. Calculate throughput:
   - Requests per minute: ___
   - Tokens per minute: ___
   - Effective parallelism: ___

2. Resource utilization:
   - CPU average: ___%
   - Memory average: ___MB
   - Network bandwidth: ___KB/s

## Recommendations

Based on test results, provide recommendations for:

### Configuration Tuning
- [ ] Optimal max_workers setting: ___
- [ ] Recommended quota_threshold: ___
- [ ] Suggested daily_limit for production: ___
- [ ] Pause duration adjustment: ___

### System Requirements
- [ ] Minimum memory needed: ___MB
- [ ] Recommended CPU cores: ___
- [ ] Network bandwidth required: ___KB/s
- [ ] Storage for outputs: ___GB per 10K artists

### Monitoring Setup
- [ ] Key metrics to track in production
- [ ] Alert thresholds to configure
- [ ] Log retention requirements
- [ ] Dashboard recommendations

## Sign-off

### Test Execution
- **Executed by**: ________________
- **Date**: ________________
- **Environment**: ________________
- **Duration**: ________________

### Review and Approval
- **Reviewed by**: ________________
- **Approved by**: ________________
- **Ready for Production**: ⬜ Yes ⬜ No

### Notes
_Additional observations, concerns, or recommendations:_

---

## Appendix A: Sample Test Data Format

```csv
artist_id,name,data
1001,"The Rolling Stones","British rock band formed in London in 1962..."
1002,"Beyoncé","American singer, songwriter, and actress..."
1003,"Miles Davis","American jazz trumpeter and composer..."
...
```

## Appendix B: Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Quota threshold not triggering" | Threshold too high | Lower threshold to 0.5 or less |
| "429 errors despite low volume" | Too many concurrent workers | Reduce max_workers |
| "Slow processing" | Network latency | Check API endpoint region |
| "Memory growing" | Output buffer not flushing | Ensure streaming mode enabled |
| "Resume not working" | State file corrupted | Delete state file and restart |

## Appendix C: Emergency Procedures

### If Testing Causes Issues:
1. **Immediate Stop**: Ctrl+C to interrupt
2. **Check API Dashboard**: Verify quota status on OpenAI dashboard
3. **Preserve Logs**: Copy all log files before cleanup
4. **Document Issue**: Record exact error and timestamp
5. **Rollback**: Restore previous version if needed

### Contact Information:
- **Technical Lead**: ________________
- **API Support**: OpenAI Support
- **Database Admin**: ________________
- **On-call Engineer**: ________________