#!/usr/bin/env python3
"""
Artist Bio Generator Package

A Python package for generating artist biographies using OpenAI's API
with UUID-based artist identification and optional PostgreSQL persistence.

This package provides both a command-line interface and a programmatic API
for processing artist data and generating biographies.
"""

__version__ = "1.0.0"
__author__ = "Artist Bio Generator"
__description__ = (
    "Generate artist biographies using OpenAI API with database persistence"
)
__license__ = "MIT"
__maintainer__ = "Artist Bio Generator"
__email__ = "support@example.com"
__url__ = "https://github.com/example/artist-bio-gen"
__status__ = "Production"

# Import models for public API
from .models import (
    ArtistData,
    ParseResult,
    ApiResponse,
    DatabaseConfig,
    DatabaseResult,
    ProcessingStats,
)

# Import constants for public API
from .constants import (
    EXIT_SUCCESS,
    EXIT_INPUT_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_API_FAILURES,
    EXIT_INTERRUPTED,
    EXIT_UNEXPECTED_ERROR,
    DEFAULT_POOL_SIZE,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_QUERY_TIMEOUT,
)

# Import core functionality for public API
from .core import (
    parse_input_file,
    write_jsonl_output,
    append_jsonl_response,
    initialize_jsonl_output,
    process_artists_concurrent,
)

# Import API functions for public API
from .api import (
    create_openai_client,
    call_openai_api,
)

# Import database functions for public API
from .database import (
    create_db_connection_pool,
    validate_database_url,
    update_artist_bio,
)

# Import CLI functionality for public API
from .cli import (
    main,
    create_argument_parser,
)

# Import utilities for public API
from .utils import (
    setup_logging,
    create_progress_bar,
)

# Public API exports
__all__ = [
    # Package metadata
    "__version__",
    "__author__",
    "__description__",
    # Data models
    "ArtistData",
    "ParseResult",
    "ApiResponse",
    "DatabaseConfig",
    "DatabaseResult",
    "ProcessingStats",
    # Constants
    "EXIT_SUCCESS",
    "EXIT_INPUT_ERROR",
    "EXIT_CONFIG_ERROR",
    "EXIT_API_FAILURES",
    "EXIT_INTERRUPTED",
    "EXIT_UNEXPECTED_ERROR",
    "DEFAULT_POOL_SIZE",
    "DEFAULT_MAX_OVERFLOW",
    "DEFAULT_CONNECTION_TIMEOUT",
    "DEFAULT_QUERY_TIMEOUT",
    # Core functionality
    "parse_input_file",
    "write_jsonl_output",
    "append_jsonl_response",
    "initialize_jsonl_output",
    "process_artists_concurrent",
    # API functions
    "create_openai_client",
    "call_openai_api",
    # Database functions
    "create_db_connection_pool",
    "validate_database_url",
    "update_artist_bio",
    # CLI functions
    "main",
    "create_argument_parser",
    # Utilities
    "setup_logging",
    "create_progress_bar",
]
