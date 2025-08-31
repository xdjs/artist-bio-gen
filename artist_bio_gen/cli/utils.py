"""
CLI utilities module.

This module provides utility functions for CLI operations including
environment variable handling and path validation.
"""

import os
from pathlib import Path
from typing import Optional, Tuple


def apply_environment_defaults(args):
    """Apply environment variable defaults to parsed arguments."""
    if args.prompt_id is None:
        args.prompt_id = os.getenv("OPENAI_PROMPT_ID")
    if not hasattr(args, 'db_url') or args.db_url is None:
        args.db_url = os.getenv("DATABASE_URL")
    return args


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