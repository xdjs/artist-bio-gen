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
    process_artists_concurrent,
    log_processing_start,
    log_processing_summary,
    calculate_processing_stats,
    get_processed_artist_ids,
)

from ..api import (
    create_openai_client,
)

from ..database import (
    create_db_connection_pool,
    create_database_config,
    close_db_connection_pool,
)

from .parser import (
    create_argument_parser,
)

from ..utils import (
    setup_logging,
    _is_output_path_writable,
)

from ..config import Env
from ..config.loader import ConfigLoader
from ..config.schema import ConfigSchema

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the script."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Setup logging with verbose flag
    setup_logging(verbose=args.verbose)

    # Load environment configuration using the new schema-driven approach
    try:
        # Use ConfigLoader directly with parsed args for cleaner integration
        config = ConfigLoader.load(schema=ConfigSchema, cli_args=args)

        # Create Env instance for backward compatibility
        env = Env(
            OPENAI_API_KEY=config.openai_api_key,
            DATABASE_URL=config.database_url,
            OPENAI_PROMPT_ID=config.openai_prompt_id,
            QUOTA_MONITORING=config.quota_monitoring,
            QUOTA_THRESHOLD=config.quota_threshold,
            DAILY_REQUEST_LIMIT=config.daily_request_limit,
            PAUSE_DURATION_HOURS=config.pause_duration_hours,
            QUOTA_LOG_INTERVAL=config.quota_log_interval,
        )

        # Set the global env instance for components that use Env.current()
        # This is a bit of a hack but maintains backward compatibility
        import artist_bio_gen.config.env as env_module
        env_module._ENV = env

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    try:
        # Handle resume functionality - read already processed artists
        processed_ids = set()
        if args.resume:
            try:
                processed_ids = get_processed_artist_ids(args.output)
                if processed_ids:
                    logger.info(f"Resume mode: Found {len(processed_ids)} already-processed artists in {args.output}")
                else:
                    logger.info(f"Resume mode: No existing output file or processed artists found in {args.output}")
            except Exception as e:
                logger.error(f"Failed to read processed artists for resume: {e}")
                sys.exit(EXIT_INPUT_ERROR)

        # Parse the input file (with optional resume filtering)
        parse_result = parse_input_file(args.input_file, skip_processed_ids=processed_ids if args.resume else None)

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

        # Validate required configuration - now handled by schema validation
        # OPENAI_PROMPT_ID is optional in the schema, so check it here for backward compatibility
        if not env.OPENAI_PROMPT_ID:
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
                # Use database URL from environment configuration
                db_config = create_database_config(url=env.DATABASE_URL, test_mode=args.test_mode)
                db_pool = create_db_connection_pool(db_config)
                logger.info(f"Database connection initialized {'(test mode)' if args.test_mode else ''}")
            except Exception as e:
                logger.error(f"Failed to initialize database connection: {e}")
                sys.exit(EXIT_CONFIG_ERROR)

        # Log processing start with enhanced details
        start_time = log_processing_start(
            total_artists=len(parse_result.artists),
            input_file=args.input_file,
            prompt_id=env.OPENAI_PROMPT_ID,
            max_workers=args.max_workers,
        )

        # Process artists concurrently
        try:
            successful_calls, failed_calls = process_artists_concurrent(
                artists=parse_result.artists,
                client=client,
                prompt_id=env.OPENAI_PROMPT_ID,
                version=args.version,
                max_workers=args.max_workers,
                output_path=args.output,
                db_pool=db_pool,
                test_mode=args.test_mode,
                resume_mode=args.resume,
                daily_request_limit=env.DAILY_REQUEST_LIMIT,
                quota_threshold=env.QUOTA_THRESHOLD,
                quota_monitoring=env.QUOTA_MONITORING,
            )

            logger.info(f"Streaming output completed: {args.output}")

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
            logger.info(f"Partial results saved to streaming output: {args.output}")
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