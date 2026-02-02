"""Unit tests for monitor module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestMonitorConnectDb:
    """Tests for monitor database connection."""

    @patch("psycopg2.connect")
    def test_connect_db_success(self, mock_connect, mock_env_vars):
        """Test successful database connection in monitor."""
        from Medic.Worker.monitor import connect_db

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = connect_db()

        assert result == mock_conn

    @patch("psycopg2.connect")
    def test_connect_db_failure(self, mock_connect, mock_env_vars):
        """Test database connection failure."""
        from Medic.Worker.monitor import connect_db
        import psycopg2

        mock_connect.side_effect = psycopg2.Error("Connection failed")

        with pytest.raises(ConnectionError):
            connect_db()


class TestToJson:
    """Tests for to_json helper function."""

    def test_to_json_conversion(self):
        """Test row to JSON conversion."""
        from Medic.Worker.monitor import to_json

        rows = [(1, "test", "UP"), (2, "test2", "DOWN")]
        columns = ["id", "name", "status"]

        result = to_json(rows, columns)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["name"] == "test"
        assert result[1]["status"] == "DOWN"


class TestQueryDb:
    """Tests for monitor query_db function."""

    @patch("Medic.Worker.monitor.connect_db")
    def test_query_db_with_params(self, mock_connect, mock_env_vars):
        """Test parameterized query execution."""
        from Medic.Worker.monitor import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, "test")]
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = query_db(
            "SELECT * FROM test WHERE id = %s",
            (1,),
            show_columns=True
        )

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM test WHERE id = %s",
            (1,)
        )
        assert len(result) == 1

    @patch("Medic.Worker.monitor.connect_db")
    def test_query_db_closes_resources(self, mock_connect, mock_env_vars):
        """Test that resources are properly closed."""
        from Medic.Worker.monitor import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        query_db("SELECT 1")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


class TestInsertDb:
    """Tests for monitor insert_db function."""

    @patch("Medic.Worker.monitor.connect_db")
    def test_insert_db_with_params(self, mock_connect, mock_env_vars):
        """Test parameterized insert execution."""
        from Medic.Worker.monitor import insert_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = insert_db(
            "INSERT INTO test VALUES (%s, %s)",
            ("value1", "value2")
        )

        assert result is True
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO test VALUES (%s, %s)",
            ("value1", "value2")
        )
        mock_conn.commit.assert_called_once()


class TestSendAlert:
    """Tests for sendAlert function."""

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_send_alert_new_alert(self, mock_query, mock_insert, mock_pd, mock_slack, mock_env_vars):
        """Test sending a new alert."""
        from Medic.Worker.monitor import sendAlert

        mock_query.return_value = []  # No existing alert
        mock_insert.return_value = True
        mock_pd.create_alert.return_value = "medic-test-key"

        sendAlert(
            service_id=1,
            service_name="test-service",
            heartbeat_name="test-heartbeat",
            last_seen="2024-01-01 00:00:00",
            interval=5,
            team="platform",
            priority="p2",
            muted=0,
            current_time="2024-01-01 00:05:00"
        )

        mock_pd.create_alert.assert_called_once()
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_send_alert_muted(self, mock_query, mock_insert, mock_pd, mock_slack, mock_env_vars):
        """Test that muted alerts don't send notifications."""
        from Medic.Worker.monitor import sendAlert

        mock_query.return_value = []
        mock_insert.return_value = True

        sendAlert(
            service_id=1,
            service_name="test-service",
            heartbeat_name="test-heartbeat",
            last_seen="2024-01-01 00:00:00",
            interval=5,
            team="platform",
            priority="p2",
            muted=1,
            current_time="2024-01-01 00:05:00"
        )

        mock_pd.create_alert.assert_not_called()
        mock_slack.send_message.assert_not_called()


class TestCloseAlert:
    """Tests for closeAlert function."""

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_close_alert_success(self, mock_query, mock_insert, mock_pd, mock_slack, mock_env_vars):
        """Test closing an alert."""
        from Medic.Worker.monitor import closeAlert

        mock_query.return_value = [(1, "test", 1, 1, "medic-test-key", 5)]
        mock_insert.return_value = True

        closeAlert(
            heartbeat_name="test-heartbeat",
            service_name="test-service",
            service_id=1,
            last_seen="2024-01-01 00:05:00",
            team="platform",
            muted=0,
            current_time="2024-01-01 00:10:00"
        )

        mock_pd.close_alert.assert_called_once_with("medic-test-key")
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_close_alert_no_pd_key(self, mock_query, mock_insert, mock_pd, mock_slack, mock_env_vars):
        """Test closing alert without PagerDuty key."""
        from Medic.Worker.monitor import closeAlert

        mock_query.return_value = [(1, "test", 1, 1, None, 5)]
        mock_insert.return_value = True

        closeAlert(
            heartbeat_name="test-heartbeat",
            service_name="test-service",
            service_id=1,
            last_seen="2024-01-01 00:05:00",
            team="platform",
            muted=0,
            current_time="2024-01-01 00:10:00"
        )

        mock_pd.close_alert.assert_not_called()


class TestColorCode:
    """Tests for color_code function."""

    def test_color_code_mapping(self):
        """Test priority to color mapping."""
        from Medic.Worker.monitor import color_code

        assert color_code("p1") == "#F35A00"
        assert color_code("p2") == "#e9a820"
        assert color_code("p3") == "#e9a820"
        assert color_code("unknown") == "#F35A00"
