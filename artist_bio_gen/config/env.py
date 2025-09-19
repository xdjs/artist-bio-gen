"""
Environment configuration management module.

This module provides a centralized Environment manager class that loads,
validates, and serves all configuration values for the application.
Now uses a schema-driven approach with Pydantic for validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Optional

from .schema import ConfigSchema
from .loader import ConfigLoader

logger = logging.getLogger(__name__)

# Module-level singleton instance
_ENV: Optional["Env"] = None


class ConfigError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass(frozen=True)
class Env:
    """
    Immutable configuration container for environment variables.

    This class maintains backward compatibility while using the new
    schema-driven configuration system internally.
    """

    OPENAI_API_KEY: str
    DATABASE_URL: str
    OPENAI_PROMPT_ID: Optional[str] = None

    # Quota and rate-limit configuration
    QUOTA_MONITORING: bool = True
    QUOTA_THRESHOLD: float = 0.8
    DAILY_REQUEST_LIMIT: Optional[int] = None
    PAUSE_DURATION_HOURS: int = 24
    QUOTA_LOG_INTERVAL: int = 100

    @staticmethod
    def load(cli_overrides: Optional[Mapping[str, str]] = None) -> "Env":
        """
        Load configuration from all sources with precedence handling.

        This method now uses the schema-driven ConfigLoader internally
        while maintaining the same external interface for backward compatibility.

        Args:
            cli_overrides: Optional mapping of CLI-provided values

        Returns:
            Configured Env instance

        Raises:
            ConfigError: If required fields are missing or invalid
        """
        global _ENV

        try:
            # Use the new schema-driven loader
            config = ConfigLoader.load(
                schema=ConfigSchema,
                cli_overrides=cli_overrides
            )

            # Create Env instance from validated config
            _ENV = Env(
                OPENAI_API_KEY=config.openai_api_key,
                DATABASE_URL=config.database_url,
                OPENAI_PROMPT_ID=config.openai_prompt_id,
                QUOTA_MONITORING=config.quota_monitoring,
                QUOTA_THRESHOLD=config.quota_threshold,
                DAILY_REQUEST_LIMIT=config.daily_request_limit,
                PAUSE_DURATION_HOURS=config.pause_duration_hours,
                QUOTA_LOG_INTERVAL=config.quota_log_interval,
            )

            logger.debug("Environment configuration loaded successfully")
            return _ENV

        except ValueError as e:
            # Convert validation errors to ConfigError for backward compatibility
            raise ConfigError(str(e)) from e

    @staticmethod
    def current() -> "Env":
        """
        Return the globally-initialized Env instance.

        Returns:
            The current Env instance

        Raises:
            ConfigError: If Env.load() has not been called yet
        """
        if _ENV is None:
            raise ConfigError("Environment not initialized. Call Env.load() first.")
        return _ENV

    def to_dict(self) -> dict:
        """
        Convert environment to dictionary representation.

        Returns:
            Dictionary with all configuration values
        """
        return {
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "DATABASE_URL": self.DATABASE_URL,
            "OPENAI_PROMPT_ID": self.OPENAI_PROMPT_ID,
        }

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> "Env":
        """
        Create Env instance from mapping (useful for testing).

        Args:
            mapping: Dictionary of configuration values

        Returns:
            Env instance

        Raises:
            ConfigError: If required fields are missing
        """
        # Extract values with None as default
        openai_api_key = mapping.get("OPENAI_API_KEY")
        database_url = mapping.get("DATABASE_URL")
        openai_prompt_id = mapping.get("OPENAI_PROMPT_ID")

        # Parse quota values with defaults
        quota_monitoring = mapping.get("QUOTA_MONITORING", "true")
        if isinstance(quota_monitoring, str):
            quota_monitoring = quota_monitoring.lower() in ("1", "true", "yes", "on")

        quota_threshold = float(mapping.get("QUOTA_THRESHOLD", "0.8"))
        daily_limit = mapping.get("DAILY_REQUEST_LIMIT")
        if daily_limit:
            daily_limit = int(daily_limit)

        pause_duration = int(mapping.get("PAUSE_DURATION_HOURS", "24"))
        quota_log_interval = int(mapping.get("QUOTA_LOG_INTERVAL", "100"))

        # Validate required fields
        missing_required = []
        if not openai_api_key:
            missing_required.append("OPENAI_API_KEY")
        if not database_url:
            missing_required.append("DATABASE_URL")

        if missing_required:
            raise ConfigError(f"Missing required configuration: {', '.join(missing_required)}")

        return cls(
            OPENAI_API_KEY=openai_api_key,
            DATABASE_URL=database_url,
            OPENAI_PROMPT_ID=openai_prompt_id,
            QUOTA_MONITORING=quota_monitoring,
            QUOTA_THRESHOLD=quota_threshold,
            DAILY_REQUEST_LIMIT=daily_limit,
            PAUSE_DURATION_HOURS=pause_duration,
            QUOTA_LOG_INTERVAL=quota_log_interval,
        )

    def mask(self) -> dict:
        """
        Return masked version for safe logging (hides sensitive values).

        Returns:
            Dictionary with sensitive values masked
        """
        return {
            "OPENAI_API_KEY": "***" if self.OPENAI_API_KEY else None,
            "DATABASE_URL": "***" if self.DATABASE_URL else None,
            "OPENAI_PROMPT_ID": self.OPENAI_PROMPT_ID,  # Not sensitive
        }