"""Unit tests for monitor module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


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


class TestMaintenanceWindowSuppression:
    """Tests for maintenance window alert suppression."""

    @patch("Medic.Worker.monitor.get_active_maintenance_window_for_service")
    @patch("Medic.Worker.monitor.is_service_in_maintenance")
    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", True)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_suppressed_during_maintenance(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_in_maintenance,
        mock_get_window,
        mock_env_vars
    ):
        """Test that alerts are suppressed when service is in maintenance."""
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Mock maintenance window functions
        mock_in_maintenance.return_value = True
        mock_window = MagicMock()
        mock_window.name = "Weekly DB Maintenance"
        mock_get_window.return_value = mock_window

        # Setup service data - threshold 2, but only 1 heartbeat (should alert)
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None
            }],
            # Second query: heartbeat count
            [(datetime.now(), 1)],  # Only 1 heartbeat, below threshold
        ]

        queryForNoHeartbeat()

        # Maintenance window check should have been called
        mock_in_maintenance.assert_called_once_with(1)

        # Alert should NOT have been sent due to maintenance
        mock_pd.create_alert.assert_not_called()
        mock_slack.send_message.assert_not_called()

    @patch("Medic.Worker.monitor.get_active_maintenance_window_for_service")
    @patch("Medic.Worker.monitor.is_service_in_maintenance")
    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", True)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_sent_when_not_in_maintenance(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_in_maintenance,
        mock_get_window,
        mock_env_vars
    ):
        """Test that alerts are sent when service is NOT in maintenance."""
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Mock maintenance window - not in maintenance
        mock_in_maintenance.return_value = False

        # Setup service data
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None
            }],
            # Second query: heartbeat count
            [(datetime.now(), 1)],  # Only 1 heartbeat, below threshold
            # Third query: check for existing alert
            [],
        ]
        mock_insert.return_value = True
        mock_pd.create_alert.return_value = "test-dedup-key"

        queryForNoHeartbeat()

        # Maintenance window check should have been called
        mock_in_maintenance.assert_called_once_with(1)

        # Alert SHOULD have been sent since not in maintenance
        mock_pd.create_alert.assert_called_once()
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_sent_when_maintenance_module_unavailable(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test alerts are sent when maintenance module is not available."""
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Setup service data
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None
            }],
            # Second query: heartbeat count
            [(datetime.now(), 1)],  # Only 1 heartbeat, below threshold
            # Third query: check for existing alert
            [],
        ]
        mock_insert.return_value = True
        mock_pd.create_alert.return_value = "test-dedup-key"

        queryForNoHeartbeat()

        # Alert SHOULD have been sent since maintenance module unavailable
        mock_pd.create_alert.assert_called_once()
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.get_active_maintenance_window_for_service")
    @patch("Medic.Worker.monitor.is_service_in_maintenance")
    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", True)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_suppressed_logs_maintenance_window_name(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_in_maintenance,
        mock_get_window,
        mock_env_vars,
        caplog
    ):
        """Test that suppressed alert logs the maintenance window name."""
        import logging
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Mock maintenance window functions
        mock_in_maintenance.return_value = True
        mock_window = MagicMock()
        mock_window.name = "Database Upgrade Window"
        mock_get_window.return_value = mock_window

        # Setup service data
        mock_query.side_effect = [
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None
            }],
            [(datetime.now(), 1)],
        ]

        with caplog.at_level(logging.INFO):
            queryForNoHeartbeat()

        # Check that log message contains the maintenance window name
        log_messages = [r.message for r in caplog.records]
        assert any(
            "Alert suppressed" in msg and "Database Upgrade Window" in msg
            for msg in log_messages
        )

    @patch("Medic.Worker.monitor.get_active_maintenance_window_for_service")
    @patch("Medic.Worker.monitor.is_service_in_maintenance")
    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", True)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_recovery_alerts_still_sent_during_maintenance(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_in_maintenance,
        mock_get_window,
        mock_env_vars
    ):
        """Test that recovery alerts are sent even during maintenance."""
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Service in maintenance but recovering (was down, now healthy)
        mock_in_maintenance.return_value = True
        mock_window = MagicMock()
        mock_window.name = "Weekly Maintenance"
        mock_get_window.return_value = mock_window

        # Setup service data - service is down but heartbeat is healthy now
        mock_query.side_effect = [
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 1,  # Service was down
                "runbook": None
            }],
            # Heartbeat count now meets threshold
            [(datetime.now(), 3)],  # 3 heartbeats, above threshold of 2
            # Query for active alert to close
            [(1, "test", 1, 1, "pd-key", 5)],
        ]
        mock_insert.return_value = True

        queryForNoHeartbeat()

        # Recovery notifications SHOULD be sent (maintenance doesn't suppress)
        mock_slack.send_message.assert_called_once()
        mock_pd.close_alert.assert_called_once_with("pd-key")


class TestGracePeriod:
    """Tests for grace period alert delay functionality."""

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_delayed_during_grace_period(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars,
        caplog
    ):
        """Test that alerts are delayed when grace period hasn't passed."""
        import logging
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 3 minutes ago (within 5 min interval + 120s grace)
        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=3)

        # Setup service data with 120 second grace period
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,  # 5 minutes
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "grace_period_seconds": 120  # 2 minute grace period
            }],
            # Second query: heartbeat count - below threshold
            [(last_hbeat_time, 1)],
        ]

        with caplog.at_level(logging.INFO):
            queryForNoHeartbeat()

        # Alert should NOT be sent - still within grace period
        mock_pd.create_alert.assert_not_called()
        mock_slack.send_message.assert_not_called()

        # Check log message indicates grace period delay
        log_messages = [r.message for r in caplog.records]
        assert any("grace period" in msg.lower() for msg in log_messages)

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_sent_after_grace_period_expired(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test that alerts are sent once grace period has passed."""
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 10 minutes ago (5 min interval + 120s grace = 7min)
        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=10)

        # Setup service data with 120 second grace period
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,  # 5 minutes
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "grace_period_seconds": 120  # 2 minute grace period
            }],
            # Second query: heartbeat count - below threshold
            [(last_hbeat_time, 1)],
            # Third query: check for existing alert
            [],
        ]
        mock_insert.return_value = True
        mock_pd.create_alert.return_value = "test-dedup-key"

        queryForNoHeartbeat()

        # Alert SHOULD be sent - grace period has passed
        mock_pd.create_alert.assert_called_once()
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_sent_immediately_when_no_grace_period(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test that alerts are sent immediately when grace period is 0."""
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 6 minutes ago (just past 5 min interval)
        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=6)

        # Setup service data with no grace period
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,  # 5 minutes
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "grace_period_seconds": 0  # No grace period
            }],
            # Second query: heartbeat count - below threshold
            [(last_hbeat_time, 1)],
            # Third query: check for existing alert
            [],
        ]
        mock_insert.return_value = True
        mock_pd.create_alert.return_value = "test-dedup-key"

        queryForNoHeartbeat()

        # Alert SHOULD be sent immediately (no grace period)
        mock_pd.create_alert.assert_called_once()
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_alert_sent_when_grace_period_is_none(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test that alerts are sent immediately when grace period is None."""
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 6 minutes ago
        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=6)

        # Setup service data with grace_period_seconds not present (legacy)
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None
                # grace_period_seconds not included (legacy data)
            }],
            # Second query: heartbeat count - below threshold
            [(last_hbeat_time, 1)],
            # Third query: check for existing alert
            [],
        ]
        mock_insert.return_value = True
        mock_pd.create_alert.return_value = "test-dedup-key"

        queryForNoHeartbeat()

        # Alert SHOULD be sent (no grace period = immediate)
        mock_pd.create_alert.assert_called_once()
        mock_slack.send_message.assert_called_once()

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_grace_period_with_naive_datetime(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test grace period works with naive (non-timezone-aware) datetime."""
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 3 minutes ago (naive datetime)
        last_hbeat_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3)

        # Setup service data with grace period
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,  # 5 minutes
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "grace_period_seconds": 120
            }],
            # Second query: heartbeat count - naive datetime
            [(last_hbeat_time, 1)],
        ]

        # Should not raise exception due to timezone handling
        queryForNoHeartbeat()

        # Alert should NOT be sent - still within grace period
        mock_pd.create_alert.assert_not_called()
        mock_slack.send_message.assert_not_called()

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_grace_period_with_large_value(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test grace period with a large value (e.g., 1 hour)."""
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 30 minutes ago
        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=30)

        # Setup service data with 1 hour grace period
        mock_query.side_effect = [
            # First query: services
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,  # 5 minutes
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "grace_period_seconds": 3600  # 1 hour grace period
            }],
            # Second query: heartbeat count - below threshold
            [(last_hbeat_time, 1)],
        ]

        queryForNoHeartbeat()

        # Alert should NOT be sent - still within 1 hour grace period
        mock_pd.create_alert.assert_not_called()
        mock_slack.send_message.assert_not_called()

    @patch("Medic.Worker.monitor.get_active_maintenance_window_for_service")
    @patch("Medic.Worker.monitor.is_service_in_maintenance")
    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", True)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_grace_period_checked_before_maintenance(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_in_maintenance,
        mock_get_window,
        mock_env_vars
    ):
        """Test that grace period is checked before maintenance window check."""
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Last heartbeat was 3 minutes ago (within grace period)
        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=3)

        # Service would be in maintenance, but grace period should prevent
        # the maintenance check from even being reached
        mock_in_maintenance.return_value = True

        mock_query.side_effect = [
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 0,
                "runbook": None,
                "grace_period_seconds": 120
            }],
            [(last_hbeat_time, 1)],
        ]

        queryForNoHeartbeat()

        # Maintenance check should NOT be called (grace period handled first)
        mock_in_maintenance.assert_not_called()

    @patch("Medic.Worker.monitor.MAINTENANCE_WINDOWS_AVAILABLE", False)
    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.insert_db")
    @patch("Medic.Worker.monitor.query_db")
    def test_grace_period_does_not_affect_recovery(
        self,
        mock_query,
        mock_insert,
        mock_pd,
        mock_slack,
        mock_env_vars
    ):
        """Test that grace period doesn't affect recovery alerts."""
        import pytz
        from datetime import timedelta
        from Medic.Worker.monitor import queryForNoHeartbeat

        now_utc = datetime.now(pytz.UTC)
        last_hbeat_time = now_utc - timedelta(minutes=1)

        # Service was down but now healthy
        mock_query.side_effect = [
            [{
                "service_id": 1,
                "heartbeat_name": "test-heartbeat",
                "service_name": "test-service",
                "alert_interval": 5,
                "threshold": 2,
                "team": "platform",
                "priority": "p2",
                "muted": 0,
                "down": 1,  # Was down
                "runbook": None,
                "grace_period_seconds": 3600  # Large grace period
            }],
            # Heartbeat count now meets threshold
            [(last_hbeat_time, 5)],  # Above threshold
            # Query for active alert to close
            [(1, "test", 1, 1, "pd-key", 5)],
        ]
        mock_insert.return_value = True

        queryForNoHeartbeat()

        # Recovery alert should be sent regardless of grace period
        mock_slack.send_message.assert_called_once()
        mock_pd.close_alert.assert_called_once_with("pd-key")
