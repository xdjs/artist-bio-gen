"""
Output formatting module.

This module handles output file generation and formatting
for the artist bio generator application.
"""

import json
import logging
from typing import List, Optional

from ..models import ApiResponse

logger = logging.getLogger(__name__)


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