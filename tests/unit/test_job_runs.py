"""Unit tests for job_runs module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytz
import json


class TestJobRunDataclass:
    """Tests for JobRun dataclass."""

    def test_job_run_initialization(self):
        """Test JobRun object creation."""
        from Medic.Core.job_runs import JobRun

        started_at = datetime.now(pytz.timezone('America/Chicago'))
        job_run = JobRun(
            run_id_pk=1,
            service_id=10,
            run_id="test-run-123",
            started_at=started_at,
            status="STARTED"
        )

        assert job_run.run_id_pk == 1
        assert job_run.service_id == 10
        assert job_run.run_id == "test-run-123"
        assert job_run.started_at == started_at
        assert job_run.completed_at is None
        assert job_run.duration_ms is None
        assert job_run.status == "STARTED"

    def test_job_run_with_completion(self):
        """Test JobRun with completion data."""
        from Medic.Core.job_runs import JobRun

        started_at = datetime.now(pytz.timezone('America/Chicago'))
        completed_at = started_at + timedelta(seconds=30)
        job_run = JobRun(
            run_id_pk=1,
            service_id=10,
            run_id="test-run-123",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=30000,
            status="COMPLETED"
        )

        assert job_run.completed_at == completed_at
        assert job_run.duration_ms == 30000
        assert job_run.status == "COMPLETED"

    def test_job_run_to_dict(self):
        """Test JobRun to_dict method."""
        from Medic.Core.job_runs import JobRun

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        job_run = JobRun(
            run_id_pk=1,
            service_id=10,
            run_id="test-run-123",
            started_at=started_at,
            status="STARTED"
        )

        result = job_run.to_dict()

        assert result["run_id_pk"] == 1
        assert result["service_id"] == 10
        assert result["run_id"] == "test-run-123"
        assert result["started_at"] == started_at.isoformat()
        assert result["completed_at"] is None
        assert result["duration_ms"] is None
        assert result["status"] == "STARTED"


class TestRecordJobStart:
    """Tests for record_job_start function."""

    @patch("Medic.Core.job_runs.db")
    def test_record_job_start_success(self, mock_db):
        """Test successful job start recording."""
        from Medic.Core.job_runs import record_job_start

        # No existing run
        mock_db.query_db.return_value = "[]"
        mock_db.insert_db.return_value = True

        result = record_job_start(service_id=10, run_id="test-run-123")

        assert result is not None
        assert result.service_id == 10
        assert result.run_id == "test-run-123"
        assert result.status == "STARTED"
        mock_db.insert_db.assert_called_once()

    @patch("Medic.Core.job_runs.db")
    def test_record_job_start_duplicate(self, mock_db):
        """Test job start with duplicate run_id returns None."""
        from Medic.Core.job_runs import record_job_start

        # Existing run found
        mock_db.query_db.return_value = '[{"run_id_pk": 1}]'

        result = record_job_start(service_id=10, run_id="test-run-123")

        assert result is None
        mock_db.insert_db.assert_not_called()

    @patch("Medic.Core.job_runs.db")
    def test_record_job_start_insert_failure(self, mock_db):
        """Test job start with insert failure returns None."""
        from Medic.Core.job_runs import record_job_start

        mock_db.query_db.return_value = "[]"
        mock_db.insert_db.return_value = False

        result = record_job_start(service_id=10, run_id="test-run-123")

        assert result is None

    @patch("Medic.Core.job_runs.db")
    def test_record_job_start_with_custom_time(self, mock_db):
        """Test job start with custom start time."""
        from Medic.Core.job_runs import record_job_start

        mock_db.query_db.return_value = "[]"
        mock_db.insert_db.return_value = True

        custom_time = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        result = record_job_start(
            service_id=10,
            run_id="test-run-123",
            started_at=custom_time
        )

        assert result is not None
        assert result.started_at == custom_time


class TestRecordJobCompletion:
    """Tests for record_job_completion function."""

    @patch("Medic.Core.job_runs.db")
    def test_record_job_completion_success(self, mock_db):
        """Test successful job completion recording."""
        from Medic.Core.job_runs import record_job_completion

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        # Existing STARTED run
        mock_db.query_db.return_value = json.dumps([{
            "run_id_pk": 1,
            "started_at": started_at.isoformat()
        }])
        mock_db.insert_db.return_value = True

        completed_at = started_at + timedelta(seconds=30)
        result = record_job_completion(
            service_id=10,
            run_id="test-run-123",
            status="COMPLETED",
            completed_at=completed_at
        )

        assert result is not None
        assert result.status == "COMPLETED"
        assert result.duration_ms == 30000  # 30 seconds in ms
        mock_db.insert_db.assert_called_once()

    @patch("Medic.Core.job_runs.db")
    def test_record_job_completion_failed_status(self, mock_db):
        """Test job completion with FAILED status."""
        from Medic.Core.job_runs import record_job_completion

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        mock_db.query_db.return_value = json.dumps([{
            "run_id_pk": 1,
            "started_at": started_at.isoformat()
        }])
        mock_db.insert_db.return_value = True

        completed_at = started_at + timedelta(seconds=5)
        result = record_job_completion(
            service_id=10,
            run_id="test-run-123",
            status="FAILED",
            completed_at=completed_at
        )

        assert result is not None
        assert result.status == "FAILED"
        assert result.duration_ms == 5000

    @patch("Medic.Core.job_runs.db")
    def test_record_job_completion_invalid_status(self, mock_db):
        """Test job completion with invalid status returns None."""
        from Medic.Core.job_runs import record_job_completion

        result = record_job_completion(
            service_id=10,
            run_id="test-run-123",
            status="INVALID"
        )

        assert result is None
        mock_db.query_db.assert_not_called()

    @patch("Medic.Core.job_runs.db")
    def test_record_job_completion_no_start(self, mock_db):
        """Test job completion when no STARTED run exists."""
        from Medic.Core.job_runs import record_job_completion

        # No existing STARTED run
        mock_db.query_db.return_value = "[]"
        mock_db.insert_db.return_value = True

        result = record_job_completion(
            service_id=10,
            run_id="test-run-123",
            status="COMPLETED"
        )

        # Should create a new record with zero duration
        assert result is not None
        assert result.duration_ms == 0
        mock_db.insert_db.assert_called_once()

    @patch("Medic.Core.job_runs.db")
    def test_record_job_completion_calculates_duration_ms(self, mock_db):
        """Test that duration is calculated correctly in milliseconds."""
        from Medic.Core.job_runs import record_job_completion

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        mock_db.query_db.return_value = json.dumps([{
            "run_id_pk": 1,
            "started_at": started_at.isoformat()
        }])
        mock_db.insert_db.return_value = True

        # Completed 1.5 seconds later
        completed_at = started_at + timedelta(milliseconds=1500)
        result = record_job_completion(
            service_id=10,
            run_id="test-run-123",
            status="COMPLETED",
            completed_at=completed_at
        )

        assert result is not None
        assert result.duration_ms == 1500


class TestGetJobRun:
    """Tests for get_job_run function."""

    @patch("Medic.Core.job_runs.db")
    def test_get_job_run_found(self, mock_db):
        """Test getting an existing job run."""
        from Medic.Core.job_runs import get_job_run

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        mock_db.query_db.return_value = json.dumps([{
            "run_id_pk": 1,
            "service_id": 10,
            "run_id": "test-run-123",
            "started_at": started_at.isoformat(),
            "completed_at": None,
            "duration_ms": None,
            "status": "STARTED"
        }])

        result = get_job_run(service_id=10, run_id="test-run-123")

        assert result is not None
        assert result.service_id == 10
        assert result.run_id == "test-run-123"
        assert result.status == "STARTED"

    @patch("Medic.Core.job_runs.db")
    def test_get_job_run_not_found(self, mock_db):
        """Test getting a non-existent job run."""
        from Medic.Core.job_runs import get_job_run

        mock_db.query_db.return_value = "[]"

        result = get_job_run(service_id=10, run_id="nonexistent")

        assert result is None


class TestGetCompletedRunsForService:
    """Tests for get_completed_runs_for_service function."""

    @patch("Medic.Core.job_runs.db")
    def test_get_completed_runs_success(self, mock_db):
        """Test getting completed runs for a service."""
        from Medic.Core.job_runs import get_completed_runs_for_service

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        completed_at = started_at + timedelta(seconds=30)
        mock_db.query_db.return_value = json.dumps([
            {
                "run_id_pk": 1,
                "service_id": 10,
                "run_id": "run-1",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_ms": 30000,
                "status": "COMPLETED"
            },
            {
                "run_id_pk": 2,
                "service_id": 10,
                "run_id": "run-2",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_ms": 25000,
                "status": "COMPLETED"
            }
        ])

        result = get_completed_runs_for_service(service_id=10)

        assert len(result) == 2
        assert result[0].run_id == "run-1"
        assert result[1].run_id == "run-2"

    @patch("Medic.Core.job_runs.db")
    def test_get_completed_runs_empty(self, mock_db):
        """Test getting completed runs when none exist."""
        from Medic.Core.job_runs import get_completed_runs_for_service

        mock_db.query_db.return_value = "[]"

        result = get_completed_runs_for_service(service_id=10)

        assert result == []

    @patch("Medic.Core.job_runs.db")
    def test_get_completed_runs_with_limit(self, mock_db):
        """Test getting completed runs with custom limit."""
        from Medic.Core.job_runs import get_completed_runs_for_service

        mock_db.query_db.return_value = "[]"

        get_completed_runs_for_service(service_id=10, limit=50)

        call_args = mock_db.query_db.call_args
        assert call_args[0][1] == (10, 50)


class TestGetStaleRuns:
    """Tests for get_stale_runs function."""

    @patch("Medic.Core.job_runs.db")
    def test_get_stale_runs_found(self, mock_db):
        """Test getting stale runs that haven't completed."""
        from Medic.Core.job_runs import get_stale_runs

        started_at = datetime(2026, 2, 3, 10, 0, 0, tzinfo=pytz.UTC)
        mock_db.query_db.return_value = json.dumps([{
            "run_id_pk": 1,
            "service_id": 10,
            "run_id": "stale-run",
            "started_at": started_at.isoformat(),
            "completed_at": None,
            "duration_ms": None,
            "status": "STARTED"
        }])

        result = get_stale_runs(service_id=10, older_than_seconds=3600)

        assert len(result) == 1
        assert result[0].run_id == "stale-run"
        assert result[0].status == "STARTED"

    @patch("Medic.Core.job_runs.db")
    def test_get_stale_runs_all_services(self, mock_db):
        """Test getting stale runs for all services."""
        from Medic.Core.job_runs import get_stale_runs

        mock_db.query_db.return_value = "[]"

        get_stale_runs(older_than_seconds=3600)

        call_args = mock_db.query_db.call_args
        # Should only have the seconds parameter, not service_id
        assert call_args[0][1] == (3600,)

    @patch("Medic.Core.job_runs.db")
    def test_get_stale_runs_specific_service(self, mock_db):
        """Test getting stale runs for a specific service."""
        from Medic.Core.job_runs import get_stale_runs

        mock_db.query_db.return_value = "[]"

        get_stale_runs(service_id=10, older_than_seconds=3600)

        call_args = mock_db.query_db.call_args
        assert call_args[0][1] == (10, 3600)


class TestParseDatetime:
    """Tests for _parse_datetime helper function."""

    def test_parse_datetime_iso_with_tz(self):
        """Test parsing ISO format with timezone."""
        from Medic.Core.job_runs import _parse_datetime

        result = _parse_datetime("2026-02-03T10:00:00+00:00")

        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 3

    def test_parse_datetime_iso_without_tz(self):
        """Test parsing ISO format without timezone."""
        from Medic.Core.job_runs import _parse_datetime

        result = _parse_datetime("2026-02-03 10:00:00")

        assert result is not None
        assert result.year == 2026

    def test_parse_datetime_invalid(self):
        """Test parsing invalid datetime string."""
        from Medic.Core.job_runs import _parse_datetime

        result = _parse_datetime("not-a-date")

        assert result is None


class TestParseJobRun:
    """Tests for _parse_job_run helper function."""

    def test_parse_job_run_success(self):
        """Test parsing a valid job run dictionary."""
        from Medic.Core.job_runs import _parse_job_run

        data = {
            "run_id_pk": 1,
            "service_id": 10,
            "run_id": "test-run",
            "started_at": "2026-02-03T10:00:00+00:00",
            "completed_at": None,
            "duration_ms": None,
            "status": "STARTED"
        }

        result = _parse_job_run(data)

        assert result is not None
        assert result.service_id == 10
        assert result.run_id == "test-run"

    def test_parse_job_run_missing_required_field(self):
        """Test parsing with missing required field."""
        from Medic.Core.job_runs import _parse_job_run

        data = {
            "run_id_pk": 1,
            # Missing service_id
            "run_id": "test-run",
            "started_at": "2026-02-03T10:00:00+00:00"
        }

        result = _parse_job_run(data)

        assert result is None


class TestDurationStatisticsDataclass:
    """Tests for DurationStatistics dataclass."""

    def test_duration_stats_initialization_full(self):
        """Test DurationStatistics with all values."""
        from Medic.Core.job_runs import DurationStatistics

        stats = DurationStatistics(
            service_id=10,
            run_count=50,
            avg_duration_ms=1500.5,
            p50_duration_ms=1200,
            p95_duration_ms=2800,
            p99_duration_ms=3500,
            min_duration_ms=500,
            max_duration_ms=4000
        )

        assert stats.service_id == 10
        assert stats.run_count == 50
        assert stats.avg_duration_ms == 1500.5
        assert stats.p50_duration_ms == 1200
        assert stats.p95_duration_ms == 2800
        assert stats.p99_duration_ms == 3500
        assert stats.min_duration_ms == 500
        assert stats.max_duration_ms == 4000

    def test_duration_stats_initialization_empty(self):
        """Test DurationStatistics with only required values."""
        from Medic.Core.job_runs import DurationStatistics

        stats = DurationStatistics(
            service_id=10,
            run_count=3
        )

        assert stats.service_id == 10
        assert stats.run_count == 3
        assert stats.avg_duration_ms is None
        assert stats.p50_duration_ms is None
        assert stats.p95_duration_ms is None
        assert stats.p99_duration_ms is None
        assert stats.min_duration_ms is None
        assert stats.max_duration_ms is None

    def test_duration_stats_to_dict(self):
        """Test DurationStatistics to_dict method."""
        from Medic.Core.job_runs import DurationStatistics

        stats = DurationStatistics(
            service_id=10,
            run_count=50,
            avg_duration_ms=1500.5,
            p50_duration_ms=1200,
            p95_duration_ms=2800,
            p99_duration_ms=3500,
            min_duration_ms=500,
            max_duration_ms=4000
        )

        result = stats.to_dict()

        assert result["service_id"] == 10
        assert result["run_count"] == 50
        assert result["avg_duration_ms"] == 1500.5
        assert result["p50_duration_ms"] == 1200
        assert result["p95_duration_ms"] == 2800
        assert result["p99_duration_ms"] == 3500
        assert result["min_duration_ms"] == 500
        assert result["max_duration_ms"] == 4000

    def test_duration_stats_to_dict_empty(self):
        """Test DurationStatistics to_dict with empty stats."""
        from Medic.Core.job_runs import DurationStatistics

        stats = DurationStatistics(service_id=10, run_count=0)
        result = stats.to_dict()

        assert result["service_id"] == 10
        assert result["run_count"] == 0
        assert result["avg_duration_ms"] is None
        assert result["p50_duration_ms"] is None


class TestPercentile:
    """Tests for _percentile helper function."""

    def test_percentile_empty_data(self):
        """Test percentile with empty data."""
        from Medic.Core.job_runs import _percentile

        result = _percentile([], 50)
        assert result == 0

    def test_percentile_single_value(self):
        """Test percentile with single value."""
        from Medic.Core.job_runs import _percentile

        result = _percentile([1000], 50)
        assert result == 1000

        result = _percentile([1000], 99)
        assert result == 1000

    def test_percentile_two_values(self):
        """Test percentile with two values."""
        from Medic.Core.job_runs import _percentile

        data = [1000, 2000]
        assert _percentile(data, 50) == 1500  # Midpoint

    def test_percentile_p50(self):
        """Test 50th percentile (median)."""
        from Medic.Core.job_runs import _percentile

        # Odd number of values
        data = [100, 200, 300, 400, 500]
        assert _percentile(data, 50) == 300

        # Even number of values
        data = [100, 200, 300, 400]
        assert _percentile(data, 50) == 250

    def test_percentile_p95(self):
        """Test 95th percentile."""
        from Medic.Core.job_runs import _percentile

        # 100 values from 1 to 100
        data = list(range(1, 101))
        result = _percentile(data, 95)
        # p95 should be close to 95
        assert 94 <= result <= 96

    def test_percentile_p99(self):
        """Test 99th percentile."""
        from Medic.Core.job_runs import _percentile

        # 100 values from 1 to 100
        data = list(range(1, 101))
        result = _percentile(data, 99)
        # p99 should be close to 99
        assert 98 <= result <= 100

    def test_percentile_interpolation(self):
        """Test that percentile uses linear interpolation."""
        from Medic.Core.job_runs import _percentile

        # 10 values
        data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        # p25: k = (10-1) * 0.25 = 2.25, interpolates between index 2 and 3
        # Values at indices 2 and 3 are 30 and 40
        # Interpolation: 30 * 0.75 + 40 * 0.25 = 22.5 + 10 = 32.5 -> 32
        result = _percentile(data, 25)
        assert 30 <= result <= 35


class TestGetDurationStatistics:
    """Tests for get_duration_statistics function."""

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_sufficient_data(self, mock_get_runs):
        """Test statistics calculation with sufficient data."""
        from Medic.Core.job_runs import (
            get_duration_statistics, JobRun, DurationStatistics
        )

        # Create 10 mock runs with increasing durations
        mock_runs = []
        for i in range(10):
            mock_runs.append(JobRun(
                run_id_pk=i,
                service_id=10,
                run_id=f"run-{i}",
                started_at=None,
                completed_at=None,
                duration_ms=(i + 1) * 1000,  # 1000, 2000, ... 10000
                status="COMPLETED"
            ))
        mock_get_runs.return_value = mock_runs

        result = get_duration_statistics(service_id=10)

        assert isinstance(result, DurationStatistics)
        assert result.service_id == 10
        assert result.run_count == 10
        assert result.avg_duration_ms == 5500.0  # Average of 1-10 thousand
        assert result.min_duration_ms == 1000
        assert result.max_duration_ms == 10000
        # p50 should be around 5000-6000
        assert 5000 <= result.p50_duration_ms <= 6000

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_insufficient_data(self, mock_get_runs):
        """Test statistics with insufficient data (< 5 runs)."""
        from Medic.Core.job_runs import (
            get_duration_statistics, JobRun, DurationStatistics
        )

        # Only 3 runs - below minimum
        mock_runs = [
            JobRun(
                run_id_pk=i, service_id=10, run_id=f"run-{i}",
                started_at=None, completed_at=None,
                duration_ms=1000, status="COMPLETED"
            )
            for i in range(3)
        ]
        mock_get_runs.return_value = mock_runs

        result = get_duration_statistics(service_id=10)

        assert result.service_id == 10
        assert result.run_count == 3
        assert result.avg_duration_ms is None
        assert result.p50_duration_ms is None
        assert result.p95_duration_ms is None
        assert result.p99_duration_ms is None

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_no_data(self, mock_get_runs):
        """Test statistics with no data."""
        from Medic.Core.job_runs import (
            get_duration_statistics, DurationStatistics
        )

        mock_get_runs.return_value = []

        result = get_duration_statistics(service_id=10)

        assert result.service_id == 10
        assert result.run_count == 0
        assert result.avg_duration_ms is None

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_custom_min_runs(self, mock_get_runs):
        """Test statistics with custom min_runs threshold."""
        from Medic.Core.job_runs import (
            get_duration_statistics, JobRun
        )

        # 3 runs - meets custom threshold of 2
        mock_runs = [
            JobRun(
                run_id_pk=i, service_id=10, run_id=f"run-{i}",
                started_at=None, completed_at=None,
                duration_ms=1000 * (i + 1), status="COMPLETED"
            )
            for i in range(3)
        ]
        mock_get_runs.return_value = mock_runs

        result = get_duration_statistics(service_id=10, min_runs=2)

        assert result.run_count == 3
        assert result.avg_duration_ms is not None
        assert result.p50_duration_ms == 2000

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_filters_null_durations(self, mock_get_runs):
        """Test that null durations are filtered out."""
        from Medic.Core.job_runs import (
            get_duration_statistics, JobRun
        )

        # 7 runs but 2 have null duration
        mock_runs = []
        for i in range(7):
            duration = (i + 1) * 1000 if i < 5 else None
            mock_runs.append(JobRun(
                run_id_pk=i, service_id=10, run_id=f"run-{i}",
                started_at=None, completed_at=None,
                duration_ms=duration, status="COMPLETED"
            ))
        mock_get_runs.return_value = mock_runs

        result = get_duration_statistics(service_id=10)

        # Only 5 runs have valid durations
        assert result.run_count == 5

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_exactly_5_runs(self, mock_get_runs):
        """Test statistics with exactly 5 runs (minimum threshold)."""
        from Medic.Core.job_runs import (
            get_duration_statistics, JobRun
        )

        mock_runs = [
            JobRun(
                run_id_pk=i, service_id=10, run_id=f"run-{i}",
                started_at=None, completed_at=None,
                duration_ms=1000 * (i + 1), status="COMPLETED"
            )
            for i in range(5)
        ]
        mock_get_runs.return_value = mock_runs

        result = get_duration_statistics(service_id=10)

        assert result.run_count == 5
        assert result.avg_duration_ms == 3000.0  # (1+2+3+4+5)*1000/5
        assert result.min_duration_ms == 1000
        assert result.max_duration_ms == 5000

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_uses_last_100_runs(self, mock_get_runs):
        """Test that statistics use at most 100 runs by default."""
        from Medic.Core.job_runs import get_duration_statistics

        mock_get_runs.return_value = []

        get_duration_statistics(service_id=10)

        mock_get_runs.assert_called_once_with(10, limit=100)

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_custom_max_runs(self, mock_get_runs):
        """Test statistics with custom max_runs."""
        from Medic.Core.job_runs import get_duration_statistics

        mock_get_runs.return_value = []

        get_duration_statistics(service_id=10, max_runs=50)

        mock_get_runs.assert_called_once_with(10, limit=50)

    @patch("Medic.Core.job_runs.get_completed_runs_for_service")
    def test_get_duration_statistics_filters_negative_durations(
        self, mock_get_runs
    ):
        """Test that negative durations are filtered out."""
        from Medic.Core.job_runs import get_duration_statistics, JobRun

        # 6 runs but 1 has negative duration
        mock_runs = []
        for i in range(6):
            duration = (i + 1) * 1000 if i < 5 else -1000
            mock_runs.append(JobRun(
                run_id_pk=i, service_id=10, run_id=f"run-{i}",
                started_at=None, completed_at=None,
                duration_ms=duration, status="COMPLETED"
            ))
        mock_get_runs.return_value = mock_runs

        result = get_duration_statistics(service_id=10)

        # Only 5 runs have valid durations (positive)
        assert result.run_count == 5
