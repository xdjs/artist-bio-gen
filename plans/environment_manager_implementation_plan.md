# Environment Manager Implementation Plan

## Overview
Implement a central Environment manager class to replace scattered `os.getenv()` calls throughout the codebase with a single, validated, type-safe configuration system. This plan addresses requirements from `env_manager_prompt.md`.

## Goals
- **Centralized Configuration**: Single source of truth for all environment variables
- **Precedence System**: CLI > OS Environment > .env.local > defaults
- **Type Safety**: Frozen dataclass with typed fields
- **Validation**: Required fields validated at startup with clear error messages
- **Backward Compatibility**: Maintain existing CLI interface and behavior

## Current State Analysis

### Environment Variable Usage Locations
1. **`artist_bio_gen/main.py:11-18`** - Loads `.env.local` via `python-dotenv`
2. **`artist_bio_gen/utils/validation.py:16,18`** - `apply_environment_defaults()` function
3. **`artist_bio_gen/api/client.py:30`** - `os.getenv("OPENAI_API_KEY")`
4. **`artist_bio_gen/database/config.py:152`** - `os.getenv("DATABASE_URL")`
5. **`artist_bio_gen/cli/main.py:63,92,112`** - Environment variable handling and validation

### Environment Variables (from .env.example)
- `OPENAI_API_KEY` (required) - OpenAI API authentication
- `OPENAI_PROMPT_ID` (optional) - Prompt template ID
- `DATABASE_URL` (required) - PostgreSQL connection string
- `OPENAI_ORG_ID` (optional) - OpenAI organization ID

## Implementation Tasks

### Phase 1: Core Environment Manager (Priority: High)

#### Task 1.1: Create Environment Manager Class ✅
- **File**: `artist_bio_gen/config/env.py`
- **Description**: Implement frozen dataclass with singleton pattern
- **Requirements**:
  - Frozen dataclass with typed fields
  - Static methods: `load()` and `current()`
  - Helper method: `to_dict()`
  - Optional method: `from_mapping()` for testing
  - Optional method: `mask()` for safe logging
- **Dependencies**: None
- **Estimate**: 2-3 hours
- **Status**: ✅ COMPLETED - Full implementation with all required methods

#### Task 1.2: Create Configuration Directory Structure ✅
- **Directory**: `artist_bio_gen/config/`
- **Files**: 
  - `__init__.py` (exports `Env` class)
  - `env.py` (main implementation)
- **Dependencies**: Task 1.1
- **Estimate**: 15 minutes
- **Status**: ✅ COMPLETED - Directory and init file created

#### Task 1.3: Implement Loading Logic with Precedence ✅
- **Location**: `artist_bio_gen/config/env.py` - `load()` method
- **Precedence Order**:
  1. Defaults (None for optional, required fields must be provided)
  2. `.env.local` file (via `python-dotenv` if available)
  3. OS environment variables
  4. CLI overrides (highest priority)
- **Error Handling**: Custom `ConfigError` for validation failures
- **Dependencies**: Task 1.1
- **Estimate**: 3-4 hours
- **Status**: ✅ COMPLETED - Full precedence system implemented with validation

#### Task 1.4: Implement Singleton Pattern ✅
- **Location**: `artist_bio_gen/config/env.py` - module-level `_ENV` variable
- **Requirements**:
  - `load()` stores instance in `_ENV`
  - `current()` returns stored instance or raises error
  - Thread-safe access (not required but good practice)
- **Dependencies**: Task 1.1
- **Estimate**: 1 hour
- **Status**: ✅ COMPLETED - Singleton pattern with module-level storage

### Phase 2: CLI Integration (Priority: High)

#### Task 2.1: Update CLI Argument Parser
- **File**: `artist_bio_gen/cli/main.py`
- **Changes**:
  - Add CLI flags: `--db-url`, `--openai-api-key`, `--openai-prompt-id`, `--openai-org-id`
  - Map CLI argument names to environment variable names
  - Build override dictionary from provided CLI arguments only
- **Dependencies**: Task 1.1
- **Estimate**: 2-3 hours

#### Task 2.2: Replace Environment Defaults Logic
- **Files**: 
  - `artist_bio_gen/cli/main.py:63` - Replace `apply_environment_defaults()` call
  - Remove validation logic that's now handled by `Env.load()`
- **Changes**:
  - Call `Env.load(cli_overrides)` after parsing arguments
  - Remove duplicate validation code
  - Update error messages to match new format
- **Dependencies**: Tasks 1.3, 2.1
- **Estimate**: 2 hours

#### Task 2.3: Update Main Entry Point Bootstrap
- **File**: `artist_bio_gen/main.py`
- **Changes**:
  - Remove direct `load_dotenv()` call (handled by `Env.load()`)
  - Add early `Env.load()` call if needed for backward compatibility
- **Dependencies**: Task 1.3
- **Estimate**: 1 hour

### Phase 3: Replace Direct Environment Access (Priority: High)

#### Task 3.1: Update API Client Module
- **File**: `artist_bio_gen/api/client.py:30-33`
- **Changes**:
  - Replace `os.getenv("OPENAI_API_KEY")` with `Env.current().OPENAI_API_KEY`
  - Use `Env.current().OPENAI_ORG_ID` if implementing org support
  - Remove validation logic (handled by `Env.load()`)
- **Dependencies**: Task 1.4
- **Estimate**: 1 hour

#### Task 3.2: Update Database Configuration
- **File**: `artist_bio_gen/database/config.py:152-158`
- **Changes**:
  - Replace `os.getenv("DATABASE_URL")` with `Env.current().DATABASE_URL`
  - Remove `get_database_url_from_env()` function (obsolete)
  - Update calling code to use `Env.current().DATABASE_URL` directly
- **Dependencies**: Task 1.4
- **Estimate**: 1-2 hours

#### Task 3.3: Remove Legacy Environment Utilities
- **File**: `artist_bio_gen/utils/validation.py:13-19`
- **Changes**:
  - Remove `apply_environment_defaults()` function
  - Update imports in modules that used this function
  - Update `__init__.py` exports
- **Dependencies**: Task 2.2
- **Estimate**: 1 hour

### Phase 4: Testing (Priority: Medium)

#### Task 4.1: Create Environment Manager Tests
- **File**: `tests/config/test_env_manager.py`
- **Test Cases**:
  - Loading precedence (CLI > env > .env.local > defaults)
  - Required field validation
  - Optional field handling
  - Error conditions and messages
  - Singleton behavior
  - `from_mapping()` helper method
- **Dependencies**: Task 1.3
- **Estimate**: 4-5 hours

#### Task 4.2: Update Existing Tests
- **Files**: Tests that mock environment variables or use `apply_environment_defaults()`
  - `tests/cli/test_run_artists.py` (environment variable tests)
  - `tests/database/test_database_functions.py` (environment tests)
- **Changes**:
  - Replace environment variable mocking with `Env.from_mapping()`
  - Update test assertions for new error messages
  - Remove tests for deprecated functions
- **Dependencies**: Tasks 3.3, 4.1
- **Estimate**: 3-4 hours

#### Task 4.3: Add Integration Tests
- **File**: `tests/integration/test_env_integration.py`
- **Test Cases**:
  - End-to-end CLI override behavior
  - .env.local file loading (with and without `python-dotenv`)
  - Error handling in complete application flow
- **Dependencies**: Task 2.2
- **Estimate**: 2-3 hours

### Phase 5: Documentation and Cleanup (Priority: Low)

#### Task 5.1: Update Documentation
- **Files**: 
  - `README.md` - Update configuration section
  - `.env.example` - Add comments about precedence
- **Content**:
  - Explain precedence order (CLI > env > .env.local)
  - Document new CLI flags
  - Update setup instructions
- **Dependencies**: Task 2.1
- **Estimate**: 1-2 hours

#### Task 5.2: Code Quality and Style
- **Tasks**:
  - Run `black` and `mypy` on new code
  - Add comprehensive docstrings
  - Ensure PEP 8 compliance
  - Review for potential security issues
- **Dependencies**: All implementation tasks
- **Estimate**: 1-2 hours

## Implementation Details

### Environment Manager Class Structure
```python
@dataclass(frozen=True)
class Env:
    OPENAI_API_KEY: str
    DATABASE_URL: str
    OPENAI_PROMPT_ID: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    
    @staticmethod
    def load(cli_overrides: Mapping[str, str] | None = None) -> "Env": ...
    
    @staticmethod
    def current() -> "Env": ...
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> "Env": ...
    
    def mask(self) -> dict: ...
```

### CLI Argument Mapping
```python
CLI_TO_ENV_MAPPING = {
    "db_url": "DATABASE_URL",
    "openai_api_key": "OPENAI_API_KEY", 
    "openai_prompt_id": "OPENAI_PROMPT_ID",
    "openai_org_id": "OPENAI_ORG_ID"
}
```

### Error Handling Strategy
- **ConfigError**: Custom exception for configuration validation failures
- **Exit Code 2**: For configuration errors (matches existing pattern)
- **Clear Messages**: "ERROR: OPENAI_API_KEY is required but was not provided (env/CLI)."
- **No Secret Logging**: Never log actual values, only presence/absence

## Migration Strategy

### Phase-by-Phase Migration
1. **Phase 1-2**: Implement core functionality and CLI integration
2. **Phase 3**: Replace all direct environment access incrementally
3. **Phase 4**: Comprehensive testing to ensure no regressions
4. **Phase 5**: Documentation and cleanup

### Backward Compatibility
- Existing CLI arguments continue to work
- `.env.local` file continues to be loaded
- Error messages are improved but functionality is preserved
- No changes to public API surface

### Risk Mitigation
- Comprehensive test coverage before removing legacy code
- Incremental migration allows for easy rollback
- Preserve existing error codes and exit behavior
- Maintain same precedence order as current implementation

## Success Criteria

### Functional Requirements
- [ ] All environment variables loaded through central `Env` class
- [ ] CLI arguments override environment variables
- [ ] Required fields validated at startup with clear errors
- [ ] Optional fields handled gracefully (None values)
- [ ] `.env.local` file support maintained (optional dependency)

### Quality Requirements  
- [ ] 100% test success rate maintained
- [ ] Type hints throughout implementation
- [ ] Clear docstrings for all public methods
- [ ] PEP 8 compliant code style
- [ ] No hard dependency on `python-dotenv`

### Documentation Requirements
- [ ] Updated README with new configuration precedence
- [ ] Code comments explaining precedence logic
- [ ] Clear error messages for configuration issues
- [ ] Updated CLI help text

## Timeline Estimate
- **Total Development Time**: 20-30 hours
- **Testing Time**: 9-12 hours  
- **Documentation Time**: 2-4 hours
- **Total Project Time**: 31-46 hours

## Dependencies and Constraints

### External Dependencies
- `python-dotenv>=1.0.0` (optional) - maintained
- Python 3.11+ - maintained
- No new hard dependencies

### Internal Dependencies
- Must maintain existing CLI interface
- Must preserve error codes and exit behavior  
- Must work with existing test infrastructure
- Must integrate with existing logging system

### Technical Constraints
- Frozen dataclass for immutability
- Singleton pattern for global access
- Type safety throughout
- Clear separation from business logic
- Optional import handling for `python-dotenv`

---

**Note**: This plan maintains the existing project architecture while centralizing configuration management. The implementation preserves all existing functionality while providing a cleaner, more maintainable foundation for environment variable handling.