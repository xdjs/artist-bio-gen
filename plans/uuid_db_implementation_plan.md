# UUID + Database Implementation Plan

## Overview
Transform `run_artists.py` to work with UUID-based artist IDs and persist generated bios to PostgreSQL database.

## Current State Analysis
- ✅ Existing: CSV parsing, OpenAI API calls, concurrent processing, JSONL output
- ❌ Missing: UUID support, database connectivity, bio persistence
- 🔄 Needs modification: Input parsing, data structures, CLI arguments

## Implementation Tasks

### Phase 1: Dependencies & Configuration
**Priority: High | Estimated Time: 1-2 hours**

#### Task 1.1: Add Database Dependencies
- [ ] Add `psycopg3[binary]` to `requirements.txt`
- [ ] Update `.env.example` with `DATABASE_URL` template
- [ ] Document database connection requirements in README

#### Task 1.2: Environment Variable Support
- [ ] Add `DATABASE_URL` environment variable handling
- [ ] Update environment variable validation logic
- [ ] Note: Model selection will use server defaults, no client-side model selection needed

### Phase 2: Data Structure Updates
**Priority: High | Estimated Time: 2-3 hours**

#### Task 2.1: Update ArtistData Class
```python
class ArtistData(NamedTuple):
    artist_id: str  # UUID string
    name: str
    data: Optional[str] = None
```

#### Task 2.2: Update ApiResponse Class
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
**Priority: High | Estimated Time: 2-3 hours**

#### Task 3.1: Update CSV Parser
- [ ] Modify `parse_input_file()` to handle `artist_id,artist_name,artist_data` format
- [ ] Add UUID validation for `artist_id` field
- [ ] Add proper CSV parsing with `csv` module (quote-aware)
- [ ] Handle optional header row
- [ ] Note: No backward compatibility - only support new UUID format

#### Task 3.2: Input Validation
- [ ] Validate UUID format for `artist_id`
- [ ] Ensure `artist_name` is non-empty
- [ ] Handle empty `artist_data` gracefully
- [ ] Add comprehensive error reporting for invalid input

#### Task 3.3: Update Example Files
- [ ] Replace `example_artists.csv` with new UUID format
- [ ] Add sample data with various UUID formats
- [ ] Create test data for validation scenarios

### Phase 4: Database Integration
**Priority: High | Estimated Time: 4-5 hours**

#### Task 4.1: Database Connection Management
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

#### Task 4.2: Database Write Operations
```python
@retry_with_exponential_backoff(max_retries=3)
def update_artist_bio(
    connection: psycopg3.Connection,
    artist_id: str,
    bio: str,
    skip_existing: bool = False,
    worker_id: str = "main"
) -> DatabaseResult

# Error handling strategy:
# - Permanent errors (invalid UUID, constraint violations): Skip and log
# - Transient errors (connection timeout, deadlock): Retry with backoff
# - Systemic errors (auth failure, schema issues): Abort processing
```

#### Task 4.3: Write Mode Logic
- [ ] Implement `--write-mode {db,file,both}` logic
- [ ] Add `--skip-existing` flag behavior
- [ ] Handle database connection failures gracefully
- [ ] Add database transaction management

#### Task 4.4: SQL Query Implementation
```sql
-- Default (force overwrite)
UPDATE artists SET bio = $2 WHERE id = $1;

-- Skip existing
UPDATE artists SET bio = $2 WHERE id = $1 AND bio IS NULL;
```

### Phase 5: CLI Argument Updates
**Priority: Medium | Estimated Time: 1-2 hours**

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
**Priority: High | Estimated Time: 3-4 hours**

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
**Priority: Medium | Estimated Time: 2-3 hours**

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
**Priority: High | Estimated Time: 4-6 hours**

#### Task 8.1: Unit Tests
- [ ] Test UUID validation logic
- [ ] Test new CSV parsing format
- [ ] Test database connection management
- [ ] Test write mode logic
- [ ] Test error handling scenarios

#### Task 8.2: Integration Tests
- [ ] Create test database schema (`test_artists` table)
- [ ] Test with real database using test schema
- [ ] Test concurrent database operations
- [ ] Test retry logic for database failures
- [ ] Test different write modes
- [ ] Test error handling (permanent, transient, systemic)

#### Task 8.3: End-to-End Tests
- [ ] Test complete workflow with sample data
- [ ] Test performance with large datasets (1000+ artists)
- [ ] Test error recovery scenarios
- [ ] Test database connection failure recovery

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
- [ ] Successfully parse UUID-based CSV input
- [ ] Generate artist bios using OpenAI API
- [ ] Persist bios to PostgreSQL database
- [ ] Support all write modes (db, file, both)
- [ ] Handle database errors gracefully
- [ ] Maintain concurrent processing performance

### Non-Functional Requirements
- [ ] Process 1000+ artists without performance degradation
- [ ] Handle database connection failures without data loss
- [ ] Provide comprehensive error reporting
- [ ] Support dry-run mode for testing

### Quality Requirements
- [ ] 95%+ test coverage for new functionality
- [ ] All existing tests continue to pass
- [ ] Performance within 5% of current implementation
- [ ] Clear documentation and examples
- [ ] Proper error handling and logging

## Timeline Estimate

**Total Estimated Time: 24-34 hours**

- **Phase 1-2 (Dependencies & Data Structures)**: 3-5 hours
- **Phase 3 (Input Parsing)**: 2-3 hours  
- **Phase 4 (Database Integration)**: 4-5 hours
- **Phase 5 (CLI Updates)**: 1-2 hours
- **Phase 6 (Processing Logic)**: 3-4 hours
- **Phase 7 (Output Format)**: 2-3 hours
- **Phase 8 (Testing)**: 4-6 hours
- **Phase 9 (Documentation)**: 2-3 hours
- **Phase 10 (Deployment)**: 1 hour

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