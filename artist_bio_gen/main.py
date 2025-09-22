#!/usr/bin/env python3
"""
Artist Bio Generator Main Entry Point

This module serves as the main entry point for the artist bio generator package.
It provides a minimal delegator to the CLI module without import-time side effects.
"""

# Import CLI main function
from .cli import main


# Main entry point - delegates to CLI module
if __name__ == "__main__":
    main()
