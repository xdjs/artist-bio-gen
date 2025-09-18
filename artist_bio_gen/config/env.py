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

    # Quota and rate-limit configuration (Task 2.2)
    QUOTA_MONITORING: bool = True
    QUOTA_THRESHOLD: float = 0.8
    DAILY_REQUEST_LIMIT: Optional[int] = None
    PAUSE_DURATION_HOURS: int = 24
    QUOTA_LOG_INTERVAL: int = 100

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
            # Quota defaults
            "QUOTA_MONITORING": "true",
            "QUOTA_THRESHOLD": "0.8",
            "DAILY_REQUEST_LIMIT": None,
            "PAUSE_DURATION_HOURS": "24",
            "QUOTA_LOG_INTERVAL": "100",
        }
        
        # Step 2: Load from .env.local file (optional)
        _load_from_dotenv_file(values)
        
        # Step 3: Load from OS environment
        for key in values.keys():
            env_value = os.getenv(key)
            if env_value is not None:
                values[key] = env_value.strip() if env_value.strip() else None
        
        # Step 4: Apply CLI overrides (highest priority)
        if cli_overrides:
            for key, value in cli_overrides.items():
                if key in values and value is not None:
                    values[key] = value.strip() if value.strip() else None

        # Validation: Check required fields
        missing_required = []
        if not values["OPENAI_API_KEY"]:
            missing_required.append("OPENAI_API_KEY")
        if not values["DATABASE_URL"]:
            missing_required.append("DATABASE_URL")
            
        if missing_required:
            for field in missing_required:
                logger.error(f"ERROR: {field} is required but was not provided (env/CLI).")
            raise ConfigError(f"Missing required configuration: {', '.join(missing_required)}")

        # Parse and validate quota-related values
        try:
            quota_monitoring = str(values["QUOTA_MONITORING"]).strip().lower()
            if quota_monitoring in ("1", "true", "yes", "on"):
                qmon = True
            elif quota_monitoring in ("0", "false", "no", "off"):
                qmon = False
            else:
                raise ConfigError("QUOTA_MONITORING must be true/false")

            qthresh = float(values["QUOTA_THRESHOLD"]) if values["QUOTA_THRESHOLD"] is not None else 0.8
            if not (0.1 <= qthresh <= 1.0):
                raise ConfigError("QUOTA_THRESHOLD must be between 0.1 and 1.0")

            dlimit = values["DAILY_REQUEST_LIMIT"]
            if dlimit is None or str(dlimit).strip() == "":
                dlimit_parsed = None
            else:
                dlimit_parsed = int(dlimit)
                if dlimit_parsed <= 0:
                    raise ConfigError("DAILY_REQUEST_LIMIT must be a positive integer")

            pause_hours = int(values["PAUSE_DURATION_HOURS"]) if values["PAUSE_DURATION_HOURS"] is not None else 24
            if not (1 <= pause_hours <= 72):
                raise ConfigError("PAUSE_DURATION_HOURS must be between 1 and 72 hours")

            qlogint = int(values["QUOTA_LOG_INTERVAL"]) if values["QUOTA_LOG_INTERVAL"] is not None else 100
            if qlogint <= 0:
                raise ConfigError("QUOTA_LOG_INTERVAL must be a positive integer")

        except ValueError as ve:
            raise ConfigError(f"Invalid quota configuration value: {ve}") from ve

        # Create and store singleton instance
        _ENV = Env(
            OPENAI_API_KEY=values["OPENAI_API_KEY"],
            DATABASE_URL=values["DATABASE_URL"], 
            OPENAI_PROMPT_ID=values["OPENAI_PROMPT_ID"],
            OPENAI_ORG_ID=values["OPENAI_ORG_ID"],
            QUOTA_MONITORING=qmon,
            QUOTA_THRESHOLD=qthresh,
            DAILY_REQUEST_LIMIT=dlimit_parsed,
            PAUSE_DURATION_HOURS=pause_hours,
            QUOTA_LOG_INTERVAL=qlogint,
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
            OPENAI_ORG_ID=openai_org_id,
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
            "OPENAI_ORG_ID": self.OPENAI_ORG_ID,        # Not sensitive
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
