"""Maintenance window evaluation for Medic.

This module provides functionality to evaluate whether a service is
currently in a maintenance window. It supports:
- One-time windows (start_time to end_time)
- Recurring windows via cron expressions
- Timezone-aware evaluation with proper DST handling

Maintenance windows are stored in medic.maintenance_windows table with:
- window_id: Unique identifier
- name: Window name (e.g., "Weekly DB Maintenance")
- start_time: Start timestamp (timezone-aware)
- end_time: End timestamp (timezone-aware)
- recurrence: Cron expression for recurring windows (nullable)
- timezone: IANA timezone for cron evaluation
- service_ids: Array of affected service IDs (empty = all services)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from Medic.Core.database import query_db

logger = logging.getLogger(__name__)

# Optional croniter import - if not available, recurring windows won't work
try:
    from croniter import croniter  # type: ignore[import-untyped]

    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
    croniter = None  # type: ignore[misc, assignment]
    logger.warning(
        "croniter not installed. Recurring maintenance windows will not work. "
        "Install with: pip install croniter"
    )


@dataclass
class MaintenanceWindow:
    """A maintenance window definition."""

    window_id: int
    name: str
    start_time: datetime
    end_time: datetime
    timezone: str
    recurrence: Optional[str] = None
    service_ids: list[int] = field(default_factory=list)

    def get_timezone(self) -> ZoneInfo:
        """
        Get the ZoneInfo for this window's timezone.

        Returns:
            ZoneInfo object for the timezone

        Raises:
            ZoneInfoNotFoundError: If timezone is invalid
        """
        return ZoneInfo(self.timezone)

    def duration(self) -> timedelta:
        """
        Get the duration of the maintenance window.

        Returns:
            timedelta representing window duration
        """
        return self.end_time - self.start_time

    def applies_to_service(self, service_id: int) -> bool:
        """
        Check if this window applies to a specific service.

        Args:
            service_id: The service ID to check

        Returns:
            True if window applies to service (empty service_ids means all)
        """
        if not self.service_ids:
            return True  # Empty means all services
        return service_id in self.service_ids

    def is_recurring(self) -> bool:
        """Check if this is a recurring maintenance window."""
        return self.recurrence is not None and self.recurrence.strip() != ""


def is_valid_cron_expression(cron_expr: Optional[str]) -> bool:
    """
    Validate a cron expression.

    Args:
        cron_expr: The cron expression to validate

    Returns:
        True if valid, False otherwise
    """
    if not CRONITER_AVAILABLE:
        logger.warning("Cannot validate cron expression: croniter not installed")
        return False

    if not cron_expr or not cron_expr.strip():
        return False

    try:
        # croniter.is_valid returns True for valid expressions
        return croniter.is_valid(cron_expr.strip())
    except Exception as e:
        logger.debug(f"Invalid cron expression '{cron_expr}': {e}")
        return False


def get_next_occurrence(
    cron_expr: str,
    base_time: datetime,
    timezone: str,
) -> Optional[datetime]:
    """
    Get the next occurrence of a cron expression.

    Args:
        cron_expr: The cron expression
        base_time: The base time to calculate from (timezone-aware)
        timezone: IANA timezone for cron evaluation

    Returns:
        Next occurrence as timezone-aware datetime, or None if invalid
    """
    if not CRONITER_AVAILABLE:
        logger.warning("Cannot calculate cron occurrence: croniter not installed")
        return None

    if not is_valid_cron_expression(cron_expr):
        return None

    try:
        tz = ZoneInfo(timezone)
        # Convert base_time to the window's timezone
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=ZoneInfo("UTC"))
        local_base = base_time.astimezone(tz)

        # Create iterator and get next occurrence
        cron = croniter(cron_expr.strip(), local_base)
        next_time = cron.get_next(datetime)

        # Ensure result is timezone-aware
        if next_time.tzinfo is None:
            next_time = next_time.replace(tzinfo=tz)

        return next_time
    except Exception as e:
        logger.error(f"Failed to calculate next cron occurrence: {e}")
        return None


def get_prev_occurrence(
    cron_expr: str,
    base_time: datetime,
    timezone: str,
) -> Optional[datetime]:
    """
    Get the previous occurrence of a cron expression.

    Args:
        cron_expr: The cron expression
        base_time: The base time to calculate from (timezone-aware)
        timezone: IANA timezone for cron evaluation

    Returns:
        Previous occurrence as timezone-aware datetime, or None if invalid
    """
    if not CRONITER_AVAILABLE:
        logger.warning("Cannot calculate cron occurrence: croniter not installed")
        return None

    if not is_valid_cron_expression(cron_expr):
        return None

    try:
        tz = ZoneInfo(timezone)
        # Convert base_time to the window's timezone
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=ZoneInfo("UTC"))
        local_base = base_time.astimezone(tz)

        # Create iterator and get previous occurrence
        cron = croniter(cron_expr.strip(), local_base)
        prev_time = cron.get_prev(datetime)

        # Ensure result is timezone-aware
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=tz)

        return prev_time
    except Exception as e:
        logger.error(f"Failed to calculate previous cron occurrence: {e}")
        return None


def is_within_one_time_window(
    window: MaintenanceWindow,
    check_time: datetime,
) -> bool:
    """
    Check if a time falls within a one-time maintenance window.

    Args:
        window: The maintenance window
        check_time: The time to check (timezone-aware)

    Returns:
        True if within window, False otherwise
    """
    # Ensure check_time is timezone-aware
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC"))

    # Window times are stored timezone-aware in the database
    # Direct comparison works across timezones
    return window.start_time <= check_time < window.end_time


def is_within_recurring_window(
    window: MaintenanceWindow,
    check_time: datetime,
) -> bool:
    """
    Check if a time falls within a recurring maintenance window.

    For recurring windows, we need to:
    1. Find the most recent occurrence of the cron expression
    2. Check if check_time is within that occurrence's duration

    Args:
        window: The maintenance window with recurrence cron
        check_time: The time to check (timezone-aware)

    Returns:
        True if within an active recurrence, False otherwise
    """
    if not CRONITER_AVAILABLE:
        logger.warning("Cannot evaluate recurring window: croniter not installed")
        return False

    if not window.recurrence:
        return False

    # Ensure check_time is timezone-aware
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC"))

    # Get the most recent cron occurrence before or at check_time
    prev_occurrence = get_prev_occurrence(
        window.recurrence,
        check_time,
        window.timezone,
    )

    if prev_occurrence is None:
        logger.debug(f"No previous occurrence found for window '{window.name}'")
        return False

    # Calculate the window duration from the original definition
    window_duration = window.duration()

    # The recurring window end time is prev_occurrence + duration
    recurring_end = prev_occurrence + window_duration

    # Check if check_time falls within this occurrence
    is_within = prev_occurrence <= check_time < recurring_end

    logger.debug(
        f"Recurring window '{window.name}': "
        f"occurrence={prev_occurrence.isoformat()}, "
        f"end={recurring_end.isoformat()}, "
        f"check_time={check_time.isoformat()}, "
        f"within={is_within}"
    )

    return is_within


def is_in_maintenance_window(
    window: MaintenanceWindow,
    check_time: Optional[datetime] = None,
) -> bool:
    """
    Check if a time falls within a maintenance window.

    Handles both one-time and recurring windows.

    Args:
        window: The maintenance window to check
        check_time: The time to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        True if within maintenance window, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(ZoneInfo("UTC"))

    # Ensure check_time is timezone-aware
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC"))

    if window.is_recurring():
        return is_within_recurring_window(window, check_time)
    else:
        return is_within_one_time_window(window, check_time)


def parse_maintenance_window(row: dict[str, Any]) -> Optional[MaintenanceWindow]:
    """
    Parse a database row into a MaintenanceWindow object.

    Args:
        row: Dictionary from database query

    Returns:
        MaintenanceWindow object or None on parse error
    """
    try:
        # Parse timestamps - database returns ISO format strings
        start_time_raw = row.get("start_time")
        end_time_raw = row.get("end_time")

        if start_time_raw is None or end_time_raw is None:
            logger.error("Missing start_time or end_time in row")
            return None

        if isinstance(start_time_raw, str):
            start_time = datetime.fromisoformat(start_time_raw)
        else:
            start_time = start_time_raw

        if isinstance(end_time_raw, str):
            end_time = datetime.fromisoformat(end_time_raw)
        else:
            end_time = end_time_raw

        # Ensure timestamps are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=ZoneInfo("UTC"))
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=ZoneInfo("UTC"))

        # Parse service_ids - can be list or None
        service_ids = row.get("service_ids", [])
        if service_ids is None:
            service_ids = []

        return MaintenanceWindow(
            window_id=row["window_id"],
            name=row["name"],
            start_time=start_time,
            end_time=end_time,
            timezone=row.get("timezone", "UTC"),
            recurrence=row.get("recurrence"),
            service_ids=service_ids,
        )
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        logger.error(f"Failed to parse maintenance window: {e}")
        return None


def get_maintenance_window(window_id: int) -> Optional[MaintenanceWindow]:
    """
    Get a maintenance window by ID.

    Args:
        window_id: The window ID to look up

    Returns:
        MaintenanceWindow object or None if not found
    """
    query = """
        SELECT window_id, name, start_time, end_time, recurrence,
               timezone, service_ids
        FROM medic.maintenance_windows
        WHERE window_id = %s
    """
    result = query_db(query, (window_id,), show_columns=True)

    if not result:
        return None

    try:
        data = json.loads(str(result))
        if not data:
            return None

        return parse_maintenance_window(data[0])
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse maintenance window {window_id}: {e}")
        return None


def get_maintenance_window_by_name(name: str) -> Optional[MaintenanceWindow]:
    """
    Get a maintenance window by name.

    Args:
        name: The window name to look up

    Returns:
        MaintenanceWindow object or None if not found
    """
    query = """
        SELECT window_id, name, start_time, end_time, recurrence,
               timezone, service_ids
        FROM medic.maintenance_windows
        WHERE name = %s
    """
    result = query_db(query, (name,), show_columns=True)

    if not result:
        return None

    try:
        data = json.loads(str(result))
        if not data:
            return None

        return parse_maintenance_window(data[0])
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse maintenance window '{name}': {e}")
        return None


def get_all_maintenance_windows() -> list[MaintenanceWindow]:
    """
    Get all maintenance windows from the database.

    Returns:
        List of MaintenanceWindow objects
    """
    query = """
        SELECT window_id, name, start_time, end_time, recurrence,
               timezone, service_ids
        FROM medic.maintenance_windows
        ORDER BY start_time
    """
    result = query_db(query, show_columns=True)

    if not result:
        return []

    try:
        data = json.loads(str(result))
        windows = []
        for row in data:
            window = parse_maintenance_window(row)
            if window:
                windows.append(window)
        return windows
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to get maintenance windows: {e}")
        return []


def get_active_maintenance_windows(
    check_time: Optional[datetime] = None,
) -> list[MaintenanceWindow]:
    """
    Get all currently active maintenance windows.

    Args:
        check_time: The time to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        List of active MaintenanceWindow objects
    """
    if check_time is None:
        check_time = datetime.now(ZoneInfo("UTC"))

    all_windows = get_all_maintenance_windows()
    return [w for w in all_windows if is_in_maintenance_window(w, check_time)]


def get_maintenance_windows_for_service(
    service_id: int,
) -> list[MaintenanceWindow]:
    """
    Get all maintenance windows that apply to a specific service.

    Args:
        service_id: The service ID to check

    Returns:
        List of MaintenanceWindow objects that apply to this service
    """
    # Query for windows that either:
    # 1. Have empty service_ids (apply to all services)
    # 2. Include this service_id in their service_ids array
    query = """
        SELECT window_id, name, start_time, end_time, recurrence,
               timezone, service_ids
        FROM medic.maintenance_windows
        WHERE service_ids = '{}' OR %s = ANY(service_ids)
        ORDER BY start_time
    """
    result = query_db(query, (service_id,), show_columns=True)

    if not result:
        return []

    try:
        data = json.loads(str(result))
        windows = []
        for row in data:
            window = parse_maintenance_window(row)
            if window:
                windows.append(window)
        return windows
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to get maintenance windows for service {service_id}: {e}")
        return []


def is_service_in_maintenance(
    service_id: int,
    check_time: Optional[datetime] = None,
) -> bool:
    """
    Check if a service is currently in a maintenance window.

    This is the primary function for determining if alerts should be
    suppressed for a service.

    Args:
        service_id: The service ID to check
        check_time: The time to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        True if service is in maintenance, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(ZoneInfo("UTC"))

    # Ensure check_time is timezone-aware
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC"))

    windows = get_maintenance_windows_for_service(service_id)

    for window in windows:
        if is_in_maintenance_window(window, check_time):
            logger.info(
                f"Service {service_id} is in maintenance window "
                f"'{window.name}' (id={window.window_id})"
            )
            return True

    return False


def get_active_maintenance_window_for_service(
    service_id: int,
    check_time: Optional[datetime] = None,
) -> Optional[MaintenanceWindow]:
    """
    Get the currently active maintenance window for a service.

    If multiple windows are active, returns the first one found.

    Args:
        service_id: The service ID to check
        check_time: The time to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        Active MaintenanceWindow or None if not in maintenance
    """
    if check_time is None:
        check_time = datetime.now(ZoneInfo("UTC"))

    # Ensure check_time is timezone-aware
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC"))

    windows = get_maintenance_windows_for_service(service_id)

    for window in windows:
        if is_in_maintenance_window(window, check_time):
            return window

    return None


def get_maintenance_status(
    service_id: int,
    check_time: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Get detailed maintenance status for a service.

    Args:
        service_id: The service ID to check
        check_time: The time to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        Dictionary with maintenance status details:
        {
            "in_maintenance": bool,
            "window_name": str or None,
            "window_id": int or None,
            "maintenance_end": str (ISO format) or None
        }
    """
    if check_time is None:
        check_time = datetime.now(ZoneInfo("UTC"))

    window = get_active_maintenance_window_for_service(service_id, check_time)

    if window is None:
        return {
            "in_maintenance": False,
            "window_name": None,
            "window_id": None,
            "maintenance_end": None,
        }

    # Calculate when maintenance ends
    if window.is_recurring() and window.recurrence:
        # For recurring windows, calculate end from last occurrence
        prev_occurrence = get_prev_occurrence(
            window.recurrence,
            check_time,
            window.timezone,
        )
        if prev_occurrence:
            maintenance_end = prev_occurrence + window.duration()
        else:
            maintenance_end = window.end_time
    else:
        maintenance_end = window.end_time

    return {
        "in_maintenance": True,
        "window_name": window.name,
        "window_id": window.window_id,
        "maintenance_end": maintenance_end.isoformat(),
    }
