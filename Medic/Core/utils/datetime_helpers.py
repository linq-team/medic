"""Shared datetime utilities for Medic.

This module provides a single source of truth for datetime helpers,
eliminating code duplication across the codebase.

Features:
    - Timezone-aware datetime operations (America/Chicago)
    - Datetime string parsing with multiple format support
    - Consistent timezone handling across all modules

Usage:
    from Medic.Core.utils.datetime_helpers import TIMEZONE, now, parse_datetime

    # Get current time
    current_time = now()

    # Parse datetime string
    dt = parse_datetime("2024-01-15T10:30:00Z")
"""
from datetime import datetime
from typing import Optional

import pytz

# Timezone constant - America/Chicago is the standard for Medic
TIMEZONE: pytz.BaseTzInfo = pytz.timezone('America/Chicago')


def now() -> datetime:
    """
    Get current time in Chicago timezone.

    Returns:
        Timezone-aware datetime in America/Chicago timezone.
    """
    return datetime.now(TIMEZONE)


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    Parse a datetime string in various formats.

    Supports ISO 8601 and common database timestamp formats.

    Args:
        dt_str: The datetime string to parse.

    Returns:
        Parsed datetime object, or None if parsing fails.
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None
