"""
Database utilities module.

This module provides utility functions for database operations including
error classification and UUID validation.
"""

import uuid


def classify_database_error(exception: Exception) -> str:
    """
    Classify database errors into permanent, transient, or systemic categories.
    
    Args:
        exception: Database exception to classify
        
    Returns:
        Error type: "permanent", "transient", or "systemic"
    """
    error_str = str(exception).lower()
    
    # Permanent errors - don't retry these
    permanent_indicators = [
        "invalid uuid",
        "constraint violation", 
        "foreign key constraint",
        "check constraint",
        "not null violation",
        "duplicate key",
        "relation does not exist",  # Table doesn't exist
        "column does not exist",    # Column doesn't exist
    ]
    
    for indicator in permanent_indicators:
        if indicator in error_str:
            return "permanent"
    
    # Systemic errors - abort processing  
    systemic_indicators = [
        "authentication failed",
        "permission denied",
        "role does not exist",
        "database does not exist",
        "ssl required",
        "password authentication failed",
    ]
    
    for indicator in systemic_indicators:
        if indicator in error_str:
            return "systemic"
    
    # Default to transient - can retry these
    # Includes: connection timeout, temporary network issues, deadlocks, etc.
    return "transient"


def validate_uuid(uuid_string: str) -> bool:
    """
    Validate that a string is a valid UUID format.
    
    Args:
        uuid_string: String to validate
        
    Returns:
        True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False