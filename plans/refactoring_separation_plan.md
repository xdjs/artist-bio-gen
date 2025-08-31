# Script Refactoring & Separation of Concerns Plan

## Overview
Refactor the monolithic `run_artists.py` script into separate, focused modules following Python conventions and separation of concerns principles. Reorganize the repository structure to follow standard Python project layout.

## Current State Analysis
- ❌ **Monolithic script**: Single 900+ line file with mixed responsibilities
- ❌ **Poor separation**: Database, API, parsing, CLI, and business logic all mixed
- ❌ **Non-standard structure**: Script at root level, no proper package organization
- ❌ **Testing challenges**: Hard to test individual components in isolation
- ❌ **Maintainability issues**: Changes to one concern affect unrelated code

## Target Architecture Goals
- ✅ **Modular design**: Each module handles one specific concern
- ✅ **Python standards**: Follow PEP 8, standard project layout, proper imports
- ✅ **Testability**: Each module easily unit testable in isolation
- ✅ **Maintainability**: Changes isolated to relevant modules
- ✅ **Reusability**: Components can be imported and reused
- ✅ **Clear interfaces**: Well-defined APIs between modules

## Implementation Tasks

### Phase 1: Repository Structure Reorganization
**Priority: High | Estimated Time: 2-3 hours**

#### Task 1.1: Create Standard Python Package Structure ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/` package directory (main package)
- ✅ Create `artist_bio_gen/__init__.py` (package initialization)
- ✅ Create `artist_bio_gen/core/` (core business logic)
- ✅ Create `artist_bio_gen/database/` (database operations)
- ✅ Create `artist_bio_gen/api/` (OpenAI API interactions)
- ✅ Create `artist_bio_gen/cli/` (command-line interface)
- ✅ Create `artist_bio_gen/utils/` (utilities and helpers)
- ✅ Create `artist_bio_gen/models/` (data structures and models)

#### Task 1.2: Update Project Root Structure ✅ **COMPLETED**
- ✅ Move `run_artists.py` to `artist_bio_gen/main.py` (main entry point)
- ✅ Create new `run_artists.py` as simple wrapper script at root
- ✅ Update `requirements.txt` location and content (no changes needed)
- ✅ Move `example_artists.csv` to `examples/` directory
- ✅ Create `setup.py` for package installation
- ✅ Update `.env.example` location if needed (no changes needed)

#### Task 1.3: Update Test Structure ✅ **COMPLETED**
- ✅ Reorganize `tests/` to mirror package structure
- ✅ Create `tests/core/`, `tests/database/`, `tests/api/`, etc.
- ✅ Move existing tests to appropriate subdirectories
- ✅ Update test imports for new package structure
- ✅ Ensure all 107 tests still pass after reorganization

### Phase 2: Data Models & Structures Extraction
**Priority: High | Estimated Time: 1-2 hours**

#### Task 2.1: Extract Data Models ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/models/__init__.py`
- ✅ Create `artist_bio_gen/models/artist.py` (ArtistData, ParseResult)
- ✅ Create `artist_bio_gen/models/api.py` (ApiResponse)
- ✅ Create `artist_bio_gen/models/database.py` (DatabaseConfig, DatabaseResult)
- ✅ Create `artist_bio_gen/models/stats.py` (ProcessingStats)
- ✅ Add proper docstrings and type hints to all models

#### Task 2.2: Extract Constants ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/constants.py`
- ✅ Move exit codes, defaults, and configuration constants
- ✅ Export constants through package `__init__.py`

### Phase 3: Database Module Separation ✅ **COMPLETED**
**Priority: High | Estimated Time: 2-3 hours**

#### Task 3.1: Create Database Connection Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/database/__init__.py`
- ✅ Create `artist_bio_gen/database/connection.py`
  - ✅ `create_db_connection_pool()`
  - ✅ `get_db_connection()`
  - ✅ `close_db_connection_pool()`

#### Task 3.2: Create Database Configuration Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/database/config.py`
  - ✅ `validate_database_url()`
  - ✅ `create_database_config()`
  - ✅ `get_database_url_from_env()`

#### Task 3.3: Create Database Operations Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/database/operations.py`
  - ✅ `update_artist_bio()`
  - ✅ `get_table_name()`
  - ✅ `retry_with_exponential_backoff()` decorator

#### Task 3.4: Create Database Utils Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/database/utils.py`
- ✅ Move database-specific utility functions (`classify_database_error()`, `validate_uuid()`)
- ✅ Update imports in main.py to use new database modules

### Phase 4: API Module Separation ✅ **COMPLETED**
**Priority: High | Estimated Time: 1-2 hours**

#### Task 4.1: Create OpenAI API Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/api/__init__.py`
- ✅ Create `artist_bio_gen/api/client.py`
  - ✅ `create_openai_client()`
  - ✅ Client configuration and setup

#### Task 4.2: Create API Operations Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/api/operations.py`
  - ✅ `call_openai_api()` (core API calling logic)
  - ✅ API response handling and processing

#### Task 4.3: Create API Utils Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/api/utils.py`
  - ✅ `should_retry_error()` (error classification)
  - ✅ `calculate_retry_delay()` (exponential backoff with jitter)
  - ✅ `retry_with_exponential_backoff()` (decorator for retry logic)
  - ✅ Update imports in main.py to use new API modules

### Phase 5: Input/Output Module Separation ✅ **COMPLETED**
**Priority: High | Estimated Time: 2-3 hours**

#### Task 5.1: Create Input Parsing Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/core/__init__.py`
- ✅ Create `artist_bio_gen/core/parser.py`
  - ✅ `parse_input_file()` (CSV parsing and validation)
  - ✅ CSV parsing and validation logic
  - ✅ UUID validation integration

#### Task 5.2: Create Output Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/core/output.py`
  - ✅ `write_jsonl_output()` (JSONL output generation)
  - ✅ Output formatting and file writing

#### Task 5.3: Create Processing Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/core/processor.py`
  - ✅ `process_artists_concurrent()` (concurrent processing coordination)
  - ✅ `log_processing_start()`, `log_progress_update()`, `log_processing_summary()`
  - ✅ `create_progress_bar()`, `calculate_processing_stats()`
  - ✅ Update imports in main.py to use new core modules

### Phase 6: CLI Module Separation ✅ **COMPLETED**
**Priority: Medium | Estimated Time: 2-3 hours**

#### Task 6.1: Create Argument Parser Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/cli/__init__.py`
- ✅ Create `artist_bio_gen/cli/parser.py`
  - ✅ `create_argument_parser()` (complete CLI argument parser)
  - ✅ All CLI argument definitions and validation

#### Task 6.2: Create CLI Main Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/cli/main.py`
  - ✅ `main()` function (main application entry point)
  - ✅ High-level application flow coordination
  - ✅ `setup_logging()` (logging configuration)

#### Task 6.3: Create CLI Utils Module ✅ **COMPLETED**
- ✅ Create `artist_bio_gen/cli/utils.py`
  - ✅ `apply_environment_defaults()` (environment variable handling)
  - ✅ `_is_output_path_writable()` (path validation utility)
  - ✅ Update imports in main.py to use new CLI modules

### Phase 7: Utilities Module Separation
**Priority: Medium | Estimated Time: 1-2 hours**

#### Task 7.1: Create Logging Utils Module
- [ ] Create `artist_bio_gen/utils/__init__.py`
- [ ] Create `artist_bio_gen/utils/logging.py`
  - [ ] `setup_logging()`
  - [ ] `log_processing_start()`
  - [ ] `log_progress_update()`
  - [ ] `log_processing_summary()`

#### Task 7.2: Create General Utils Module
- [ ] Create `artist_bio_gen/utils/helpers.py`
  - [ ] `create_progress_bar()`
  - [ ] `calculate_processing_stats()`
  - [ ] Other utility functions

#### Task 7.3: Create Validation Utils Module
- [ ] Create `artist_bio_gen/utils/validation.py`
  - [ ] `_is_output_path_writable()`
  - [ ] Input validation helpers

### Phase 8: Integration & Coordination
**Priority: High | Estimated Time: 2-3 hours**

#### Task 8.1: Create Package Initialization
- [ ] Update `artist_bio_gen/__init__.py` with proper exports
- [ ] Define public API for the package
- [ ] Set package version and metadata

#### Task 8.2: Update Main Entry Point
- [ ] Refactor `artist_bio_gen/main.py` to coordinate modules
- [ ] Import and wire together all separated components
- [ ] Maintain existing CLI interface and behavior

#### Task 8.3: Create Simple Runner Script
- [ ] Create new minimal `run_artists.py` at root
- [ ] Import and call main from package
- [ ] Maintain backward compatibility for existing usage

### Phase 9: Testing & Validation
**Priority: High | Estimated Time: 3-4 hours**

#### Task 9.1: Update Test Imports
- [ ] Update all existing tests for new module structure
- [ ] Fix import statements in all test files
- [ ] Ensure test isolation with new module boundaries

#### Task 9.2: Add Module-Specific Tests
- [ ] Create tests for each new module in isolation
- [ ] Test module interfaces and public APIs
- [ ] Add integration tests for module interactions

#### Task 9.3: Validate Existing Functionality
- [ ] Ensure all 107 existing tests pass
- [ ] Run full integration tests with sample data
- [ ] Verify CLI interface remains unchanged
- [ ] Test backward compatibility

### Phase 10: Documentation & Polish
**Priority: Medium | Estimated Time: 2-3 hours**

#### Task 10.1: Update Documentation
- [ ] Update README with new package structure
- [ ] Document module responsibilities and interfaces
- [ ] Add import examples for using as library
- [ ] Update AGENTS.md with new structure

#### Task 10.2: Add Module Documentation
- [ ] Add comprehensive docstrings to all modules
- [ ] Document public APIs and interfaces
- [ ] Add usage examples for each module

#### Task 10.3: Code Quality Improvements
- [ ] Run `black` formatting on all modules
- [ ] Run `mypy` type checking on all modules
- [ ] Ensure consistent code style across modules
- [ ] Add `__all__` declarations where appropriate

## Target Package Structure

```
artist-bio-gen/
├── artist_bio_gen/                 # Main package
│   ├── __init__.py                 # Package initialization & public API
│   ├── main.py                     # Main entry point (refactored run_artists.py)
│   ├── constants.py                # Constants and configuration
│   ├── api/                        # OpenAI API interactions
│   │   ├── __init__.py
│   │   ├── client.py               # Client creation and configuration
│   │   ├── operations.py           # API calling logic
│   │   └── utils.py                # API utilities
│   ├── cli/                        # Command-line interface
│   │   ├── __init__.py
│   │   ├── parser.py               # Argument parsing
│   │   ├── main.py                 # CLI main function
│   │   └── utils.py                # CLI utilities
│   ├── core/                       # Core business logic
│   │   ├── __init__.py
│   │   ├── parser.py               # CSV input parsing
│   │   ├── processor.py            # Main processing logic
│   │   └── output.py               # Output generation
│   ├── database/                   # Database operations
│   │   ├── __init__.py
│   │   ├── connection.py           # Connection management
│   │   ├── config.py               # Database configuration
│   │   ├── operations.py           # Database operations
│   │   └── utils.py                # Database utilities
│   ├── models/                     # Data structures
│   │   ├── __init__.py
│   │   ├── artist.py               # Artist-related models
│   │   ├── api.py                  # API response models
│   │   ├── database.py             # Database models
│   │   └── stats.py                # Statistics models
│   └── utils/                      # Utilities and helpers
│       ├── __init__.py
│       ├── logging.py              # Logging utilities
│       ├── helpers.py              # General helpers
│       └── validation.py           # Validation utilities
├── tests/                          # Test suite (mirrors package structure)
│   ├── api/
│   ├── cli/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── utils/
│   └── integration/                # Integration tests
├── examples/                       # Example files
│   └── example_artists.csv
├── plans/                          # Planning documents
├── run_artists.py                  # Simple entry point wrapper
├── setup.py                       # Package installation
├── requirements.txt               # Dependencies
├── .env.example                   # Environment template
├── README.md                      # Main documentation
└── AGENTS.md                      # Agent instructions
```

## Module Responsibilities

### `artist_bio_gen.models.*`
- **Responsibility**: Data structures and type definitions
- **Dependencies**: None (pure data classes)
- **Exports**: All model classes (ArtistData, ApiResponse, etc.)

### `artist_bio_gen.database.*`
- **Responsibility**: All database-related operations
- **Dependencies**: models, utils.logging
- **Exports**: Connection management, operations, configuration

### `artist_bio_gen.api.*` 
- **Responsibility**: OpenAI API interactions
- **Dependencies**: models, utils.logging  
- **Exports**: Client creation, API calling operations

### `artist_bio_gen.core.*`
- **Responsibility**: Core business logic (parsing, processing, output)
- **Dependencies**: models, api, database, utils
- **Exports**: Main processing functions

### `artist_bio_gen.cli.*`
- **Responsibility**: Command-line interface and argument handling
- **Dependencies**: core, constants
- **Exports**: Argument parsing, main CLI function

### `artist_bio_gen.utils.*`
- **Responsibility**: Cross-cutting utilities (logging, validation, helpers)
- **Dependencies**: models, constants
- **Exports**: Logging setup, validation functions, helpers

## Benefits of This Refactoring

### Maintainability
- **Single Responsibility**: Each module has one clear purpose
- **Loose Coupling**: Modules depend on interfaces, not implementations
- **Change Isolation**: Modifications affect only relevant modules

### Testability
- **Unit Testing**: Each module can be tested in isolation
- **Mocking**: Clean interfaces make mocking dependencies easy
- **Test Organization**: Tests mirror code structure

### Reusability
- **Library Usage**: Package can be imported and used programmatically
- **Component Reuse**: Individual modules can be used independently
- **API Access**: Clean public interfaces for external usage

### Code Quality
- **Type Safety**: Better type hints and mypy checking
- **Documentation**: Module-level documentation and examples  
- **Standards Compliance**: Follows Python packaging conventions

## Migration Strategy

### Phase Approach
1. **Structure First**: Set up package structure without breaking existing functionality
2. **Extract Gradually**: Move code piece by piece, maintaining tests
3. **Integrate Carefully**: Wire modules together while preserving behavior
4. **Validate Continuously**: Ensure tests pass at each step

### Backward Compatibility
- **CLI Interface**: Maintain exact same command-line behavior
- **File Locations**: Keep important files accessible
- **Import Paths**: Provide compatibility imports if needed

### Risk Mitigation
- **Incremental Changes**: Small, testable changes at each step  
- **Test-Driven**: All 107 tests must pass throughout refactoring
- **Rollback Ready**: Each commit should be a stable checkpoint

## Success Criteria

### Functional Requirements
- [ ] All 107 existing tests continue to pass
- [ ] CLI interface remains exactly the same
- [ ] All existing functionality preserved
- [ ] Performance maintained or improved

### Quality Requirements  
- [ ] Each module has single, clear responsibility
- [ ] Clean interfaces between modules
- [ ] Comprehensive module documentation
- [ ] Type hints throughout codebase
- [ ] Code passes `black` and `mypy` checks

### Architectural Requirements
- [ ] Follows standard Python package layout
- [ ] Clear separation of concerns achieved
- [ ] Modules can be tested in isolation
- [ ] Package can be imported and used as library
- [ ] Dependencies flow in correct direction (no circular imports)

## Timeline Estimate

**Total Estimated Time: 18-26 hours**

- **Phase 1 (Structure)**: 2-3 hours
- **Phase 2 (Models)**: 1-2 hours  
- **Phase 3 (Database)**: 2-3 hours
- **Phase 4 (API)**: 1-2 hours
- **Phase 5 (I/O)**: 2-3 hours
- **Phase 6 (CLI)**: 2-3 hours
- **Phase 7 (Utils)**: 1-2 hours
- **Phase 8 (Integration)**: 2-3 hours
- **Phase 9 (Testing)**: 3-4 hours
- **Phase 10 (Documentation)**: 2-3 hours

## Dependencies

### External Dependencies
- All existing dependencies (no new external requirements)
- Standard Python packaging tools (setuptools)

### Internal Dependencies
- Current working UUID database implementation
- All existing tests and functionality
- Current CLI interface and behavior

## Implementation Notes

### Import Strategy
- Use absolute imports throughout (`from artist_bio_gen.models import ArtistData`)
- Provide convenience imports in `__init__.py` files
- Maintain backward compatibility where needed

### Testing Strategy
- Move tests to mirror package structure
- Add module-specific unit tests
- Maintain integration tests for full workflows
- Test public APIs of each module

### Documentation Strategy
- Module-level docstrings explaining purpose and usage
- Function-level docstrings with examples
- Package-level documentation with import examples
- Update README with new structure and usage patterns