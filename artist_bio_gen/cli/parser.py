"""
CLI argument parser module.

This module now uses the schema-driven configuration system to
automatically generate the argument parser.
"""

from ..config.loader import ConfigLoader


def create_argument_parser():
    """
    Create and configure the argument parser.

    This now uses the schema-driven ConfigLoader to automatically
    generate the parser from the configuration schema.
    """
    return ConfigLoader.generate_cli_parser()