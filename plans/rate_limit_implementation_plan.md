# Rate Limiting Implementation Plan

## Overview
Implementation plan for adding rate limiting and quota management to the artist bio generation system. Updated based on detailed codebase analysis and technical feedback review.

## Project Context
- **Target**: 42,888 artist bio generations
- **Current Limits**: Tier 3 (4M TPM, 5K RPM)
- **Timeline**: 1 week implementation + processing
- **Priority**: Reliability and quota management over speed

## Codebase Analysis Key Findings
- ❌ **No streaming API usage** - Standard `client.responses.create()` calls only
- ❌ **Basic rate limiting** - Simple exponential backoff in `api/utils.py`
- ✅ **ThreadPoolExecutor concurrency** - Uses configurable `max_workers` with worker IDs
- ✅ **Simple environment setup** - No dev/prod config differences
- ✅ **Existing retry framework** - Can be enhanced rather than replaced
- ✅ **Structured testing** - Follows `tests/api/`, `tests/core/` patterns
---

## Phase 1: Core Infrastructure (Days 1-2)

### Task 1.1: Create Quota Management Models
**File**: `artist_bio_gen/models/quota.py` (NEW)
**Estimated Time**: 2 hours
**Dependencies**: None

```python
# Implementation details:
@dataclass
class QuotaStatus:
    requests_remaining: int
    requests_limit: int
    tokens_remaining: int
    tokens_limit: int
    reset_requests: str
    reset_tokens: str
    timestamp: datetime

@dataclass
class QuotaMetrics:
    requests_used_today: int
    daily_limit: Optional[int]
    usage_percentage: float
    should_pause: bool
    pause_reason: Optional[str]

```

**Acceptance Criteria**:
- [x] Models handle all OpenAI header fields
- [x] Include validation for required fields
- [x] Add helper methods for percentage calculations
- [x] Include serialization support for persistence

### Task 1.2: Implement HTTP Header Parser
**File**: `artist_bio_gen/api/quota.py` (NEW)  
**Estimated Time**: 3 hours
**Dependencies**: Task 1.1

```python
# Key functions to implement:
def parse_rate_limit_headers(response) -> QuotaStatus
def calculate_usage_metrics(quota_status, daily_limit) -> QuotaMetrics
def should_pause_processing(quota_metrics, threshold) -> Tuple[bool, str]
```

**Acceptance Criteria**:
- [x] Parse all OpenAI rate limit headers correctly
- [x] Handle missing headers gracefully
- [x] Calculate accurate usage percentages
- [x] Implement threshold checking logic
- [x] Add comprehensive logging

### Task 1.3: Enhanced Exponential Backoff Strategy
**File**: `artist_bio_gen/api/utils.py` (MODIFY)
**Estimated Time**: 4 hours
**Dependencies**: Task 1.2

**Modifications**:
1. **Add error classification utility**:
   ```python
   def classify_error(exc) -> ErrorClassification:
       """Classify error using SDK types, status_code, and body error code"""
       # Use HTTP status + error code vs string matching
   ```

2. **Enhance `retry_with_exponential_backoff` decorator**:
   - Extract `Retry-After` from exception/HTTP response for 429/503
   - Different backoff strategies per error type
   - Add 10% jitter consistently
   - Use single backoff helper function

3. **New backoff helper**:
   ```python
   def compute_backoff(attempt, kind, retry_after, base, cap, jitter) -> float:
       """Single function used by retry decorator with consistent caps and jitter"""
   ```

**Current vs Enhanced Backoff**:
| Error Type | Current | Enhanced |
|------------|---------|----------|
| Rate Limit (429) | 0.5s → 4s | Use Retry-After or 60s → 300s + 10% jitter |
| Quota (insufficient_quota) | 0.5s → 4s | 300s → 3600s + 10% jitter |
| Server (5xx) | 0.5s → 4s | 0.5s → 4s (unchanged) |
| Network | 0.5s → 4s | 0.5s → 4s (unchanged) |

**Acceptance Criteria**:
- [x] Capture `Retry-After` from exception/HTTP response for 429/503
- [x] Map SDK exceptions and error codes precisely (429 rate limiting vs billing quota)
- [x] Use HTTP status + error code rather than string matching
- [x] Apply 10% jitter consistently
- [x] Maintain backward compatibility with existing retry logic
- [x] Add comprehensive unit tests with different SDK exception types

### Task 1.4: Quota Monitor Class Implementation
**File**: `artist_bio_gen/api/quota.py` (EXTEND)
**Estimated Time**: 4 hours
**Dependencies**: Tasks 1.1, 1.2

```python
class QuotaMonitor:
    def __init__(self, daily_limit_requests=None, pause_threshold=0.8):
        self._lock = threading.Lock()  # Thread safety for concurrent workers

    def update_from_response(self, headers, usage_stats) -> QuotaMetrics
    def should_pause(self) -> Tuple[bool, str]
    def can_resume(self) -> bool
    def get_current_metrics(self) -> QuotaMetrics
    def persist_state(self, filepath: str)  # Atomic writes (temp + rename)
    def load_state(self, filepath: str)

class PauseController:
    def __init__(self):
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused

    def pause(self, reason: str):
    def resume_at(self, timestamp: float):
    def wait_if_paused(self):
    def is_paused(self) -> bool
```

**Acceptance Criteria**:
- [x] Track quota usage across requests
- [x] Implement configurable pause thresholds
- [x] Persist quota state to disk
- [x] Handle quota resets (daily/hourly)
- [x] Thread-safe implementation
- [x] Comprehensive logging

---

## Phase 2: Integration with Existing System (Days 2-3)

### Task 2.1: Integrate Raw Response Access for Header Parsing
**File**: `artist_bio_gen/api/operations.py` (MODIFY)
**Estimated Time**: 3 hours
**Dependencies**: Tasks 1.1-1.4

**Critical Change**: Use `with_raw_response` to access headers

**Integration Points**:
- **Line ~77**: Replace `client.responses.create()` with raw response wrapper
- **Add quota monitoring**: Extract headers and update quota state
- **Add pause checks**: Check quota before making API calls

```python
# Modification in call_openai_api():
# OLD: response = client.responses.create(prompt=prompt_config)
# NEW:
raw_response = client.responses.with_raw_response.create(prompt=prompt_config)
response = raw_response.parse()
headers = raw_response.headers

# Extract usage from response body (not just headers)
usage_stats = getattr(response, 'usage', None)
quota_metrics = quota_monitor.update_from_response(headers, usage_stats)

# Check pause controller before continuing
pause_controller.wait_if_paused()
```

**Acceptance Criteria**:
- [x] Parse headers from every API response
- [x] Update global quota state
- [x] Log quota metrics at configured intervals
- [x] Maintain existing functionality
- [x] Handle errors gracefully

### Task 2.2: Add Configuration Parameters
**Files**:
- Environment variables and CLI parameters
- Update `.env.example` with new variables

**Estimated Time**: 2 hours
**Dependencies**: None

**New Configuration Fields**:
```python

# Environment variables:
QUOTA_MONITORING=true  # Default enabled for all environments
QUOTA_THRESHOLD=0.8
DAILY_REQUEST_LIMIT=null  # Optional daily budget
PAUSE_DURATION_HOURS=24
QUOTA_LOG_INTERVAL=100

# CLI parameters:
--quota-threshold: Pause threshold (default: 0.8)
--quota-monitoring: Enable/disable monitoring (default: true)
--daily-limit: Set daily request limit (optional)
--pause-duration: Hours to pause when quota hit (default: 24)
```

**Acceptance Criteria**:
- [x] All quota parameters configurable via CLI and environment variables
- [x] Default monitoring enabled (no dev/prod differences)
- [x] Validation ranges: threshold 0.1-1.0, pause_duration 1-72 hours
- [x] Update `.env.example` with documentation
- [x] Backward compatibility maintained
- [x] Help text for all new parameters

### Task 2.3: Implement Pause/Resume Logic in Processor
**File**: `artist_bio_gen/core/processor.py` (MODIFY)
**Estimated Time**: 5 hours
**Dependencies**: Tasks 1.4, 2.1, 2.2

**Integration Strategy**:
1. **Add pause controller to ThreadPoolExecutor** (around line where executor is created)
2. **Gate task submission** with pause event
3. **Let in-flight tasks finish** during pause
4. **Use computed resume time** from headers vs fixed 24h

```python
# Key modifications in process_artists_concurrent():
quota_monitor = QuotaMonitor(config.daily_request_limit, config.quota_pause_threshold)
pause_controller = PauseController()

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    for i, artist in enumerate(artists):
        # Gate new task submission
        pause_controller.wait_if_paused()

        worker_id = f"W{i % max_workers + 1:02d}"
        future = executor.submit(
            call_openai_api_with_pause_check,
            client, artist, prompt_id, version, worker_id,
            db_pool, skip_existing, test_mode, pause_controller
        )
        # Store future mapping...
```

**Acceptance Criteria**:
- [x] Graceful pause without losing work
- [x] Automatic resume after quota reset
- [x] Preserve worker thread pool during pause
- [x] Log pause/resume events clearly
- [x] Maintain progress tracking
- [x] Handle interruptions gracefully

---

## Phase 3: Advanced Features & Optimization (Days 3-4)

### Task 3.1: Adaptive Concurrency Management (OPTIONAL)
**File**: `artist_bio_gen/core/processor.py` (MODIFY)
**Estimated Time**: 3 hours
**Dependencies**: Task 2.3
**Status**: Ship behind feature flag, default OFF

```python
class AdaptiveConcurrencyManager:
    def __init__(self, initial_workers=4, max_workers=16, enabled=False):
        self.enabled = enabled  # Default disabled for stability

    def adjust_concurrency(self, success_rate, quota_usage)
    def get_recommended_workers(self, remaining_items, time_remaining)
    def should_scale_down(self, error_rate) -> bool
    def should_scale_up(self, success_rate, quota_headroom) -> bool
```

**Implementation Note**:
Feedback suggests deferring this complexity. Focus on stable core implementation first.

**Acceptance Criteria**:
- [ ] Behind feature flag (ADAPTIVE_CONCURRENCY_ENABLED=false)
- [ ] Conservative default behavior when disabled
- [ ] Comprehensive logging when enabled
- [ ] Consider deferring until after initial deployment

### Task 3.2: Priority Queue Enhancement
**File**: `artist_bio_gen/core/processor.py` (MODIFY)
**Estimated Time**: 2 hours
**Dependencies**: Task 3.1

**Enhancements**:
- **Retry queue**: Separate queue for failed items
- **Priority handling**: Respect existing order (high priority first)
- **Quota-aware scheduling**: Pause low priority items when quota limited

**Acceptance Criteria**:
- [ ] Failed items queued for retry
- [ ] Priority order maintained  
- [ ] Configurable retry delays
- [ ] Clear separation of queues in logging

### Task 3.3: Enhanced Monitoring & Alerting
**File**: `artist_bio_gen/utils/logging.py` (MODIFY)
**Estimated Time**: 2 hours
**Dependencies**: Task 1.4

**New Logging Functions**:
```python
def log_quota_metrics(quota_metrics: QuotaMetrics, worker_id: str)
def log_pause_event(reason: str, resume_time: datetime)
def log_resume_event(duration_paused: int, quota_status: QuotaStatus)
def log_rate_limit_event(error_type: str, retry_after: int, worker_id: str)
```

**Alert Thresholds & Rate-limited Logging**:
- **Warning**: 60% quota usage
- **Critical**: 80% quota usage
- **Emergency**: 95% quota usage
- **Rate-limited**: Log every N requests or threshold crossings to prevent spam

**Acceptance Criteria**:
- [x] Structured JSON logging for all quota events
- [x] Rate-limited logging to prevent spam under load
- [x] Clear event categorization
- [x] Fits existing logging utilities pattern

---

## Phase 4: Testing & Validation (Days 4-5)

### Task 4.1: Unit Tests for Quota Components ✅ COMPLETED
**Files** (Following existing test structure):
- `tests/api/test_quota_headers.py` (NEW)
- `tests/api/test_enhanced_backoff.py` (NEW)
- `tests/models/test_quota_models.py` (NEW)
- `tests/core/test_pause_resume.py` (NEW)

**Estimated Time**: 4 hours
**Dependencies**: Phases 1-3

**Test Coverage**:
- [x] Mock `with_raw_response` objects exposing `headers` and `parse().usage`
- [x] Header parsing (missing/zero/units), handle None gracefully
- [x] Backoff calculations with different error types
- [x] Thread safety under concurrency
- [x] State persistence with atomic writes
- [x] All tests offline with mocked SDK responses

**Completion Notes**: All test files reviewed and verified. 59 quota-specific tests passing, 293 total tests passing.

### Task 4.2: Integration Tests with Mock API ✅ COMPLETED
**File**: `tests/integration/test_rate_limiting_integration.py` (NEW)
**Estimated Time**: 3 hours
**Dependencies**: Task 4.1

**Test Scenarios**:
- [x] Quota threshold triggering pause with PauseController
- [x] Resume from computed header times vs fixed 24h
- [x] Different SDK exception types and retry strategies
- [x] ThreadPoolExecutor behavior during pause events
- [x] Configuration parameter validation
- [x] Progress preservation during pauses
- [x] Non-streaming response path coverage (no streaming in codebase)

**Completion Notes**: All integration tests created and passing. 17 new integration tests covering all scenarios, 310 total tests passing.

### Task 4.3: Small Batch Testing (100 Artists)
**Estimated Time**: 2 hours
**Dependencies**: Tasks 4.1, 4.2

**Test Plan**:
1. **Process 100 artists** with quota monitoring enabled
2. **Verify logging** shows quota tracking
3. **Simulate quota threshold** (set low limit)  
4. **Test pause/resume** functionality
5. **Validate configuration** parameters work correctly

**Acceptance Criteria**:
- [ ] All 100 artists processed successfully
- [ ] Quota monitoring logs appear as expected
- [ ] Pause/resume works without data loss
- [ ] Performance within expected ranges
- [ ] No regression in existing functionality

---

## Phase 5: Documentation & Deployment (Day 5)

### Task 5.1: Update Configuration Documentation
**Files**:
- `README.md` (MODIFY)
- `docs/CONFIGURATION.md` (NEW/MODIFY)

**Estimated Time**: 1 hour

**Documentation Updates**:
- [ ] New command-line parameters
- [ ] Configuration file options  
- [ ] Quota monitoring explanation
- [ ] Troubleshooting guide
- [ ] Performance tuning recommendations

### Task 5.2: Update Monitoring Documentation  
**File**: `docs/MONITORING.md` (NEW/MODIFY)
**Estimated Time**: 1 hour

**Content**:
- [ ] Log format changes
- [ ] Quota alert interpretations
- [ ] Dashboard setup recommendations
- [ ] Common error scenarios and solutions

### Task 5.3: Production Deployment Checklist
**File**: `plans/DEPLOYMENT_CHECKLIST.md` (NEW)
**Estimated Time**: 1 hour

**Checklist Items**:
- [ ] Configuration validation
- [ ] Test run with 1000 artists
- [ ] Monitoring setup verification  
- [ ] Rollback plan preparation
- [ ] Performance baseline establishment

---

## Implementation Timeline

### Week 1: Implementation
| Day | Phase | Tasks | Hours | Deliverables |
|-----|-------|-------|-------|--------------|
| 1 | Phase 1 | Tasks 1.1-1.2 | 5h | Models + Header Parser |
| 2 | Phase 1-2 | Tasks 1.3-1.4, 2.1 | 10h | Enhanced Backoff + Raw Response Integration |
| 3 | Phase 2 | Tasks 2.2-2.3 | 7h | Configuration + Pause/Resume with Events |
| 4 | Phase 3 | Tasks 3.2-3.3 | 4h | Core Features (Skip adaptive concurrency) |
| 5 | Phase 4-5 | Tasks 4.1-5.3 | 8h | Testing + Documentation |

**Total Estimated Time**: 34 hours (6.8 hours/day for 5 days)
**Note**: Adaptive concurrency (Task 3.1) deferred per feedback recommendation

### Week 2: Production Processing
- **Day 6**: Final testing and deployment
- **Days 7-12**: Production processing of 42,888 artists
- **Monitoring**: Continuous quota and performance monitoring

---

## Risk Mitigation

### High Priority Risks

#### Risk: Thread Safety Issues with QuotaMonitor
- **Mitigation**: Explicit `threading.Lock` usage, comprehensive concurrency tests
- **Contingency**: Process-level coordination if thread-level fails

#### Risk: SDK Raw Response Integration Complexity
- **Mitigation**: Focus on `with_raw_response` pattern, thorough testing
- **Contingency**: Fallback to existing retry mechanism without header parsing

#### Risk: Pause Mechanism Blocking Workers
- **Mitigation**: Use `threading.Event` for gating, let in-flight tasks complete
- **Contingency**: Manual pause detection if automatic fails

### Medium Priority Risks

#### Risk: Performance Regression from Header Parsing
- **Mitigation**: Benchmark with/without quota monitoring
- **Contingency**: Feature flag to disable if performance impact detected

#### Risk: Header Format Changes by OpenAI
- **Mitigation**: Robust parsing with graceful fallbacks for missing headers
- **Contingency**: Default delay strategies when headers unavailable

---

## Success Metrics

### Implementation Success
- [ ] All unit tests pass with >90% coverage
- [ ] Integration tests pass with mock API
- [ ] Small batch test (100 artists) completes successfully
- [ ] No regression in processing performance
- [ ] Configuration parameters work as documented

### Production Success  
- [ ] Process all 42,888 artists within 1 week
- [ ] Zero quota exhaustion incidents
- [ ] Error rate <1% (excluding quota-related retries)
- [ ] Automatic pause/resume functions correctly
- [ ] Comprehensive monitoring and alerting working

### Quality Metrics
- [ ] Code review approval from team
- [ ] Documentation complete and accurate
- [ ] Monitoring dashboards functional
- [ ] Rollback plan validated

---

## File Modification Summary

### New Files (7)
1. `artist_bio_gen/models/quota.py` - Quota data models with thread safety
2. `artist_bio_gen/api/quota.py` - Quota monitoring and pause controller
3. `tests/api/test_quota_headers.py` - Header parsing tests
4. `tests/api/test_enhanced_backoff.py` - Backoff strategy tests
5. `tests/models/test_quota_models.py` - Model tests
6. `tests/core/test_pause_resume.py` - Pause/resume mechanism tests
7. `tests/integration/test_rate_limiting_integration.py` - Integration tests

### Modified Files (4)
1. `artist_bio_gen/api/utils.py` - Enhanced backoff with error classification
2. `artist_bio_gen/api/operations.py` - Raw response integration for headers
3. `artist_bio_gen/core/processor.py` - PauseController integration with ThreadPoolExecutor
4. `artist_bio_gen/utils/logging.py` - Rate-limited quota logging

### Configuration Files
- `.env.example` - Updated with quota configuration variables
- Documentation updates as needed

**Total**: 11 core files (7 new, 4 modified) + configuration updates

---

## Dependencies & Prerequisites

### External Dependencies
- No new external packages required
- Uses existing `threading.Lock`, `threading.Event` for thread safety
- OpenAI SDK `with_raw_response` method (existing capability)

### Internal Dependencies
- Existing retry mechanism (`api/utils.py`) - enhanced, not replaced
- ThreadPoolExecutor system (`core/processor.py`) - integrated with pause events
- Environment variable configuration - extended
- Logging infrastructure (`utils/logging.py`) - extended

### Environment Requirements
- Python 3.8+ (existing requirement)
- OpenAI API key (existing requirement)
- Write access to log files (existing requirement)

---

## Post-Implementation Maintenance

### Monitoring Requirements
- Daily quota usage reporting
- Error rate trending  
- Performance metric tracking
- Configuration drift detection

### Maintenance Tasks
- Weekly log analysis for optimization opportunities
- Monthly quota limit evaluation
- Quarterly performance tuning
- Annual strategy review based on usage patterns

This implementation plan provides a structured approach to adding sophisticated rate limiting while maintaining system reliability and meeting the project timeline.
