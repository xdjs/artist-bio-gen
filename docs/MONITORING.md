# Monitoring & Logging Guide

This guide covers the monitoring, logging, and observability features of the Artist Bio Generator, with a focus on the rate limiting and quota management system.

## Table of Contents

1. [Logging Overview](#logging-overview)
2. [Log Levels](#log-levels)
3. [Quota Monitoring Logs](#quota-monitoring-logs)
4. [Progress Tracking](#progress-tracking)
5. [Error Monitoring](#error-monitoring)
6. [Performance Metrics](#performance-metrics)
7. [Log Formats](#log-formats)
8. [Alert Interpretations](#alert-interpretations)
9. [Dashboard Setup](#dashboard-setup)
10. [Troubleshooting Common Issues](#troubleshooting-common-issues)

## Logging Overview

The application provides comprehensive logging at multiple levels:

- **Standard Output**: Progress bars and summary statistics
- **Log Messages**: Detailed operational logs with timestamps
- **Error Tracking**: Structured error logging with context
- **Quota Events**: Specialized logging for rate limit events

### Enabling Verbose Logging

```bash
# Enable debug-level logging
python3 -m artist_bio_gen.main --input-file artists.csv --verbose

# With quota monitoring (recommended)
python3 -m artist_bio_gen.main --input-file artists.csv --verbose --quota-monitoring true
```

## Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| **DEBUG** | Detailed diagnostic info | API request/response details |
| **INFO** | Normal operations | Artist processed successfully |
| **WARNING** | Potential issues | Approaching quota threshold |
| **ERROR** | Recoverable errors | API call failed, will retry |
| **CRITICAL** | Serious issues | Quota exhausted, pausing |

## Quota Monitoring Logs

### Quota Initialization

```
2025-09-18 15:18:16 - INFO - QuotaMonitor initialized: daily_limit=5000, threshold=0.8
2025-09-18 15:18:16 - INFO - Quota monitoring enabled: daily_limit=5000, threshold=0.8
```

### Regular Quota Updates

Logged every N requests (configurable via `--quota-log-interval`):

```
2025-09-18 15:20:30 - INFO - 📊 Quota Status:
  Requests: 450/5000 (9.0% used)
  Tokens: 125000/4000000 (3.1% used)
  Reset in: 23h 45m
  Current threshold: 0.8
```

### Quota Warnings

```
2025-09-18 16:30:45 - WARNING - ⚠️ Approaching quota threshold:
  Current usage: 4250/5000 requests (85.0%)
  Threshold: 80.0%
  Recommendation: Reduce workers or prepare for pause
```

### Quota Pause Events

```
2025-09-18 17:15:22 - CRITICAL - 🛑 QUOTA THRESHOLD EXCEEDED - PAUSING
  Usage: 4500/5000 requests (90.0%)
  Threshold: 80.0%
  Pause duration: 24 hours
  Resume time: 2025-09-19 17:15:22
```

### Quota Resume Events

```
2025-09-19 17:15:22 - INFO - ✅ RESUMING PROCESSING
  Quota reset detected
  New limits: 5000 requests, 4000000 tokens
  Pause duration was: 24h 0m
```

## Progress Tracking

### Real-time Progress Bar

```
[███████████████░░░░░░░░░░░░░░░] [ 50/100] ( 50.0%) [W04] ✅ Artist Name - SUCCESS (2.50s)
```

Components:
- **Progress Bar**: Visual representation of completion
- **Count**: Current/Total artists
- **Percentage**: Overall completion
- **Worker ID**: Thread identifier (W01-W16)
- **Status**: ✅ SUCCESS, ❌ FAILED, ⏸️ PAUSED
- **Duration**: Processing time per artist

### Concurrent Processing Updates

```
2025-09-18 15:19:55 - INFO - 📊 Concurrent Progress: 16/100 artists processed (16.0%)
  Rate: 1.46 artists/sec
  ETA: 58s remaining
  Quota: 3.2% used
```

## Error Monitoring

### Rate Limit Errors (429)

```
2025-09-18 15:45:12 - WARNING - Rate limit hit (429):
  Retry-After: 60 seconds
  Worker: W03
  Artist: John Doe
  Attempt: 1/3
  Backing off for: 60.0s
```

### Quota Exhaustion

```
2025-09-18 16:00:00 - ERROR - Quota exhausted (insufficient_quota):
  Error: You exceeded your current quota
  Worker: W07
  Backing off for: 300.0s
  Will retry with exponential backoff
```

### Network Errors

```
2025-09-18 15:30:00 - ERROR - Network error:
  Type: ConnectionError
  Message: Connection timeout
  Worker: W02
  Retry attempt: 2/3
  Next retry in: 2.0s
```

### API Errors

```
2025-09-18 15:35:00 - ERROR - API error for artist "Test Artist":
  Status: 500
  Message: Internal server error
  Request ID: req_abc123
  Will retry with backoff
```

## Performance Metrics

### Processing Summary

```
======================================================================
PROCESSING SUMMARY
======================================================================
End time: 2025-09-18 16:27:16
Total duration: 540.07 seconds (0:09:00)

INPUT STATISTICS:
  Total artists processed: 100
  Skipped lines (comments/blanks): 5
  Error lines (invalid data): 0

API CALL STATISTICS:
  Successful calls: 100
  Failed calls: 0
  Success rate: 100.0%
  Average time per artist: 5.40s
  API calls per second: 0.19
  Processing efficiency: 100.0%

QUOTA STATISTICS:
  Starting quota: 5000 requests
  Requests used: 100
  Remaining quota: 4900
  Peak usage: 2.0%
  Pauses triggered: 0
  Total pause time: 0s
======================================================================
```

### Worker Performance

```
WORKER STATISTICS:
  Worker W01: 13 artists, avg 5.2s, 100% success
  Worker W02: 12 artists, avg 5.5s, 100% success
  Worker W03: 13 artists, avg 5.3s, 100% success
  Worker W04: 12 artists, avg 5.4s, 100% success
  Worker W05: 13 artists, avg 5.1s, 100% success
  Worker W06: 12 artists, avg 5.6s, 100% success
  Worker W07: 13 artists, avg 5.3s, 100% success
  Worker W08: 12 artists, avg 5.4s, 100% success
```

## Log Formats

### Standard Log Format

```
TIMESTAMP - LEVEL - [COMPONENT] MESSAGE
```

Example:
```
2025-09-18 15:18:16 - INFO - [QuotaMonitor] Initialized with threshold=0.8
```

### Structured Error Format

```json
{
  "timestamp": "2025-09-18T15:30:00Z",
  "level": "ERROR",
  "component": "api",
  "worker_id": "W03",
  "artist_id": "uuid-123",
  "error_type": "RateLimitError",
  "message": "Rate limit exceeded",
  "retry_after": 60,
  "attempt": 1,
  "max_attempts": 3
}
```

### Quota Event Format

```json
{
  "timestamp": "2025-09-18T16:00:00Z",
  "event": "quota_warning",
  "usage": {
    "requests_used": 4000,
    "requests_limit": 5000,
    "percentage": 80.0
  },
  "threshold": 0.8,
  "action": "monitor"
}
```

## Alert Interpretations

### Critical Alerts

| Alert | Meaning | Action Required |
|-------|---------|-----------------|
| `QUOTA THRESHOLD EXCEEDED` | Usage > configured threshold | Will auto-pause, consider reducing load |
| `QUOTA EXHAUSTED` | No remaining quota | Wait for reset or increase limits |
| `ALL RETRIES FAILED` | Artist processing failed permanently | Manual investigation needed |

### Warning Alerts

| Alert | Meaning | Action Suggested |
|-------|---------|------------------|
| `Approaching quota threshold` | Usage > 60% of threshold | Monitor closely |
| `High error rate detected` | >10% failures | Check API status |
| `Slow response times` | >30s per artist | Reduce workers |

### Info Notifications

| Notification | Meaning |
|--------------|---------|
| `QuotaMonitor initialized` | System ready |
| `Processing resumed` | Quota reset or manual resume |
| `Checkpoint saved` | Progress persisted |

## Dashboard Setup

### Log Aggregation

For production monitoring, aggregate logs to a central system:

```bash
# Example: Send logs to file for aggregation
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --verbose \
  2>&1 | tee -a /var/log/artist-bio-gen/processing.log

# With timestamp rotation
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --verbose \
  2>&1 | tee -a "/var/log/artist-bio-gen/processing-$(date +%Y%m%d).log"
```

### Key Metrics to Monitor

1. **Request Rate**
   - Requests per second
   - Requests per worker
   - Peak vs average rate

2. **Quota Usage**
   - Current usage percentage
   - Time to reset
   - Pause frequency

3. **Error Rates**
   - API errors (4xx, 5xx)
   - Network errors
   - Retry success rate

4. **Performance**
   - Average processing time
   - P95 processing time
   - Queue depth

### Sample Monitoring Queries

#### Prometheus/Grafana

```promql
# Request rate
rate(artist_bio_requests_total[5m])

# Error rate
rate(artist_bio_errors_total[5m]) / rate(artist_bio_requests_total[5m])

# Quota usage
artist_bio_quota_used / artist_bio_quota_limit

# Processing time
histogram_quantile(0.95, artist_bio_processing_duration_seconds)
```

#### CloudWatch Logs Insights

```sql
fields @timestamp, level, message
| filter level = "ERROR"
| stats count() by bin(5m)

fields @timestamp, quota_percentage
| filter @message like /Quota Status/
| stats avg(quota_percentage) by bin(1h)
```

## Troubleshooting Common Issues

### Issue: No Quota Logs Appearing

**Check:**
1. Verbose mode enabled: `--verbose`
2. Quota monitoring enabled: `--quota-monitoring true`
3. Log interval setting: `--quota-log-interval 50`

**Debug Command:**
```bash
python3 -m artist_bio_gen.main \
  --input-file test.csv \
  --verbose \
  --quota-monitoring true \
  --quota-log-interval 1
```

### Issue: Frequent Pauses

**Check:**
1. Threshold too low: Try `--quota-threshold 0.9`
2. Daily limit too restrictive: Increase `--daily-limit`
3. Too many workers: Reduce `--max-workers`

**Monitor Command:**
```bash
# Watch quota in real-time
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --verbose \
  --quota-log-interval 10 \
  2>&1 | grep -E "(Quota|PAUSE|RESUME)"
```

### Issue: High Error Rates

**Check Logs For:**
```bash
# Count error types
grep "ERROR" processing.log | grep -oE "error_type: \w+" | sort | uniq -c

# Find failing artists
grep "FAILED" processing.log | grep -oE "artist: [^,]+" | sort | uniq

# Check retry patterns
grep "Retry attempt" processing.log | tail -20
```

### Issue: Slow Processing

**Performance Analysis:**
```bash
# Average processing time
grep "SUCCESS" processing.log | \
  grep -oE "\([0-9.]+s\)" | \
  sed 's/[()]//g' | sed 's/s//' | \
  awk '{sum+=$1; count++} END {print sum/count "s average"}'

# Slowest artists
grep "SUCCESS" processing.log | \
  sed 's/.*\[\(.*\)\].*(\([0-9.]*\)s).*/\2 \1/' | \
  sort -rn | head -10
```

## Log Rotation

### Configure logrotate

Create `/etc/logrotate.d/artist-bio-gen`:

```
/var/log/artist-bio-gen/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 appuser appgroup
    sharedscripts
    postrotate
        # Signal application if needed
        /usr/bin/killall -USR1 python3 2>/dev/null || true
    endscript
}
```

### Manual Rotation Script

```bash
#!/bin/bash
# rotate-logs.sh

LOG_DIR="/var/log/artist-bio-gen"
MAX_AGE=30  # days

# Rotate current log
if [ -f "$LOG_DIR/processing.log" ]; then
    mv "$LOG_DIR/processing.log" "$LOG_DIR/processing-$(date +%Y%m%d-%H%M%S).log"
fi

# Compress old logs
find "$LOG_DIR" -name "*.log" -mtime +1 -exec gzip {} \;

# Delete old compressed logs
find "$LOG_DIR" -name "*.gz" -mtime +$MAX_AGE -delete
```

## Best Practices

1. **Always Enable Verbose Mode** for production runs
2. **Set Appropriate Log Intervals** based on batch size (1-10 for testing, 100-1000 for production)
3. **Monitor Quota Usage** proactively to avoid surprises
4. **Archive Logs** for compliance and debugging
5. **Set Up Alerts** for critical events (quota exhaustion, high error rates)
6. **Use Structured Logging** for easier parsing and analysis
7. **Correlate Logs** with API provider's status page

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
- [README.md](../README.md) - Main documentation
- [plans/rate_limit_implementation_plan.md](../plans/rate_limit_implementation_plan.md) - Implementation details