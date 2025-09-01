"""
Output formatting module.

This module handles output file generation and formatting
for the artist bio generator application.
"""

import json
import logging
import os
import threading
from typing import List, Optional

from ..models import ApiResponse

logger = logging.getLogger(__name__)

# Global lock for JSONL file writing to ensure thread safety
_jsonl_write_lock = threading.Lock()


def write_jsonl_output(
    responses: List[ApiResponse],
    output_path: str,
    prompt_id: str,
    version: Optional[str] = None,
) -> None:
    """
    Write all API responses to a JSONL output file.

    Args:
        responses: List of API responses to write
        output_path: Path to the output JSONL file
        prompt_id: OpenAI prompt ID used for requests
        version: Optional prompt version used for requests
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for response in responses:
                # Create the JSONL record using shared helper
                record = _create_jsonl_record(response, prompt_id, version)
                
                # Write the JSONL record (one JSON object per line)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info(f"Successfully wrote {len(responses)} records to {output_path}")

    except Exception as e:
        logger.error(f"Failed to write JSONL output to {output_path}: {e}")
        raise


def _create_jsonl_record(
    response: ApiResponse,
    prompt_id: str,
    version: Optional[str] = None,
) -> dict:
    """
    Create a JSONL record from an API response.
    
    Args:
        response: The API response to format
        prompt_id: OpenAI prompt ID used for requests
        version: Optional prompt version used for requests
        
    Returns:
        Dictionary representing the JSONL record
    """
    # Build the JSONL record
    record = {
        "artist_name": response.artist_name,
        "request": {
            "prompt_id": prompt_id,
            "variables": {
                "artist_name": response.artist_name,
                "artist_data": (
                    response.artist_data
                    if response.artist_data
                    else "No additional data provided"
                ),
            },
        },
        "response_text": response.response_text,
        "response_id": response.response_id,
        "created": response.created,
        "error": response.error,
    }

    # Add version to request if provided
    if version:
        record["request"]["version"] = version

    # Omit artist_data from top level if empty (as per spec)
    if response.artist_data:
        record["artist_data"] = response.artist_data

    return record


def append_jsonl_response(
    response: ApiResponse,
    output_path: str,
    prompt_id: str,
    version: Optional[str] = None,
    create_if_missing: bool = True,
) -> None:
    """
    Append a single API response to a JSONL output file.
    
    This function is thread-safe and can be called concurrently to append
    responses to the same file as they complete processing.
    
    Args:
        response: The API response to append
        output_path: Path to the output JSONL file
        prompt_id: OpenAI prompt ID used for requests
        version: Optional prompt version used for requests
        create_if_missing: Whether to create the file if it doesn't exist
        
    Raises:
        IOError: If file operations fail
        OSError: If filesystem operations fail
    """
    try:
        # Create the JSONL record
        record = _create_jsonl_record(response, prompt_id, version)
        
        # Use thread lock to ensure safe concurrent writes
        with _jsonl_write_lock:
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                if create_if_missing:
                    os.makedirs(output_dir, exist_ok=True)
                else:
                    raise FileNotFoundError(f"Output directory does not exist: {output_dir}")
            
            # Append the record to the file
            file_mode = "a" if os.path.exists(output_path) or create_if_missing else "x"
            with open(output_path, file_mode, encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()  # Ensure data is written to disk immediately
                
        logger.debug(f"Appended response for '{response.artist_name}' to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to append JSONL response to {output_path}: {e}")
        raise


def initialize_jsonl_output(
    output_path: str,
    overwrite_existing: bool = False,
) -> None:
    """
    Initialize a JSONL output file for streaming writes.
    
    Args:
        output_path: Path to the output JSONL file
        overwrite_existing: Whether to overwrite if file already exists
        
    Raises:
        FileExistsError: If file exists and overwrite_existing is False
        IOError: If file operations fail
    """
    try:
        with _jsonl_write_lock:
            # Check if file exists
            if os.path.exists(output_path) and not overwrite_existing:
                logger.info(f"JSONL output file already exists: {output_path}")
                return
                
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            # Create/truncate the file
            with open(output_path, "w", encoding="utf-8") as f:
                pass  # Just create/truncate the file
                
        logger.info(f"Initialized JSONL output file: {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to initialize JSONL output file {output_path}: {e}")
        raise
