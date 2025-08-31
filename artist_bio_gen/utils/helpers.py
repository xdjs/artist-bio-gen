"""
General helper utilities for the artist bio generator.

This module provides common utility functions that are used
across multiple modules in the application.
"""


def create_progress_bar(current: int, total: int, width: int = 30) -> str:
    """
    Create a text-based progress bar.

    Args:
        current: Current progress (1-based)
        total: Total items
        width: Width of the progress bar

    Returns:
        Progress bar string
    """
    if total == 0:
        return "[" + " " * width + "]"

    percentage = current / total
    filled = int(width * percentage)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"
