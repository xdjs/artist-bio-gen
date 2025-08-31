#!/usr/bin/env python3
"""
Artist Bio Generator using OpenAI Responses API

This script processes CSV-like input files containing artist information
and uses the OpenAI Responses API to generate artist bios using reusable prompts.
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Any
from urllib.parse import urlparse

# Import data models
from .models import (
    ArtistData,
    ParseResult,
    ApiResponse,
    DatabaseConfig,
    DatabaseResult,
    ProcessingStats,
)

# Import constants
from .constants import (
    EXIT_SUCCESS,
    EXIT_INPUT_ERROR,
    EXIT_CONFIG_ERROR,
    EXIT_API_FAILURES,
    EXIT_INTERRUPTED,
    EXIT_UNEXPECTED_ERROR,
    DEFAULT_POOL_SIZE,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_QUERY_TIMEOUT,
)

# Import database functions
from .database import (
    create_db_connection_pool,
    get_db_connection,
    close_db_connection_pool,
    validate_database_url,
    create_database_config,
    get_database_url_from_env,
    update_artist_bio,
    get_table_name,
    classify_database_error,
    validate_uuid,
)

# Import API functions
from .api import (
    create_openai_client,
    call_openai_api,
    should_retry_error,
    calculate_retry_delay,
    retry_with_exponential_backoff,
)

# Import OpenAI for type annotations
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import psycopg3
    from psycopg3 import pool
except ImportError:
    psycopg3 = None
    pool = None

# Load environment variables from .env.local file
try:
    from dotenv import load_dotenv

    load_dotenv(".env.local")
except ImportError:
    # dotenv not available, continue without it
    pass


# Configure logging
def setup_logging(verbose: bool = False):
    """Setup logging configuration with appropriate level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    format_string = "%(asctime)s - %(levelname)s - %(message)s"

    logging.basicConfig(level=level, format=format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Set specific logger levels
    logging.getLogger("openai").setLevel(logging.WARNING)  # Reduce OpenAI client noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Reduce HTTP client noise


setup_logging()
logger = logging.getLogger("__main__")

# Input Parsing Functions


def parse_input_file(file_path: str) -> ParseResult:
    """
    Parse a CSV input file containing artist data.

    Expected format: artist_id,artist_name,artist_data
    - Lines starting with # are comments and will be skipped
    - Blank lines are skipped
    - artist_id must be a valid UUID, artist_name is required, artist_data is optional
    - Uses proper CSV parsing with quote-aware handling
    - Optional header row is automatically detected and skipped

    Args:
        file_path: Path to the input file

    Returns:
        ParseResult containing parsed artists and statistics

    Raises:
        FileNotFoundError: If the file doesn't exist
        UnicodeDecodeError: If the file can't be decoded as UTF-8
    """
    artists = []
    skipped_lines = 0
    error_lines = 0
    header_skipped = False

    try:
        with open(file_path, "r", encoding="utf-8", newline='') as f:
            csv_reader = csv.reader(f)
            
            for line_num, row in enumerate(csv_reader, 1):
                # Skip blank lines
                if not row or (len(row) == 1 and not row[0].strip()):
                    skipped_lines += 1
                    continue

                # Skip comment lines (lines starting with #)
                if row[0].strip().startswith("#"):
                    skipped_lines += 1
                    continue

                # Skip header row if it looks like a header
                if not header_skipped and len(row) >= 2:
                    first_field = row[0].strip().lower()
                    if first_field in ['artist_id', 'id', 'uuid']:
                        header_skipped = True
                        skipped_lines += 1
                        continue

                # Parse the row
                try:
                    if len(row) < 2:
                        logger.warning(f"Line {line_num}: Insufficient columns (need at least artist_id,artist_name), skipping")
                        error_lines += 1
                        continue

                    artist_id = row[0].strip()
                    artist_name = row[1].strip()
                    artist_data = row[2].strip() if len(row) > 2 else None

                    # Validate artist_id is a valid UUID
                    if not validate_uuid(artist_id):
                        logger.warning(f"Line {line_num}: Invalid UUID format for artist_id '{artist_id}', skipping")
                        error_lines += 1
                        continue

                    # Validate artist_name is not empty
                    if not artist_name:
                        logger.warning(f"Line {line_num}: Empty artist name, skipping")
                        error_lines += 1
                        continue

                    # Create artist data object
                    artist = ArtistData(
                        artist_id=artist_id,
                        name=artist_name, 
                        data=artist_data if artist_data else None
                    )
                    artists.append(artist)

                except Exception as e:
                    logger.warning(f"Line {line_num}: Error parsing line: {e}")
                    error_lines += 1
                    continue

    except FileNotFoundError:
        logger.error(f"Input file not found: {file_path}")
        raise
    except UnicodeDecodeError as e:
        logger.error(f"Unable to decode file as UTF-8: {file_path}, error: {e}")
        raise

    logger.info(f"Parsed {len(artists)} artists from {file_path}")
    if skipped_lines > 0:
        logger.info(f"Skipped {skipped_lines} comment/blank/header lines")
    if error_lines > 0:
        logger.warning(f"Encountered {error_lines} error lines")

    return ParseResult(
        artists=artists, skipped_lines=skipped_lines, error_lines=error_lines
    )


# CLI Utility Functions


def apply_environment_defaults(args):
    """Apply environment variable defaults to parsed arguments."""
    if args.prompt_id is None:
        args.prompt_id = os.getenv("OPENAI_PROMPT_ID")
    if not hasattr(args, 'db_url') or args.db_url is None:
        args.db_url = os.getenv("DATABASE_URL")
    return args


def _is_output_path_writable(path_str: str) -> Tuple[bool, Optional[str]]:
    """Check whether the output path's parent directory is writable without creating the file."""
    try:
        path = Path(path_str)
        parent = path.parent if path.parent != Path("") else Path(".")
        if not parent.exists():
            return False, f"Output directory does not exist: {parent}"
        if not os.access(parent, os.W_OK):
            return False, f"No write permission for directory: {parent}"
        return True, None
    except Exception as e:
        return False, f"Unable to validate output path '{path_str}': {e}"


def log_processing_start(
    total_artists: int, input_file: str, prompt_id: str, max_workers: int
) -> float:
    """
    Log the start of processing with configuration details.

    Args:
        total_artists: Total number of artists to process
        input_file: Path to input file
        prompt_id: OpenAI prompt ID
        max_workers: Maximum number of concurrent workers

    Returns:
        Start timestamp for timing calculations
    """
    start_time = time.time()
    start_datetime = datetime.fromtimestamp(start_time)

    logger.info("=" * 70)
    logger.info("ARTIST BIO GENERATION - PROCESSING STARTED")
    logger.info("=" * 70)
    logger.info(f"Start time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Prompt ID: {prompt_id}")
    logger.info(f"Total artists to process: {total_artists}")
    logger.info(f"Max concurrent workers: {max_workers}")
    logger.info("=" * 70)

    return start_time


def create_progress_bar(current: int, total: int, width: int = 30) -> str:
    """
    Create a text-based progress bar.

    Args:
        current: Current progress (1-based)
        total: Total items
        width: Width of the progress bar

    Returns:
        Progress bar string
    """
    if total == 0:
        return "[" + " " * width + "]"

    percentage = current / total
    filled = int(width * percentage)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


def log_progress_update(
    current: int,
    total: int,
    artist_name: str,
    success: bool,
    duration: float,
    worker_id: str = "main",
):
    """
    Log progress update for individual artist processing.

    Args:
        current: Current artist number (1-based)
        total: Total number of artists
        artist_name: Name of the artist being processed
        success: Whether the processing was successful
        duration: Time taken for this artist
        worker_id: Unique identifier for the worker thread
    """
    percentage = (current / total) * 100
    status_icon = "✅" if success else "❌"
    status_text = "SUCCESS" if success else "FAILED"
    progress_bar = create_progress_bar(current, total)

    logger.info(
        f"{progress_bar} [{current:3d}/{total:3d}] ({percentage:5.1f}%) [{worker_id}] {status_icon} {artist_name} - {status_text} ({duration:.2f}s)"
    )


def log_processing_summary(stats: ProcessingStats):
    """
    Log comprehensive processing summary with statistics.

    Args:
        stats: Processing statistics to log
    """
    end_datetime = datetime.fromtimestamp(stats.end_time)

    logger.info("=" * 70)
    logger.info("PROCESSING SUMMARY")
    logger.info("=" * 70)
    logger.info(f"End time: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(
        f"Total duration: {stats.total_duration:.2f} seconds ({timedelta(seconds=int(stats.total_duration))})"
    )
    logger.info("")
    logger.info("INPUT STATISTICS:")
    logger.info(f"  Total artists processed: {stats.total_artists}")
    logger.info(f"  Skipped lines (comments/blanks): {stats.skipped_lines}")
    logger.info(f"  Error lines (invalid data): {stats.error_lines}")
    logger.info("")
    logger.info("API CALL STATISTICS:")
    logger.info(f"  Successful calls: {stats.successful_calls}")
    logger.info(f"  Failed calls: {stats.failed_calls}")
    logger.info(
        f"  Success rate: {(stats.successful_calls / stats.total_artists * 100):.1f}%"
    )
    logger.info("")
    logger.info("PERFORMANCE STATISTICS:")
    logger.info(f"  Average time per artist: {stats.avg_time_per_artist:.2f}s")
    logger.info(f"  API calls per second: {stats.api_calls_per_second:.2f}")

    if stats.successful_calls > 0:
        estimated_total_time = stats.avg_time_per_artist * stats.total_artists
        logger.info(f"  Estimated total time: {estimated_total_time:.2f}s")

    # Calculate efficiency metrics
    if stats.total_artists > 0:
        processing_efficiency = (stats.successful_calls / stats.total_artists) * 100
        logger.info(f"  Processing efficiency: {processing_efficiency:.1f}%")

    # Time breakdown
    if stats.total_duration > 0:
        successful_time = stats.avg_time_per_artist * stats.successful_calls
        failed_time = stats.total_duration - successful_time
        logger.info(f"  Time spent on successful calls: {successful_time:.2f}s")
        if failed_time > 0:
            logger.info(f"  Time spent on failed calls: {failed_time:.2f}s")

    logger.info("=" * 70)

    # Log warnings for any issues
    if stats.failed_calls > 0:
        logger.warning(f"⚠️  {stats.failed_calls} artists failed to process")

    if stats.error_lines > 0:
        logger.warning(f"⚠️  {stats.error_lines} lines had parsing errors")

    if stats.skipped_lines > 0:
        logger.info(f"ℹ️  {stats.skipped_lines} lines were skipped (comments/blanks)")


def process_artists_concurrent(
    artists: List[ArtistData],
    client: OpenAI,
    prompt_id: str,
    version: Optional[str],
    max_workers: int,
) -> Tuple[int, int, List[ApiResponse]]:
    """
    Process artists concurrently using ThreadPoolExecutor with enhanced error isolation.

    Args:
        artists: List of artists to process
        client: Initialized OpenAI client
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        max_workers: Maximum number of concurrent workers

    Returns:
        Tuple of (successful_calls, failed_calls, all_responses)
    """
    successful_calls = 0
    failed_calls = 0
    all_responses = []

    logger.info(f"Starting concurrent processing with {max_workers} workers")

    # Track progress for periodic updates
    progress_interval = max(
        1, len(artists) // 10
    )  # Log every 10% or at least every artist
    last_progress_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks with unique worker IDs
        future_to_artist = {}
        future_to_worker = {}
        for i, artist in enumerate(artists):
            worker_id = f"W{i % max_workers + 1:02d}"  # W01, W02, W03, etc.
            future = executor.submit(
                call_openai_api, client, artist, prompt_id, version, worker_id
            )
            future_to_artist[future] = artist
            future_to_worker[future] = worker_id

        # Process completed tasks as they finish
        for future in as_completed(future_to_artist):
            artist = future_to_artist[future]
            worker_id = future_to_worker[future]
            try:
                api_response, duration = future.result()
                all_responses.append(api_response)

                if api_response.error:
                    failed_calls += 1
                    log_progress_update(
                        len(all_responses),
                        len(artists),
                        artist.name,
                        False,
                        duration,
                        worker_id,
                    )
                else:
                    successful_calls += 1
                    log_progress_update(
                        len(all_responses),
                        len(artists),
                        artist.name,
                        True,
                        duration,
                        worker_id,
                    )
                    # Print response to stdout
                    print(api_response.response_text)

            except Exception as e:
                # Enhanced error isolation - each thread failure is isolated
                failed_calls += 1
                exc_name = type(e).__name__
                error_msg = f"Concurrent processing error [{exc_name}]: {str(e)}"

                error_response = ApiResponse(
                    artist_id=artist.artist_id,
                    artist_name=artist.name,
                    artist_data=artist.data,
                    response_text="",
                    response_id="",
                    created=0,
                    error=error_msg,
                )
                all_responses.append(error_response)
                log_progress_update(
                    len(all_responses), len(artists), artist.name, False, 0.0, worker_id
                )
                logger.error(
                    f"[{worker_id}] Thread error processing artist '{artist.name}': {error_msg}"
                )

            # Log periodic progress updates during concurrent processing
            current_time = time.time()
            if (
                len(all_responses) % progress_interval == 0
                or len(all_responses) == len(artists)
                or current_time - last_progress_time >= 5.0
            ):  # At least every 5 seconds

                elapsed_time = current_time - last_progress_time
                current_rate = (
                    len(all_responses) / elapsed_time if elapsed_time > 0 else 0
                )
                remaining_artists = len(artists) - len(all_responses)
                estimated_remaining_time = (
                    remaining_artists / current_rate if current_rate > 0 else 0
                )

                logger.info(
                    f"📊 Concurrent Progress: {len(all_responses)}/{len(artists)} artists processed "
                    f"({(len(all_responses)/len(artists)*100):.1f}%) - "
                    f"Rate: {current_rate:.2f} artists/sec - "
                    f"ETA: {estimated_remaining_time:.0f}s remaining"
                )
                last_progress_time = current_time

    logger.info(
        f"Concurrent processing completed: {successful_calls} successful, {failed_calls} failed"
    )
    return successful_calls, failed_calls, all_responses


def write_jsonl_output(responses: List[ApiResponse], output_path: str, prompt_id: str, version: Optional[str] = None) -> None:
    """
    Write all API responses to a JSONL output file.
    
    Args:
        responses: List of API responses to write
        output_path: Path to the output JSONL file
        prompt_id: OpenAI prompt ID used for requests
        version: Optional prompt version used for requests
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for response in responses:
                # Build the JSONL record
                record = {
                    "artist_name": response.artist_name,
                    "request": {
                        "prompt_id": prompt_id,
                        "variables": {
                            "artist_name": response.artist_name,
                            "artist_data": response.artist_data if response.artist_data else "No additional data provided"
                        }
                    },
                    "response_text": response.response_text,
                    "response_id": response.response_id,
                    "created": response.created,
                    "error": response.error
                }
                
                # Add version to request if provided
                if version:
                    record["request"]["version"] = version
                
                # Omit artist_data from top level if empty (as per spec)
                if response.artist_data:
                    record["artist_data"] = response.artist_data
                
                # Write the JSONL record (one JSON object per line)
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        logger.info(f"Successfully wrote {len(responses)} records to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to write JSONL output to {output_path}: {e}")
        raise


def calculate_processing_stats(
    total_artists: int,
    successful_calls: int,
    failed_calls: int,
    skipped_lines: int,
    error_lines: int,
    start_time: float,
    end_time: float,
) -> ProcessingStats:
    """
    Calculate comprehensive processing statistics.

    Args:
        total_artists: Total number of artists
        successful_calls: Number of successful API calls
        failed_calls: Number of failed API calls
        skipped_lines: Number of skipped lines
        error_lines: Number of error lines
        start_time: Processing start timestamp
        end_time: Processing end timestamp

    Returns:
        ProcessingStats object with calculated statistics
    """
    total_duration = end_time - start_time
    avg_time_per_artist = total_duration / total_artists if total_artists > 0 else 0
    api_calls_per_second = total_artists / total_duration if total_duration > 0 else 0

    return ProcessingStats(
        total_artists=total_artists,
        successful_calls=successful_calls,
        failed_calls=failed_calls,
        skipped_lines=skipped_lines,
        error_lines=error_lines,
        start_time=start_time,
        end_time=end_time,
        total_duration=total_duration,
        avg_time_per_artist=avg_time_per_artist,
        api_calls_per_second=api_calls_per_second,
    )


def main():
    """Main entry point for the script."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Setup logging with verbose flag
    setup_logging(verbose=args.verbose)

    # Handle environment variable defaults
    args = apply_environment_defaults(args)

    try:
        # Parse the input file
        parse_result = parse_input_file(args.input_file)

        if not parse_result.artists:
            logger.error("No valid artists found in input file")
            sys.exit(1)

        if args.dry_run:
            logger.info("=" * 70)
            logger.info("DRY RUN MODE - SHOWING FIRST 5 ARTIST PAYLOADS")
            logger.info("=" * 70)
            for i, artist in enumerate(parse_result.artists[:5], 1):
                payload = {"artist_name": artist.name, "artist_data": artist.data}
                print(f"{i}. {json.dumps(payload, indent=2)}")

            if len(parse_result.artists) > 5:
                print(f"... and {len(parse_result.artists) - 5} more artists")

            logger.info("=" * 70)
            logger.info("DRY RUN COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            return

        # Validate required configuration
        if not args.prompt_id:
            logger.error(
                "Prompt ID is required. Set OPENAI_PROMPT_ID environment variable or use --prompt-id"
            )
            sys.exit(EXIT_CONFIG_ERROR)

        # Validate output path (non-destructive check)
        if not args.dry_run:
            ok, reason = _is_output_path_writable(args.output)
            if not ok:
                logger.error(f"Invalid output path: {reason}")
                sys.exit(EXIT_INPUT_ERROR)

        # Initialize OpenAI client
        client = create_openai_client()

        # Log processing start with enhanced details
        start_time = log_processing_start(
            total_artists=len(parse_result.artists),
            input_file=args.input_file,
            prompt_id=args.prompt_id,
            max_workers=args.max_workers,
        )

        # Process artists concurrently
        try:
            successful_calls, failed_calls, all_responses = process_artists_concurrent(
                artists=parse_result.artists,
                client=client,
                prompt_id=args.prompt_id,
                version=args.version,
                max_workers=args.max_workers,
            )

            # Write all responses to JSONL file
            write_jsonl_output(
                responses=all_responses,
                output_path=args.output,
                prompt_id=args.prompt_id,
                version=args.version
            )

        except KeyboardInterrupt:
            # Graceful interruption handling
            end_time = time.time()
            processed = successful_calls + failed_calls
            stats = calculate_processing_stats(
                total_artists=processed,
                successful_calls=successful_calls,
                failed_calls=failed_calls,
                skipped_lines=parse_result.skipped_lines,
                error_lines=parse_result.error_lines,
                start_time=start_time,
                end_time=end_time,
            )
            logger.warning("Processing interrupted by user (Ctrl+C). Partial summary:")
            log_processing_summary(stats)
            sys.exit(EXIT_INTERRUPTED)

        # Calculate overall timing and statistics
        end_time = time.time()
        stats = calculate_processing_stats(
            total_artists=len(parse_result.artists),
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            skipped_lines=parse_result.skipped_lines,
            error_lines=parse_result.error_lines,
            start_time=start_time,
            end_time=end_time,
        )

        # Log comprehensive summary
        log_processing_summary(stats)

        # Exit with appropriate code
        if failed_calls > 0:
            logger.error(f"Processing completed with {failed_calls} failures")
            sys.exit(EXIT_API_FAILURES)
        else:
            logger.info("🎉 All artists processed successfully!")

    except (FileNotFoundError, UnicodeDecodeError, PermissionError) as e:
        logger.error(f"Failed to process input file: {e}")
        # Maintain legacy behavior expected by tests
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(EXIT_UNEXPECTED_ERROR)


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

    return parser


if __name__ == "__main__":
    main()
