"""
Schema-driven configuration loader.

This module provides a ConfigLoader that uses the configuration schema
to automatically load, validate, and merge configuration from multiple sources.
"""

import logging
import os
from typing import Dict, Any, Optional, Mapping
from argparse import ArgumentParser, Namespace

from pydantic import ValidationError

from .schema import ConfigSchema


logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and validates configuration using a schema-driven approach."""

    @staticmethod
    def load(
        schema: type[ConfigSchema] = ConfigSchema,
        cli_args: Optional[Namespace] = None,
        cli_overrides: Optional[Mapping[str, Any]] = None,
    ) -> ConfigSchema:
        """
        Load configuration from all sources with precedence handling.

        Loading order (lowest to highest priority):
        1. Schema defaults
        2. .env.local file (if python-dotenv is installed and file exists)
        3. OS environment variables
        4. CLI arguments (highest priority)

        Args:
            schema: The configuration schema class to use
            cli_args: Parsed CLI arguments (if available)
            cli_overrides: Direct CLI overrides mapping (legacy support)

        Returns:
            Validated configuration instance

        Raises:
            ValidationError: If configuration validation fails
        """
        # Start with an empty dict - we'll build up the config
        config_dict: Dict[str, Any] = {}

        # Step 1: Load from .env.local file if available
        _load_from_dotenv_file()

        # Step 2: Load from environment variables based on schema
        for field_name, field_info in schema.model_fields.items():
            env_var = field_info.json_schema_extra.get("env_var") if field_info.json_schema_extra else None
            if env_var:
                env_value = os.getenv(env_var)
                if env_value is not None:
                    # Strip whitespace and convert empty strings to None
                    stripped = env_value.strip()
                    if stripped:
                        config_dict[field_name] = stripped
                    # Don't add to config_dict if empty string - let default/None be used

        # Step 3: Apply CLI arguments (highest priority)
        if cli_args:
            for field_name, field_info in schema.model_fields.items():
                cli_arg = field_info.json_schema_extra.get("cli_arg") if field_info.json_schema_extra else None
                if cli_arg and hasattr(cli_args, cli_arg):
                    cli_value = getattr(cli_args, cli_arg)
                    if cli_value is not None:
                        # For strings, strip whitespace
                        if isinstance(cli_value, str):
                            stripped = cli_value.strip()
                            if stripped:
                                config_dict[field_name] = stripped
                            else:
                                # Treat explicit empty string as an override to clear the value
                                config_dict[field_name] = None
                        else:
                            config_dict[field_name] = cli_value

        # Step 4: Apply legacy CLI overrides if provided (for backward compatibility)
        if cli_overrides:
            for field_name, field_info in schema.model_fields.items():
                env_var = field_info.json_schema_extra.get("env_var") if field_info.json_schema_extra else None
                if env_var in cli_overrides and cli_overrides[env_var] is not None:
                    value = cli_overrides[env_var]
                    # For strings, strip whitespace
                    if isinstance(value, str):
                        stripped = value.strip()
                        if stripped:
                            config_dict[field_name] = stripped
                        else:
                            # Treat explicit empty string as an override to clear the value
                            config_dict[field_name] = None
                    else:
                        config_dict[field_name] = value

        # Step 5: Create and validate the configuration
        try:
            config = schema(**config_dict)
            logger.debug("Configuration loaded and validated successfully")
            return config
        except ValidationError as e:
            # Convert Pydantic validation errors to more user-friendly messages
            errors = []
            for error in e.errors():
                field = error["loc"][0]
                msg = error["msg"]
                field_info = schema.model_fields.get(field)
                env_var = field_info.json_schema_extra.get("env_var") if field_info and field_info.json_schema_extra else field.upper()
                errors.append(f"{env_var}: {msg}")

            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            raise ValueError(error_msg) from e

    @staticmethod
    def generate_cli_parser(
        schema: type[ConfigSchema] = ConfigSchema,
        description: str = "Generate artist bios using OpenAI Responses API",
    ) -> ArgumentParser:
        """
        Generate an ArgumentParser from the configuration schema.

        Args:
            schema: The configuration schema class
            description: Parser description

        Returns:
            Configured ArgumentParser
        """
        parser = ArgumentParser(
            description=description,
            epilog="""
Examples:
  python run_artists.py --input-file artists.csv --prompt-id prompt_123
  python run_artists.py --input-file data.txt --max-workers 8
  python run_artists.py --input-file artists.csv --dry-run
            """,
        )

        # Add CLI-only arguments that don't map to config
        parser.add_argument(
            "--input-file",
            required=True,
            help="CSV-like text file path containing artist data",
        )
        parser.add_argument(
            "--version",
            help="Prompt version (optional)",
        )
        parser.add_argument(
            "--output",
            default="out.jsonl",
            help="JSONL output file path (default: out.jsonl)",
        )
        parser.add_argument(
            "--max-workers",
            type=int,
            default=4,
            help="Maximum number of concurrent requests (default: 4)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse inputs and show first 5 payloads without making API calls",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging (DEBUG level)",
        )
        parser.add_argument(
            "--enable-db",
            action="store_true",
            help="Enable database updates (requires DATABASE_URL env var)",
        )
        parser.add_argument(
            "--test-mode",
            action="store_true",
            help="Use test_artists table instead of artists table",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Resume processing by skipping artists already present in output file",
        )

        # Add schema-based arguments
        for field_name, field_info in schema.model_fields.items():
            if not field_info.json_schema_extra:
                continue

            cli_arg = field_info.json_schema_extra.get("cli_arg")
            if not cli_arg:
                continue

            # Build argument name
            arg_name = f"--{cli_arg.replace('_', '-')}"

            # Build kwargs for add_argument
            kwargs = {
                "help": field_info.description or f"Override {field_info.json_schema_extra.get('env_var', field_name.upper())} env var",
                "default": None,  # Don't set schema defaults here - let the loader handle it
            }

            # Handle different field types
            field_type = field_info.annotation

            # Handle Optional types - check for Union with None
            import typing
            if hasattr(typing, 'get_origin') and hasattr(typing, 'get_args'):
                origin = typing.get_origin(field_type)
                if origin is typing.Union:
                    args = typing.get_args(field_type)
                    # Filter out None from Union args to get the actual type
                    non_none_args = [arg for arg in args if arg is not type(None)]
                    if len(non_none_args) == 1:
                        field_type = non_none_args[0]

            # Add type conversion
            if field_type == int:
                kwargs["type"] = int
            elif field_type == float:
                kwargs["type"] = float
            elif field_type == bool:
                # Special handling for boolean fields
                choices = field_info.json_schema_extra.get("cli_choices")
                if choices:
                    kwargs["choices"] = choices
                else:
                    kwargs["action"] = "store_true"

            parser.add_argument(arg_name, **kwargs)

        return parser


def _load_from_dotenv_file() -> None:
    """Load values from .env.local file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        # Load .env.local file if it exists
        if os.path.exists(".env.local"):
            load_dotenv(".env.local", override=False)
            logger.debug("Loaded configuration from .env.local file")
        else:
            logger.debug(".env.local file not found, skipping")

    except ImportError:
        # python-dotenv not available, continue silently
        logger.debug("python-dotenv not available, skipping .env.local file loading")
