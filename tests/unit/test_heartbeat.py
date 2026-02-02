"""Unit tests for heartbeat module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


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
