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
__description__ = "Generate artist biographies using OpenAI API with database persistence"

# Public API exports will be added as modules are created
__all__ = [
    "__version__",
    "__author__", 
    "__description__",
]