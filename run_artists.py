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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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


def call_openai_api(client: OpenAI, artist: ArtistData, prompt_id: str, version: Optional[str] = None) -> ApiResponse:
    """
    Make an API call to OpenAI Responses API for a single artist.
    
    Args:
        client: Initialized OpenAI client
        artist: Artist data to process
        prompt_id: OpenAI prompt ID
        version: Optional prompt version
        
    Returns:
        ApiResponse with the result or error information
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
        
        logger.info(f"Successfully processed artist: {artist.name} (took {duration:.2f}s)")
        
        return ApiResponse(
            artist_name=artist.name,
            artist_data=artist.data,
            response_text=response_text,
            response_id=response_id,
            created=created
        )
        
    except Exception as e:
        # Calculate timing even for errors
        end_time = time.time()
        duration = end_time - start_time
        
        error_msg = f"API call failed for artist '{artist.name}': {str(e)}"
        logger.error(f"{error_msg} (took {duration:.2f}s)")
        
        return ApiResponse(
            artist_name=artist.name,
            artist_data=artist.data,
            response_text="",
            response_id="",
            created=0,
            error=error_msg
        )


def apply_environment_defaults(args):
    """Apply environment variable defaults to parsed arguments."""
    if args.prompt_id is None:
        args.prompt_id = os.getenv('OPENAI_PROMPT_ID')
    return args


def main():
    """Main entry point for the script."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Handle environment variable defaults
    args = apply_environment_defaults(args)
    
    logger.info("Starting artist bio generation process")
    logger.info(f"Input file: {args.input_file}")
    logger.info(f"Prompt ID: {args.prompt_id}")
    
    try:
        # Parse the input file
        parse_result = parse_input_file(args.input_file)
        
        if not parse_result.artists:
            logger.error("No valid artists found in input file")
            sys.exit(1)
        
        if args.dry_run:
            logger.info("DRY RUN MODE - Showing first 5 artist payloads:")
            for i, artist in enumerate(parse_result.artists[:5], 1):
                payload = {
                    "artist_name": artist.name,
                    "artist_data": artist.data
                }
                print(f"{i}. {json.dumps(payload, indent=2)}")
            
            if len(parse_result.artists) > 5:
                print(f"... and {len(parse_result.artists) - 5} more artists")
            
            logger.info("Dry run completed successfully")
            return
        
        # Validate required configuration
        if not args.prompt_id:
            logger.error("Prompt ID is required. Set OPENAI_PROMPT_ID environment variable or use --prompt-id")
            sys.exit(1)
        
        # Initialize OpenAI client
        client = create_openai_client()
        
        # Process artists sequentially (concurrency will be added later)
        logger.info(f"Processing {len(parse_result.artists)} artists...")
        successful_calls = 0
        failed_calls = 0
        
        # Start overall timing
        overall_start_time = time.time()
        
        for i, artist in enumerate(parse_result.artists, 1):
            logger.info(f"Processing artist {i}/{len(parse_result.artists)}: {artist.name}")
            
            # Make API call
            api_response = call_openai_api(client, artist, args.prompt_id, args.version)
            
            if api_response.error:
                failed_calls += 1
                logger.error(f"Failed to process {artist.name}: {api_response.error}")
            else:
                successful_calls += 1
                # Print response to stdout
                print(api_response.response_text)
                
                # TODO: Write to JSONL file (will be implemented in output formatting task)
        
        # Calculate overall timing
        overall_end_time = time.time()
        overall_duration = overall_end_time - overall_start_time
        
        # Summary
        logger.info(f"Processing completed: {successful_calls} successful, {failed_calls} failed")
        logger.info(f"Total processing time: {overall_duration:.2f}s")
        
        if successful_calls > 0:
            avg_time_per_artist = overall_duration / successful_calls
            logger.info(f"Average time per artist: {avg_time_per_artist:.2f}s")
        
        if failed_calls > 0:
            logger.warning(f"{failed_calls} artists failed to process")
            sys.exit(1)
        
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
    
    return parser


if __name__ == '__main__':
    main()