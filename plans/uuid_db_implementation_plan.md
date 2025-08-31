# UUID + Database Implementation Plan

## 📊 Implementation Progress
**Overall Completion: ~70% (6/10 phases completed, Phase 4 partially complete)**

### ✅ **Completed Phases (6/10):**
- Phase 1: Dependencies & Configuration
- Phase 2: Data Structure Updates  
- Phase 3: Input Parsing Updates
- Phase 8: Testing & Validation (Partial - UUID/CSV parts + database function tests)

### 🔄 **In Progress:**
- **Phase 4: Database Integration** - 4/10 tasks completed (connection management, configuration, write operations, API integration)
- All tests now passing (107/107) with UUID-based data structures + 19 new database function tests
- Core database infrastructure complete and ready for remaining integration work

### 🚧 **Remaining Work:**
- Phase 4: Complete remaining 6 tasks (write modes, health monitoring, test database setup)
- Phase 5: CLI Argument Updates (Database-related flags)
- Phase 6: Processing Logic Updates (Database write integration in concurrent processing)
- Phase 7: Output Format Updates (Database status reporting)

## Overview
Transform `run_artists.py` to work with UUID-based artist IDs and persist generated bios to PostgreSQL database.

## Current State Analysis
- ✅ Existing: CSV parsing, OpenAI API calls, concurrent processing, JSONL output
- ✅ **NEW**: UUID support, CSV format validation, comprehensive test coverage
- 🔄 Still missing: Database connectivity, bio persistence
- 🔄 Needs completion: Database integration, CLI arguments, write modes

## Implementation Tasks

### Phase 1: Dependencies & Configuration
**Priority: High | Estimated Time: 1-2 hours** ✅ **COMPLETED**

#### Task 1.1: Add Database Dependencies
- ✅ Add `psycopg3[binary]` to `requirements.txt`
- ✅ Update `.env.example` with `DATABASE_URL` template
- ✅ Document database connection requirements in README

#### Task 1.2: Environment Variable Support
- ✅ Add `DATABASE_URL` environment variable handling
- ✅ Update environment variable validation logic
- ✅ Note: Model selection will use server defaults, no client-side model selection needed

### Phase 2: Data Structure Updates
**Priority: High | Estimated Time: 2-3 hours** ✅ **COMPLETED**

#### Task 2.1: Update ArtistData Class
- ✅ **COMPLETED** - Updated to include `artist_id` UUID field
```python
class ArtistData(NamedTuple):
    artist_id: str  # UUID string
    name: str
    data: Optional[str] = None
```

#### Task 2.2: Update ApiResponse Class
- ✅ **COMPLETED** - Added `artist_id` and `db_status` fields
```python
class ApiResponse(NamedTuple):
    artist_id: str  # Add UUID
    artist_name: str
    artist_data: Optional[str]
    response_text: str
    response_id: str
    created: int
    db_status: Optional[str] = None  # "updated|skipped|error|null"
    error: Optional[str] = None
```

#### Task 2.3: Create Database Models
- 🔄 **PENDING** - Database classes not implemented yet
```python
class DatabaseConfig(NamedTuple):
    url: str
    pool_size: int = 5
    max_overflow: int = 10

class DatabaseResult(NamedTuple):
    success: bool
    rows_affected: int
    error: Optional[str] = None
```

### Phase 3: Input Parsing Updates
**Priority: High | Estimated Time: 2-3 hours** ✅ **COMPLETED**

#### Task 3.1: Update CSV Parser
- ✅ Modify `parse_input_file()` to handle `artist_id,artist_name,artist_data` format
- ✅ Add UUID validation for `artist_id` field
- ✅ Add proper CSV parsing with `csv` module (quote-aware)
- ✅ Handle optional header row
- ✅ Note: No backward compatibility - only support new UUID format

#### Task 3.2: Input Validation
- ✅ Validate UUID format for `artist_id`
- ✅ Ensure `artist_name` is non-empty
- ✅ Handle empty `artist_data` gracefully
- ✅ Add comprehensive error reporting for invalid input

#### Task 3.3: Update Example Files
- ✅ Replace `example_artists.csv` with new UUID format
- ✅ Add sample data with various UUID formats
- ✅ Create test data for validation scenarios

### Phase 4: Database Integration
**Priority: High | Estimated Time: 6-8 hours** 🔄 **PARTIALLY COMPLETED (4/10 tasks)**

#### Task 4.1: Database Connection Management ✅ **COMPLETED**
- ✅ Implement connection pool creation function
- ✅ Implement get/close connection functions  
- ✅ Add connection pool constants and defaults
```python
def create_db_connection_pool(config: DatabaseConfig) -> psycopg3.Pool
def get_db_connection(pool: psycopg3.Pool) -> psycopg3.Connection
def close_db_connection_pool(pool: psycopg3.Pool) -> None

# Sensible defaults for connection pooling
DEFAULT_POOL_SIZE = 4  # Match default worker count
DEFAULT_MAX_OVERFLOW = 8  # Allow burst connections
DEFAULT_CONNECTION_TIMEOUT = 30  # seconds
DEFAULT_QUERY_TIMEOUT = 60  # seconds
```

#### Task 4.2: Database Configuration Management ✅ **COMPLETED**
- ✅ Implement `DatabaseConfig` and `DatabaseResult` classes from Phase 2.3
- ✅ Add database URL parsing and validation
- ✅ Handle connection string parameter validation
- ✅ Add environment-based configuration (production vs test)

#### Task 4.3: Database Write Operations ✅ **COMPLETED**
- ✅ Implement get_table_name function for dynamic table selection
- ✅ Add error classification (permanent, transient, systemic)
- ✅ Add retry decorator with exponential backoff
- ✅ Implement update_artist_bio function with retry logic
```python
@retry_with_exponential_backoff(max_retries=3)
def update_artist_bio(
    connection: psycopg3.Connection,
    artist_id: str,
    bio: str,
    skip_existing: bool = False,
    test_mode: bool = False,
    worker_id: str = "main"
) -> DatabaseResult

# Error handling strategy:
# - Permanent errors (invalid UUID, constraint violations): Skip and log
# - Transient errors (connection timeout, deadlock): Retry with backoff
# - Systemic errors (auth failure, schema issues): Abort processing
```

#### Task 4.4: Integration with Existing Processing Flow ✅ **COMPLETED**
- ✅ Modify `call_openai_api()` to call database write operations
- ✅ Update `ApiResponse` objects with database write results (`db_status` field)
- ✅ Handle database failures without stopping API processing
- ✅ Integrate database operations into the concurrent processing pipeline

#### Task 4.5: Write Mode Logic
- [ ] Implement `--write-mode {db,file,both}` logic
- [ ] Add `--skip-existing` flag behavior
- [ ] Handle database connection failures gracefully
- [ ] Add database transaction management
- [ ] Implement file-only mode (existing behavior)
- [ ] Implement database-only mode (skip JSONL output)
- [ ] Implement both mode (database + JSONL simultaneously)
- [ ] Handle partial failures in "both" mode

#### Task 4.6: Database Health Monitoring
- [ ] Add connection health checks
- [ ] Implement connection recovery after failures
- [ ] Add database operation metrics/logging
- [ ] Handle database connection pool exhaustion

#### Task 4.7: Test Database Schema Management
- [ ] Create `test_artists` table with same schema as production (`id UUID, name TEXT, bio TEXT`)
- [ ] Add database setup scripts for development/testing
- [ ] Implement test table creation/teardown in test suite
- [ ] Add environment-based table selection (production uses `artists`, tests use `test_artists`)

#### Task 4.8: Development Database Configuration
- [ ] Add test database connection configuration
- [ ] Implement table name selection based on environment/mode
- [ ] Add test data seeding for development
- [ ] Create database cleanup utilities for tests

#### Task 4.9: Test-Specific Database Operations
- [ ] Modify SQL queries to use configurable table name
- [ ] Add test database reset/cleanup functions
- [ ] Implement isolated test transactions (rollback after tests)
- [ ] Add test database connection validation

#### Task 4.10: SQL Query Implementation
```python
# Configurable table name based on environment
def get_table_name(test_mode: bool = False) -> str:
    return "test_artists" if test_mode else "artists"

# Updated SQL queries with dynamic table names
```
```sql
-- Default (force overwrite) - dynamic table name
UPDATE {table_name} SET bio = $2 WHERE id = $1;

-- Skip existing - dynamic table name
UPDATE {table_name} SET bio = $2 WHERE id = $1 AND bio IS NULL;
```

### Phase 5: CLI Argument Updates
**Priority: Medium | Estimated Time: 1-2 hours** 🚧 **PENDING**

#### Task 5.1: Add New Arguments
- [ ] `--db-url STRING` (default: `DATABASE_URL` env var)
- [ ] `--write-mode {db,file,both}` (default: `db`)
- [ ] `--skip-existing` (flag)
- [ ] Note: Model selection removed - will use server defaults

#### Task 5.2: Update Existing Arguments
- [ ] Modify `--input-file` help text for new format
- [ ] Update `--output` behavior for different write modes
- [ ] Enhance `--dry-run` to show database operations

#### Task 5.3: Argument Validation
- [ ] Validate `--write-mode` choices
- [ ] Validate `--db-url` format
- [ ] Add mutual exclusivity checks where needed
- [ ] Remove model validation (using server defaults)

### Phase 6: Processing Logic Updates
**Priority: High | Estimated Time: 3-4 hours** 🚧 **PENDING**

#### Task 6.1: Update Concurrent Processing
- [ ] Modify `process_artists_concurrent()` to handle database writes
- [ ] Add database connection pool management
- [ ] Implement write mode logic in processing loop
- [ ] Add database error handling and retries

#### Task 6.2: Update API Response Handling
- [ ] Modify `call_openai_api()` to return artist_id
- [ ] Add database write status to response tracking
- [ ] Update progress logging to include database operations

#### Task 6.3: Enhanced Error Handling
- [ ] Add database-specific error types
- [ ] Implement database retry logic
- [ ] Add connection pool error recovery
- [ ] Update error reporting in JSONL output

### Phase 7: Output Format Updates
**Priority: Medium | Estimated Time: 2-3 hours** 🚧 **PENDING**

#### Task 7.1: Update JSONL Output Schema
```json
{
  "artist_id": "uuid",
  "artist_name": "...",
  "artist_data": "...",
  "response_text": "...",
  "response_id": "...",
  "db_status": "updated|skipped|error|null",
  "error": null
}
```
Note: Removed "model" field since using server defaults

#### Task 7.2: Write Mode Output Logic
- [ ] Handle `--write-mode file` (existing JSONL behavior)
- [ ] Handle `--write-mode db` (database only, minimal JSONL)
- [ ] Handle `--write-mode both` (database + full JSONL simultaneously)

#### Task 7.3: Dry Run Enhancements
- [ ] Show database update previews
- [ ] Display connection pool configuration
- [ ] Preview SQL queries for first 5 artists

### Phase 8: Testing & Validation
**Priority: High | Estimated Time: 4-6 hours** ✅ **PARTIALLY COMPLETED**

#### Task 8.1: Unit Tests
- ✅ Test UUID validation logic
- ✅ Test new CSV parsing format
- 🔄 Test database connection management (pending database implementation)
- 🔄 Test write mode logic (pending database implementation)
- ✅ Test error handling scenarios

#### Task 8.2: Integration Tests
- 🔄 Create test database schema (`test_artists` table) (moved to Phase 4.7)
- 🔄 Test with real database using test schema (pending)
- 🔄 Test concurrent database operations (pending)
- 🔄 Test retry logic for database failures (pending)
- 🔄 Test different write modes (pending)
- 🔄 Test error handling (permanent, transient, systemic) (pending)
- 🔄 Test table name selection (production vs test) (pending)

#### Task 8.3: End-to-End Tests
- ✅ Test complete workflow with sample data (file mode)
- 🔄 Test performance with large datasets (1000+ artists) (pending)
- 🔄 Test error recovery scenarios (pending)
- 🔄 Test database connection failure recovery (pending)

### Phase 9: Documentation & Examples
**Priority: Medium | Estimated Time: 2-3 hours**

#### Task 9.1: Update Documentation
- [ ] Update README with new usage examples
- [ ] Document database setup requirements
- [ ] Add troubleshooting guide for database issues
- [ ] Update CLI help text and examples

#### Task 9.2: Create Examples
- [ ] Create sample UUID CSV files
- [ ] Add database setup scripts
- [ ] Add performance tuning examples

### Phase 10: Deployment Preparation
**Priority: Medium | Estimated Time: 1 hour**

#### Task 10.1: Deployment Preparation
- [ ] Update deployment scripts
- [ ] Add database schema setup scripts
- [ ] Update environment configuration

## Technical Considerations

### Database Connection Management
- Use connection pooling for concurrent operations
- Implement proper connection lifecycle management
- Add connection health checks
- Handle connection timeouts gracefully

### Error Handling Strategy
- Database errors should not stop processing other artists
- Implement exponential backoff for database retries
- Log database errors separately from API errors
- Provide clear error messages for troubleshooting

### Performance Considerations
- Database writes should be batched where possible
- Connection pool size should match worker count
- Add database query performance monitoring
- Consider read replicas for large datasets

### Security Considerations
- Validate all UUID inputs to prevent injection
- Use parameterized queries exclusively
- Secure database connection strings
- Add audit logging for database operations

## Risk Mitigation

### High Risk Items
1. **Database Connection Failures**: Implement robust retry logic and fallback modes
2. **UUID Validation**: Add comprehensive validation to prevent malformed data
3. **Concurrent Database Access**: Use proper transaction management and locking

### Medium Risk Items
1. **Performance Degradation**: Monitor database performance and optimize queries
2. **Data Consistency**: Implement proper error handling for partial failures
3. **Configuration Complexity**: Provide clear documentation and examples

## Success Criteria

### Functional Requirements
- ✅ Successfully parse UUID-based CSV input
- ✅ Generate artist bios using OpenAI API
- 🔄 Persist bios to PostgreSQL database (pending implementation)
- 🔄 Support all write modes (db, file, both) (pending implementation)
- 🔄 Handle database errors gracefully (pending implementation)
- ✅ Maintain concurrent processing performance

### Non-Functional Requirements
- 🔄 Process 1000+ artists without performance degradation (pending full testing)
- 🔄 Handle database connection failures without data loss (pending implementation)
- ✅ Provide comprehensive error reporting
- ✅ Support dry-run mode for testing

### Quality Requirements
- ✅ 95%+ test coverage for new functionality (UUID parsing & database functions complete)
- ✅ All existing tests continue to pass (107/107 tests passing - 88 original + 19 database tests)
- ✅ Performance within 5% of current implementation
- ✅ Clear documentation and examples
- ✅ Proper error handling and logging

## Timeline Estimate

**Total Estimated Time: 26-38 hours** *(Updated)*

- **Phase 1-2 (Dependencies & Data Structures)**: ✅ 3-5 hours *(COMPLETED)*
- **Phase 3 (Input Parsing)**: ✅ 2-3 hours *(COMPLETED)*
- **Phase 4 (Database Integration)**: 6-8 hours *(Updated - more comprehensive)*
- **Phase 5 (CLI Updates)**: 1-2 hours
- **Phase 6 (Processing Logic)**: 3-4 hours
- **Phase 7 (Output Format)**: 2-3 hours
- **Phase 8 (Testing)**: 4-6 hours
- **Phase 9 (Documentation)**: 2-3 hours
- **Phase 10 (Deployment)**: 1 hour

**Remaining Estimated Time: ~20-30 hours**

## Dependencies

### External Dependencies
- `psycopg3[binary]` - PostgreSQL adapter
- Existing OpenAI client
- Existing concurrent processing framework

### Internal Dependencies
- Current CSV parsing logic (to be modified)
- Current API calling logic (to be enhanced)
- Current error handling framework (to be extended)
- Current logging system (to be enhanced)

## Implementation Decisions Made

1. **Database Schema**: Using simplified schema from prompt (`id UUID, name TEXT, bio TEXT`)
2. **Model Selection**: Removed - will use server defaults (no client-side model selection)
3. **Write Mode Behavior**: `--write-mode both` writes to both database AND file simultaneously
4. **Database Library**: Using psycopg3 for modern async support and better performance
5. **OpenAI API**: Keeping existing API call structure unchanged

## Implementation Decisions Made (Updated)

1. **Database Schema**: Using simplified schema from prompt (`id UUID, name TEXT, bio TEXT`)
2. **Model Selection**: Removed - will use server defaults (no client-side model selection)
3. **Write Mode Behavior**: `--write-mode both` writes to both database AND file simultaneously
4. **Database Library**: Using psycopg3 for modern async support and better performance
5. **OpenAI API**: Keeping existing API call structure unchanged
6. **Backward Compatibility**: None - will only support new UUID-based CSV format
7. **Database Connection**: Use sensible defaults for connection pooling
8. **Error Handling**: Skip/log permanent errors, retry transient errors, abort on systemic errors
9. **Performance Requirements**: Target 1000+ artists/hour with <5% overhead vs current implementation
10. **Testing Database**: Create dedicated test schema for isolated testing

## Performance Recommendations

### Target Performance Metrics:
- **Throughput**: 1000+ artists processed per hour
- **Overhead**: <5% performance degradation vs current file-only implementation
- **Database Operations**: <100ms average per artist bio update
- **Concurrency**: Maintain current 4-worker default with database connection pooling
- **Memory Usage**: <50MB additional memory for database connections

### Optimization Strategies:
- Connection pooling with 4-8 connections (matching worker count)
- Batch database operations where possible
- Use prepared statements for repeated UPDATE queries
- Implement connection health checks and automatic reconnection
- Add database query performance monitoring