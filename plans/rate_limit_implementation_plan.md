# Rate Limiting Implementation Plan

## Overview
Detailed implementation plan for adding sophisticated rate limiting and quota management to the artist bio generation system based on OpenAI best practices and the existing codebase architecture.

## Project Context
- **Target**: 42,888 artist bio generations
- **Current Limits**: Tier 3 (4M TPM, 5K RPM)  
- **Timeline**: 1 week implementation + processing
- **Priority**: Reliability and quota management over speed

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
- [ ] Models handle all OpenAI header fields
- [ ] Include validation for required fields
- [ ] Add helper methods for percentage calculations
- [ ] Include serialization support for persistence

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
- [ ] Parse all OpenAI rate limit headers correctly
- [ ] Handle missing headers gracefully
- [ ] Calculate accurate usage percentages
- [ ] Implement threshold checking logic
- [ ] Add comprehensive logging

### Task 1.3: Enhanced Exponential Backoff Strategy
**File**: `artist_bio_gen/api/utils.py` (MODIFY)
**Estimated Time**: 4 hours  
**Dependencies**: Task 1.2

**Modifications**:
1. **Enhance `retry_with_exponential_backoff` decorator**:
   - Add `Retry-After` header parsing
   - Different backoff strategies per error type
   - Add jitter to prevent thundering herd
   - Support quota-aware retry limits

2. **New functions**:
   ```python
   def get_enhanced_backoff_delay(attempt, error_type, retry_after=None)
   def should_retry_error(error, attempt, error_type)
   def extract_retry_after_header(response_headers)
   ```

**Current vs Enhanced Backoff**:
| Error Type | Current | Enhanced |
|------------|---------|----------|
| Rate Limit | 0.5s → 4s | 60s → 300s + jitter |
| Quota | 0.5s → 4s | 300s → 3600s + jitter |  
| Server | 0.5s → 4s | 0.5s → 4s (unchanged) |

**Acceptance Criteria**:
- [ ] Respect `Retry-After` headers when present
- [ ] Use appropriate delays for each error type
- [ ] Add 10% jitter to prevent synchronized retries
- [ ] Maintain backward compatibility
- [ ] Add comprehensive unit tests

### Task 1.4: Quota Monitor Class Implementation
**File**: `artist_bio_gen/api/quota.py` (EXTEND)
**Estimated Time**: 3 hours
**Dependencies**: Tasks 1.1, 1.2

```python
class QuotaMonitor:
    def __init__(self, daily_limit_requests=None, pause_threshold=0.8)
    def update_from_response(self, response) -> QuotaMetrics
    def should_pause(self) -> Tuple[bool, str]
    def can_resume(self) -> bool
    def get_current_metrics(self) -> QuotaMetrics
    def persist_state(self, filepath: str)
    def load_state(self, filepath: str)
```

**Acceptance Criteria**:
- [ ] Track quota usage across requests
- [ ] Implement configurable pause thresholds
- [ ] Persist quota state to disk
- [ ] Handle quota resets (daily/hourly)
- [ ] Thread-safe implementation
- [ ] Comprehensive logging

---

## Phase 2: Integration with Existing System (Days 2-3)

### Task 2.1: Integrate Header Parsing with API Calls
**File**: `artist_bio_gen/api/operations.py` (MODIFY)
**Estimated Time**: 2 hours
**Dependencies**: Tasks 1.1-1.4

**Integration Points**:
- **Line ~77**: After `client.responses.create()` call
- **Add quota monitoring**: Extract headers and update quota state
- **Add pause checks**: Check quota before making API calls

```python
# Modification in call_openai_api():
response = client.responses.create(...)
quota_metrics = quota_monitor.update_from_response(response)

if quota_monitor.should_pause()[0]:
    # Handle pause logic
    pass
```

**Acceptance Criteria**:
- [ ] Parse headers from every API response
- [ ] Update global quota state
- [ ] Log quota metrics at configured intervals
- [ ] Maintain existing functionality
- [ ] Handle errors gracefully

### Task 2.2: Add Configuration Parameters  
**Files**: 
- `artist_bio_gen/config/env.py` (MODIFY)
- `artist_bio_gen/cli/parser.py` (MODIFY)
- `artist_bio_gen/constants.py` (MODIFY)

**Estimated Time**: 2 hours
**Dependencies**: None

**New Configuration Fields**:
```python
# env.py additions:
quota_pause_threshold: float = 0.8
quota_monitoring_enabled: bool = True
quota_log_interval: int = 100
daily_request_limit: Optional[int] = None
pause_duration_hours: int = 24

# CLI parameters:
--quota-threshold: Pause threshold (default: 0.8)
--quota-monitoring: Enable/disable monitoring
--daily-limit: Set daily request limit
--pause-duration: Hours to pause when quota hit
```

**Acceptance Criteria**:
- [ ] All quota parameters configurable via CLI
- [ ] Environment variable support
- [ ] Validation of parameter ranges
- [ ] Backward compatibility maintained
- [ ] Help text for all new parameters

### Task 2.3: Implement Pause/Resume Logic in Processor
**File**: `artist_bio_gen/core/processor.py` (MODIFY)  
**Estimated Time**: 4 hours
**Dependencies**: Tasks 1.4, 2.1, 2.2

**Integration Strategy**:
1. **Add quota monitoring to processing loop** (around line 271)
2. **Implement pause detection** in `as_completed()` loop  
3. **Add resume conditions** and timing logic
4. **Preserve worker state** during pauses

```python
# Key modifications in process_artists_concurrent():
quota_monitor = QuotaMonitor(config.daily_request_limit, config.quota_pause_threshold)

# In the processing loop:
if quota_monitor.should_pause()[0]:
    # Graceful pause implementation
    logger.warning(f"PAUSING: {reason}")
    # Wait for resume conditions
    while not quota_monitor.can_resume():
        time.sleep(300)  # Check every 5 minutes
    logger.info("RESUMING: Processing continue")
```

**Acceptance Criteria**:
- [ ] Graceful pause without losing work
- [ ] Automatic resume after quota reset  
- [ ] Preserve worker thread pool during pause
- [ ] Log pause/resume events clearly
- [ ] Maintain progress tracking
- [ ] Handle interruptions gracefully

---

## Phase 3: Advanced Features & Optimization (Days 3-4)

### Task 3.1: Adaptive Concurrency Management
**File**: `artist_bio_gen/core/processor.py` (MODIFY)
**Estimated Time**: 3 hours  
**Dependencies**: Task 2.3

```python
class AdaptiveConcurrencyManager:
    def __init__(self, initial_workers=4, max_workers=16)
    def adjust_concurrency(self, success_rate, quota_usage)
    def get_recommended_workers(self, remaining_items, time_remaining)
    def should_scale_down(self, error_rate) -> bool
    def should_scale_up(self, success_rate, quota_headroom) -> bool
```

**Scaling Logic**:
- **Scale down** if error rate > 20% or quota usage > 90%
- **Scale up** if success rate > 95% and quota usage < 50%
- **Never exceed** safe concurrency limits

**Acceptance Criteria**:
- [ ] Dynamic worker adjustment based on performance
- [ ] Respect quota constraints in scaling decisions
- [ ] Configurable scaling parameters
- [ ] Smooth transitions (no abrupt changes)
- [ ] Comprehensive logging of scaling decisions

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
def log_concurrency_change(old_workers: int, new_workers: int, reason: str)
```

**Alert Thresholds**:
- **Warning**: 60% quota usage
- **Critical**: 80% quota usage  
- **Emergency**: 95% quota usage

**Acceptance Criteria**:
- [ ] Structured JSON logging for all quota events
- [ ] Configurable alert thresholds
- [ ] Clear event categorization
- [ ] Machine-readable log format

---

## Phase 4: Testing & Validation (Days 4-5)

### Task 4.1: Unit Tests for Quota Components
**Files**: 
- `tests/test_quota_monitor.py` (NEW)
- `tests/test_enhanced_backoff.py` (NEW) 
- `tests/test_header_parsing.py` (NEW)

**Estimated Time**: 4 hours
**Dependencies**: Phases 1-3

**Test Coverage**:
- [ ] Header parsing with various response formats
- [ ] Quota calculations and thresholds  
- [ ] Backoff delay calculations
- [ ] Error handling for malformed headers
- [ ] State persistence and recovery
- [ ] Thread safety of quota monitor

### Task 4.2: Integration Tests with Mock API
**File**: `tests/test_rate_limiting_integration.py` (NEW)
**Estimated Time**: 3 hours
**Dependencies**: Task 4.1

**Test Scenarios**:
- [ ] Quota threshold triggering pause
- [ ] Resume after quota reset
- [ ] Different error types and retry strategies  
- [ ] Concurrent worker behavior during pauses
- [ ] Configuration parameter validation
- [ ] Progress preservation during pauses

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
| 2 | Phase 1-2 | Tasks 1.3-1.4, 2.1 | 9h | Enhanced Backoff + Integration |
| 3 | Phase 2 | Tasks 2.2-2.3 | 6h | Configuration + Pause/Resume |
| 4 | Phase 3 | Tasks 3.1-3.3 | 7h | Advanced Features |
| 5 | Phase 4-5 | Tasks 4.1-5.3 | 8h | Testing + Documentation |

**Total Estimated Time**: 35 hours (7 hours/day for 5 days)

### Week 2: Production Processing
- **Day 6**: Final testing and deployment
- **Days 7-12**: Production processing of 42,888 artists
- **Monitoring**: Continuous quota and performance monitoring

---

## Risk Mitigation

### High Priority Risks

#### Risk: Implementation Complexity Underestimated
- **Mitigation**: Implement core quota monitoring first, advanced features second
- **Contingency**: Skip adaptive concurrency if timeline tight

#### Risk: Quota Threshold Miscalculation  
- **Mitigation**: Start with conservative 60% threshold, adjust based on testing
- **Contingency**: Manual monitoring during initial production runs

#### Risk: Performance Regression
- **Mitigation**: Comprehensive testing with performance benchmarks
- **Contingency**: Feature flags to disable quota monitoring if needed

### Medium Priority Risks

#### Risk: Configuration Complexity
- **Mitigation**: Provide sensible defaults, comprehensive documentation
- **Contingency**: Environment-specific configuration templates

#### Risk: Thread Safety Issues
- **Mitigation**: Use thread-safe data structures, comprehensive unit tests
- **Contingency**: Fallback to process-level coordination if needed

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
1. `artist_bio_gen/models/quota.py` - Quota data models
2. `artist_bio_gen/api/quota.py` - Quota monitoring logic  
3. `tests/test_quota_monitor.py` - Unit tests
4. `tests/test_enhanced_backoff.py` - Backoff tests
5. `tests/test_header_parsing.py` - Parser tests
6. `tests/test_rate_limiting_integration.py` - Integration tests
7. `docs/MONITORING.md` - Monitoring documentation

### Modified Files (7)
1. `artist_bio_gen/api/utils.py` - Enhanced backoff logic
2. `artist_bio_gen/api/operations.py` - Header parsing integration
3. `artist_bio_gen/core/processor.py` - Pause/resume + concurrency  
4. `artist_bio_gen/config/env.py` - New configuration fields
5. `artist_bio_gen/cli/parser.py` - New CLI parameters
6. `artist_bio_gen/constants.py` - Quota-related constants
7. `artist_bio_gen/utils/logging.py` - Enhanced logging

**Total**: 14 files (7 new, 7 modified)

---

## Dependencies & Prerequisites

### External Dependencies
- No new external packages required
- All functionality using existing dependencies (requests, threading, etc.)

### Internal Dependencies  
- Existing retry mechanism (`api/utils.py`)
- Worker management system (`core/processor.py`)
- Configuration system (`config/env.py`)
- Logging infrastructure (`utils/logging.py`)

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