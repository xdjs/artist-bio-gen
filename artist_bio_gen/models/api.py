#!/usr/bin/env python3
"""
API Response Models

This module contains data structures related to OpenAI API interactions
and response handling.
"""

from typing import Optional, NamedTuple


class ApiResponse(NamedTuple):
    """
    Result of an OpenAI API call.
    
    Attributes:
        artist_id: UUID string identifying the artist
        artist_name: Name of the artist processed
        artist_data: Additional data about the artist (may be None)
        response_text: Generated bio text from OpenAI
        response_id: OpenAI response ID
        created: Timestamp of when response was created
        db_status: Database write status ("updated|skipped|error|null")
        error: Error message if the API call failed
    """
    
    artist_id: str  # UUID string
    artist_name: str
    artist_data: Optional[str]
    response_text: str
    response_id: str
    created: int
    db_status: Optional[str] = None  # "updated|skipped|error|null"
    error: Optional[str] = None