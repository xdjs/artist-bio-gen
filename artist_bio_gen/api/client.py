"""
OpenAI API client management module.

This module handles OpenAI API client creation and initialization
for the artist bio generator application.
"""

import logging
import os
import sys

from ..constants import EXIT_CONFIG_ERROR

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


def create_openai_client() -> "OpenAI":
    """Create and initialize OpenAI client."""
    if OpenAI is None:
        logger.error("OpenAI package not installed. Please install with: pip install openai")
        sys.exit(EXIT_CONFIG_ERROR)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(EXIT_CONFIG_ERROR)

    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client initialized successfully")
    return client