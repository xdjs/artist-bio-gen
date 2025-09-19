"""
Configuration schema definition using Pydantic.

This module defines the declarative configuration schema that serves as
the single source of truth for all configuration in the application.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class ConfigField(BaseModel):
    """Metadata for a configuration field."""

    env_var: str
    cli_arg: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    description: str = ""
    type_hint: type = str
    choices: Optional[list] = None


class ConfigSchema(BaseModel):
    """
    Declarative configuration schema.

    This is the single source of truth for all application configuration.
    Each field can be set via environment variables or CLI arguments.
    """

    # Core OpenAI configuration
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for authentication",
        json_schema_extra={
            "env_var": "OPENAI_API_KEY",
            "cli_arg": "openai_api_key",
            "sensitive": True,
        }
    )

    openai_prompt_id: Optional[str] = Field(
        None,
        description="OpenAI prompt ID",
        json_schema_extra={
            "env_var": "OPENAI_PROMPT_ID",
            "cli_arg": "prompt_id",
        }
    )

    # Database configuration
    database_url: str = Field(
        ...,
        description="Database connection URL",
        json_schema_extra={
            "env_var": "DATABASE_URL",
            "cli_arg": "db_url",
            "sensitive": True,
        }
    )

    # Quota monitoring configuration
    quota_monitoring: bool = Field(
        True,
        description="Enable or disable quota monitoring",
        json_schema_extra={
            "env_var": "QUOTA_MONITORING",
            "cli_arg": "quota_monitoring",
            "cli_choices": ["true", "false"],
        }
    )

    quota_threshold: float = Field(
        0.8,
        ge=0.1,
        le=1.0,
        description="Pause threshold as a decimal between 0.1 and 1.0",
        json_schema_extra={
            "env_var": "QUOTA_THRESHOLD",
            "cli_arg": "quota_threshold",
        }
    )

    daily_request_limit: Optional[int] = Field(
        None,
        gt=0,
        description="Optional daily request limit used for pausing",
        json_schema_extra={
            "env_var": "DAILY_REQUEST_LIMIT",
            "cli_arg": "daily_limit",
        }
    )

    pause_duration_hours: int = Field(
        24,
        ge=1,
        le=72,
        description="Hours to pause when quota is hit (1-72)",
        json_schema_extra={
            "env_var": "PAUSE_DURATION_HOURS",
            "cli_arg": "pause_duration",
        }
    )

    quota_log_interval: int = Field(
        100,
        gt=0,
        description="Log quota metrics every N requests to reduce noise",
        json_schema_extra={
            "env_var": "QUOTA_LOG_INTERVAL",
            "cli_arg": "quota_log_interval",
        }
    )

    @field_validator('quota_monitoring', mode='before')
    @classmethod
    def parse_bool(cls, v: Any) -> bool:
        """Parse boolean from string values."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ('1', 'true', 'yes', 'on'):
                return True
            elif v_lower in ('0', 'false', 'no', 'off'):
                return False
            else:
                raise ValueError(f"Invalid boolean value: {v}")
        return bool(v)

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }