"""
Logging utilities for the artist bio generator.

This module provides centralized logging configuration and utilities
to ensure consistent logging behavior across the application.
"""

import logging


def setup_logging(verbose: bool = False):
    """Setup logging configuration with appropriate level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    format_string = "%(asctime)s - %(levelname)s - %(message)s"

    logging.basicConfig(level=level, format=format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Set specific logger levels
    logging.getLogger("openai").setLevel(logging.WARNING)  # Reduce OpenAI client noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Reduce HTTP client noise
