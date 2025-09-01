"""
Validation utilities for the artist bio generator.

This module provides validation functions for paths, environment variables,
and other data validation needs across the application.
"""

import os
from pathlib import Path
from typing import Optional, Tuple



def _is_output_path_writable(path_str: str) -> Tuple[bool, Optional[str]]:
    """Check whether the output path's parent directory is writable without creating the file."""
    try:
        path = Path(path_str)
        parent = path.parent if path.parent != Path("") else Path(".")
        if not parent.exists():
            return False, f"Output directory does not exist: {parent}"
        if not os.access(parent, os.W_OK):
            return False, f"No write permission for directory: {parent}"
        return True, None
    except Exception as e:
        return False, f"Unable to validate output path '{path_str}': {e}"
