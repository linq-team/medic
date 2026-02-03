"""Unit tests for maintenance window evaluation."""
import json
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from Medic.Core.maintenance_windows import (
    MaintenanceWindow,
    get_active_maintenance_window_for_service,
    get_active_maintenance_windows,
    get_all_maintenance_windows,
    get_maintenance_status,
    get_maintenance_window,
    get_maintenance_window_by_name,
    get_maintenance_windows_for_service,
    get_next_occurrence,
    get_prev_occurrence,
    is_in_maintenance_window,
    is_service_in_maintenance,
    is_valid_cron_expression,
    is_within_one_time_window,
    is_within_recurring_window,
    parse_maintenance_window,
)


class TestMaintenanceWindowDataclass:
    """Tests for MaintenanceWindow dataclass."""

    def test_creates_window_with_required_fields(self):
        """Test creating a maintenance window with required fields."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test Window",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        assert window.window_id == 1
        assert window.name == "Test Window"
        assert window.recurrence is None
        assert window.service_ids == []

    def test_creates_window_with_all_fields(self):
        """Test creating a maintenance window with all fields."""
        window = MaintenanceWindow(
            window_id=1,
            name="DB Maintenance",
            start_time=datetime(2026, 2, 1, 2, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 4, 0, tzinfo=ZoneInfo("UTC")),
            timezone="America/Chicago",
            recurrence="0 2 * * 0",
            service_ids=[1, 2, 3],
        )
        assert window.recurrence == "0 2 * * 0"
        assert window.service_ids == [1, 2, 3]
        assert window.timezone == "America/Chicago"

    def test_get_timezone_returns_zoneinfo(self):
        """Test get_timezone returns proper ZoneInfo object."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="America/New_York",
        )
        tz = window.get_timezone()
        assert tz == ZoneInfo("America/New_York")

    def test_duration_returns_timedelta(self):
        """Test duration calculates correctly."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 30, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        assert window.duration() == timedelta(hours=2, minutes=30)

    def test_applies_to_service_with_empty_ids(self):
        """Test window with empty service_ids applies to all services."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            service_ids=[],
        )
        assert window.applies_to_service(1) is True
        assert window.applies_to_service(999) is True

    def test_applies_to_service_with_specific_ids(self):
        """Test window with specific service_ids only applies to those."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            service_ids=[1, 2, 3],
        )
        assert window.applies_to_service(1) is True
        assert window.applies_to_service(3) is True
        assert window.applies_to_service(5) is False

    def test_is_recurring_true(self):
        """Test is_recurring returns True for recurring windows."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 2 * * 0",
        )
        assert window.is_recurring() is True

    def test_is_recurring_false_when_none(self):
        """Test is_recurring returns False for one-time windows."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence=None,
        )
        assert window.is_recurring() is False

    def test_is_recurring_false_when_empty(self):
        """Test is_recurring returns False for empty string."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="  ",
        )
        assert window.is_recurring() is False


class TestIsValidCronExpression:
    """Tests for is_valid_cron_expression function."""

    def test_valid_standard_cron(self):
        """Test validation of standard cron expressions."""
        assert is_valid_cron_expression("0 2 * * 0") is True  # Every Sunday 2am
        assert is_valid_cron_expression("0 * * * *") is True  # Every hour
        assert is_valid_cron_expression("*/5 * * * *") is True  # Every 5 mins
        assert is_valid_cron_expression("0 0 1 * *") is True  # 1st of month

    def test_valid_cron_with_ranges(self):
        """Test validation of cron with ranges."""
        assert is_valid_cron_expression("0 9-17 * * 1-5") is True  # Weekdays 9-5

    def test_valid_cron_with_lists(self):
        """Test validation of cron with lists."""
        assert is_valid_cron_expression("0 0 1,15 * *") is True  # 1st and 15th

    def test_invalid_cron_returns_false(self):
        """Test that invalid cron expressions return False."""
        assert is_valid_cron_expression("invalid") is False
        assert is_valid_cron_expression("0 0 0 0 0 0 0") is False  # Too many
        assert is_valid_cron_expression("") is False
        assert is_valid_cron_expression("  ") is False

    def test_none_returns_false(self):
        """Test that None returns False."""
        # This would raise TypeError without our check
        result = is_valid_cron_expression(None)
        assert result is False


class TestCronOccurrences:
    """Tests for cron occurrence calculations."""

    def test_get_next_occurrence_basic(self):
        """Test getting next occurrence of hourly cron."""
        base = datetime(2026, 2, 3, 10, 30, tzinfo=ZoneInfo("UTC"))
        next_occ = get_next_occurrence("0 * * * *", base, "UTC")

        assert next_occ is not None
        assert next_occ.hour == 11
        assert next_occ.minute == 0

    def test_get_next_occurrence_weekly(self):
        """Test getting next occurrence of weekly cron."""
        # Monday Feb 3, 2026
        base = datetime(2026, 2, 3, 10, 0, tzinfo=ZoneInfo("UTC"))
        # Every Sunday at 2am
        next_occ = get_next_occurrence("0 2 * * 0", base, "UTC")

        assert next_occ is not None
        assert next_occ.weekday() == 6  # Sunday
        assert next_occ.hour == 2

    def test_get_prev_occurrence_basic(self):
        """Test getting previous occurrence of hourly cron."""
        base = datetime(2026, 2, 3, 10, 30, tzinfo=ZoneInfo("UTC"))
        prev_occ = get_prev_occurrence("0 * * * *", base, "UTC")

        assert prev_occ is not None
        assert prev_occ.hour == 10
        assert prev_occ.minute == 0

    def test_get_prev_occurrence_weekly(self):
        """Test getting previous occurrence of weekly cron."""
        # Tuesday Feb 3, 2026
        base = datetime(2026, 2, 3, 10, 0, tzinfo=ZoneInfo("UTC"))
        # Every Sunday at 2am
        prev_occ = get_prev_occurrence("0 2 * * 0", base, "UTC")

        assert prev_occ is not None
        assert prev_occ.weekday() == 6  # Sunday
        assert prev_occ.hour == 2
        # Should be Sunday Feb 1, 2026
        assert prev_occ.day == 1

    def test_occurrence_with_timezone(self):
        """Test cron occurrence respects timezone."""
        base = datetime(2026, 2, 3, 10, 0, tzinfo=ZoneInfo("UTC"))
        # Daily at 2am Chicago time
        next_occ = get_next_occurrence("0 2 * * *", base, "America/Chicago")

        assert next_occ is not None
        # Chicago is UTC-6 in winter
        chicago_time = next_occ.astimezone(ZoneInfo("America/Chicago"))
        assert chicago_time.hour == 2

    def test_invalid_cron_returns_none(self):
        """Test invalid cron returns None."""
        base = datetime(2026, 2, 3, 10, 0, tzinfo=ZoneInfo("UTC"))
        assert get_next_occurrence("invalid", base, "UTC") is None
        assert get_prev_occurrence("invalid", base, "UTC") is None


class TestIsWithinOneTimeWindow:
    """Tests for is_within_one_time_window function."""

    def test_time_within_window(self):
        """Test time within one-time window returns True."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_one_time_window(window, check) is True

    def test_time_at_start_of_window(self):
        """Test time at start of window is included."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_one_time_window(window, check) is True

    def test_time_at_end_of_window_excluded(self):
        """Test time at end of window is excluded (end is exclusive)."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_one_time_window(window, check) is False

    def test_time_before_window(self):
        """Test time before window returns False."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2026, 2, 1, 9, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_one_time_window(window, check) is False

    def test_time_after_window(self):
        """Test time after window returns False."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2026, 2, 1, 13, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_one_time_window(window, check) is False

    def test_handles_naive_check_time(self):
        """Test that naive check_time is treated as UTC."""
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2026, 2, 1, 11, 0)  # Naive
        assert is_within_one_time_window(window, check) is True

    def test_cross_timezone_comparison(self):
        """Test window comparison across different timezones."""
        # Window in UTC
        window = MaintenanceWindow(
            window_id=1,
            name="Test",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        # Check time in Chicago (UTC-6) - 5am Chicago = 11am UTC
        check = datetime(2026, 2, 1, 5, 0, tzinfo=ZoneInfo("America/Chicago"))
        assert is_within_one_time_window(window, check) is True


class TestIsWithinRecurringWindow:
    """Tests for is_within_recurring_window function."""

    def test_within_recurring_hourly_window(self):
        """Test time within hourly recurring window."""
        # Window that recurs hourly and lasts 30 minutes
        window = MaintenanceWindow(
            window_id=1,
            name="Hourly Maintenance",
            start_time=datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 1, 1, 0, 30, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 * * * *",  # Every hour at :00
        )
        # Check at 10:15 - should be within window (started at 10:00)
        check = datetime(2026, 2, 3, 10, 15, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is True

    def test_outside_recurring_hourly_window(self):
        """Test time outside hourly recurring window."""
        window = MaintenanceWindow(
            window_id=1,
            name="Hourly Maintenance",
            start_time=datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 1, 1, 0, 30, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 * * * *",
        )
        # Check at 10:45 - should be outside window (ended at 10:30)
        check = datetime(2026, 2, 3, 10, 45, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is False

    def test_within_weekly_recurring_window(self):
        """Test time within weekly recurring window."""
        # Weekly maintenance every Sunday at 2am for 2 hours
        window = MaintenanceWindow(
            window_id=1,
            name="Weekly DB Maintenance",
            start_time=datetime(2026, 1, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 1, 5, 4, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 2 * * 0",  # Every Sunday at 2am
        )
        # Sunday Feb 1, 2026 at 3am - should be within window
        check = datetime(2026, 2, 1, 3, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is True

    def test_outside_weekly_recurring_window(self):
        """Test time outside weekly recurring window."""
        window = MaintenanceWindow(
            window_id=1,
            name="Weekly DB Maintenance",
            start_time=datetime(2026, 1, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 1, 5, 4, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 2 * * 0",
        )
        # Sunday Feb 1, 2026 at 5am - should be outside (ended at 4am)
        check = datetime(2026, 2, 1, 5, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is False

    def test_non_recurring_window_returns_false(self):
        """Test that non-recurring window returns False."""
        window = MaintenanceWindow(
            window_id=1,
            name="One-time Window",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence=None,
        )
        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is False

    def test_recurring_with_timezone(self):
        """Test recurring window respects timezone for evaluation."""
        # Maintenance every day at 2am Chicago time for 2 hours
        window = MaintenanceWindow(
            window_id=1,
            name="Daily Chicago Maintenance",
            start_time=datetime(2026, 1, 1, 2, 0, tzinfo=ZoneInfo("America/Chicago")),
            end_time=datetime(2026, 1, 1, 4, 0, tzinfo=ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
            recurrence="0 2 * * *",
        )
        # 8am UTC = 2am Chicago (during winter)
        check = datetime(2026, 2, 3, 8, 30, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is True


class TestIsInMaintenanceWindow:
    """Tests for is_in_maintenance_window function."""

    def test_delegates_to_one_time_check(self):
        """Test one-time window uses one-time check."""
        window = MaintenanceWindow(
            window_id=1,
            name="One-time",
            start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence=None,
        )
        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        assert is_in_maintenance_window(window, check) is True

    def test_delegates_to_recurring_check(self):
        """Test recurring window uses recurring check."""
        window = MaintenanceWindow(
            window_id=1,
            name="Recurring",
            start_time=datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2026, 1, 1, 0, 30, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 * * * *",
        )
        check = datetime(2026, 2, 3, 10, 15, tzinfo=ZoneInfo("UTC"))
        assert is_in_maintenance_window(window, check) is True

    def test_uses_current_time_when_none(self):
        """Test uses current UTC time when check_time is None."""
        # Create a window that includes "now"
        now = datetime.now(ZoneInfo("UTC"))
        window = MaintenanceWindow(
            window_id=1,
            name="Current Window",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            timezone="UTC",
        )
        assert is_in_maintenance_window(window, None) is True


class TestParseMaintenanceWindow:
    """Tests for parse_maintenance_window function."""

    def test_parses_valid_row(self):
        """Test parsing a valid database row."""
        row = {
            "window_id": 1,
            "name": "Test Window",
            "start_time": "2026-02-01T10:00:00+00:00",
            "end_time": "2026-02-01T12:00:00+00:00",
            "timezone": "UTC",
            "recurrence": None,
            "service_ids": [1, 2, 3],
        }
        window = parse_maintenance_window(row)

        assert window is not None
        assert window.window_id == 1
        assert window.name == "Test Window"
        assert window.service_ids == [1, 2, 3]

    def test_handles_datetime_objects(self):
        """Test parsing row with datetime objects (not strings)."""
        row = {
            "window_id": 1,
            "name": "Test",
            "start_time": datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            "end_time": datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            "timezone": "UTC",
            "recurrence": None,
            "service_ids": [],
        }
        window = parse_maintenance_window(row)

        assert window is not None
        assert window.start_time.hour == 10

    def test_handles_null_service_ids(self):
        """Test parsing row with null service_ids."""
        row = {
            "window_id": 1,
            "name": "Test",
            "start_time": "2026-02-01T10:00:00+00:00",
            "end_time": "2026-02-01T12:00:00+00:00",
            "timezone": "UTC",
            "recurrence": None,
            "service_ids": None,
        }
        window = parse_maintenance_window(row)

        assert window is not None
        assert window.service_ids == []

    def test_returns_none_on_missing_keys(self):
        """Test returns None when required keys are missing."""
        row = {"window_id": 1}  # Missing required fields
        window = parse_maintenance_window(row)
        assert window is None


class TestDatabaseFunctions:
    """Tests for database query functions."""

    @patch("Medic.Core.maintenance_windows.query_db")
    def test_get_maintenance_window_by_id(self, mock_query):
        """Test getting maintenance window by ID."""
        mock_query.return_value = json.dumps([{
            "window_id": 1,
            "name": "Test Window",
            "start_time": "2026-02-01T10:00:00+00:00",
            "end_time": "2026-02-01T12:00:00+00:00",
            "timezone": "UTC",
            "recurrence": None,
            "service_ids": [],
        }])

        window = get_maintenance_window(1)

        assert window is not None
        assert window.window_id == 1
        assert window.name == "Test Window"
        mock_query.assert_called_once()

    @patch("Medic.Core.maintenance_windows.query_db")
    def test_get_maintenance_window_returns_none_when_not_found(self, mock_query):
        """Test returns None when window not found."""
        mock_query.return_value = json.dumps([])

        window = get_maintenance_window(999)

        assert window is None

    @patch("Medic.Core.maintenance_windows.query_db")
    def test_get_maintenance_window_by_name(self, mock_query):
        """Test getting maintenance window by name."""
        mock_query.return_value = json.dumps([{
            "window_id": 1,
            "name": "Weekly Maintenance",
            "start_time": "2026-02-01T10:00:00+00:00",
            "end_time": "2026-02-01T12:00:00+00:00",
            "timezone": "UTC",
            "recurrence": "0 2 * * 0",
            "service_ids": [],
        }])

        window = get_maintenance_window_by_name("Weekly Maintenance")

        assert window is not None
        assert window.name == "Weekly Maintenance"
        assert window.recurrence == "0 2 * * 0"

    @patch("Medic.Core.maintenance_windows.query_db")
    def test_get_all_maintenance_windows(self, mock_query):
        """Test getting all maintenance windows."""
        mock_query.return_value = json.dumps([
            {
                "window_id": 1,
                "name": "Window 1",
                "start_time": "2026-02-01T10:00:00+00:00",
                "end_time": "2026-02-01T12:00:00+00:00",
                "timezone": "UTC",
                "recurrence": None,
                "service_ids": [],
            },
            {
                "window_id": 2,
                "name": "Window 2",
                "start_time": "2026-02-02T10:00:00+00:00",
                "end_time": "2026-02-02T12:00:00+00:00",
                "timezone": "UTC",
                "recurrence": None,
                "service_ids": [1],
            },
        ])

        windows = get_all_maintenance_windows()

        assert len(windows) == 2
        assert windows[0].name == "Window 1"
        assert windows[1].name == "Window 2"

    @patch("Medic.Core.maintenance_windows.query_db")
    def test_get_maintenance_windows_for_service(self, mock_query):
        """Test getting maintenance windows for a specific service."""
        mock_query.return_value = json.dumps([{
            "window_id": 1,
            "name": "Service 1 Maintenance",
            "start_time": "2026-02-01T10:00:00+00:00",
            "end_time": "2026-02-01T12:00:00+00:00",
            "timezone": "UTC",
            "recurrence": None,
            "service_ids": [1, 2],
        }])

        windows = get_maintenance_windows_for_service(1)

        assert len(windows) == 1
        assert windows[0].name == "Service 1 Maintenance"


class TestServiceMaintenanceChecks:
    """Tests for service-level maintenance checks."""

    @patch("Medic.Core.maintenance_windows.get_maintenance_windows_for_service")
    def test_is_service_in_maintenance_true(self, mock_get_windows):
        """Test returns True when service is in maintenance."""
        mock_get_windows.return_value = [
            MaintenanceWindow(
                window_id=1,
                name="Active Window",
                start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            )
        ]

        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        result = is_service_in_maintenance(1, check)

        assert result is True

    @patch("Medic.Core.maintenance_windows.get_maintenance_windows_for_service")
    def test_is_service_in_maintenance_false(self, mock_get_windows):
        """Test returns False when service is not in maintenance."""
        mock_get_windows.return_value = [
            MaintenanceWindow(
                window_id=1,
                name="Inactive Window",
                start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            )
        ]

        check = datetime(2026, 2, 1, 13, 0, tzinfo=ZoneInfo("UTC"))
        result = is_service_in_maintenance(1, check)

        assert result is False

    @patch("Medic.Core.maintenance_windows.get_maintenance_windows_for_service")
    def test_is_service_in_maintenance_no_windows(self, mock_get_windows):
        """Test returns False when no windows apply to service."""
        mock_get_windows.return_value = []

        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        result = is_service_in_maintenance(1, check)

        assert result is False

    @patch("Medic.Core.maintenance_windows.get_maintenance_windows_for_service")
    def test_get_active_maintenance_window_for_service(self, mock_get_windows):
        """Test getting active maintenance window for service."""
        mock_get_windows.return_value = [
            MaintenanceWindow(
                window_id=1,
                name="Active Window",
                start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            )
        ]

        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        window = get_active_maintenance_window_for_service(1, check)

        assert window is not None
        assert window.name == "Active Window"

    @patch("Medic.Core.maintenance_windows.get_maintenance_windows_for_service")
    def test_get_maintenance_status(self, mock_get_windows):
        """Test getting detailed maintenance status."""
        mock_get_windows.return_value = [
            MaintenanceWindow(
                window_id=1,
                name="Active Window",
                start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            )
        ]

        check = datetime(2026, 2, 1, 11, 0, tzinfo=ZoneInfo("UTC"))
        status = get_maintenance_status(1, check)

        assert status["in_maintenance"] is True
        assert status["window_name"] == "Active Window"
        assert status["window_id"] == 1
        assert status["maintenance_end"] == "2026-02-01T12:00:00+00:00"

    @patch("Medic.Core.maintenance_windows.get_maintenance_windows_for_service")
    def test_get_maintenance_status_not_in_maintenance(self, mock_get_windows):
        """Test maintenance status when not in maintenance."""
        mock_get_windows.return_value = []

        status = get_maintenance_status(1)

        assert status["in_maintenance"] is False
        assert status["window_name"] is None
        assert status["window_id"] is None
        assert status["maintenance_end"] is None


class TestDSTHandling:
    """Tests for DST transition handling."""

    def test_one_time_window_during_dst_spring_forward(self):
        """Test one-time window handles DST spring forward correctly."""
        # March 8, 2026 at 2am - DST starts in US (clocks spring forward)
        # Window scheduled in America/Chicago
        window = MaintenanceWindow(
            window_id=1,
            name="DST Window",
            start_time=datetime(2026, 3, 8, 1, 0, tzinfo=ZoneInfo("America/Chicago")),
            end_time=datetime(2026, 3, 8, 4, 0, tzinfo=ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
        # Check at 3:30am Chicago time (which is 1:30am + DST jump)
        check = datetime(2026, 3, 8, 3, 30, tzinfo=ZoneInfo("America/Chicago"))
        assert is_within_one_time_window(window, check) is True

    def test_one_time_window_during_dst_fall_back(self):
        """Test one-time window handles DST fall back correctly."""
        # November 1, 2026 at 2am - DST ends in US (clocks fall back)
        window = MaintenanceWindow(
            window_id=1,
            name="DST Window",
            start_time=datetime(2026, 11, 1, 1, 0, tzinfo=ZoneInfo("America/Chicago")),
            end_time=datetime(2026, 11, 1, 4, 0, tzinfo=ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
        # Check at 2:30am (first occurrence, before fall back)
        check = datetime(2026, 11, 1, 2, 30, tzinfo=ZoneInfo("America/Chicago"))
        assert is_within_one_time_window(window, check) is True


class TestLeapYearHandling:
    """Tests for leap year handling."""

    def test_one_time_window_on_leap_day(self):
        """Test one-time window on Feb 29 (leap day) in 2028."""
        # 2028 is a leap year
        window = MaintenanceWindow(
            window_id=1,
            name="Leap Day Maintenance",
            start_time=datetime(2028, 2, 29, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2028, 2, 29, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
        )
        check = datetime(2028, 2, 29, 11, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_one_time_window(window, check) is True

    def test_recurring_window_includes_leap_day(self):
        """Test recurring window executes on leap day."""
        # Daily maintenance at 10am
        window = MaintenanceWindow(
            window_id=1,
            name="Daily Maintenance",
            start_time=datetime(2028, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            end_time=datetime(2028, 1, 1, 12, 0, tzinfo=ZoneInfo("UTC")),
            timezone="UTC",
            recurrence="0 10 * * *",  # Every day at 10am
        )
        # Feb 29, 2028 at 11am - should be in maintenance
        check = datetime(2028, 2, 29, 11, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_recurring_window(window, check) is True


class TestActiveWindowQueries:
    """Tests for active window query functions."""

    @patch("Medic.Core.maintenance_windows.get_all_maintenance_windows")
    def test_get_active_maintenance_windows(self, mock_get_all):
        """Test getting all currently active maintenance windows."""
        mock_get_all.return_value = [
            MaintenanceWindow(
                window_id=1,
                name="Active Window",
                start_time=datetime(2026, 2, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 1, 14, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            ),
            MaintenanceWindow(
                window_id=2,
                name="Inactive Window",
                start_time=datetime(2026, 2, 1, 15, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 1, 17, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            ),
        ]

        check = datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
        active = get_active_maintenance_windows(check)

        assert len(active) == 1
        assert active[0].name == "Active Window"

    @patch("Medic.Core.maintenance_windows.get_all_maintenance_windows")
    def test_get_active_maintenance_windows_none_active(self, mock_get_all):
        """Test returns empty list when no windows are active."""
        mock_get_all.return_value = [
            MaintenanceWindow(
                window_id=1,
                name="Future Window",
                start_time=datetime(2026, 2, 10, 10, 0, tzinfo=ZoneInfo("UTC")),
                end_time=datetime(2026, 2, 10, 14, 0, tzinfo=ZoneInfo("UTC")),
                timezone="UTC",
            ),
        ]

        check = datetime(2026, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
        active = get_active_maintenance_windows(check)

        assert len(active) == 0
