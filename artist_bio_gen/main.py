#!/usr/bin/env python3
"""
Artist Bio Generator Main Entry Point

This module serves as the main entry point for the artist bio generator package.
It coordinates all the separated modules and provides the primary CLI interface.
"""

import logging

# Import and setup utilities
from .utils import setup_logging

# Import CLI main function
from .cli import main

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


# Main entry point - delegates to CLI module
if __name__ == "__main__":
    main()
