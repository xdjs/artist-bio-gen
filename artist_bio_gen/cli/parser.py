"""
CLI argument parser module.

This module handles command-line argument parsing and configuration
for the artist bio generator application.
"""

import argparse


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate artist bios using OpenAI Responses API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_artists.py --input-file artists.csv --prompt-id prompt_123
  python run_artists.py --input-file data.txt --max-workers 8
  python run_artists.py --input-file artists.csv --dry-run
        """,
    )

    # Required arguments
    parser.add_argument(
        "--input-file",
        required=True,
        help="CSV-like text file path containing artist data",
    )

    # Optional arguments with defaults
    parser.add_argument(
        "--prompt-id",
        default=None,
        help="OpenAI prompt ID (default: OPENAI_PROMPT_ID env var)",
    )

    parser.add_argument("--version", help="Prompt version (optional)")

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
        "--verbose", action="store_true", help="Enable verbose logging (DEBUG level)"
    )

    parser.add_argument(
        "--enable-db",
        action="store_true",
        help="Enable database updates (requires DATABASE_URL env var)"
    )

    parser.add_argument(
        "--test-mode",
        action="store_true", 
        help="Use test_artists table instead of artists table"
    )

    parser.add_argument(
        "--stream-output",
        action="store_true",
        help="Stream JSONL output as responses complete (saves memory for large datasets)"
    )

    # Environment variable overrides
    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="OpenAI API key (default: OPENAI_API_KEY env var)"
    )

    parser.add_argument(
        "--openai-prompt-id",
        default=None,
        help="OpenAI prompt ID (default: OPENAI_PROMPT_ID env var)"
    )

    parser.add_argument(
        "--openai-org-id",
        default=None,
        help="OpenAI organization ID (default: OPENAI_ORG_ID env var)"
    )

    parser.add_argument(
        "--db-url",
        default=None,
        help="Database URL (default: DATABASE_URL env var)"
    )

    return parser
