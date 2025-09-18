#!/usr/bin/env python3
"""
Quota Management Models

This module contains data structures for OpenAI API quota monitoring,
rate limiting, and error classification.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class QuotaStatus:
    """
    Current quota status from OpenAI API response headers.

    Attributes:
        requests_remaining: Number of requests remaining in current window
        requests_limit: Total request limit for current window
        tokens_remaining: Number of tokens remaining in current window
        tokens_limit: Total token limit for current window
        reset_requests: Time when request limit resets (ISO string or seconds)
        reset_tokens: Time when token limit resets (ISO string or seconds)
        timestamp: When this status was captured
    """
    requests_remaining: int
    requests_limit: int
    tokens_remaining: int
    tokens_limit: int
    reset_requests: str
    reset_tokens: str
    timestamp: datetime

    def __post_init__(self):
        """Validate required fields after initialization."""
        if self.requests_remaining < 0:
            self.requests_remaining = 0
        if self.tokens_remaining < 0:
            self.tokens_remaining = 0
        if self.requests_limit <= 0:
            raise ValueError("requests_limit must be positive")
        if self.tokens_limit <= 0:
            raise ValueError("tokens_limit must be positive")

    def get_requests_usage_percentage(self) -> float:
        """Calculate percentage of requests used."""
        if self.requests_limit == 0:
            return 0.0
        used = self.requests_limit - self.requests_remaining
        return (used / self.requests_limit) * 100.0

    def get_tokens_usage_percentage(self) -> float:
        """Calculate percentage of tokens used."""
        if self.tokens_limit == 0:
            return 0.0
        used = self.tokens_limit - self.tokens_remaining
        return (used / self.tokens_limit) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuotaStatus':
        """Create instance from dictionary."""
        data = data.copy()
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class QuotaMetrics:
    """
    Calculated quota metrics and pause decisions.

    Attributes:
        requests_used_today: Number of requests used in current day
        daily_limit: Optional daily request limit (None if not set)
        usage_percentage: Current usage as percentage of daily limit
        should_pause: Whether processing should pause
        pause_reason: Reason for pausing (None if not pausing)
    """
    requests_used_today: int
    daily_limit: Optional[int]
    usage_percentage: float
    should_pause: bool
    pause_reason: Optional[str]

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.requests_used_today < 0:
            self.requests_used_today = 0
        if self.daily_limit is not None and self.daily_limit <= 0:
            raise ValueError("daily_limit must be positive or None")
        if not 0.0 <= self.usage_percentage <= 100.0:
            # Allow slightly over 100% due to calculation timing
            if self.usage_percentage > 110.0:
                raise ValueError("usage_percentage must be between 0-100%")

    def get_remaining_requests(self) -> Optional[int]:
        """Get remaining requests if daily limit is set."""
        if self.daily_limit is None:
            return None
        return max(0, self.daily_limit - self.requests_used_today)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuotaMetrics':
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class ErrorClassification:
    """
    Classification of API errors for retry strategy.

    Attributes:
        kind: Type of error ('rate_limit', 'quota', 'server', 'network')
        retry_after: Retry-After header value in seconds (None if not present)
        should_retry: Whether this error type should be retried
    """
    kind: str
    retry_after: Optional[int]
    should_retry: bool

    def __post_init__(self):
        """Validate error classification."""
        valid_kinds = {'rate_limit', 'quota', 'server', 'network'}
        if self.kind not in valid_kinds:
            raise ValueError(f"kind must be one of {valid_kinds}")
        if self.retry_after is not None and self.retry_after < 0:
            raise ValueError("retry_after must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorClassification':
        """Create instance from dictionary."""
        return cls(**data)


def serialize_quota_state(quota_status: QuotaStatus, quota_metrics: QuotaMetrics) -> str:
    """
    Serialize quota state to JSON string for persistence.

    Args:
        quota_status: Current quota status
        quota_metrics: Current quota metrics

    Returns:
        JSON string representation
    """
    state = {
        'quota_status': quota_status.to_dict(),
        'quota_metrics': quota_metrics.to_dict()
    }
    return json.dumps(state, indent=2)


def deserialize_quota_state(json_str: str) -> tuple[QuotaStatus, QuotaMetrics]:
    """
    Deserialize quota state from JSON string.

    Args:
        json_str: JSON string representation

    Returns:
        Tuple of (QuotaStatus, QuotaMetrics)
    """
    data = json.loads(json_str)
    quota_status = QuotaStatus.from_dict(data['quota_status'])
    quota_metrics = QuotaMetrics.from_dict(data['quota_metrics'])
    return quota_status, quota_metrics