# Streaming JSONL Output Implementation Plan

## Problem Statement
Currently, the artist bio generation system writes JSONL output only after all artists are processed. This approach has critical issues for large-scale processing:

- Memory usage grows linearly with number of artists
- Complete data loss if process crashes/times out  
- No progress visibility in output files
- Difficulty resuming interrupted processing
- Inaccurate logging of actual database state

## Solution Overview
Implement streaming JSONL output where each response is written immediately after successful database commit, ensuring JSONL file always reflects exact database state.

## Implementation Tasks

### Phase 1: Core Streaming Infrastructure (Priority: High)

#### Task 1.1: Refactor JSONL Writing Function
**File**: `artist_bio_gen/core/output.py`
**Estimated Time**: 2-3 hours
**Dependencies**: None

**Changes Required**:
- Create new `append_jsonl_response()` function for single response writes
- Add file locking mechanism for concurrent write safety
- Implement proper error handling for file I/O operations
- Maintain existing `write_jsonl_output()` for backward compatibility
- Add configuration for JSONL file buffering/flushing

**Acceptance Criteria**:
- Can append single response to JSONL file safely
- Handles concurrent writes without corruption
- Maintains exact same output format as current implementation
- Includes comprehensive error handling and recovery

#### Task 1.2: Modify Concurrent Processor Architecture  
**File**: `artist_bio_gen/core/processor.py`
**Estimated Time**: 3-4 hours
**Dependencies**: Task 1.1

**Changes Required**:
- Move JSONL writing inside the per-artist processing loop
- Ensure JSONL write happens after successful DB commit
- Modify return values to not accumulate all responses in memory
- Update error handling to continue processing on individual failures
- Add progress tracking with exact counts

**Acceptance Criteria**:
- JSONL entries written immediately after DB commit
- Memory usage remains constant regardless of total artist count
- Individual artist failures don't stop overall processing
- Progress logs show real-time completion status

#### Task 1.3: Update CLI Main Flow
**File**: `artist_bio_gen/cli/main.py`  
**Estimated Time**: 2 hours
**Dependencies**: Task 1.2

**Changes Required**:
- Remove the post-processing `write_jsonl_output()` call
- Update error handling and logging to reflect streaming model
- Modify statistics calculation to work with streaming approach
- Ensure cleanup handlers work correctly with streaming

**Acceptance Criteria**:
- No memory accumulation of responses
- Accurate statistics and logging
- Proper cleanup on interruption/error
- Backward compatibility maintained for all CLI options

### Phase 2: Enhanced Logging and Recovery (Priority: Medium)

#### Task 2.1: Implement Transaction-Level Logging
**File**: `artist_bio_gen/utils/logging.py` (new/enhanced)
**Estimated Time**: 2 hours  
**Dependencies**: Task 1.3

**Changes Required**:
- Add structured logging for each successful DB commit
- Include artist ID, timestamp, processing time, and status
- Log exact database transaction details
- Create recovery-friendly log format

**Acceptance Criteria**:
- Each DB commit generates a structured log entry
- Logs contain sufficient detail for crash recovery
- Log format is machine-readable for automation
- Integration with existing logging infrastructure

#### Task 2.2: Add Progress Resume Capability
**File**: `artist_bio_gen/core/parser.py` and `artist_bio_gen/cli/main.py`
**Estimated Time**: 3-4 hours
**Dependencies**: Task 2.1

**Changes Required**:
- Add `--resume` CLI flag to check existing JSONL for processed artists
- Modify input parsing to skip already-processed entries
- Update progress reporting to account for skipped entries
- Add validation to ensure JSONL and DB are in sync

**Acceptance Criteria**:
- Can resume processing from any interruption point
- Validates consistency between JSONL file and database
- Accurate progress reporting for resumed sessions
- No duplicate processing of already-completed artists

### Phase 3: Testing and Validation (Priority: High)

#### Task 3.1: Update Test Suite
**Files**: `tests/core/`, `tests/cli/`
**Estimated Time**: 4-5 hours
**Dependencies**: Tasks 1.1, 1.2, 1.3

**Changes Required**:
- Add tests for streaming JSONL functionality
- Add concurrent write safety tests
- Add interruption/recovery scenario tests
- Update existing tests to work with streaming model
- Add performance tests for large datasets

**Acceptance Criteria**:
- All existing tests pass
- New streaming functionality has comprehensive test coverage
- Performance tests validate memory usage improvements
- Edge cases (interruption, disk full, etc.) are tested

#### Task 3.2: Integration Testing with Large Dataset
**Files**: Test data and integration tests
**Estimated Time**: 2-3 hours
**Dependencies**: Task 3.1

**Changes Required**:
- Create test dataset with 1000+ artists
- Test full processing pipeline with interruptions
- Validate memory usage remains constant
- Test resume functionality with partial completions
- Verify JSONL/database consistency under all scenarios

**Acceptance Criteria**:
- Successfully processes 1000+ artists with constant memory usage
- Recovery works correctly after various interruption scenarios
- JSONL file always matches database state exactly
- Performance benchmarks meet requirements

### Phase 4: Documentation and Deployment (Priority: Medium)

#### Task 4.1: Update Documentation
**Files**: `README.md`, `AGENTS.md`, docstrings
**Estimated Time**: 2 hours
**Dependencies**: Tasks 3.1, 3.2

**Changes Required**:
- Document new streaming behavior and benefits
- Add resume functionality documentation
- Update troubleshooting guide for new error scenarios
- Add performance characteristics documentation

**Acceptance Criteria**:
- Complete documentation of new functionality
- Clear migration guide from old behavior
- Troubleshooting guide updated
- Performance expectations documented

#### Task 4.2: Backward Compatibility and Migration
**File**: Various
**Estimated Time**: 2-3 hours  
**Dependencies**: Task 4.1

**Changes Required**:
- Ensure existing scripts continue to work
- Add deprecation warnings if needed
- Provide migration tools if necessary
- Validate against existing usage patterns

**Acceptance Criteria**:
- Existing integrations continue to work unchanged
- Clear upgrade path for users
- No breaking changes in public APIs
- Migration completed successfully

## Success Metrics
- **Memory Usage**: Constant memory usage regardless of dataset size
- **Data Integrity**: JSONL file always matches database state exactly  
- **Recovery**: Can resume processing from any interruption point
- **Performance**: No significant performance degradation
- **Compatibility**: All existing functionality continues to work

## Risk Mitigation
- **File Corruption**: Atomic writes and proper file locking
- **Performance Impact**: Benchmarking at each phase
- **Breaking Changes**: Maintain backward compatibility throughout
- **Data Loss**: Comprehensive error handling and transaction logging

## Timeline Estimate
- **Phase 1**: 7-9 hours (1-2 days)
- **Phase 2**: 5-6 hours (1 day) 
- **Phase 3**: 6-8 hours (1-2 days)
- **Phase 4**: 4-5 hours (1 day)
- **Total**: 22-28 hours (4-6 days)

## Next Steps
1. Create feature branch: `feat/streaming-jsonl-output`
2. Begin with Task 1.1: Refactor JSONL Writing Function
3. Implement incrementally with testing at each stage
4. Regular commits and progress tracking via todo list