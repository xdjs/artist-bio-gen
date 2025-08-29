# OpenAI Responses API Implementation Plan

## Project Overview

This implementation plan details the development of `run_artists.py`, a Python script that uses the OpenAI Responses API to invoke reusable prompts for multiple artists. The script will process CSV-like input files, make concurrent API calls with retry logic, and output results in both stdout and JSONL format.

## 🎯 Current Status: 69% Complete (9/13 tasks)

### ✅ Completed Tasks
- **Project Structure Setup** - All files and directories created
- **CLI Argument Parser** - Full argument parsing with environment variable support
- **Input File Parser** - Robust CSV parser with validation and error handling
- **OpenAI Client Integration** - API client with proper error handling
- **Logging and Monitoring** - Comprehensive progress tracking with visual elements
- **Type Hints and Documentation** - Full type safety and comprehensive docstrings
- **Testing and Validation** - 84 test cases covering all functionality
- **Dependencies and Environment Setup** - Complete requirements.txt
- **Example Data and Documentation** - Example files and comprehensive README.md

### 🔄 In Progress
- **Error Handling and Edge Cases** - Enhanced error recovery

### ⏳ Pending Tasks
- **Concurrency Implementation** - Async processing with worker limits
- **Retry Logic with Exponential Backoff** - Resilience against API failures
- **Output Formatting and File Handling** - JSONL file output generation

## Technical Requirements Summary

- **Language**: Python 3.11+
- **API**: OpenAI Responses API (Python SDK)
- **Concurrency**: asyncio or ThreadPoolExecutor
- **Retry Policy**: Exponential backoff (0.5s, 1s, 2s, 4s, jitter)
- **Output**: JSONL format + stdout
- **CLI**: argparse with comprehensive argument handling

## Implementation Tasks

### 1. Project Structure Setup
**Priority**: High | **Estimated Time**: 30 minutes

Create the following project structure:
```
scripts/
├── run_artists.py
├── requirements.txt
├── example_artists.csv
└── README.md (optional)
```

**Deliverables**:
- [x] Create `scripts/` directory
- [x] Initialize `run_artists.py` with basic structure
- [x] Create `requirements.txt` with dependencies
- [x] Create `example_artists.csv` with sample data

### 2. CLI Argument Parser Implementation
**Priority**: High | **Estimated Time**: 45 minutes

Implement comprehensive argument parsing with argparse:

**Required Arguments**:
- [x] `--input-file PATH` (required) - CSV-like text file path
- [x] `--prompt-id STRING` (default from env `OPENAI_PROMPT_ID`)
- [x] `--model STRING` (default from env `OPENAI_MODEL`, fallback `gpt-5`)
- [x] `--version STRING` (optional) - prompt version
- [x] `--output PATH` (default `out.jsonl`) - JSONL output file
- [x] `--max-workers INT` (default 4) - concurrent request limit
- [x] `--dry-run` - parse inputs and show first 5 payloads
- [x] `--verbose` - enable debug logging

**Implementation Details**:
- [x] Validate file paths exist and are readable
- [x] Handle environment variable fallbacks
- [x] Add help text and usage examples
- [x] Implement argument validation logic

### 3. Input File Parser
**Priority**: High | **Estimated Time**: 60 minutes

Create robust CSV-like file parser with validation:

**Features**:
- [x] Parse UTF-8 text files with `artist_name,artist_data` format
- [x] Skip lines starting with `#` or blank lines
- [x] Trim whitespace from both fields
- [x] Validate `artist_name` is non-empty (required)
- [x] Handle optional `artist_data` field
- [x] Log warnings for invalid lines
- [x] Return structured data for processing

**Error Handling**:
- [x] File not found errors
- [x] Encoding issues
- [x] Malformed CSV lines
- [x] Empty artist names

### 4. OpenAI Client Integration
**Priority**: High | **Estimated Time**: 45 minutes

Implement OpenAI Responses API client:

**Core Functionality**:
- [x] Initialize OpenAI client with API key from environment
- [x] Implement `client.responses.create()` calls
- [x] Handle prompt ID and version parameters
- [x] Build variables dictionary dynamically
- [x] Extract response data (output_text, response_id, created timestamp)

**API Call Structure**:
```python
client.responses.create(
    model=MODEL,
    prompt={
        "id": PROMPT_ID,
        "version": VERSION,  # only if provided
        "variables": {
            "artist_name": "...",  # required
            "artist_data": "..."   # only if non-empty
        }
    }
)
```

### 5. Concurrency Implementation
**Priority**: Medium | **Estimated Time**: 90 minutes

Add concurrent processing with configurable worker limits:

**Options to Implement**:
- [ ] **Option A**: asyncio with aiohttp (recommended for I/O bound)
- [ ] **Option B**: ThreadPoolExecutor (simpler, good for API calls)

**Features**:
- [ ] Configurable max workers via `--max-workers`
- [ ] Queue management for large input files
- [ ] Progress tracking for long-running operations
- [ ] Graceful shutdown handling

**Implementation Considerations**:
- [ ] Rate limiting to avoid API quota issues
- [ ] Memory management for large datasets
- [ ] Error isolation (one failed request shouldn't stop others)

### 6. Retry Logic with Exponential Backoff
**Priority**: Medium | **Estimated Time**: 60 minutes

Implement robust retry mechanism:

**Retry Policy**:
- [ ] Exponential backoff: 0.5s, 1s, 2s, 4s
- [ ] Add jitter to prevent thundering herd
- [ ] Maximum 5 retry attempts
- [ ] Retry on network errors, 5xx status codes, 429 rate limits
- [ ] Don't retry on 4xx client errors

**Implementation**:
- [ ] Create retry decorator or wrapper function
- [ ] Track retry attempts and delays
- [ ] Log retry attempts for debugging
- [ ] Handle final failure after all retries exhausted

### 7. Output Formatting and File Handling
**Priority**: Medium | **Estimated Time**: 45 minutes

Implement dual output (stdout + JSONL file):

**JSONL Output Format**:
```json
{
  "artist_name": "...",
  "artist_data": "...",   // omit if empty
  "request": { "prompt_id": "...", "variables": {...} },
  "response_text": "...",
  "response_id": "...",
  "created": 1234567890,
  "error": null
}
```

**Features**:
- [ ] Print `output_text` to stdout for each successful response
- [ ] Write complete JSONL record to output file
- [ ] Handle empty `artist_data` (omit from JSON)
- [ ] Include error information for failed requests
- [ ] Ensure atomic file writes (no partial records)

### 8. Logging and Monitoring
**Priority**: Medium | **Estimated Time**: 30 minutes

Implement comprehensive logging system:

**Logging Features**:
- [x] INFO level logging to console
- [x] Log each API call attempt and result
- [x] Track processing progress
- [x] Log warnings for skipped/invalid lines
- [x] Final summary with statistics
- [x] Visual progress bars with Unicode characters
- [x] Real-time progress updates with timing
- [x] Periodic progress summaries with ETA

**Summary Statistics**:
- [x] Total records processed
- [x] Successful API calls
- [x] Failed API calls
- [x] Skipped records (invalid input)
- [x] Processing time
- [x] API calls per second
- [x] Processing efficiency metrics
- [x] Time breakdown for successful vs failed calls

### 9. Error Handling and Edge Cases
**Priority**: High | **Estimated Time**: 45 minutes

Comprehensive error handling for all scenarios:

**Error Categories**:
- [ ] **Input Errors**: Invalid files, malformed data, missing required fields
- [ ] **API Errors**: Authentication, rate limits, service unavailable
- [ ] **Network Errors**: Connection timeouts, DNS resolution
- [ ] **Output Errors**: File write permissions, disk space

**Error Recovery**:
- [ ] Graceful degradation (continue processing other records)
- [ ] Clear error messages for debugging
- [ ] Proper exit codes for different failure modes
- [ ] Cleanup on interruption (Ctrl+C)

### 10. Type Hints and Documentation
**Priority**: Medium | **Estimated Time**: 60 minutes

Add comprehensive type safety and documentation:

**Type Hints**:
- [x] Function parameter and return types
- [x] Class attributes and methods
- [x] Generic types for collections
- [x] Optional types for nullable fields
- [x] Union types for error handling

**Documentation**:
- [x] Module-level docstring
- [x] Function docstrings with parameters and return values
- [x] Class docstrings with usage examples
- [x] Inline comments for complex logic
- [x] README with usage examples

### 11. Testing and Validation
**Priority**: High | **Estimated Time**: 90 minutes

Comprehensive testing strategy:

**Test Categories**:
- [x] **Unit Tests**: Individual function testing
- [x] **Integration Tests**: End-to-end workflow testing
- [x] **Error Handling Tests**: Various failure scenarios
- [x] **Performance Tests**: Large dataset processing
- [x] **CLI Tests**: Argument parsing and validation
- [x] **Logging Tests**: Progress tracking and monitoring

**Test Scenarios**:
- [x] Valid input file processing
- [x] Invalid input handling
- [x] API failure simulation
- [x] Network timeout scenarios
- [x] Concurrent processing limits
- [x] Output format validation
- [x] Progress bar functionality
- [x] Statistics calculation

**Test Data**:
- [x] Create test input files with various edge cases
- [x] Mock OpenAI API responses
- [x] Test with different prompt IDs and models

### 12. Dependencies and Environment Setup
**Priority**: Low | **Estimated Time**: 15 minutes

Create requirements.txt with all necessary dependencies:

**Required Packages**:
- [x] `openai>=1.0.0` - OpenAI Python SDK
- [x] `aiohttp>=3.8.0` - For async HTTP requests (if using asyncio)
- [x] `tenacity>=8.0.0` - For retry logic implementation
- [x] `python-dotenv>=1.0.0` - For environment variable management

**Optional Packages**:
- [x] `pytest>=7.0.0` - For testing
- [x] `pytest-asyncio>=0.21.0` - For async testing
- [x] `black>=23.0.0` - For code formatting
- [x] `mypy>=1.0.0` - For type checking

### 13. Example Data and Documentation
**Priority**: Low | **Estimated Time**: 30 minutes

Create example files and documentation:

**Example Files**:
- [x] `example_artists.csv` with at least 4 sample records
- [x] Include various data scenarios (empty artist_data, special characters)
- [x] Add comments and blank lines to test parser

**Documentation**:
- [x] Usage examples in docstrings
- [x] Command-line examples
- [x] Environment variable setup instructions
- [x] Troubleshooting guide
- [x] Comprehensive README.md with all features

## Implementation Timeline

### Phase 1: Core Functionality (Days 1-2)
- Project structure setup
- CLI argument parser
- Input file parser
- Basic OpenAI client integration

### Phase 2: Advanced Features (Days 3-4)
- Concurrency implementation
- Retry logic
- Output formatting
- Error handling

### Phase 3: Polish and Testing (Days 5-6)
- Logging and monitoring
- Type hints and documentation
- Comprehensive testing
- Example data and final documentation

## Success Criteria

The implementation will be considered complete when:

1. **Functionality**: All CLI arguments work as specified
2. **Reliability**: Handles all error scenarios gracefully
3. **Performance**: Processes large datasets efficiently with concurrency
4. **Usability**: Clear error messages and comprehensive logging
5. **Maintainability**: Well-documented code with type hints
6. **Testing**: Comprehensive test coverage for all scenarios

## Risk Mitigation

**Potential Risks**:
- OpenAI API rate limits and quotas
- Large file processing memory issues
- Network connectivity problems
- Concurrent request limits

**Mitigation Strategies**:
- Implement proper rate limiting and retry logic
- Process files in chunks for large datasets
- Robust error handling and recovery
- Configurable concurrency limits

## Dependencies

**External Dependencies**:
- OpenAI API access and valid API key
- Python 3.11+ runtime environment
- Network connectivity for API calls
- File system write permissions for output

**Internal Dependencies**:
- Valid OpenAI prompt ID
- Properly formatted input files
- Environment variables configured correctly