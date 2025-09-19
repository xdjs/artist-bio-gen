"""
OpenAI API client management module.

This module handles OpenAI API client creation and initialization
for the artist bio generator application.
"""

import logging
import sys

from ..constants import EXIT_CONFIG_ERROR
from ..config import Env

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


def create_openai_client() -> "OpenAI":
    """Create and initialize OpenAI client."""
    if OpenAI is None:
        logger.error(
            "OpenAI package not installed. Please install with: pip install openai"
        )
        sys.exit(EXIT_CONFIG_ERROR)

    # Get configuration from centralized environment manager
    env = Env.current()

    # Create client with API key
    client = OpenAI(api_key=env.OPENAI_API_KEY)
    logger.info("OpenAI client initialized successfully")
    return client
