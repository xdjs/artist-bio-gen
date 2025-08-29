#!/usr/bin/env python3
"""
Artist Bio Generator using OpenAI Responses API

This script processes CSV-like input files containing artist information
and uses the OpenAI Responses API to generate artist bios using reusable prompts.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple

# Load environment variables from .env.local file
try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
except ImportError:
    # dotenv not available, continue without it
    pass

# Configure logging
def setup_logging(verbose: bool = False):
    """Setup logging configuration with appropriate level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    format_string = '%(asctime)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_string,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set specific logger levels
    logging.getLogger('openai').setLevel(logging.WARNING)  # Reduce OpenAI client noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)  # Reduce HTTP client noise

setup_logging()
logger = logging.getLogger('__main__')

# OpenAI client
try:
    from openai import OpenAI
except ImportError:
    logger.error("OpenAI package not installed. Please install with: pip install openai")
    sys.exit(1)


class ArtistData(NamedTuple):
    """Represents parsed artist data from input file."""
    name: str
    data: Optional[str] = None


class ParseResult(NamedTuple):
    """Result of parsing an input file."""
    artists: List[ArtistData]
    skipped_lines: int
    error_lines: int


class ApiResponse(NamedTuple):
    """Result of an OpenAI API call."""
    artist_name: str
    artist_data: Optional[str]
    response_text: str
    response_id: str
    created: int
    error: Optional[str] = None


class ProcessingStats(NamedTuple):
    """Statistics for processing operations."""
    total_artists: int
    successful_calls: int
    failed_calls: int
    skipped_lines: int
    error_lines: int
    start_time: float
    end_time: float
    total_duration: float
    avg_time_per_artist: float
    api_calls_per_second: float


def parse_input_file(file_path: str) -> ParseResult:
    """
    Parse a CSV-like input file containing artist data.
    
    Expected format: artist_name,artist_data
    - Lines starting with # are comments and will be skipped
    - Blank lines are skipped
    - artist_name is required, artist_data is optional
    - Whitespace is trimmed from both fields
    
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
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip blank lines
                if not line:
                    skipped_lines += 1
                    continue
                
                # Skip comment lines
                if line.startswith('#'):
                    skipped_lines += 1
                    continue
                
                # Parse the line
                try:
                    # Split on first comma only
                    parts = line.split(',', 1)
                    artist_name = parts[0].strip()
                    artist_data = parts[1].strip() if len(parts) > 1 else None
                    
                    # Validate artist name is not empty
                    if not artist_name:
                        logger.warning(f"Line {line_num}: Empty artist name, skipping")
                        error_lines += 1
                        continue
                    
                    # Create artist data object
                    artist = ArtistData(
                        name=artist_name,
                        data=artist_data if artist_data else None
                    )
                    artists.append(artist)
                    
                except Exception as e:
                    logger.warning(f"Line {line_num}: Error parsing line '{line}': {e}")
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
        logger.info(f"Skipped {skipped_lines} comment/blank lines")
    if error_lines > 0:
        logger.warning(f"Encountered {error_lines} error lines")
    
    return ParseResult(
        artists=artists,
        skipped_lines=skipped_lines,
        error_lines=error_lines
    )


def create_openai_client() -> OpenAI:
    """Create and initialize OpenAI client."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client initialized successfully")
    return client


def call_openai_api(client: OpenAI, artist: ArtistData, prompt_id: str, version: Optional[str] = None) -> Tuple[ApiResponse, float]:
    """
    Make an API call to OpenAI Responses API for a single artist.
    
    Args:
        client: Initialized OpenAI client
        artist: Artist data to process
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        
    Returns:
        Tuple of (ApiResponse with the result or error information, duration in seconds)
    """
    start_time = time.time()
    
    try:
        # Build variables dictionary
        variables = {
            "artist_name": artist.name,
            "artist_data": artist.data if artist.data else "No additional data provided"
        }
        
        # Build prompt configuration
        prompt_config = {
            "id": prompt_id,
            "variables": variables
        }
        if version:
            prompt_config["version"] = version
        
        logger.debug(f"Calling API for artist: {artist.name}")
        
        # Make the API call
        response = client.responses.create(
            prompt=prompt_config
        )
        
        # Extract response data
        response_text = response.output_text
        response_id = response.id
        created = int(response.created_at)
        
        # Calculate timing
        end_time = time.time()
        duration = end_time - start_time
        
        api_response = ApiResponse(
            artist_name=artist.name,
            artist_data=artist.data,
            response_text=response_text,
            response_id=response_id,
            created=created
        )
        
        return api_response, duration
        
    except Exception as e:
        # Calculate timing even for errors
        end_time = time.time()
        duration = end_time - start_time
        
        error_msg = f"API call failed for artist '{artist.name}': {str(e)}"
        
        api_response = ApiResponse(
            artist_name=artist.name,
            artist_data=artist.data,
            response_text="",
            response_id="",
            created=0,
            error=error_msg
        )
        
        return api_response, duration


def apply_environment_defaults(args):
    """Apply environment variable defaults to parsed arguments."""
    if args.prompt_id is None:
        args.prompt_id = os.getenv('OPENAI_PROMPT_ID')
    return args


def log_processing_start(total_artists: int, input_file: str, prompt_id: str, max_workers: int) -> float:
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


def log_progress_update(current: int, total: int, artist_name: str, success: bool, duration: float):
    """
    Log progress update for individual artist processing.
    
    Args:
        current: Current artist number (1-based)
        total: Total number of artists
        artist_name: Name of the artist being processed
        success: Whether the processing was successful
        duration: Time taken for this artist
    """
    percentage = (current / total) * 100
    status_icon = "✅" if success else "❌"
    status_text = "SUCCESS" if success else "FAILED"
    progress_bar = create_progress_bar(current, total)
    
    logger.info(f"{progress_bar} [{current:3d}/{total:3d}] ({percentage:5.1f}%) {status_icon} {artist_name} - {status_text} ({duration:.2f}s)")


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
    logger.info(f"Total duration: {stats.total_duration:.2f} seconds ({timedelta(seconds=int(stats.total_duration))})")
    logger.info("")
    logger.info("INPUT STATISTICS:")
    logger.info(f"  Total artists processed: {stats.total_artists}")
    logger.info(f"  Skipped lines (comments/blanks): {stats.skipped_lines}")
    logger.info(f"  Error lines (invalid data): {stats.error_lines}")
    logger.info("")
    logger.info("API CALL STATISTICS:")
    logger.info(f"  Successful calls: {stats.successful_calls}")
    logger.info(f"  Failed calls: {stats.failed_calls}")
    logger.info(f"  Success rate: {(stats.successful_calls / stats.total_artists * 100):.1f}%")
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


def calculate_processing_stats(
    total_artists: int,
    successful_calls: int,
    failed_calls: int,
    skipped_lines: int,
    error_lines: int,
    start_time: float,
    end_time: float
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
        api_calls_per_second=api_calls_per_second
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
                payload = {
                    "artist_name": artist.name,
                    "artist_data": artist.data
                }
                print(f"{i}. {json.dumps(payload, indent=2)}")
            
            if len(parse_result.artists) > 5:
                print(f"... and {len(parse_result.artists) - 5} more artists")
            
            logger.info("=" * 70)
            logger.info("DRY RUN COMPLETED SUCCESSFULLY")
            logger.info("=" * 70)
            return
        
        # Validate required configuration
        if not args.prompt_id:
            logger.error("Prompt ID is required. Set OPENAI_PROMPT_ID environment variable or use --prompt-id")
            sys.exit(1)
        
        # Initialize OpenAI client
        client = create_openai_client()
        
        # Log processing start with enhanced details
        start_time = log_processing_start(
            total_artists=len(parse_result.artists),
            input_file=args.input_file,
            prompt_id=args.prompt_id,
            max_workers=args.max_workers
        )
        
        # Process artists sequentially (concurrency will be added later)
        successful_calls = 0
        failed_calls = 0
        
        # Log periodic progress updates
        progress_interval = max(1, len(parse_result.artists) // 10)  # Log every 10% or at least every artist
        
        for i, artist in enumerate(parse_result.artists, 1):
            # Make API call
            api_response, artist_duration = call_openai_api(client, artist, args.prompt_id, args.version)
            
            if api_response.error:
                failed_calls += 1
                log_progress_update(i, len(parse_result.artists), artist.name, False, artist_duration)
            else:
                successful_calls += 1
                log_progress_update(i, len(parse_result.artists), artist.name, True, artist_duration)
                # Print response to stdout
                print(api_response.response_text)
                
                # TODO: Write to JSONL file (will be implemented in output formatting task)
            
            # Log periodic summary
            if i % progress_interval == 0 or i == len(parse_result.artists):
                elapsed_time = time.time() - start_time
                current_rate = i / elapsed_time if elapsed_time > 0 else 0
                remaining_artists = len(parse_result.artists) - i
                estimated_remaining_time = remaining_artists / current_rate if current_rate > 0 else 0
                
                logger.info(f"📊 Progress Update: {i}/{len(parse_result.artists)} artists processed "
                          f"({(i/len(parse_result.artists)*100):.1f}%) - "
                          f"Rate: {current_rate:.2f} artists/sec - "
                          f"ETA: {estimated_remaining_time:.0f}s remaining")
        
        # Calculate overall timing and statistics
        end_time = time.time()
        stats = calculate_processing_stats(
            total_artists=len(parse_result.artists),
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            skipped_lines=parse_result.skipped_lines,
            error_lines=parse_result.error_lines,
            start_time=start_time,
            end_time=end_time
        )
        
        # Log comprehensive summary
        log_processing_summary(stats)
        
        # Exit with appropriate code
        if failed_calls > 0:
            logger.error(f"Processing completed with {failed_calls} failures")
            sys.exit(1)
        else:
            logger.info("🎉 All artists processed successfully!")
        
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.error(f"Failed to process input file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


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
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--input-file',
        required=True,
        help='CSV-like text file path containing artist data'
    )
    
    # Optional arguments with defaults
    parser.add_argument(
        '--prompt-id',
        default=None,
        help='OpenAI prompt ID (default: OPENAI_PROMPT_ID env var)'
    )
    

    
    parser.add_argument(
        '--version',
        help='Prompt version (optional)'
    )
    
    parser.add_argument(
        '--output',
        default='out.jsonl',
        help='JSONL output file path (default: out.jsonl)'
    )
    
    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Maximum number of concurrent requests (default: 4)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse inputs and show first 5 payloads without making API calls'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )
    
    return parser


if __name__ == '__main__':
    main()