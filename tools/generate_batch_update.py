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
    error_field = entry.get('error')
    return error_field is None or error_field == '' or error_field == 'null'


def validate_jsonl_entry(entry: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate a JSONL entry for required fields and data integrity.
    
    Args:
        entry: The parsed JSONL entry dictionary
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Check for required fields
    if 'artist_id' not in entry:
        return False, "Missing required field 'artist_id'"
    
    if 'bio' not in entry:
        return False, "Missing required field 'bio'"
    
    # Validate UUID format
    if not validate_uuid_format(entry['artist_id']):
        return False, f"Invalid UUID format for artist_id: {entry['artist_id']}"
    
    # Check if bio is valid (no error)
    if not has_valid_bio(entry):
        return False, f"Bio has error: {entry.get('error', 'Unknown error')}"
    
    # Check if bio content exists and is not empty
    bio = entry.get('bio', '').strip()
    if not bio:
        return False, "Bio content is empty"
    
    return True, ""


def parse_jsonl_line(line: str, line_number: int) -> Tuple[Optional[Dict[str, Any]], str]:
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


def parse_jsonl_file(file_path: str) -> Tuple[list, list, list]:
    """
    Parse JSONL file line by line with comprehensive error handling and duplicate detection.
    
    Args:
        file_path: Path to the JSONL input file
        
    Returns:
        Tuple[list, list, list]: (valid_entries, invalid_entries, error_messages)
    """
    # First pass: parse all entries and collect artist_ids to detect duplicates
    all_parsed_entries = []
    artist_id_counts = {}
    error_messages = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, 1):
                # Parse the JSON line
                entry, parse_error = parse_jsonl_line(line, line_number)
                
                if parse_error:
                    error_messages.append(parse_error)
                    continue
                
                if entry is None:  # Empty line
                    continue
                
                # Store entry with line number for processing
                entry['_line_number'] = line_number
                all_parsed_entries.append(entry)
                
                # Track artist_id counts for duplicate detection
                artist_id = entry.get('artist_id')
                if artist_id:
                    artist_id_counts[artist_id] = artist_id_counts.get(artist_id, 0) + 1
                    
    except FileNotFoundError:
        error_messages.append(f"Input file not found: {file_path}")
        return [], [], error_messages
    except PermissionError:
        error_messages.append(f"Permission denied reading file: {file_path}")
        return [], [], error_messages
    except Exception as e:
        error_messages.append(f"Unexpected error reading file: {str(e)}")
        return [], [], error_messages
    
    # Identify duplicated artist_ids
    duplicated_artist_ids = {aid for aid, count in artist_id_counts.items() if count > 1}
    
    # Second pass: process entries and separate valid, invalid, and duplicates
    valid_entries = []
    invalid_entries = []
    duplicate_entries = []
    
    for entry in all_parsed_entries:
        line_number = entry['_line_number']
        artist_id = entry.get('artist_id')
        
        # Check if this artist_id is duplicated
        if artist_id and artist_id in duplicated_artist_ids:
            error_messages.append(f"Line {line_number}: Duplicate artist_id: {artist_id}")
            entry['_error'] = f"Duplicate artist_id: {artist_id}"
            duplicate_entries.append(entry)
            continue
        
        # Validate the entry
        is_valid, validation_error = validate_jsonl_entry(entry)
        
        if is_valid:
            # Remove internal tracking fields before adding to valid entries
            clean_entry = {k: v for k, v in entry.items() if not k.startswith('_')}
            valid_entries.append(clean_entry)
        else:
            error_messages.append(f"Line {line_number}: {validation_error}")
            entry['_error'] = validation_error
            invalid_entries.append(entry)
    
    # Combine invalid and duplicate entries
    all_invalid_entries = invalid_entries + duplicate_entries
    
    # Log duplicate detection summary
    if duplicated_artist_ids:
        error_messages.append(f"Duplicate detection: found {len(duplicated_artist_ids)} duplicated artist_ids affecting {sum(artist_id_counts[aid] for aid in duplicated_artist_ids)} entries")
    
    return valid_entries, all_invalid_entries, error_messages


def setup_argument_parser() -> argparse.ArgumentParser:
    """
    Set up command-line argument parser.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Generate SQL batch update files from JSONL output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input out.jsonl
  %(prog)s --input out.jsonl --test-mode
  %(prog)s --input out.jsonl --output-dir /tmp/batches
        """
    )
    
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input JSONL file path (required)'
    )
    
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Use test_artists table instead of artists table'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='.',
        help='Output directory for generated files (default: current directory)'
    )
    
    return parser


def generate_timestamp() -> str:
    """
    Generate timestamp in YYYYMMDD_HHMMSS format.
    
    Returns:
        str: Formatted timestamp string
    """
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def generate_output_filenames(timestamp: str, output_dir: str) -> Tuple[str, str, str]:
    """
    Generate output filenames based on timestamp.
    
    Args:
        timestamp: Timestamp string in YYYYMMDD_HHMMSS format
        output_dir: Output directory path
        
    Returns:
        Tuple[str, str, str]: (sql_file, csv_file, skipped_file) paths
    """
    sql_file = os.path.join(output_dir, f'batch_update_{timestamp}.sql')
    csv_file = os.path.join(output_dir, f'batch_update_{timestamp}.csv')
    skipped_file = os.path.join(output_dir, f'batch_update_skipped_{timestamp}.jsonl')
    
    return sql_file, csv_file, skipped_file


def write_csv_file(valid_entries: list, csv_file_path: str) -> None:
    """
    Write valid entries to CSV file with UTF-8 support and proper escaping.
    
    Args:
        valid_entries: List of valid JSONL entries
        csv_file_path: Path to output CSV file
    """
    # Create temporary file first for atomic writes
    temp_fd, temp_path = tempfile.mkstemp(suffix='.csv', dir=os.path.dirname(csv_file_path))
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8', newline='') as temp_file:
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)
            
            # Write header
            writer.writerow(['id', 'bio'])
            
            # Write data rows
            for entry in valid_entries:
                artist_id = entry['artist_id']
                bio = entry['bio']
                writer.writerow([artist_id, bio])
        
        # Move temp file to final location
        os.rename(temp_path, csv_file_path)
        
    except Exception as e:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise e


def write_skipped_file(invalid_entries: list, skipped_file_path: str) -> None:
    """
    Write invalid/skipped entries to JSONL file.
    
    Args:
        invalid_entries: List of invalid JSONL entries
        skipped_file_path: Path to output skipped JSONL file
    """
    # Create temporary file first for atomic writes
    temp_fd, temp_path = tempfile.mkstemp(suffix='.jsonl', dir=os.path.dirname(skipped_file_path))
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as temp_file:
            for entry in invalid_entries:
                # Remove internal tracking fields before writing
                clean_entry = {k: v for k, v in entry.items() if not k.startswith('_')}
                json.dump(clean_entry, temp_file, ensure_ascii=False)
                temp_file.write('\n')
        
        # Move temp file to final location
        os.rename(temp_path, skipped_file_path)
        
    except Exception as e:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise e


def write_sql_file(csv_file_path: str, sql_file_path: str, table_name: str, total_records: int, batch_size: int = 1000) -> None:
    """
    Generate SQL script file with batched UPDATE statements.
    
    Args:
        csv_file_path: Path to the CSV data file
        sql_file_path: Path to output SQL script file
        table_name: Target table name (artists or test_artists)
        total_records: Total number of records to process
        batch_size: Number of records per batch (default: 1000)
    """
    # Create temporary file first for atomic writes
    temp_fd, temp_path = tempfile.mkstemp(suffix='.sql', dir=os.path.dirname(sql_file_path))
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as temp_file:
            # Write SQL header with error handling
            temp_file.write('\\set ON_ERROR_STOP on\n')
            temp_file.write("\\echo 'Starting batch bio update...'\n")
            temp_file.write('\n')
            
            # Begin transaction and create temp table
            temp_file.write('BEGIN;\n')
            temp_file.write('\n')
            temp_file.write('CREATE TEMP TABLE temp_bio_updates (id UUID, bio TEXT);\n')
            temp_file.write('\n')
            
            # Copy data from CSV file
            csv_filename = os.path.basename(csv_file_path)
            temp_file.write(f"\\copy temp_bio_updates FROM '{csv_filename}' WITH CSV HEADER;\n")
            temp_file.write('\n')
            
            # Generate batched UPDATE statements
            if total_records > 0:
                num_batches = (total_records + batch_size - 1) // batch_size  # Ceiling division
                
                for batch_num in range(num_batches):
                    offset = batch_num * batch_size
                    current_batch_size = min(batch_size, total_records - offset)
                    batch_end = offset + current_batch_size
                    
                    temp_file.write(f"\\echo 'Processing batch {batch_num + 1}/{num_batches} (records {offset + 1}-{batch_end})...'\n")
                    temp_file.write(f'WITH batch AS (SELECT * FROM temp_bio_updates LIMIT {batch_size} OFFSET {offset})\n')
                    temp_file.write(f'UPDATE {table_name} SET bio = batch.bio, updated_at = CURRENT_TIMESTAMP\n')
                    temp_file.write(f'FROM batch WHERE {table_name}.id = batch.id;\n')
                    temp_file.write('\n')
            
            # Add cleanup and summary
            temp_file.write('SELECT COUNT(*) as total_processed FROM temp_bio_updates;\n')
            temp_file.write('DROP TABLE temp_bio_updates;\n')
            temp_file.write('COMMIT;\n')
            temp_file.write("\\echo 'Batch update completed successfully!'\n")
        
        # Move temp file to final location
        os.rename(temp_path, sql_file_path)
        
    except Exception as e:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise e


def validate_arguments(args: argparse.Namespace) -> list:
    """
    Validate command-line arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        list: List of validation error messages
    """
    errors = []
    
    # Validate input file
    if not os.path.exists(args.input):
        errors.append(f"Input file does not exist: {args.input}")
    elif not os.path.isfile(args.input):
        errors.append(f"Input path is not a file: {args.input}")
    elif not os.access(args.input, os.R_OK):
        errors.append(f"Input file is not readable: {args.input}")
    
    # Validate output directory
    if not os.path.exists(args.output_dir):
        errors.append(f"Output directory does not exist: {args.output_dir}")
    elif not os.path.isdir(args.output_dir):
        errors.append(f"Output path is not a directory: {args.output_dir}")
    elif not os.access(args.output_dir, os.W_OK):
        errors.append(f"Output directory is not writable: {args.output_dir}")
    
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
    valid_entries, invalid_entries, error_messages = parse_jsonl_file(args.input)
    
    # Print any error messages
    if error_messages:
        print("Warnings and errors during parsing:", file=sys.stderr)
        for error in error_messages:
            print(f"  {error}", file=sys.stderr)
    
    # Print summary statistics
    print(f"\nParsing Summary:")
    print(f"  Valid entries: {len(valid_entries)}")
    print(f"  Invalid entries: {len(invalid_entries)}")
    print(f"  Parse errors: {len(error_messages)}")
    
    table_name = "test_artists" if args.test_mode else "artists"
    print(f"  Target table: {table_name}")
    print(f"  Output directory: {args.output_dir}")
    
    # Generate files if we have any data to process
    if valid_entries or invalid_entries:
        print(f"\nGenerating output files...")
        
        # Generate timestamp and filenames
        timestamp = generate_timestamp()
        sql_file, csv_file, skipped_file = generate_output_filenames(timestamp, args.output_dir)
        
        try:
            # Write CSV file for valid entries
            if valid_entries:
                write_csv_file(valid_entries, csv_file)
                print(f"  Created CSV file: {csv_file}")
            
            # Write skipped JSONL file for invalid entries
            if invalid_entries:
                write_skipped_file(invalid_entries, skipped_file)
                print(f"  Created skipped file: {skipped_file}")
            
            # Generate SQL script file
            if valid_entries:
                write_sql_file(csv_file, sql_file, table_name, len(valid_entries))
                print(f"  Created SQL file: {sql_file}")
            else:
                print(f"  No valid entries - SQL file not created")
            
            print(f"\nFile generation completed successfully!")
            print(f"  Timestamp: {timestamp}")
            if valid_entries:
                num_batches = (len(valid_entries) + 999) // 1000  # Ceiling division for 1000 batch size
                print(f"  Generated {num_batches} batch(es) for {len(valid_entries)} records")
            
        except Exception as e:
            print(f"Error generating files: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\nNo data to process - no output files generated.")


if __name__ == '__main__':
    main()