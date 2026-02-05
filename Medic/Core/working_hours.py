"""Working hours evaluation for Medic.

This module provides functionality to evaluate whether a given time
is within a schedule's working hours. It supports IANA timezones and
properly handles DST transitions and edge cases.

Working hours are stored in JSONB format:
{
    "monday": [{"start": "09:00", "end": "17:00"}],
    "tuesday": [{"start": "09:00", "end": "17:00"}],
    ...
}

Multiple time ranges per day are supported:
{
    "monday": [
        {"start": "09:00", "end": "12:00"},
        {"start": "13:00", "end": "17:00"}
    ]
}
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Medic.Core.database import query_db

logger = logging.getLogger(__name__)

# Mapping of day names to weekday numbers (Monday=0, Sunday=6)
DAY_NAME_TO_WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

WEEKDAY_TO_DAY_NAME = {v: k for k, v in DAY_NAME_TO_WEEKDAY.items()}


@dataclass
class TimeRange:
    """A time range within a day."""

    start: time
    end: time

    def contains(self, check_time: time) -> bool:
        """
        Check if a time falls within this range.

        Handles ranges that cross midnight (e.g., 22:00 to 02:00).

        Args:
            check_time: The time to check

        Returns:
            True if check_time is within this range
        """
        if self.start <= self.end:
            # Normal range: start <= check_time < end
            return self.start <= check_time < self.end
        else:
            # Range crosses midnight: check_time >= start OR check_time < end
            return check_time >= self.start or check_time < self.end


@dataclass
class Schedule:
    """A working hours schedule."""

    schedule_id: int
    name: str
    timezone: str
    hours: dict[str, list[TimeRange]]

    def get_timezone(self) -> ZoneInfo:
        """
        Get the ZoneInfo for this schedule's timezone.

        Returns:
            ZoneInfo object for the timezone

        Raises:
            ZoneInfoNotFoundError: If timezone is invalid
        """
        return ZoneInfo(self.timezone)


def parse_time(time_str: str) -> time:
    """
    Parse a time string in HH:MM format.

    Args:
        time_str: Time string in "HH:MM" format

    Returns:
        datetime.time object

    Raises:
        ValueError: If time string is invalid
    """
    try:
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")

        hour = int(parts[0])
        minute = int(parts[1])

        if not (0 <= hour <= 23):
            raise ValueError(f"Hour must be 0-23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"Minute must be 0-59, got {minute}")

        return time(hour=hour, minute=minute)
    except (IndexError, TypeError) as e:
        raise ValueError(f"Invalid time format: {time_str}") from e


def parse_hours(hours_data: dict[str, Any]) -> dict[str, list[TimeRange]]:
    """
    Parse hours JSON data into structured TimeRange objects.

    Args:
        hours_data: Dictionary with day names as keys and lists of
                   {"start": "HH:MM", "end": "HH:MM"} as values

    Returns:
        Dictionary mapping day names to lists of TimeRange objects

    Raises:
        ValueError: If hours data is invalid
    """
    result: dict[str, list[TimeRange]] = {}

    for day_name, ranges in hours_data.items():
        day_name_lower = day_name.lower()
        if day_name_lower not in DAY_NAME_TO_WEEKDAY:
            logger.warning(f"Unknown day name: {day_name}, skipping")
            continue

        if not isinstance(ranges, list):
            raise ValueError(f"Hours for {day_name} must be a list, got {type(ranges)}")

        day_ranges: list[TimeRange] = []
        for range_data in ranges:
            if not isinstance(range_data, dict):
                raise ValueError(f"Time range must be a dict, got {type(range_data)}")

            start_str = range_data.get("start")
            end_str = range_data.get("end")

            if not start_str or not end_str:
                raise ValueError(
                    f"Time range must have 'start' and 'end' keys: {range_data}"
                )

            start_time = parse_time(start_str)
            end_time = parse_time(end_str)

            day_ranges.append(TimeRange(start=start_time, end=end_time))

        result[day_name_lower] = day_ranges

    return result


def is_valid_timezone(timezone: str) -> bool:
    """
    Check if a timezone string is a valid IANA timezone.

    Args:
        timezone: The timezone string to validate

    Returns:
        True if valid, False otherwise
    """
    if not timezone:
        return False
    try:
        ZoneInfo(timezone)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def get_schedule(schedule_id: int) -> Optional[Schedule]:
    """
    Get a schedule by ID from the database.

    Args:
        schedule_id: The schedule ID to look up

    Returns:
        Schedule object or None if not found
    """
    query = """
        SELECT schedule_id, name, timezone, hours
        FROM medic.schedules
        WHERE schedule_id = %s
    """
    result = query_db(query, (schedule_id,), show_columns=True)

    if not result:
        return None

    try:
        data = json.loads(str(result))
        if not data:
            return None

        row = data[0]
        hours_data = row.get("hours", {})
        if isinstance(hours_data, str):
            hours_data = json.loads(hours_data)

        return Schedule(
            schedule_id=row["schedule_id"],
            name=row["name"],
            timezone=row["timezone"],
            hours=parse_hours(hours_data),
        )
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse schedule {schedule_id}: {e}")
        return None


def get_schedule_for_service(service_id: int) -> Optional[Schedule]:
    """
    Get the schedule associated with a service.

    Args:
        service_id: The service ID to look up

    Returns:
        Schedule object or None if service has no schedule
    """
    query = """
        SELECT s.schedule_id, s.name, s.timezone, s.hours
        FROM medic.schedules s
        INNER JOIN services svc ON svc.schedule_id = s.schedule_id
        WHERE svc.service_id = %s
    """
    result = query_db(query, (service_id,), show_columns=True)

    if not result:
        return None

    try:
        data = json.loads(str(result))
        if not data:
            return None

        row = data[0]
        hours_data = row.get("hours", {})
        if isinstance(hours_data, str):
            hours_data = json.loads(hours_data)

        return Schedule(
            schedule_id=row["schedule_id"],
            name=row["name"],
            timezone=row["timezone"],
            hours=parse_hours(hours_data),
        )
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse schedule for service {service_id}: {e}")
        return None


def is_within_working_hours(
    schedule: Schedule,
    check_time: Optional[datetime] = None,
) -> bool:
    """
    Check if a given time is within the schedule's working hours.

    This function properly handles:
    - IANA timezones (e.g., "America/Chicago", "Europe/London")
    - DST transitions (uses the schedule's timezone for evaluation)
    - Leap years (datetime handles these automatically)
    - Ranges that cross midnight

    Args:
        schedule: The Schedule object containing timezone and hours
        check_time: The datetime to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        True if check_time is within working hours, False otherwise
    """
    if check_time is None:
        check_time = datetime.now(ZoneInfo("UTC"))

    # Ensure check_time is timezone-aware
    if check_time.tzinfo is None:
        # Assume UTC if no timezone
        check_time = check_time.replace(tzinfo=ZoneInfo("UTC"))

    try:
        # Convert to schedule's timezone
        tz = schedule.get_timezone()
        local_time = check_time.astimezone(tz)
    except ZoneInfoNotFoundError:
        logger.error(f"Invalid timezone: {schedule.timezone}")
        return False

    # Get the day name for this local time
    weekday = local_time.weekday()
    day_name = WEEKDAY_TO_DAY_NAME[weekday]

    # Get the time ranges for this day
    day_ranges = schedule.hours.get(day_name, [])

    if not day_ranges:
        logger.debug(
            f"No working hours defined for {day_name} in schedule " f"'{schedule.name}'"
        )
        return False

    # Check if the time falls within any of the day's ranges
    local_time_only = local_time.time()

    for time_range in day_ranges:
        if time_range.contains(local_time_only):
            logger.debug(
                f"Time {local_time_only} is within range "
                f"{time_range.start}-{time_range.end} for {day_name}"
            )
            return True

    logger.debug(f"Time {local_time_only} is outside all working hours for {day_name}")
    return False


def is_service_within_working_hours(
    service_id: int,
    check_time: Optional[datetime] = None,
) -> tuple[bool, Optional[str]]:
    """
    Check if a service is within its configured working hours.

    Args:
        service_id: The service ID to check
        check_time: The datetime to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        Tuple of (is_within_hours, schedule_name):
        - (True, schedule_name) if within working hours
        - (False, schedule_name) if outside working hours
        - (True, None) if service has no schedule (always within hours)
    """
    schedule = get_schedule_for_service(service_id)

    if schedule is None:
        # No schedule means always "within hours"
        logger.debug(f"Service {service_id} has no schedule, treating as within hours")
        return (True, None)

    within_hours = is_within_working_hours(schedule, check_time)
    return (within_hours, schedule.name)


def get_current_period(
    schedule: Schedule,
    check_time: Optional[datetime] = None,
) -> str:
    """
    Get the current period for a schedule (during_hours or after_hours).

    Args:
        schedule: The Schedule object
        check_time: The datetime to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        "during_hours" if within working hours, "after_hours" otherwise
    """
    if is_within_working_hours(schedule, check_time):
        return "during_hours"
    return "after_hours"


def get_service_current_period(
    service_id: int,
    check_time: Optional[datetime] = None,
) -> str:
    """
    Get the current period for a service (during_hours or after_hours).

    Args:
        service_id: The service ID to check
        check_time: The datetime to check (UTC or timezone-aware).
                   If None, uses current UTC time.

    Returns:
        "during_hours" if within working hours or no schedule,
        "after_hours" if outside working hours
    """
    within_hours, _ = is_service_within_working_hours(service_id, check_time)
    return "during_hours" if within_hours else "after_hours"
