# OpenAI Responses API Implementation Plan

## Project Overview

This implementation plan details the development of `run_artists.py`, a Python script that uses the OpenAI Responses API to invoke reusable prompts for multiple artists. The script will process CSV-like input files, make concurrent API calls with retry logic, and output results in both stdout and JSONL format.

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
- [ ] Create `scripts/` directory
- [ ] Initialize `run_artists.py` with basic structure
- [ ] Create `requirements.txt` with dependencies
- [ ] Create `example_artists.csv` with sample data

### 2. CLI Argument Parser Implementation
**Priority**: High | **Estimated Time**: 45 minutes

Implement comprehensive argument parsing with argparse:

**Required Arguments**:
- [ ] `--input-file PATH` (required) - CSV-like text file path
- [ ] `--prompt-id STRING` (default from env `OPENAI_PROMPT_ID`)
- [ ] `--model STRING` (default from env `OPENAI_MODEL`, fallback `gpt-5`)
- [ ] `--version STRING` (optional) - prompt version
- [ ] `--output PATH` (default `out.jsonl`) - JSONL output file
- [ ] `--max-workers INT` (default 4) - concurrent request limit
- [ ] `--dry-run` - parse inputs and show first 5 payloads

**Implementation Details**:
- [ ] Validate file paths exist and are readable
- [ ] Handle environment variable fallbacks
- [ ] Add help text and usage examples
- [ ] Implement argument validation logic

### 3. Input File Parser
**Priority**: High | **Estimated Time**: 60 minutes

Create robust CSV-like file parser with validation:

**Features**:
- [ ] Parse UTF-8 text files with `artist_name,artist_data` format
- [ ] Skip lines starting with `#` or blank lines
- [ ] Trim whitespace from both fields
- [ ] Validate `artist_name` is non-empty (required)
- [ ] Handle optional `artist_data` field
- [ ] Log warnings for invalid lines
- [ ] Return structured data for processing

**Error Handling**:
- [ ] File not found errors
- [ ] Encoding issues
- [ ] Malformed CSV lines
- [ ] Empty artist names

### 4. OpenAI Client Integration
**Priority**: High | **Estimated Time**: 45 minutes

Implement OpenAI Responses API client:

**Core Functionality**:
- [ ] Initialize OpenAI client with API key from environment
- [ ] Implement `client.responses.create()` calls
- [ ] Handle prompt ID and version parameters
- [ ] Build variables dictionary dynamically
- [ ] Extract response data (output_text, response_id, created timestamp)

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
- [ ] INFO level logging to console
- [ ] Log each API call attempt and result
- [ ] Track processing progress
- [ ] Log warnings for skipped/invalid lines
- [ ] Final summary with statistics

**Summary Statistics**:
- [ ] Total records processed
- [ ] Successful API calls
- [ ] Failed API calls
- [ ] Skipped records (invalid input)
- [ ] Processing time

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
- [ ] Function parameter and return types
- [ ] Class attributes and methods
- [ ] Generic types for collections
- [ ] Optional types for nullable fields
- [ ] Union types for error handling

**Documentation**:
- [ ] Module-level docstring
- [ ] Function docstrings with parameters and return values
- [ ] Class docstrings with usage examples
- [ ] Inline comments for complex logic
- [ ] README with usage examples

### 11. Testing and Validation
**Priority**: High | **Estimated Time**: 90 minutes

Comprehensive testing strategy:

**Test Categories**:
- [ ] **Unit Tests**: Individual function testing
- [ ] **Integration Tests**: End-to-end workflow testing
- [ ] **Error Handling Tests**: Various failure scenarios
- [ ] **Performance Tests**: Large dataset processing
- [ ] **CLI Tests**: Argument parsing and validation

**Test Scenarios**:
- [ ] Valid input file processing
- [ ] Invalid input handling
- [ ] API failure simulation
- [ ] Network timeout scenarios
- [ ] Concurrent processing limits
- [ ] Output format validation

**Test Data**:
- [ ] Create test input files with various edge cases
- [ ] Mock OpenAI API responses
- [ ] Test with different prompt IDs and models

### 12. Dependencies and Environment Setup
**Priority**: Low | **Estimated Time**: 15 minutes

Create requirements.txt with all necessary dependencies:

**Required Packages**:
- [ ] `openai>=1.0.0` - OpenAI Python SDK
- [ ] `aiohttp>=3.8.0` - For async HTTP requests (if using asyncio)
- [ ] `tenacity>=8.0.0` - For retry logic implementation
- [ ] `python-dotenv>=1.0.0` - For environment variable management

**Optional Packages**:
- [ ] `pytest>=7.0.0` - For testing
- [ ] `pytest-asyncio>=0.21.0` - For async testing
- [ ] `black>=23.0.0` - For code formatting
- [ ] `mypy>=1.0.0` - For type checking

### 13. Example Data and Documentation
**Priority**: Low | **Estimated Time**: 30 minutes

Create example files and documentation:

**Example Files**:
- [ ] `example_artists.csv` with at least 4 sample records
- [ ] Include various data scenarios (empty artist_data, special characters)
- [ ] Add comments and blank lines to test parser

**Documentation**:
- [ ] Usage examples in docstrings
- [ ] Command-line examples
- [ ] Environment variable setup instructions
- [ ] Troubleshooting guide

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