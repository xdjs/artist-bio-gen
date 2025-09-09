# Rate Limiting & Quota Management Plan

## Project Context
- **Target**: 42,888 artist bio generations
- **Timeline**: Within 1 week
- **Current Limits**: Usage Tier 3 (4,000,000 TPM, 5,000 RPM)
- **Processing Mode**: One-time bulk processing with priority ordering
- **Current Status**: Previous run stopped at 8,180/36,831 due to quota exhaustion

## Current System Analysis

### Existing Configuration
- **Concurrent Workers**: 4 (configurable via `--max-workers`)
- **Retry Logic**: 5 attempts with exponential backoff (0.5s to 4s)
- **Actual Throughput**: ~240 requests/minute with 4 workers
- **Rate Limit Headroom**: Well within 5K RPM limit

### Issues Identified
1. **Quota Exhaustion**: Main failure point - no quota monitoring
2. **Inadequate Backoff**: Current 0.5-4s delays too aggressive for rate limits
3. **No Pause/Resume**: System continued attempting after quota exhaustion
4. **Missing Header Parsing**: Not leveraging OpenAI rate limit headers

## Recommended Strategy

### 1. Quota Monitoring System

**Implementation**: Real-time quota tracking with 80% pause threshold

```python
class QuotaMonitor:
    def __init__(self, daily_limit_requests=None, pause_threshold=0.8):
        self.daily_limit_requests = daily_limit_requests
        self.pause_threshold = pause_threshold
        self.requests_used_today = 0
        self.last_reset = datetime.now().replace(hour=0, minute=0, second=0)
        
    def update_from_headers(self, headers):
        """Parse OpenAI response headers for quota info"""
        return {
            'requests_remaining': int(headers.get('x-ratelimit-remaining-requests', 0)),
            'requests_limit': int(headers.get('x-ratelimit-limit-requests', 5000)),
            'tokens_remaining': int(headers.get('x-ratelimit-remaining-tokens', 0)),
            'tokens_limit': int(headers.get('x-ratelimit-limit-tokens', 4000000)),
            'reset_requests': headers.get('x-ratelimit-reset-requests'),
            'reset_tokens': headers.get('x-ratelimit-reset-tokens')
        }
        
    def should_pause(self, rate_limit_info):
        """Check if we should pause based on quota usage"""
        if self.daily_limit_requests:
            usage_pct = self.requests_used_today / self.daily_limit_requests
            if usage_pct >= self.pause_threshold:
                return True, f"Daily quota {usage_pct*100:.1f}% used"
                
        # Also check immediate rate limits
        req_pct = 1 - (rate_limit_info['requests_remaining'] / rate_limit_info['requests_limit'])
        if req_pct >= 0.95:  # 95% of minute limit used
            return True, f"Rate limit {req_pct*100:.1f}% used"
            
        return False, None
```

### 2. Enhanced Exponential Backoff Strategy

**OpenAI Recommendations**: Different strategies per error type with jitter

```python
def get_backoff_delay(attempt, error_type, retry_after=None):
    """Enhanced backoff following OpenAI recommendations"""
    if retry_after:
        return int(retry_after) + random.uniform(0, 5)  # Respect header + jitter
    
    if error_type == "rate_limit_exceeded":
        base_delay = 60  # 1 minute for rate limits
        max_delay = 300  # 5 minutes max
    elif error_type == "insufficient_quota":
        base_delay = 300  # 5 minutes for quota
        max_delay = 3600  # 1 hour max
    else:
        base_delay = 0.5  # Current setup for other errors
        max_delay = 4.0
    
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return delay + jitter

class AdaptiveRetryStrategy:
    def __init__(self, max_quota_retries=3, max_rate_retries=5):
        self.max_quota_retries = max_quota_retries
        self.max_rate_retries = max_rate_retries
        
    def get_retry_config(self, error_type):
        if error_type == "insufficient_quota":
            return {
                "max_retries": self.max_quota_retries,
                "base_delay": 300,  # 5 minutes
                "max_delay": 3600   # 1 hour
            }
        elif error_type == "rate_limit_exceeded":
            return {
                "max_retries": self.max_rate_retries,
                "base_delay": 60,   # 1 minute
                "max_delay": 300    # 5 minutes
            }
        else:  # server errors, etc.
            return {
                "max_retries": 3,
                "base_delay": 0.5,
                "max_delay": 4
            }
```

**Key Improvements**:
- **Respect `Retry-After` headers** when provided
- **Longer delays** for rate limits (60s vs 0.5s base)
- **Different strategies** per error type
- **10% jitter** to prevent thundering herd

### 3. Configurable Concurrency Management

**Conservative Approach**: Prioritize reliability over speed

```python
class ConcurrencyConfig:
    def __init__(self):
        self.conservative_workers = 2    # Conservative default
        self.moderate_workers = 4        # Current default  
        self.aggressive_workers = 8      # For faster processing
        self.max_safe_workers = 16       # Never exceed (5000 RPM / 300 req/min per worker)
        
    def get_recommended_workers(self, total_items, time_constraint_hours):
        """Calculate optimal workers for timeline"""
        required_rate = total_items / (time_constraint_hours * 3600)  # items per second
        workers_needed = math.ceil(required_rate / 0.75)  # ~0.75 items/sec per worker
        return min(workers_needed, self.max_safe_workers)
```

**For Current Project**:
- **Recommended**: 2-4 workers (conservative to moderate)
- **Timeline Analysis**: 42,888 artists in 168 hours = ~0.07 items/sec needed
- **Buffer**: Plenty of time, prioritize reliability over speed

### 4. HTTP Header Parsing for Real-time Tracking

**Implementation**: Extract and monitor rate limit information

```python
def parse_rate_limit_headers(response):
    """Extract and log rate limit information from OpenAI response headers"""
    headers = response.headers
    
    rate_info = {
        'requests_remaining': int(headers.get('x-ratelimit-remaining-requests', 0)),
        'requests_limit': int(headers.get('x-ratelimit-limit-requests', 5000)),
        'tokens_remaining': int(headers.get('x-ratelimit-remaining-tokens', 0)),
        'tokens_limit': int(headers.get('x-ratelimit-limit-tokens', 4000000)),
        'reset_requests': headers.get('x-ratelimit-reset-requests'),
        'reset_tokens': headers.get('x-ratelimit-reset-tokens')
    }
    
    # Log every 100 requests or when < 10% remaining
    req_pct_remaining = rate_info['requests_remaining'] / rate_info['requests_limit']
    if req_pct_remaining < 0.1:
        logger.warning(f"Rate limit warning: {req_pct_remaining*100:.1f}% requests remaining")
        
    return rate_info
```

**Benefits**:
- **Real-time visibility** into rate limit status
- **Proactive warnings** when approaching limits
- **Data-driven decisions** for pause/resume logic

### 5. Graceful Pause/Resume System

**Automatic Recovery**: Pause at 80% quota usage, resume after reset

```python
class ProcessingManager:
    def __init__(self, quota_monitor, pause_duration_hours=24):
        self.quota_monitor = quota_monitor
        self.pause_duration = pause_duration_hours * 3600  # seconds
        self.paused = False
        
    def should_pause_processing(self, rate_limit_info):
        should_pause, reason = self.quota_monitor.should_pause(rate_limit_info)
        if should_pause and not self.paused:
            logger.warning(f"PAUSING: {reason} - Resuming in {self.pause_duration/3600} hours")
            self.paused = True
            self.pause_start_time = time.time()
            return True
        return False
        
    def can_resume(self):
        if not self.paused:
            return True
        if time.time() - self.pause_start_time >= self.pause_duration:
            logger.info("RESUMING: Pause duration completed")
            self.paused = False
            return True
        return False
```

**Features**:
- **Automatic pausing** at configurable threshold
- **Resume after reset** (typically 24 hours)
- **Existing resume logic** maintains progress

## Configuration Parameters

```yaml
rate_limiting:
  # Concurrency levels
  conservative_workers: 2
  moderate_workers: 4  
  aggressive_workers: 8
  
  # Quota management
  pause_threshold: 0.8  # 80%
  daily_request_limit: null  # Set based on your plan
  pause_duration_hours: 24
  
  # Retry configuration
  quota_failure_retries: 3
  rate_limit_retries: 5
  server_error_retries: 3
  
  # Monitoring
  log_rate_limit_warnings: true
  log_quota_usage_interval: 100  # every N requests
  
  # Backoff parameters
  rate_limit_base_delay: 60      # 1 minute
  rate_limit_max_delay: 300      # 5 minutes
  quota_base_delay: 300          # 5 minutes
  quota_max_delay: 3600          # 1 hour
  backoff_jitter_percent: 0.1    # 10%
```

## Implementation Priority

1. **HTTP header parsing** (immediate rate limit visibility)
2. **Enhanced exponential backoff** (proper OpenAI compliance)
3. **Quota monitoring** (prevent quota exhaustion)  
4. **Graceful pause/resume** (automatic recovery)
5. **Configurable concurrency** (performance tuning)

## Timeline Estimates

### Processing Time Analysis
- **Conservative (2 workers)**: ~60 hours total processing time
- **Moderate (4 workers)**: ~30 hours total processing time
- **With 80% pause threshold**: Built-in safety buffer
- **Weekly timeline**: Comfortably achievable with conservative approach

### Error Recovery Time
- **Rate limit errors**: 1-5 minutes (with proper backoff)
- **Quota exhaustion**: 24 hours pause (automatic resume)
- **Server errors**: 0.5-4 seconds (existing logic)

## Risk Mitigation

### High Priority Risks
1. **Quota exhaustion during processing**
   - **Mitigation**: 80% pause threshold with 24-hour resume
   
2. **Rate limit violations**
   - **Mitigation**: Enhanced backoff with `Retry-After` header respect
   
3. **Cascading failures**
   - **Mitigation**: Different retry strategies per error type

### Medium Priority Risks
1. **Processing time overrun**
   - **Mitigation**: Conservative worker count with ample timeline buffer
   
2. **Incomplete data priority**
   - **Mitigation**: Existing resume logic maintains progress and priority order

## Success Metrics

- **Completion Rate**: 100% of 42,888 artists processed
- **Timeline Adherence**: Complete within 1 week
- **Error Rate**: < 1% permanent failures
- **Quota Efficiency**: No quota exhaustion incidents
- **Recovery Time**: < 5 minutes for rate limit errors

## Next Steps

1. **Review and approve** this strategy
2. **Implement components** in priority order
3. **Test with small batch** (100-500 artists)
4. **Deploy for full processing** with monitoring
5. **Monitor and adjust** parameters as needed