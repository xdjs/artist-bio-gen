"""
Environment configuration management module.

This module provides a centralized Environment manager class that loads,
validates, and serves all configuration values for the application.
Supports .env.local files, OS environment variables, and CLI overrides.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Mapping, Optional

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

    Loads configuration from multiple sources with precedence:
    1. CLI overrides (highest priority)
    2. OS environment variables
    3. .env.local file (if python-dotenv available)
    4. Defaults (lowest priority)
    """

    OPENAI_API_KEY: str
    DATABASE_URL: str
    OPENAI_PROMPT_ID: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    OPENAI_RPM: int = 500
    OPENAI_TPM: int = 200_000
    OPENAI_TPD: int = 2_000_000

    @staticmethod
    def load(cli_overrides: Optional[Mapping[str, str]] = None) -> "Env":
        """
        Load configuration from all sources with precedence handling.

        Loading order (lowest to highest priority):
        1. Defaults (None for optional fields)
        2. .env.local file (if python-dotenv is installed and file exists)
        3. OS environment variables
        4. CLI overrides (highest priority)

        Args:
            cli_overrides: Optional mapping of CLI-provided values

        Returns:
            Configured Env instance

        Raises:
            ConfigError: If required fields are missing or invalid
        """
        global _ENV

        # Start with defaults
        values = {
            "OPENAI_API_KEY": None,
            "DATABASE_URL": None,
            "OPENAI_PROMPT_ID": None,
            "OPENAI_ORG_ID": None,
            "OPENAI_RPM": 500,
            "OPENAI_TPM": 200_000,
            "OPENAI_TPD": 2_000_000,
        }

        # Step 2: Load from .env.local file (optional)
        _load_from_dotenv_file(values)

        # Step 3: Load from OS environment
        for key in values.keys():
            env_value = os.getenv(key)
            if env_value is not None and env_value.strip():
                if key in {"OPENAI_RPM", "OPENAI_TPM", "OPENAI_TPD"}:
                    try:
                        values[key] = int(env_value.strip())
                    except ValueError:
                        logger.warning(f"Invalid integer for {key} in environment")
                else:
                    values[key] = env_value.strip()

        # Step 4: Apply CLI overrides (highest priority)
        if cli_overrides:
            for key, value in cli_overrides.items():
                if key in values and value is not None:
                    if key in {"OPENAI_RPM", "OPENAI_TPM", "OPENAI_TPD"}:
                        values[key] = int(value)
                    else:
                        values[key] = value.strip() if value.strip() else None

        # Validation: Check required fields
        missing_required = []
        if not values["OPENAI_API_KEY"]:
            missing_required.append("OPENAI_API_KEY")
        if not values["DATABASE_URL"]:
            missing_required.append("DATABASE_URL")

        if missing_required:
            for field in missing_required:
                logger.error(
                    f"ERROR: {field} is required but was not provided (env/CLI)."
                )
            raise ConfigError(
                f"Missing required configuration: {', '.join(missing_required)}"
            )

        # Create and store singleton instance
        _ENV = Env(
            OPENAI_API_KEY=values["OPENAI_API_KEY"],
            DATABASE_URL=values["DATABASE_URL"],
            OPENAI_PROMPT_ID=values["OPENAI_PROMPT_ID"],
            OPENAI_ORG_ID=values["OPENAI_ORG_ID"],
            OPENAI_RPM=values["OPENAI_RPM"],
            OPENAI_TPM=values["OPENAI_TPM"],
            OPENAI_TPD=values["OPENAI_TPD"],
        )

        logger.debug("Environment configuration loaded successfully")
        return _ENV

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
            "OPENAI_ORG_ID": self.OPENAI_ORG_ID,
            "OPENAI_RPM": self.OPENAI_RPM,
            "OPENAI_TPM": self.OPENAI_TPM,
            "OPENAI_TPD": self.OPENAI_TPD,
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
        openai_org_id = mapping.get("OPENAI_ORG_ID")
        openai_rpm = int(mapping.get("OPENAI_RPM", 500))
        openai_tpm = int(mapping.get("OPENAI_TPM", 200_000))
        openai_tpd = int(mapping.get("OPENAI_TPD", 2_000_000))

        # Validate required fields
        missing_required = []
        if not openai_api_key:
            missing_required.append("OPENAI_API_KEY")
        if not database_url:
            missing_required.append("DATABASE_URL")

        if missing_required:
            raise ConfigError(
                f"Missing required configuration: {', '.join(missing_required)}"
            )

        return cls(
            OPENAI_API_KEY=openai_api_key,
            DATABASE_URL=database_url,
            OPENAI_PROMPT_ID=openai_prompt_id,
            OPENAI_ORG_ID=openai_org_id,
            OPENAI_RPM=openai_rpm,
            OPENAI_TPM=openai_tpm,
            OPENAI_TPD=openai_tpd,
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
            "OPENAI_ORG_ID": self.OPENAI_ORG_ID,  # Not sensitive
            "OPENAI_RPM": self.OPENAI_RPM,
            "OPENAI_TPM": self.OPENAI_TPM,
            "OPENAI_TPD": self.OPENAI_TPD,
        }


def _load_from_dotenv_file(values: dict) -> None:
    """
    Load values from .env.local file if python-dotenv is available.

    Args:
        values: Dictionary to update with loaded values
    """
    try:
        from dotenv import load_dotenv

        # Load .env.local file if it exists, don't override existing values
        if os.path.exists(".env.local"):
            load_dotenv(".env.local", override=False)
            logger.debug("Loaded configuration from .env.local file")
        else:
            logger.debug(".env.local file not found, skipping")

    except ImportError:
        # python-dotenv not available, continue silently
        logger.debug("python-dotenv not available, skipping .env.local file loading")
        pass
