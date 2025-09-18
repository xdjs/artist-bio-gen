# Configuration Guide

This guide covers all configuration options available for the Artist Bio Generator, including the new rate limiting and quota management features.

## Table of Contents

1. [Configuration Precedence](#configuration-precedence)
2. [Core Configuration](#core-configuration)
3. [Rate Limiting & Quota Management](#rate-limiting--quota-management)
4. [Processing Configuration](#processing-configuration)
5. [Database Configuration](#database-configuration)
6. [Environment Setup](#environment-setup)
7. [Command-Line Interface](#command-line-interface)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

## Configuration Precedence

Configuration values are loaded with the following precedence (highest to lowest):

1. **CLI arguments** - Direct command-line parameters (highest priority)
2. **OS environment variables** - System environment settings
3. **`.env.local` file** - Local environment file (if `python-dotenv` is installed)
4. **Application defaults** - Built-in default values (lowest priority)

### Example of Precedence

```bash
# .env.local file
QUOTA_THRESHOLD=0.7

# Environment variable
export QUOTA_THRESHOLD=0.8

# CLI override (takes precedence)
python3 -m artist_bio_gen.main --input-file artists.csv --quota-threshold 0.9
# Uses 0.9 (CLI) instead of 0.8 (env) or 0.7 (.env.local)
```

## Core Configuration

### OpenAI API Settings

| Parameter | Environment Variable | CLI Flag | Default | Description |
|-----------|---------------------|----------|---------|-------------|
| API Key | `OPENAI_API_KEY` | `--openai-api-key` | Required | Your OpenAI API key |
| Prompt ID | `OPENAI_PROMPT_ID` | `--openai-prompt-id` | Required | Reusable prompt ID for Responses API |
| Organization ID | `OPENAI_ORG_ID` | `--openai-org-id` | None | OpenAI organization ID (optional) |

### Input/Output Settings

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Input File | `--input-file` | Required | CSV-like text file with artist data |
| Output File | `--output` | `out.jsonl` | JSONL output file path |
| Prompt Version | `--version` | None | Specific prompt version to use |

## Rate Limiting & Quota Management

### Quota Monitoring

| Parameter | Environment Variable | CLI Flag | Default | Description |
|-----------|---------------------|----------|---------|-------------|
| Enable Monitoring | `QUOTA_MONITORING` | `--quota-monitoring` | `true` | Enable/disable quota tracking |
| Threshold | `QUOTA_THRESHOLD` | `--quota-threshold` | `0.8` | Pause threshold (0.1-1.0) |
| Daily Limit | `DAILY_REQUEST_LIMIT` | `--daily-limit` | None | Optional daily request budget |
| Pause Duration | `PAUSE_DURATION_HOURS` | `--pause-duration` | `24` | Hours to pause (1-72) |
| Log Interval | `QUOTA_LOG_INTERVAL` | `--quota-log-interval` | `100` | Log metrics every N requests |

### How Quota Management Works

1. **Header Parsing**: Extracts rate limit information from OpenAI API response headers
2. **Usage Tracking**: Monitors requests and tokens against limits
3. **Threshold Monitoring**: Triggers pause when usage exceeds configured threshold
4. **Automatic Pause**: Pauses processing to avoid quota exhaustion
5. **Smart Resume**: Automatically resumes when quota resets

### Rate Limiting Strategy

The system implements sophisticated exponential backoff strategies:

| Error Type | Backoff Strategy | Cap | Jitter |
|------------|------------------|-----|--------|
| Rate Limit (429) | Use `Retry-After` header or 60s → 300s | 300s | 10% |
| Quota Exhaustion | 300s → 3600s | 3600s | 10% |
| Server Errors (5xx) | 0.5s → 4s | 4s | 10% |
| Network Errors | 0.5s → 4s | 4s | 10% |

## Processing Configuration

### Concurrency Settings

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Max Workers | `--max-workers` | `4` | Maximum concurrent API requests |
| Resume Processing | `--resume` | `false` | Skip artists already in output file |

### Processing Modes

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Dry Run | `--dry-run` | `false` | Parse inputs without API calls |
| Verbose Mode | `--verbose` | `false` | Enable debug logging |
| Test Mode | `--test-mode` | `false` | Use test_artists database table |

## Database Configuration

### Database Connection

| Parameter | Environment Variable | CLI Flag | Default | Description |
|-----------|---------------------|----------|---------|-------------|
| Database URL | `DATABASE_URL` | `--db-url` | Required* | PostgreSQL connection string |
| Enable Database | - | `--enable-db` | `false` | Enable database bio updates |

*Required only when `--enable-db` is used

### Connection String Format

```
postgresql://username:password@host:port/database
```

### Example Configurations

```bash
# Local development
postgresql://dev:devpass@localhost:5432/artist_bios

# Production with SSL
postgresql://user:pass@prod-host:5432/artist_bios?sslmode=require

# With connection pooling parameters
postgresql://user:pass@host:5432/db?pool_size=20&max_overflow=0
```

## Environment Setup

### Using .env.local File

Create a `.env.local` file in the project root:

```bash
# Core Configuration
OPENAI_API_KEY=sk-proj-abc123...
OPENAI_PROMPT_ID=pmpt_68ae36812ef48193b07eb66e07bea5e8009423aa3140ae26
DATABASE_URL=postgresql://user:pass@localhost:5432/artist_bios

# Quota Management
QUOTA_MONITORING=true
QUOTA_THRESHOLD=0.8
DAILY_REQUEST_LIMIT=10000
PAUSE_DURATION_HOURS=24
QUOTA_LOG_INTERVAL=100

# Optional
OPENAI_ORG_ID=org-abc123
```

### Using System Environment Variables

```bash
# Set environment variables
export OPENAI_API_KEY="sk-proj-abc123..."
export QUOTA_THRESHOLD="0.9"
export DAILY_REQUEST_LIMIT="5000"

# Run the application
python3 -m artist_bio_gen.main --input-file artists.csv
```

## Command-Line Interface

### Basic Syntax

```bash
python3 -m artist_bio_gen.main [OPTIONS]
```

### Complete Options Reference

```
Required Arguments:
  --input-file FILE           Input CSV-like file with artist data

API Configuration:
  --openai-api-key KEY       Override OpenAI API key
  --openai-prompt-id ID      Override prompt ID
  --openai-org-id ID         Override organization ID
  --version VERSION          Specific prompt version

Output Configuration:
  --output FILE              Output JSONL file (default: out.jsonl)

Processing Options:
  --max-workers N            Max concurrent workers (default: 4)
  --dry-run                  Parse without API calls
  --verbose                  Enable debug logging
  --resume                   Skip existing artists in output

Quota Management:
  --quota-monitoring {true,false}  Enable quota monitoring (default: true)
  --quota-threshold DECIMAL        Pause threshold 0.1-1.0 (default: 0.8)
  --daily-limit N                  Daily request limit (optional)
  --pause-duration HOURS           Pause duration 1-72 (default: 24)
  --quota-log-interval N           Log interval (default: 100)

Database Options:
  --enable-db                Enable database updates
  --test-mode                Use test_artists table
  --db-url URL               Override database URL
```

## Examples

### Basic Processing

```bash
# Simple run with defaults
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --openai-prompt-id pmpt_123

# With custom output and more workers
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --output results.jsonl \
  --max-workers 8
```

### With Quota Management

```bash
# Conservative quota settings
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --quota-threshold 0.7 \
  --daily-limit 1000 \
  --pause-duration 12

# Aggressive processing (higher threshold)
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --quota-threshold 0.95 \
  --max-workers 16 \
  --quota-log-interval 50
```

### Database Integration

```bash
# Production run with database
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --enable-db \
  --db-url "postgresql://user:pass@prod-host:5432/artist_bios"

# Test mode with local database
python3 -m artist_bio_gen.main \
  --input-file test_artists.csv \
  --enable-db \
  --test-mode \
  --verbose
```

### Resume After Interruption

```bash
# Resume processing from where it left off
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --output partial_results.jsonl \
  --resume \
  --quota-monitoring true
```

### Development and Testing

```bash
# Dry run to validate input
python3 -m artist_bio_gen.main \
  --input-file artists.csv \
  --dry-run \
  --verbose

# Test with minimal quota
python3 -m artist_bio_gen.main \
  --input-file test_batch.csv \
  --daily-limit 10 \
  --quota-threshold 0.5 \
  --verbose
```

## Troubleshooting

### Common Issues

#### Quota Monitoring Not Working

**Symptoms**: No quota logs appearing, pause not triggering

**Solutions**:
1. Ensure `--quota-monitoring true` is set
2. Check logs for "QuotaMonitor initialized" message
3. Verify `--verbose` mode for detailed logging

#### Pause Not Resuming

**Symptoms**: Processing stays paused after quota should reset

**Solutions**:
1. Check `--pause-duration` setting (might be too long)
2. Verify system time is correct
3. Check logs for resume time calculation

#### Configuration Not Loading

**Symptoms**: Settings from .env.local not being used

**Solutions**:
1. Ensure `python-dotenv` is installed: `pip install python-dotenv`
2. Check file is named `.env.local` (not `.env`)
3. Verify file is in project root directory
4. Use `--verbose` to see configuration loading

#### Rate Limit Errors (429)

**Symptoms**: Getting 429 errors despite quota management

**Solutions**:
1. Lower `--quota-threshold` (e.g., 0.7 instead of 0.8)
2. Reduce `--max-workers` to decrease request rate
3. Set a `--daily-limit` to enforce budget
4. Check if using correct API tier limits

### Validation Rules

1. **Quota Threshold**: Must be between 0.1 and 1.0
2. **Pause Duration**: Must be between 1 and 72 hours
3. **Daily Limit**: Optional, but must be positive integer if set
4. **Max Workers**: Recommended 1-16 based on API tier
5. **Log Interval**: Minimum 1, recommended 50-200

### Best Practices

1. **Start Conservative**: Begin with lower thresholds (0.7-0.8) and fewer workers
2. **Monitor Early**: Use `--verbose` for initial runs to understand behavior
3. **Set Daily Limits**: Use `--daily-limit` to prevent unexpected costs
4. **Log Appropriately**: Adjust `--quota-log-interval` based on batch size
5. **Test First**: Always do a `--dry-run` with new input files

## Performance Tuning

### Recommended Settings by Use Case

#### Development/Testing
```bash
--max-workers 2
--quota-threshold 0.7
--daily-limit 100
--verbose
```

#### Small Batches (< 1000 artists)
```bash
--max-workers 4
--quota-threshold 0.8
--quota-log-interval 50
```

#### Large Batches (> 10000 artists)
```bash
--max-workers 8
--quota-threshold 0.85
--quota-log-interval 200
--daily-limit 10000
--resume
```

#### Maximum Throughput
```bash
--max-workers 16
--quota-threshold 0.95
--quota-log-interval 500
```

## See Also

- [README.md](../README.md) - Main project documentation
- [MONITORING.md](MONITORING.md) - Logging and monitoring guide
- [tools/README.md](../tools/README.md) - Batch processing tools
- [plans/rate_limit_implementation_plan.md](../plans/rate_limit_implementation_plan.md) - Implementation details