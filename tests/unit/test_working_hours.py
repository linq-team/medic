"""Unit tests for working hours evaluation."""
import json
from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest


class TestParseTime:
    """Tests for parse_time function."""

    def test_parses_valid_time(self):
        """Test parsing valid time strings."""
        from Medic.Core.working_hours import parse_time

        result = parse_time("09:00")
        assert result == time(9, 0)

        result = parse_time("17:30")
        assert result == time(17, 30)

        result = parse_time("00:00")
        assert result == time(0, 0)

        result = parse_time("23:59")
        assert result == time(23, 59)

    def test_parses_time_with_whitespace(self):
        """Test parsing time strings with leading/trailing whitespace."""
        from Medic.Core.working_hours import parse_time

        result = parse_time("  09:00  ")
        assert result == time(9, 0)

    def test_raises_on_invalid_format(self):
        """Test that invalid format raises ValueError."""
        from Medic.Core.working_hours import parse_time

        with pytest.raises(ValueError):
            parse_time("09:00:00")  # Seconds not supported

        with pytest.raises(ValueError):
            parse_time("invalid")

        with pytest.raises(ValueError):
            parse_time("")

    def test_raises_on_invalid_hour(self):
        """Test that invalid hour raises ValueError."""
        from Medic.Core.working_hours import parse_time

        with pytest.raises(ValueError):
            parse_time("24:00")

        with pytest.raises(ValueError):
            parse_time("-1:00")

    def test_raises_on_invalid_minute(self):
        """Test that invalid minute raises ValueError."""
        from Medic.Core.working_hours import parse_time

        with pytest.raises(ValueError):
            parse_time("09:60")

        with pytest.raises(ValueError):
            parse_time("09:-1")


class TestTimeRange:
    """Tests for TimeRange class."""

    def test_contains_time_in_range(self):
        """Test that times within range are detected."""
        from Medic.Core.working_hours import TimeRange

        tr = TimeRange(start=time(9, 0), end=time(17, 0))

        assert tr.contains(time(9, 0)) is True
        assert tr.contains(time(12, 0)) is True
        assert tr.contains(time(16, 59)) is True

    def test_excludes_time_outside_range(self):
        """Test that times outside range are excluded."""
        from Medic.Core.working_hours import TimeRange

        tr = TimeRange(start=time(9, 0), end=time(17, 0))

        assert tr.contains(time(8, 59)) is False
        assert tr.contains(time(17, 0)) is False  # End time is exclusive
        assert tr.contains(time(17, 1)) is False
        assert tr.contains(time(0, 0)) is False

    def test_handles_midnight_crossing_range(self):
        """Test ranges that cross midnight (e.g., night shift)."""
        from Medic.Core.working_hours import TimeRange

        # 22:00 to 06:00 (overnight shift)
        tr = TimeRange(start=time(22, 0), end=time(6, 0))

        assert tr.contains(time(22, 0)) is True
        assert tr.contains(time(23, 0)) is True
        assert tr.contains(time(0, 0)) is True
        assert tr.contains(time(3, 0)) is True
        assert tr.contains(time(5, 59)) is True

        assert tr.contains(time(6, 0)) is False  # End time exclusive
        assert tr.contains(time(12, 0)) is False
        assert tr.contains(time(21, 59)) is False

    def test_handles_full_day_range(self):
        """Test a range covering the entire day."""
        from Medic.Core.working_hours import TimeRange

        tr = TimeRange(start=time(0, 0), end=time(0, 0))

        # When start == end and both are 00:00, nothing is in range
        # This is an edge case - full day should be 00:00 to 23:59
        assert tr.contains(time(12, 0)) is False


class TestParseHours:
    """Tests for parse_hours function."""

    def test_parses_simple_hours(self):
        """Test parsing simple working hours."""
        from Medic.Core.working_hours import parse_hours

        hours_data = {
            "monday": [{"start": "09:00", "end": "17:00"}],
            "tuesday": [{"start": "09:00", "end": "17:00"}],
        }

        result = parse_hours(hours_data)

        assert "monday" in result
        assert "tuesday" in result
        assert len(result["monday"]) == 1
        assert result["monday"][0].start == time(9, 0)
        assert result["monday"][0].end == time(17, 0)

    def test_parses_multiple_ranges_per_day(self):
        """Test parsing multiple time ranges per day."""
        from Medic.Core.working_hours import parse_hours

        hours_data = {
            "monday": [
                {"start": "09:00", "end": "12:00"},
                {"start": "13:00", "end": "17:00"},
            ]
        }

        result = parse_hours(hours_data)

        assert len(result["monday"]) == 2
        assert result["monday"][0].start == time(9, 0)
        assert result["monday"][0].end == time(12, 0)
        assert result["monday"][1].start == time(13, 0)
        assert result["monday"][1].end == time(17, 0)

    def test_normalizes_day_names_to_lowercase(self):
        """Test that day names are normalized to lowercase."""
        from Medic.Core.working_hours import parse_hours

        hours_data = {
            "Monday": [{"start": "09:00", "end": "17:00"}],
            "TUESDAY": [{"start": "09:00", "end": "17:00"}],
        }

        result = parse_hours(hours_data)

        assert "monday" in result
        assert "tuesday" in result
        assert "Monday" not in result
        assert "TUESDAY" not in result

    def test_ignores_unknown_day_names(self):
        """Test that unknown day names are ignored with warning."""
        from Medic.Core.working_hours import parse_hours

        hours_data = {
            "monday": [{"start": "09:00", "end": "17:00"}],
            "funday": [{"start": "09:00", "end": "17:00"}],
        }

        result = parse_hours(hours_data)

        assert "monday" in result
        assert "funday" not in result

    def test_raises_on_invalid_ranges_type(self):
        """Test that non-list ranges raise ValueError."""
        from Medic.Core.working_hours import parse_hours

        hours_data = {
            "monday": {"start": "09:00", "end": "17:00"},  # Not a list
        }

        with pytest.raises(ValueError):
            parse_hours(hours_data)

    def test_raises_on_invalid_range_dict(self):
        """Test that invalid range dicts raise ValueError."""
        from Medic.Core.working_hours import parse_hours

        # Missing end
        hours_data = {"monday": [{"start": "09:00"}]}
        with pytest.raises(ValueError):
            parse_hours(hours_data)

        # Missing start
        hours_data = {"monday": [{"end": "17:00"}]}
        with pytest.raises(ValueError):
            parse_hours(hours_data)

        # Not a dict
        hours_data = {"monday": ["09:00-17:00"]}
        with pytest.raises(ValueError):
            parse_hours(hours_data)


class TestIsValidTimezone:
    """Tests for is_valid_timezone function."""

    def test_valid_iana_timezones(self):
        """Test that valid IANA timezones return True."""
        from Medic.Core.working_hours import is_valid_timezone

        assert is_valid_timezone("America/Chicago") is True
        assert is_valid_timezone("America/New_York") is True
        assert is_valid_timezone("Europe/London") is True
        assert is_valid_timezone("Asia/Tokyo") is True
        assert is_valid_timezone("UTC") is True
        assert is_valid_timezone("Etc/UTC") is True

    def test_invalid_timezones(self):
        """Test that invalid timezones return False."""
        from Medic.Core.working_hours import is_valid_timezone

        assert is_valid_timezone("Invalid/Timezone") is False
        assert is_valid_timezone("CST") is False  # Abbreviations not supported
        assert is_valid_timezone("") is False
        assert is_valid_timezone("US/Central") is True  # Legacy but supported


class TestIsWithinWorkingHours:
    """Tests for is_within_working_hours function."""

    def test_within_hours_returns_true(self):
        """Test that times within working hours return True."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="US Business Hours",
            timezone="America/Chicago",
            hours={
                "monday": [TimeRange(time(9, 0), time(17, 0))],
                "tuesday": [TimeRange(time(9, 0), time(17, 0))],
            },
        )

        # Monday at 10:00 CST
        check_time = datetime(2024, 1, 8, 16, 0, 0, tzinfo=ZoneInfo("UTC"))
        # 16:00 UTC = 10:00 CST
        assert is_within_working_hours(schedule, check_time) is True

    def test_outside_hours_returns_false(self):
        """Test that times outside working hours return False."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="US Business Hours",
            timezone="America/Chicago",
            hours={
                "monday": [TimeRange(time(9, 0), time(17, 0))],
            },
        )

        # Monday at 08:00 CST (before 9am)
        check_time = datetime(2024, 1, 8, 14, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

        # Monday at 18:00 CST (after 5pm)
        check_time = datetime(2024, 1, 9, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

    def test_day_without_hours_returns_false(self):
        """Test that days without defined hours return False."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Weekdays Only",
            timezone="America/Chicago",
            hours={
                "monday": [TimeRange(time(9, 0), time(17, 0))],
                # Saturday and Sunday not defined
            },
        )

        # Saturday at 10:00 CST
        check_time = datetime(2024, 1, 6, 16, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

    def test_uses_current_time_when_none(self, mock_env_vars):
        """Test that current time is used when check_time is None."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Always Open",
            timezone="UTC",
            hours={day: [TimeRange(time(0, 0), time(23, 59))]
                   for day in ["monday", "tuesday", "wednesday", "thursday",
                               "friday", "saturday", "sunday"]},
        )

        # Should use current time and be within hours
        result = is_within_working_hours(schedule)
        assert result is True

    def test_handles_naive_datetime_as_utc(self):
        """Test that naive datetimes are treated as UTC."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test Schedule",
            timezone="UTC",
            hours={
                "monday": [TimeRange(time(9, 0), time(17, 0))],
            },
        )

        # Naive datetime for Monday 10:00
        check_time = datetime(2024, 1, 8, 10, 0, 0)  # No tzinfo
        assert is_within_working_hours(schedule, check_time) is True

    def test_handles_multiple_ranges_per_day(self):
        """Test evaluation with multiple ranges per day (lunch break)."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="With Lunch Break",
            timezone="UTC",
            hours={
                "monday": [
                    TimeRange(time(9, 0), time(12, 0)),
                    TimeRange(time(13, 0), time(17, 0)),
                ],
            },
        )

        # Monday 10:00 - within morning hours
        check_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

        # Monday 12:30 - lunch break (not working)
        check_time = datetime(2024, 1, 8, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

        # Monday 15:00 - within afternoon hours
        check_time = datetime(2024, 1, 8, 15, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True


class TestDSTTransitions:
    """Tests for DST transition edge cases."""

    def test_spring_forward_dst_transition(self):
        """Test handling of spring forward DST transition.

        In America/Chicago, on March 10, 2024 at 2:00 AM CST,
        clocks spring forward to 3:00 AM CDT.
        """
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="DST Test Schedule",
            timezone="America/Chicago",
            hours={
                "sunday": [TimeRange(time(1, 0), time(4, 0))],
            },
        )

        # 1:30 AM CST (before DST, still in range)
        check_time = datetime(2024, 3, 10, 7, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

        # 3:30 AM CDT (after DST, still in range)
        # This is 8:30 UTC
        check_time = datetime(2024, 3, 10, 8, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

        # 4:30 AM CDT (after range)
        check_time = datetime(2024, 3, 10, 9, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

    def test_fall_back_dst_transition(self):
        """Test handling of fall back DST transition.

        In America/Chicago, on November 3, 2024 at 2:00 AM CDT,
        clocks fall back to 1:00 AM CST.
        """
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="DST Test Schedule",
            timezone="America/Chicago",
            hours={
                "sunday": [TimeRange(time(0, 0), time(3, 0))],
            },
        )

        # 1:30 AM CDT (before fall back)
        check_time = datetime(2024, 11, 3, 6, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

        # 1:30 AM CST (after fall back - same hour repeated)
        check_time = datetime(2024, 11, 3, 7, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

    def test_dst_europe_london(self):
        """Test DST handling for Europe/London timezone."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="UK Business Hours",
            timezone="Europe/London",
            hours={
                "monday": [TimeRange(time(9, 0), time(17, 0))],
            },
        )

        # March 25, 2024 - after UK DST starts (last Sunday of March)
        # 10:00 BST = 09:00 UTC
        check_time = datetime(2024, 3, 25, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

        # October 28, 2024 - after UK DST ends
        # 10:00 GMT = 10:00 UTC
        check_time = datetime(2024, 10, 28, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True


class TestLeapYearHandling:
    """Tests for leap year handling."""

    def test_leap_year_feb_29(self):
        """Test that February 29 in leap year is handled correctly."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="All Days",
            timezone="UTC",
            hours={
                "thursday": [TimeRange(time(9, 0), time(17, 0))],
            },
        )

        # Feb 29, 2024 is a Thursday (leap year)
        check_time = datetime(2024, 2, 29, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

    def test_non_leap_year_feb_28(self):
        """Test that February 28 in non-leap year works correctly."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="All Days",
            timezone="UTC",
            hours={
                "tuesday": [TimeRange(time(9, 0), time(17, 0))],
            },
        )

        # Feb 28, 2023 is a Tuesday (non-leap year)
        check_time = datetime(2023, 2, 28, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True


class TestGetSchedule:
    """Tests for get_schedule function."""

    def test_returns_schedule_when_found(self, mock_env_vars):
        """Test that schedule is returned when found."""
        from Medic.Core.working_hours import get_schedule

        schedule_data = [{
            "schedule_id": 1,
            "name": "US Business Hours",
            "timezone": "America/Chicago",
            "hours": {"monday": [{"start": "09:00", "end": "17:00"}]},
        }]

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps(schedule_data)

            result = get_schedule(1)

            assert result is not None
            assert result.schedule_id == 1
            assert result.name == "US Business Hours"
            assert result.timezone == "America/Chicago"
            assert "monday" in result.hours

    def test_returns_none_when_not_found(self, mock_env_vars):
        """Test that None is returned when schedule not found."""
        from Medic.Core.working_hours import get_schedule

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_schedule(999)

            assert result is None

    def test_returns_none_on_query_failure(self, mock_env_vars):
        """Test that None is returned when query fails."""
        from Medic.Core.working_hours import get_schedule

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = None

            result = get_schedule(1)

            assert result is None

    def test_handles_string_hours_json(self, mock_env_vars):
        """Test that hours as JSON string is parsed."""
        from Medic.Core.working_hours import get_schedule

        schedule_data = [{
            "schedule_id": 1,
            "name": "US Business Hours",
            "timezone": "America/Chicago",
            "hours": '{"monday": [{"start": "09:00", "end": "17:00"}]}',
        }]

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps(schedule_data)

            result = get_schedule(1)

            assert result is not None
            assert "monday" in result.hours


class TestGetScheduleForService:
    """Tests for get_schedule_for_service function."""

    def test_returns_schedule_for_service_with_schedule(self, mock_env_vars):
        """Test that schedule is returned for service with schedule."""
        from Medic.Core.working_hours import get_schedule_for_service

        schedule_data = [{
            "schedule_id": 1,
            "name": "US Business Hours",
            "timezone": "America/Chicago",
            "hours": {"monday": [{"start": "09:00", "end": "17:00"}]},
        }]

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps(schedule_data)

            result = get_schedule_for_service(123)

            assert result is not None
            assert result.schedule_id == 1
            mock_query.assert_called_once()
            query = mock_query.call_args[0][0]
            assert "services" in query
            assert "medic.schedules" in query

    def test_returns_none_for_service_without_schedule(self, mock_env_vars):
        """Test that None is returned for service without schedule."""
        from Medic.Core.working_hours import get_schedule_for_service

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            result = get_schedule_for_service(123)

            assert result is None


class TestIsServiceWithinWorkingHours:
    """Tests for is_service_within_working_hours function."""

    def test_within_hours_with_schedule(self, mock_env_vars):
        """Test service within hours when schedule exists."""
        from Medic.Core.working_hours import is_service_within_working_hours

        schedule_data = [{
            "schedule_id": 1,
            "name": "US Business Hours",
            "timezone": "UTC",
            "hours": {"monday": [{"start": "09:00", "end": "17:00"}]},
        }]

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps(schedule_data)

            # Monday 10:00 UTC
            check_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
            within, name = is_service_within_working_hours(123, check_time)

            assert within is True
            assert name == "US Business Hours"

    def test_outside_hours_with_schedule(self, mock_env_vars):
        """Test service outside hours when schedule exists."""
        from Medic.Core.working_hours import is_service_within_working_hours

        schedule_data = [{
            "schedule_id": 1,
            "name": "US Business Hours",
            "timezone": "UTC",
            "hours": {"monday": [{"start": "09:00", "end": "17:00"}]},
        }]

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps(schedule_data)

            # Monday 08:00 UTC (before 9am)
            check_time = datetime(2024, 1, 8, 8, 0, 0, tzinfo=ZoneInfo("UTC"))
            within, name = is_service_within_working_hours(123, check_time)

            assert within is False
            assert name == "US Business Hours"

    def test_no_schedule_returns_within_hours(self, mock_env_vars):
        """Test that service without schedule is always within hours."""
        from Medic.Core.working_hours import is_service_within_working_hours

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            within, name = is_service_within_working_hours(123)

            assert within is True
            assert name is None


class TestGetCurrentPeriod:
    """Tests for get_current_period and get_service_current_period functions."""

    def test_returns_during_hours_when_within(self):
        """Test that 'during_hours' is returned when within hours."""
        from Medic.Core.working_hours import (
            get_current_period, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test",
            timezone="UTC",
            hours={"monday": [TimeRange(time(9, 0), time(17, 0))]},
        )

        check_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert get_current_period(schedule, check_time) == "during_hours"

    def test_returns_after_hours_when_outside(self):
        """Test that 'after_hours' is returned when outside hours."""
        from Medic.Core.working_hours import (
            get_current_period, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test",
            timezone="UTC",
            hours={"monday": [TimeRange(time(9, 0), time(17, 0))]},
        )

        check_time = datetime(2024, 1, 8, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert get_current_period(schedule, check_time) == "after_hours"

    def test_service_current_period_with_schedule(self, mock_env_vars):
        """Test get_service_current_period with schedule."""
        from Medic.Core.working_hours import get_service_current_period

        schedule_data = [{
            "schedule_id": 1,
            "name": "Test",
            "timezone": "UTC",
            "hours": {"monday": [{"start": "09:00", "end": "17:00"}]},
        }]

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps(schedule_data)

            check_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
            assert get_service_current_period(123, check_time) == "during_hours"

            check_time = datetime(2024, 1, 8, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
            assert get_service_current_period(123, check_time) == "after_hours"

    def test_service_current_period_without_schedule(self, mock_env_vars):
        """Test get_service_current_period without schedule."""
        from Medic.Core.working_hours import get_service_current_period

        with patch("Medic.Core.working_hours.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            # Should always return during_hours when no schedule
            check_time = datetime(2024, 1, 8, 3, 0, 0, tzinfo=ZoneInfo("UTC"))
            assert get_service_current_period(123, check_time) == "during_hours"


class TestInvalidTimezoneHandling:
    """Tests for handling of invalid timezones."""

    def test_invalid_timezone_returns_false(self):
        """Test that invalid timezone returns False for is_within_working_hours."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, parse_hours
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test",
            timezone="Invalid/Timezone",
            hours=parse_hours({"monday": [{"start": "00:00", "end": "23:59"}]}),
        )

        check_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False


class TestEdgeCases:
    """Tests for various edge cases."""

    def test_empty_hours_returns_false(self):
        """Test that empty hours definition returns False."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule
        )

        schedule = Schedule(
            schedule_id=1,
            name="Empty Schedule",
            timezone="UTC",
            hours={},
        )

        check_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

    def test_end_time_is_exclusive(self):
        """Test that end time is exclusive (not included in range)."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test",
            timezone="UTC",
            hours={"monday": [TimeRange(time(9, 0), time(17, 0))]},
        )

        # Exactly 17:00 should be outside hours
        check_time = datetime(2024, 1, 8, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is False

    def test_start_time_is_inclusive(self):
        """Test that start time is inclusive (included in range)."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test",
            timezone="UTC",
            hours={"monday": [TimeRange(time(9, 0), time(17, 0))]},
        )

        # Exactly 09:00 should be within hours
        check_time = datetime(2024, 1, 8, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

    def test_year_boundary(self):
        """Test handling of year boundary (Dec 31 -> Jan 1)."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        schedule = Schedule(
            schedule_id=1,
            name="Test",
            timezone="UTC",
            hours={
                "tuesday": [TimeRange(time(9, 0), time(17, 0))],  # Dec 31, 2024
                "wednesday": [TimeRange(time(9, 0), time(17, 0))],  # Jan 1, 2025
            },
        )

        # Dec 31, 2024 is Tuesday
        check_time = datetime(2024, 12, 31, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

        # Jan 1, 2025 is Wednesday
        check_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_within_working_hours(schedule, check_time) is True

    def test_all_days_of_week(self):
        """Test that all days of week are recognized."""
        from Medic.Core.working_hours import (
            is_within_working_hours, Schedule, TimeRange
        )

        all_days = {
            "monday": [TimeRange(time(9, 0), time(17, 0))],
            "tuesday": [TimeRange(time(9, 0), time(17, 0))],
            "wednesday": [TimeRange(time(9, 0), time(17, 0))],
            "thursday": [TimeRange(time(9, 0), time(17, 0))],
            "friday": [TimeRange(time(9, 0), time(17, 0))],
            "saturday": [TimeRange(time(9, 0), time(17, 0))],
            "sunday": [TimeRange(time(9, 0), time(17, 0))],
        }

        schedule = Schedule(
            schedule_id=1,
            name="All Week",
            timezone="UTC",
            hours=all_days,
        )

        # Test each day (Jan 8-14, 2024 is Mon-Sun)
        for day_offset in range(7):
            check_time = datetime(
                2024, 1, 8 + day_offset, 10, 0, 0, tzinfo=ZoneInfo("UTC")
            )
            assert is_within_working_hours(schedule, check_time) is True
