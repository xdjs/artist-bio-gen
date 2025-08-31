"""
Input parsing module.

This module handles CSV input file parsing and validation
for the artist bio generator application.
"""

import csv
import logging

from ..models import ArtistData, ParseResult
from ..database import validate_uuid

logger = logging.getLogger(__name__)


def parse_input_file(file_path: str) -> ParseResult:
    """
    Parse a CSV input file containing artist data.

    Expected format: artist_id,artist_name,artist_data
    - Lines starting with # are comments and will be skipped
    - Blank lines are skipped
    - artist_id must be a valid UUID, artist_name is required, artist_data is optional
    - Uses proper CSV parsing with quote-aware handling
    - Optional header row is automatically detected and skipped

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
    header_skipped = False

    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            csv_reader = csv.reader(f)

            for line_num, row in enumerate(csv_reader, 1):
                # Skip blank lines
                if not row or (len(row) == 1 and not row[0].strip()):
                    skipped_lines += 1
                    continue

                # Skip comment lines (lines starting with #)
                if row[0].strip().startswith("#"):
                    skipped_lines += 1
                    continue

                # Skip header row if it looks like a header
                if not header_skipped and len(row) >= 2:
                    first_field = row[0].strip().lower()
                    if first_field in ["artist_id", "id", "uuid"]:
                        header_skipped = True
                        skipped_lines += 1
                        continue

                # Parse the row
                try:
                    if len(row) < 2:
                        logger.warning(
                            f"Line {line_num}: Insufficient columns (need at least artist_id,artist_name), skipping"
                        )
                        error_lines += 1
                        continue

                    artist_id = row[0].strip()
                    artist_name = row[1].strip()
                    artist_data = row[2].strip() if len(row) > 2 else None

                    # Validate artist_id is a valid UUID
                    if not validate_uuid(artist_id):
                        logger.warning(
                            f"Line {line_num}: Invalid UUID format for artist_id '{artist_id}', skipping"
                        )
                        error_lines += 1
                        continue

                    # Validate artist_name is not empty
                    if not artist_name:
                        logger.warning(f"Line {line_num}: Empty artist name, skipping")
                        error_lines += 1
                        continue

                    # Create artist data object
                    artist = ArtistData(
                        artist_id=artist_id,
                        name=artist_name,
                        data=artist_data if artist_data else None,
                    )
                    artists.append(artist)

                except Exception as e:
                    logger.warning(f"Line {line_num}: Error parsing line: {e}")
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
        logger.info(f"Skipped {skipped_lines} comment/blank/header lines")
    if error_lines > 0:
        logger.warning(f"Encountered {error_lines} error lines")

    return ParseResult(
        artists=artists, skipped_lines=skipped_lines, error_lines=error_lines
    )
