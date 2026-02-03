"""Unit tests for heartbeat module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestHeartbeatStatus:
    """Tests for HeartbeatStatus enum."""

    def test_status_values(self):
        """Test that all status values are defined."""
        from Medic.Helpers.heartbeat import HeartbeatStatus

        assert HeartbeatStatus.UP.value == "UP"
        assert HeartbeatStatus.DOWN.value == "DOWN"
        assert HeartbeatStatus.STARTED.value == "STARTED"
        assert HeartbeatStatus.COMPLETED.value == "COMPLETED"
        assert HeartbeatStatus.FAILED.value == "FAILED"

    def test_is_valid_with_valid_status(self):
        """Test is_valid returns True for valid statuses."""
        from Medic.Helpers.heartbeat import HeartbeatStatus

        assert HeartbeatStatus.is_valid("UP") is True
        assert HeartbeatStatus.is_valid("DOWN") is True
        assert HeartbeatStatus.is_valid("STARTED") is True
        assert HeartbeatStatus.is_valid("COMPLETED") is True
        assert HeartbeatStatus.is_valid("FAILED") is True

    def test_is_valid_with_invalid_status(self):
        """Test is_valid returns False for invalid statuses."""
        from Medic.Helpers.heartbeat import HeartbeatStatus

        assert HeartbeatStatus.is_valid("INVALID") is False
        assert HeartbeatStatus.is_valid("up") is False  # Case sensitive
        assert HeartbeatStatus.is_valid("") is False

    def test_is_job_status_with_job_statuses(self):
        """Test is_job_status returns True for job-related statuses."""
        from Medic.Helpers.heartbeat import HeartbeatStatus

        assert HeartbeatStatus.is_job_status("STARTED") is True
        assert HeartbeatStatus.is_job_status("COMPLETED") is True
        assert HeartbeatStatus.is_job_status("FAILED") is True

    def test_is_job_status_with_non_job_statuses(self):
        """Test is_job_status returns False for non-job statuses."""
        from Medic.Helpers.heartbeat import HeartbeatStatus

        assert HeartbeatStatus.is_job_status("UP") is False
        assert HeartbeatStatus.is_job_status("DOWN") is False

    def test_status_is_string_enum(self):
        """Test that HeartbeatStatus can be used as a string."""
        from Medic.Helpers.heartbeat import HeartbeatStatus

        # Should be able to compare directly with strings
        assert HeartbeatStatus.UP == "UP"
        assert HeartbeatStatus.STARTED == "STARTED"


class TestHeartbeat:
    """Tests for Heartbeat class."""

    def test_heartbeat_initialization(self):
        """Test Heartbeat object creation."""
        from Medic.Helpers.heartbeat import Heartbeat

        hb = Heartbeat(s_id=1, name="test-heartbeat", current_status="UP")

        assert hb.service_id == 1
        assert hb.heartbeat_name == "test-heartbeat"
        assert hb.status == "UP"
        assert hb.time is not None
        assert hb.run_id is None  # Default is None

    def test_heartbeat_with_run_id(self):
        """Test Heartbeat object creation with run_id."""
        from Medic.Helpers.heartbeat import Heartbeat

        hb = Heartbeat(
            s_id=1,
            name="test-job",
            current_status="STARTED",
            run_id="job-run-12345"
        )

        assert hb.service_id == 1
        assert hb.heartbeat_name == "test-job"
        assert hb.status == "STARTED"
        assert hb.run_id == "job-run-12345"

    def test_heartbeat_time_format(self):
        """Test that heartbeat time is in correct format."""
        from Medic.Helpers.heartbeat import Heartbeat

        hb = Heartbeat(s_id=1, name="test-heartbeat", current_status="UP")

        # Should be in format: YYYY-MM-DD HH:MM:SS TZ
        assert len(hb.time.split()) >= 2


class TestAddHeartbeat:
    """Tests for addHeartbeat function."""

    @patch("Medic.Helpers.heartbeat.db")
    def test_add_heartbeat_success(self, mock_db):
        """Test successful heartbeat insertion."""
        from Medic.Helpers.heartbeat import Heartbeat, addHeartbeat

        mock_db.insert_db.return_value = True

        hb = Heartbeat(s_id=1, name="test-heartbeat", current_status="UP")
        result = addHeartbeat(hb)

        assert result is True
        mock_db.insert_db.assert_called_once()
        # Verify parameterized query was used
        call_args = mock_db.insert_db.call_args
        assert "%s" in call_args[0][0]  # Query contains placeholders
        assert len(call_args[0][1]) == 3  # Three parameters

    @patch("Medic.Helpers.heartbeat.db")
    def test_add_heartbeat_failure(self, mock_db):
        """Test heartbeat insertion failure."""
        from Medic.Helpers.heartbeat import Heartbeat, addHeartbeat

        mock_db.insert_db.return_value = False

        hb = Heartbeat(s_id=1, name="test-heartbeat", current_status="UP")
        result = addHeartbeat(hb)

        assert result is False

    @patch("Medic.Helpers.heartbeat.db")
    def test_add_heartbeat_with_run_id(self, mock_db):
        """Test heartbeat insertion with run_id."""
        from Medic.Helpers.heartbeat import Heartbeat, addHeartbeat

        mock_db.insert_db.return_value = True

        hb = Heartbeat(
            s_id=1,
            name="test-job",
            current_status="STARTED",
            run_id="job-run-12345"
        )
        result = addHeartbeat(hb)

        assert result is True
        mock_db.insert_db.assert_called_once()
        call_args = mock_db.insert_db.call_args
        assert "run_id" in call_args[0][0]  # Query includes run_id
        assert len(call_args[0][1]) == 4  # Four parameters (including run_id)
        assert call_args[0][1][3] == "job-run-12345"

    @patch("Medic.Helpers.heartbeat.db")
    def test_add_heartbeat_without_run_id_uses_three_params(self, mock_db):
        """Test heartbeat without run_id uses 3-param query."""
        from Medic.Helpers.heartbeat import Heartbeat, addHeartbeat

        mock_db.insert_db.return_value = True

        hb = Heartbeat(s_id=1, name="test-heartbeat", current_status="UP")
        result = addHeartbeat(hb)

        assert result is True
        call_args = mock_db.insert_db.call_args
        assert "run_id" not in call_args[0][0]  # Query doesn't include run_id
        assert len(call_args[0][1]) == 3  # Three parameters


class TestQueryHeartbeats:
    """Tests for queryHeartbeats function."""

    @patch("Medic.Helpers.heartbeat.db")
    def test_query_heartbeats_no_time_range(self, mock_db):
        """Test querying heartbeats without time range."""
        from Medic.Helpers.heartbeat import queryHeartbeats

        mock_db.query_db.return_value = "[]"

        result = queryHeartbeats("test-heartbeat")

        mock_db.query_db.assert_called_once()
        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]
        assert call_args[0][1] == ("test-heartbeat",)

    @patch("Medic.Helpers.heartbeat.db")
    def test_query_heartbeats_with_time_range(self, mock_db):
        """Test querying heartbeats with time range."""
        from Medic.Helpers.heartbeat import queryHeartbeats

        mock_db.query_db.return_value = "[]"

        result = queryHeartbeats(
            "test-heartbeat",
            starttime="2024-01-01 00:00:00",
            endtime="2024-01-02 00:00:00"
        )

        mock_db.query_db.assert_called_once()
        call_args = mock_db.query_db.call_args
        assert len(call_args[0][1]) == 3  # h_name, starttime, endtime

    def test_query_heartbeats_missing_start_time(self):
        """Test error when only end time provided."""
        from Medic.Helpers.heartbeat import queryHeartbeats

        result = queryHeartbeats("test-heartbeat", endtime="2024-01-02 00:00:00")
        assert "end_time" in result

    def test_query_heartbeats_missing_end_time(self):
        """Test error when only start time provided."""
        from Medic.Helpers.heartbeat import queryHeartbeats

        result = queryHeartbeats("test-heartbeat", starttime="2024-01-01 00:00:00")
        assert "start_time" in result


class TestQueryLastHeartbeat:
    """Tests for queryLastHeartbeat function."""

    @patch("Medic.Helpers.heartbeat.db")
    def test_query_last_heartbeat(self, mock_db):
        """Test querying most recent heartbeat."""
        from Medic.Helpers.heartbeat import queryLastHeartbeat

        mock_db.query_db.return_value = "[]"

        result = queryLastHeartbeat("test-heartbeat")

        mock_db.query_db.assert_called_once()
        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]
        assert call_args[0][1] == ("test-heartbeat",)

    @patch("Medic.Helpers.heartbeat.db")
    def test_query_last_heartbeat_includes_run_id(self, mock_db):
        """Test that queryLastHeartbeat includes run_id in results."""
        from Medic.Helpers.heartbeat import queryLastHeartbeat

        mock_db.query_db.return_value = "[]"

        queryLastHeartbeat("test-heartbeat")

        call_args = mock_db.query_db.call_args
        # Query should include run_id column
        assert "run_id" in call_args[0][0]


class TestQueryHeartbeatsByRunId:
    """Tests for queryHeartbeatsByRunId function."""

    @patch("Medic.Helpers.heartbeat.db")
    def test_query_heartbeats_by_run_id(self, mock_db):
        """Test querying heartbeats by run_id."""
        from Medic.Helpers.heartbeat import queryHeartbeatsByRunId

        mock_db.query_db.return_value = "[]"

        result = queryHeartbeatsByRunId("job-run-12345")

        mock_db.query_db.assert_called_once()
        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]
        assert call_args[0][1] == ("job-run-12345",)
        # Query should filter by run_id
        assert "run_id = %s" in call_args[0][0]
        # Results should be ordered ASC (start before complete)
        assert "ORDER BY time ASC" in call_args[0][0]

    @patch("Medic.Helpers.heartbeat.db")
    def test_query_heartbeats_by_run_id_returns_results(self, mock_db):
        """Test that queryHeartbeatsByRunId returns correlated events."""
        from Medic.Helpers.heartbeat import queryHeartbeatsByRunId

        mock_db.query_db.return_value = '[{"status": "STARTED"}, {"status": "COMPLETED"}]'

        result = queryHeartbeatsByRunId("job-run-12345")

        assert result == '[{"status": "STARTED"}, {"status": "COMPLETED"}]'
