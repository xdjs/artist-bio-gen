#!/usr/bin/env python3
"""
Artist Data Models

This module contains data structures related to artist information and
input file parsing results.
"""

from typing import List, Optional, NamedTuple


class ArtistData(NamedTuple):
    """
    Represents parsed artist data from input file.
    
    Attributes:
        artist_id: UUID string identifying the artist
        name: Artist name (required)
        data: Optional additional data about the artist
    """
    
    artist_id: str  # UUID string
    name: str
    data: Optional[str] = None


class ParseResult(NamedTuple):
    """
    Result of parsing an input file.
    
    Attributes:
        artists: List of successfully parsed artists
        skipped_lines: Number of lines skipped (comments, blanks, headers)
        error_lines: Number of lines that had parsing errors
    """
    
    artists: List[ArtistData]
    skipped_lines: int
    error_lines: int