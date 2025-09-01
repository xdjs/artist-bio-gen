"""
Utilities module for the artist bio generator.

This module provides shared utility functions organized by concern:
- Logging utilities for consistent logging setup
- General helper functions for common operations
- Validation utilities for data validation
"""

# Logging utilities
from .logging import setup_logging

# General helper utilities
from .helpers import create_progress_bar

# Validation utilities
from .validation import _is_output_path_writable
from .text import strip_trailing_citations

__all__ = [
    "setup_logging",
    "create_progress_bar",
    "_is_output_path_writable",
    "strip_trailing_citations",
]
