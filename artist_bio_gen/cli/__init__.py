#!/usr/bin/env python3
"""
CLI package for artist bio generator.

This package provides command-line interface components including
argument parsing, main application flow, and CLI utilities.
"""

from .parser import (
    create_argument_parser,
)

from .main import (
    main,
)

__all__ = [
    # Argument parsing
    "create_argument_parser",
    # Main application flow
    "main",
]
