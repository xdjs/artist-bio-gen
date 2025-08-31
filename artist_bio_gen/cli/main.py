"""
CLI main application module.

This module contains the main application entry point and high-level
application flow coordination for the artist bio generator.
"""

import json
import logging
import sys
import time

from ..constants import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_API_FAILURES,
    EXIT_INTERRUPTED,
    EXIT_UNEXPECTED_ERROR,
)

from ..core import (
    parse_input_file,
    write_jsonl_output,
    process_artists_concurrent,
    log_processing_start,
    log_processing_summary,
    calculate_processing_stats,
)

from ..api import (
    create_openai_client,
)

from ..database import (
    create_db_connection_pool,
    get_database_url_from_env,
    create_database_config,
    close_db_connection_pool,
)

from .parser import (
    create_argument_parser,
)

from ..utils import (
    setup_logging,
    apply_environment_defaults,
    _is_output_path_writable,
)

logger = logging.getLogger(__name__)


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

        # Initialize database connection if enabled
        db_pool = None
        if args.enable_db:
            try:
                db_url = get_database_url_from_env(test_mode=args.test_mode)
                if not db_url:
                    logger.error("Database URL not found. Set DATABASE_URL environment variable.")
                    sys.exit(EXIT_CONFIG_ERROR)
                
                db_config = create_database_config(url=db_url, test_mode=args.test_mode)
                db_pool = create_db_connection_pool(db_config)
                logger.info(f"Database connection initialized {'(test mode)' if args.test_mode else ''}")
            except Exception as e:
                logger.error(f"Failed to initialize database connection: {e}")
                sys.exit(EXIT_CONFIG_ERROR)

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
                db_pool=db_pool,
                test_mode=args.test_mode,
            )

            # Write all responses to JSONL file
            write_jsonl_output(
                responses=all_responses,
                output_path=args.output,
                prompt_id=args.prompt_id,
                version=args.version,
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
    finally:
        # Clean up database connection pool
        if 'db_pool' in locals() and db_pool is not None:
            try:
                close_db_connection_pool(db_pool)
            except Exception as e:
                logger.warning(f"Error closing database connection pool: {e}")
