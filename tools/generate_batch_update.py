#!/usr/bin/env python3
"""
Batch Update Generator

Generates SQL batch update files from JSONL output for efficient bulk database updates
using PostgreSQL COPY operations.
"""

import argparse
import csv
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple


def validate_uuid_format(artist_id: str) -> bool:
    """
    Validate that the artist_id is a properly formatted UUID.

    Args:
        artist_id: The artist ID string to validate

    Returns:
        bool: True if valid UUID format, False otherwise
    """
    try:
        # Ensure we have a string
        if not isinstance(artist_id, str):
            return False
        uuid.UUID(artist_id)
        return True
    except (ValueError, TypeError):
        return False


def has_valid_bio(entry: Dict[str, Any]) -> bool:
    """
    Check if the entry has a valid bio (error field is null/empty).

    Args:
        entry: The JSONL entry dictionary

    Returns:
        bool: True if bio is valid (no error), False otherwise
    """
    error_field = entry.get("error")
    return error_field is None or error_field == "" or error_field == "null"


def validate_jsonl_entry(entry: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate a JSONL entry for required fields and data integrity.

    Args:
        entry: The parsed JSONL entry dictionary

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Check for required fields
    if "artist_id" not in entry:
        return False, "Missing required field 'artist_id'"

    if "bio" not in entry:
        return False, "Missing required field 'bio'"

    # Validate UUID format
    if not validate_uuid_format(entry["artist_id"]):
        return False, f"Invalid UUID format for artist_id: {entry['artist_id']}"

    # Check if bio is valid (no error)
    if not has_valid_bio(entry):
        return False, f"Bio has error: {entry.get('error', 'Unknown error')}"

    # Check if bio content exists and is not empty
    bio = entry.get("bio", "").strip()
    if not bio:
        return False, "Bio content is empty"

    return True, ""


def parse_jsonl_line(
    line: str, line_number: int
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Parse a single JSONL line with error handling.

    Args:
        line: The JSONL line to parse
        line_number: Line number for error reporting

    Returns:
        Tuple[Optional[Dict], str]: (parsed_entry, error_message)
    """
    line = line.strip()
    if not line:
        return None, ""  # Skip empty lines

    try:
        entry = json.loads(line)
        return entry, ""
    except json.JSONDecodeError as e:
        return None, f"Line {line_number}: JSON decode error - {str(e)}"


def parse_jsonl_file(file_path: str) -> Tuple[list, list, list, dict]:
    """
    Parse JSONL file line by line with comprehensive error handling and duplicate detection.

    Args:
        file_path: Path to the JSONL input file

    Returns:
        Tuple[list, list, list, dict]: (valid_entries, invalid_entries, error_messages, statistics)
    """
    # First pass: parse all entries and collect artist_ids to detect duplicates
    all_parsed_entries = []
    artist_id_counts: Dict[str, int] = {}
    error_messages = []
    
    # Initialize statistics tracking
    statistics = {
        "total_lines_processed": 0,
        "empty_lines": 0,
        "json_decode_errors": 0,
        "valid_entries": 0,
        "invalid_entries": 0,
        "duplicate_entries": 0,
        "duplicated_artist_ids": 0,
    }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                statistics["total_lines_processed"] += 1
                
                # Parse the JSON line
                entry, parse_error = parse_jsonl_line(line, line_number)

                if parse_error:
                    error_messages.append(parse_error)
                    statistics["json_decode_errors"] += 1
                    continue

                if entry is None:  # Empty line
                    statistics["empty_lines"] += 1
                    continue

                # Store entry with line number for processing
                entry["_line_number"] = line_number
                all_parsed_entries.append(entry)

                # Track artist_id counts for duplicate detection
                artist_id = entry.get("artist_id")
                if artist_id:
                    artist_id_counts[artist_id] = artist_id_counts.get(artist_id, 0) + 1

    except FileNotFoundError:
        error_messages.append(f"Input file not found: {file_path}")
        return [], [], error_messages, statistics
    except PermissionError:
        error_messages.append(f"Permission denied reading file: {file_path}")
        return [], [], error_messages, statistics
    except Exception as e:
        error_messages.append(f"Unexpected error reading file: {str(e)}")
        return [], [], error_messages, statistics

    # Identify duplicated artist_ids
    duplicated_artist_ids = {
        aid for aid, count in artist_id_counts.items() if count > 1
    }
    statistics["duplicated_artist_ids"] = len(duplicated_artist_ids)

    # Second pass: process entries and separate valid, invalid, and duplicates
    valid_entries = []
    invalid_entries = []
    duplicate_entries = []

    for entry in all_parsed_entries:
        line_number = entry["_line_number"]
        artist_id = entry.get("artist_id")

        # Check if this artist_id is duplicated
        if artist_id and artist_id in duplicated_artist_ids:
            error_messages.append(
                f"Line {line_number}: Duplicate artist_id: {artist_id}"
            )
            entry["_error"] = f"Duplicate artist_id: {artist_id}"
            duplicate_entries.append(entry)
            statistics["duplicate_entries"] += 1
            continue

        # Validate the entry
        is_valid, validation_error = validate_jsonl_entry(entry)

        if is_valid:
            # Remove internal tracking fields before adding to valid entries
            clean_entry = {k: v for k, v in entry.items() if not k.startswith("_")}
            valid_entries.append(clean_entry)
            statistics["valid_entries"] += 1
        else:
            error_messages.append(f"Line {line_number}: {validation_error}")
            entry["_error"] = validation_error
            invalid_entries.append(entry)
            statistics["invalid_entries"] += 1

    # Combine invalid and duplicate entries
    all_invalid_entries = invalid_entries + duplicate_entries

    # Log duplicate detection summary
    if duplicated_artist_ids:
        error_messages.append(
            f"Duplicate detection: found {len(duplicated_artist_ids)} duplicated artist_ids affecting {sum(artist_id_counts[aid] for aid in duplicated_artist_ids)} entries"
        )

    return valid_entries, all_invalid_entries, error_messages, statistics


def setup_argument_parser() -> argparse.ArgumentParser:
    """
    Set up command-line argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Generate SQL batch update files from JSONL output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input out.jsonl
  %(prog)s --input out.jsonl --test-mode
  %(prog)s --input out.jsonl --output-dir /tmp/batches
        """,
    )

    parser.add_argument(
        "--input", type=str, required=True, help="Input JSONL file path (required)"
    )

    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Use test_artists table instead of artists table",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory for generated files (default: current directory)",
    )

    return parser


def generate_timestamp() -> str:
    """
    Generate timestamp in YYYYMMDD_HHMMSS format.

    Returns:
        str: Formatted timestamp string
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_output_filenames(timestamp: str, output_dir: str) -> Tuple[str, str, str]:
    """
    Generate output filenames based on timestamp.

    Args:
        timestamp: Timestamp string in YYYYMMDD_HHMMSS format
        output_dir: Output directory path

    Returns:
        Tuple[str, str, str]: (sql_file, csv_file, skipped_file) paths
    """
    sql_file = os.path.join(output_dir, f"batch_update_{timestamp}.sql")
    csv_file = os.path.join(output_dir, f"batch_update_{timestamp}.csv")
    skipped_file = os.path.join(output_dir, f"batch_update_skipped_{timestamp}.jsonl")

    return sql_file, csv_file, skipped_file


def write_csv_file(valid_entries: list, csv_file_path: str) -> None:
    """
    Write valid entries to CSV file with UTF-8 support and proper escaping.

    Args:
        valid_entries: List of valid JSONL entries
        csv_file_path: Path to output CSV file
    """
    print(f"  Writing CSV data with {len(valid_entries)} entries...")
    # Create temporary file first for atomic writes
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".csv", dir=os.path.dirname(csv_file_path)
    )

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8", newline="") as temp_file:
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            # Write header
            writer.writerow(["id", "bio"])

            # Write data rows with error tracking
            rows_written = 0
            for i, entry in enumerate(valid_entries):
                try:
                    artist_id = entry["artist_id"]
                    bio = entry["bio"]
                    writer.writerow([artist_id, bio])
                    rows_written += 1
                except (KeyError, TypeError) as e:
                    print(f"Warning: Skipping entry {i+1} due to data error: {str(e)}", file=sys.stderr)
                    continue
                except Exception as e:
                    raise RuntimeError(f"Failed to write CSV row {i+1}: {str(e)}") from e

        # Verify temp file was written correctly
        if rows_written == 0 and len(valid_entries) > 0:
            raise RuntimeError("No data was written to CSV file - all entries may be invalid")
        
        print(f"  Successfully wrote {rows_written} rows to CSV file")

        # Move temp file to final location atomically
        try:
            os.rename(temp_path, csv_file_path)
        except OSError as e:
            raise RuntimeError(f"Failed to move temporary CSV file to final location: {str(e)}") from e

    except Exception as e:
        # Enhanced cleanup with detailed error reporting
        temp_file_exists = os.path.exists(temp_path)
        try:
            if temp_file_exists:
                os.unlink(temp_path)
                print(f"  Cleaned up temporary file: {temp_path}", file=sys.stderr)
        except OSError as cleanup_error:
            print(f"  Warning: Could not clean up temporary file {temp_path}: {str(cleanup_error)}", file=sys.stderr)
        
        # Re-raise with enhanced error context
        raise RuntimeError(f"CSV file generation failed: {str(e)}") from e


def write_skipped_file(invalid_entries: list, skipped_file_path: str) -> None:
    """
    Write invalid/skipped entries to JSONL file.

    Args:
        invalid_entries: List of invalid JSONL entries
        skipped_file_path: Path to output skipped JSONL file
    """
    print(f"  Writing skipped entries with {len(invalid_entries)} entries...")
    # Create temporary file first for atomic writes
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".jsonl", dir=os.path.dirname(skipped_file_path)
    )

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            entries_written = 0
            for i, entry in enumerate(invalid_entries):
                try:
                    # Remove internal tracking fields before writing
                    clean_entry = {k: v for k, v in entry.items() if not k.startswith("_")}
                    json.dump(clean_entry, temp_file, ensure_ascii=False)
                    temp_file.write("\n")
                    entries_written += 1
                except (TypeError, ValueError) as e:
                    print(f"Warning: Could not serialize skipped entry {i+1}: {str(e)}", file=sys.stderr)
                    # Write a fallback entry with error information
                    fallback_entry = {
                        "original_line": entry.get("_line_number", i+1),
                        "serialization_error": str(e),
                        "partial_data": str(entry)[:200] + ("..." if len(str(entry)) > 200 else "")
                    }
                    json.dump(fallback_entry, temp_file, ensure_ascii=False)
                    temp_file.write("\n")
                    entries_written += 1
                except Exception as e:
                    raise RuntimeError(f"Failed to write skipped entry {i+1}: {str(e)}") from e

        print(f"  Successfully wrote {entries_written} entries to skipped file")

        # Move temp file to final location atomically
        try:
            os.rename(temp_path, skipped_file_path)
        except OSError as e:
            raise RuntimeError(f"Failed to move temporary skipped file to final location: {str(e)}") from e

    except Exception as e:
        # Enhanced cleanup with detailed error reporting
        temp_file_exists = os.path.exists(temp_path)
        try:
            if temp_file_exists:
                os.unlink(temp_path)
                print(f"  Cleaned up temporary file: {temp_path}", file=sys.stderr)
        except OSError as cleanup_error:
            print(f"  Warning: Could not clean up temporary file {temp_path}: {str(cleanup_error)}", file=sys.stderr)
        
        # Re-raise with enhanced error context
        raise RuntimeError(f"Skipped file generation failed: {str(e)}") from e


def write_sql_file(
    csv_file_path: str,
    sql_file_path: str,
    table_name: str,
    total_records: int,
    batch_size: int = 1000,
) -> None:
    """
    Generate SQL script file with batched UPDATE statements.

    Args:
        csv_file_path: Path to the CSV data file
        sql_file_path: Path to output SQL script file
        table_name: Target table name (artists or test_artists)
        total_records: Total number of records to process
        batch_size: Number of records per batch (default: 1000)
    """
    num_batches = (total_records + batch_size - 1) // batch_size
    print(f"  Generating SQL script for {total_records} records in {num_batches} batches...")
    # Create temporary file first for atomic writes
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=".sql", dir=os.path.dirname(sql_file_path)
    )

    try:
        lines_written = 0
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            # Write SQL header with error handling
            temp_file.write("\\set ON_ERROR_STOP on\n")
            temp_file.write("\\echo 'Starting batch bio update...'\n")
            temp_file.write("\n")
            lines_written += 3

            # Begin transaction and create temp table
            temp_file.write("BEGIN;\n")
            temp_file.write("\n")
            temp_file.write("CREATE TEMP TABLE temp_bio_updates (id UUID, bio TEXT);\n")
            temp_file.write("\n")
            lines_written += 4

            # Verify CSV file exists before referencing it (only if we expect records)
            if total_records > 0 and not os.path.exists(csv_file_path):
                raise RuntimeError(f"CSV file does not exist: {csv_file_path}")

            # Copy CSV data into the temp table using psql \copy
            # Use only the basename so the script references a relative path
            csv_filename = os.path.basename(csv_file_path)
            temp_file.write(
                f"\\copy temp_bio_updates FROM '{csv_filename}' WITH CSV HEADER;\n"
            )
            temp_file.write("\n")
            lines_written += 2

            # Generate batched UPDATE statements
            if total_records > 0:
                num_batches = (
                    total_records + batch_size - 1
                ) // batch_size  # Ceiling division

                for batch_num in range(num_batches):
                    offset = batch_num * batch_size
                    current_batch_size = min(batch_size, total_records - offset)
                    batch_end = offset + current_batch_size

                    try:
                        temp_file.write(
                            f"\\echo 'Processing batch {batch_num + 1}/{num_batches} (records {offset + 1}-{batch_end})...'\n"
                        )
                        temp_file.write(
                            f"WITH batch AS (SELECT * FROM temp_bio_updates ORDER BY id LIMIT {batch_size} OFFSET {offset})\n"
                        )
                        temp_file.write(
                            f"UPDATE {table_name} SET bio = batch.bio, updated_at = CURRENT_TIMESTAMP\n"
                        )
                        temp_file.write(f"FROM batch WHERE {table_name}.id = batch.id;\n")
                        temp_file.write("\n")
                        lines_written += 5
                    except Exception as e:
                        raise RuntimeError(f"Failed to write batch {batch_num + 1} SQL statements: {str(e)}") from e

            # Add cleanup and summary
            temp_file.write(
                "SELECT COUNT(*) as total_processed FROM temp_bio_updates;\n"
            )
            temp_file.write("DROP TABLE temp_bio_updates;\n")
            temp_file.write("COMMIT;\n")
            temp_file.write("\\echo 'Batch update completed successfully!';\n")
            lines_written += 4

        print(f"  Successfully wrote {lines_written} lines to SQL script")

        # Verify the SQL file has reasonable content
        if lines_written < 10:
            raise RuntimeError(f"SQL file appears incomplete ({lines_written} lines written)")

        # Move temp file to final location atomically
        try:
            os.rename(temp_path, sql_file_path)
        except OSError as e:
            raise RuntimeError(f"Failed to move temporary SQL file to final location: {str(e)}") from e

    except Exception as e:
        # Enhanced cleanup with detailed error reporting
        temp_file_exists = os.path.exists(temp_path)
        try:
            if temp_file_exists:
                os.unlink(temp_path)
                print(f"  Cleaned up temporary file: {temp_path}", file=sys.stderr)
        except OSError as cleanup_error:
            print(f"  Warning: Could not clean up temporary file {temp_path}: {str(cleanup_error)}", file=sys.stderr)
        
        # Re-raise with enhanced error context
        raise RuntimeError(f"SQL file generation failed: {str(e)}") from e


def validate_arguments(args: argparse.Namespace) -> list:
    """
    Validate command-line arguments with comprehensive error checking.

    Args:
        args: Parsed command-line arguments

    Returns:
        list: List of validation error messages with detailed descriptions
    """
    errors = []

    # Validate input file
    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        errors.append(f"Input file does not exist: {input_path}")
        errors.append("  Suggestion: Check the file path and ensure the file exists")
    elif not os.path.isfile(input_path):
        if os.path.isdir(input_path):
            errors.append(f"Input path is a directory, not a file: {input_path}")
            errors.append("  Suggestion: Specify the JSONL file within the directory")
        else:
            errors.append(f"Input path is not a regular file: {input_path}")
    elif not os.access(input_path, os.R_OK):
        errors.append(f"Input file is not readable: {input_path}")
        errors.append(f"  File permissions: {oct(os.stat(input_path).st_mode)[-3:]}")
        errors.append("  Suggestion: Check file permissions with 'ls -la' and ensure read access")
    else:
        # Additional validation for readable files
        try:
            file_size = os.path.getsize(input_path)
            if file_size == 0:
                errors.append(f"Input file is empty: {input_path}")
                errors.append("  Suggestion: Ensure the JSONL file contains data to process")
            elif file_size > 100 * 1024 * 1024:  # 100MB warning
                print(f"Warning: Large input file detected ({file_size:,} bytes). Processing may take longer.", file=sys.stderr)
        except OSError as e:
            errors.append(f"Cannot access input file metadata: {input_path}")
            errors.append(f"  System error: {str(e)}")

    # Validate output directory
    output_path = os.path.abspath(args.output_dir)
    if not os.path.exists(output_path):
        errors.append(f"Output directory does not exist: {output_path}")
        errors.append("  Suggestion: Create the directory with 'mkdir -p' or choose an existing directory")
    elif not os.path.isdir(output_path):
        errors.append(f"Output path is not a directory: {output_path}")
        errors.append("  Suggestion: Specify a valid directory path for output files")
    elif not os.access(output_path, os.W_OK):
        errors.append(f"Output directory is not writable: {output_path}")
        errors.append(f"  Directory permissions: {oct(os.stat(output_path).st_mode)[-3:]}")
        errors.append("  Suggestion: Check directory permissions and ensure write access")
    else:
        # Additional validation for writable directories
        try:
            # Check available disk space (warn if less than 10MB)
            statvfs = os.statvfs(output_path)
            available_space = statvfs.f_frsize * statvfs.f_bavail
            if available_space < 10 * 1024 * 1024:  # 10MB
                print(f"Warning: Low disk space in output directory ({available_space:,} bytes available).", file=sys.stderr)
                print("  Large batch operations may fail due to insufficient space.", file=sys.stderr)
        except (OSError, AttributeError):
            # os.statvfs not available on all platforms (e.g., Windows)
            pass

        # Test write access by creating a temporary file
        try:
            test_fd, test_path = tempfile.mkstemp(dir=output_path, prefix="write_test_")
            os.close(test_fd)
            os.unlink(test_path)
        except OSError as e:
            errors.append(f"Cannot create temporary files in output directory: {output_path}")
            errors.append(f"  System error: {str(e)}")
            errors.append("  Suggestion: Check directory permissions and available disk space")

    return errors


def main():
    """Main entry point for the batch update generator."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Validate arguments
    validation_errors = validate_arguments(args)
    if validation_errors:
        print("Error: Invalid arguments:", file=sys.stderr)
        for error in validation_errors:
            print(f"  {error}", file=sys.stderr)
        sys.exit(1)

    # Parse JSONL file
    print(f"Processing JSONL file: {args.input}")
    valid_entries, invalid_entries, error_messages, statistics = parse_jsonl_file(args.input)

    # Print any error messages
    if error_messages:
        print("Warnings and errors during parsing:", file=sys.stderr)
        for error in error_messages:
            print(f"  {error}", file=sys.stderr)

    # Print comprehensive summary statistics
    print(f"\n=== PROCESSING SUMMARY ===")
    print(f"Input file: {os.path.abspath(args.input)}")
    print(f"Output directory: {os.path.abspath(args.output_dir)}")
    table_name = "test_artists" if args.test_mode else "artists"
    print(f"Target table: {table_name}")
    
    print(f"\n--- Parsing Statistics ---")
    print(f"Total lines processed: {statistics['total_lines_processed']}")
    print(f"Empty lines skipped: {statistics['empty_lines']}")
    print(f"JSON decode errors: {statistics['json_decode_errors']}")
    
    print(f"\n--- Entry Classification ---")
    print(f"Valid entries: {statistics['valid_entries']}")
    print(f"Invalid entries: {statistics['invalid_entries']}")
    print(f"Duplicate entries: {statistics['duplicate_entries']}")
    
    if statistics['duplicated_artist_ids'] > 0:
        print(f"Duplicated artist IDs: {statistics['duplicated_artist_ids']}")
    
    print(f"\n--- Error Summary ---")
    print(f"Total error messages: {len(error_messages)}")
    
    # Calculate success rate
    if statistics['total_lines_processed'] > 0:
        success_rate = (statistics['valid_entries'] / statistics['total_lines_processed']) * 100
        print(f"Processing success rate: {success_rate:.1f}%")

    # Generate files if we have any data to process
    if valid_entries or invalid_entries:
        print(f"\n=== FILE GENERATION ===")

        # Generate timestamp and filenames
        timestamp = generate_timestamp()
        sql_file, csv_file, skipped_file = generate_output_filenames(
            timestamp, args.output_dir
        )

        # Validate we have space and permissions before starting
        try:
            # Pre-flight check: ensure we can create all required files
            temp_files = []
            for file_path in [csv_file, sql_file, skipped_file]:
                try:
                    test_fd, test_path = tempfile.mkstemp(
                        dir=os.path.dirname(file_path),
                        prefix=f"preflight_{os.path.basename(file_path)}_"
                    )
                    os.close(test_fd)
                    temp_files.append(test_path)
                except OSError as e:
                    raise RuntimeError(f"Cannot create files in output directory: {str(e)}") from e
            
            # Clean up test files
            for test_path in temp_files:
                try:
                    os.unlink(test_path)
                except OSError:
                    pass
            
            print("Pre-flight validation passed - proceeding with file generation")
        
        except Exception as e:
            print(f"\n=== PRE-FLIGHT ERROR ===", file=sys.stderr)
            print(f"File generation aborted: {str(e)}", file=sys.stderr)
            print("Check output directory permissions and available disk space", file=sys.stderr)
            sys.exit(1)

        # File generation with comprehensive error handling
        files_created = []
        generation_errors = []
        
        try:
            # Write CSV file for valid entries
            if valid_entries:
                print(f"Creating CSV file with {len(valid_entries)} records...")
                try:
                    write_csv_file(valid_entries, csv_file)
                    files_created.append(("CSV data file", csv_file))
                except Exception as e:
                    generation_errors.append(f"CSV file generation failed: {str(e)}")
                    raise

            # Write skipped JSONL file for invalid entries
            if invalid_entries:
                print(f"Creating skipped file with {len(invalid_entries)} entries...")
                try:
                    write_skipped_file(invalid_entries, skipped_file)
                    files_created.append(("Skipped entries file", skipped_file))
                except Exception as e:
                    generation_errors.append(f"Skipped file generation failed: {str(e)}")
                    # Don't raise - this is not critical for the main workflow
                    print(f"Warning: {str(e)}", file=sys.stderr)

            # Generate SQL script file
            if valid_entries:
                batch_size = 1000
                num_batches = (len(valid_entries) + batch_size - 1) // batch_size
                print(f"Generating SQL script with {num_batches} batch(es)...")
                try:
                    write_sql_file(csv_file, sql_file, table_name, len(valid_entries))
                    files_created.append(("SQL batch script", sql_file))
                except Exception as e:
                    generation_errors.append(f"SQL file generation failed: {str(e)}")
                    raise
            else:
                print("No valid entries - SQL file not created")

            print(f"\n=== GENERATION COMPLETE ===")
            print(f"Timestamp: {timestamp}")
            print(f"Files created:")
            for file_type, file_path in files_created:
                try:
                    file_size = os.path.getsize(file_path)
                    print(f"  {file_type}: {file_path} ({file_size:,} bytes)")
                except OSError:
                    print(f"  {file_type}: {file_path} (size unknown)")
            
            if valid_entries:
                print(f"\nBatch processing details:")
                print(f"  Records per batch: 1000")
                print(f"  Total batches: {num_batches}")
                print(f"  Total records to update: {len(valid_entries)}")
            
            if generation_errors:
                print(f"\nWarnings during generation:")
                for error in generation_errors:
                    print(f"  - {error}")

        except Exception as e:
            print(f"\n=== GENERATION ERROR ===", file=sys.stderr)
            print(f"File generation failed: {str(e)}", file=sys.stderr)
            
            # Attempt cleanup of partial files
            cleanup_successful = []
            cleanup_failed = []
            for file_type, file_path in files_created:
                try:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        cleanup_successful.append(file_path)
                except OSError as cleanup_error:
                    cleanup_failed.append((file_path, str(cleanup_error)))
            
            if cleanup_successful:
                print(f"Cleaned up partial files: {', '.join(cleanup_successful)}", file=sys.stderr)
            if cleanup_failed:
                print("Failed to clean up some files:", file=sys.stderr)
                for file_path, error in cleanup_failed:
                    print(f"  {file_path}: {error}", file=sys.stderr)
            
            sys.exit(1)
    else:
        print("\n=== NO OUTPUT ===")
        print("No data to process - no output files generated.")
        print("This could be due to:")
        print("  - Empty input file")
        print("  - All entries were invalid or had errors")
        print("  - File processing errors")


if __name__ == "__main__":
    main()
