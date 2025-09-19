"""
Configuration management for the artist bio generator.

This module provides centralized configuration handling with support for
environment variables, .env files, and CLI overrides.

Now uses a schema-driven approach with Pydantic for validation.
"""

from .env import Env, ConfigError
from .schema import ConfigSchema
from .loader import ConfigLoader

__all__ = ["Env", "ConfigError", "ConfigSchema", "ConfigLoader"]