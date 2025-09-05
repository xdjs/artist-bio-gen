#!/usr/bin/env python3
"""
Batch Update Generator

Generates SQL batch update files from JSONL output for efficient bulk database updates
using PostgreSQL COPY operations.
"""

import argparse
import json
import os
import sys
import uuid
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
    
    # TODO: Implement file generation (Task 1.4)
    # TODO: Implement duplicate detection (Task 1.3)


if __name__ == '__main__':
    main()