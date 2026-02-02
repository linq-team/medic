"""Integration tests for worker with database."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestWorkerIntegration:
    """Integration tests for worker monitoring loop."""

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.connect_db")
    def test_monitoring_loop_healthy_service(self, mock_connect, mock_pd, mock_slack, mock_env_vars):
        """Test monitoring loop with healthy services."""
        from Medic.Worker.monitor import queryForNoHeartbeat

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock service query - active service with recent heartbeat
        mock_cursor.fetchall.side_effect = [
            # First call: get services
            [(1, "test-hb", "test-service", 1, 5, 1, "platform", "p2", 0, 0)],
            # Second call: get recent heartbeats
            [("2024-01-01 00:00:00+00", 2)],  # time, count
        ]
        mock_cursor.description = [
            ("service_id",), ("heartbeat_name",), ("service_name",),
            ("active",), ("alert_interval",), ("threshold",),
            ("team",), ("priority",), ("muted",), ("down",)
        ]

        with patch("Medic.Worker.monitor.query_db") as mock_query:
            # Service is healthy - has enough heartbeats
            mock_query.side_effect = [
                [{"service_id": 1, "heartbeat_name": "test-hb", "service_name": "test-service",
                  "active": 1, "alert_interval": 5, "threshold": 1, "team": "platform",
                  "priority": "p2", "muted": 0, "down": 0}],
                [("2024-01-01 00:00:00", 2)]  # Has heartbeats
            ]

            queryForNoHeartbeat()

            # Should not send alerts for healthy service
            mock_pd.create_alert.assert_not_called()

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    @patch("Medic.Worker.monitor.connect_db")
    def test_monitoring_loop_unhealthy_service(self, mock_connect, mock_pd, mock_slack, mock_env_vars):
        """Test monitoring loop detecting unhealthy service."""
        from Medic.Worker.monitor import queryForNoHeartbeat

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        with patch("Medic.Worker.monitor.query_db") as mock_query:
            with patch("Medic.Worker.monitor.sendAlert") as mock_send_alert:
                # Service is unhealthy - no heartbeats
                mock_query.side_effect = [
                    [{"service_id": 1, "heartbeat_name": "test-hb", "service_name": "test-service",
                      "active": 1, "alert_interval": 5, "threshold": 1, "team": "platform",
                      "priority": "p2", "muted": 0, "down": 0}],
                    [("2024-01-01 00:00:00", 0)]  # Zero heartbeats - unhealthy
                ]

                queryForNoHeartbeat()

                # Should trigger alert
                mock_send_alert.assert_called_once()

    @patch("Medic.Worker.monitor.slack")
    @patch("Medic.Worker.monitor.pagerduty")
    def test_alert_and_recovery_cycle(self, mock_pd, mock_slack, mock_env_vars, mock_db_connection):
        """Test full alert and recovery cycle."""
        from Medic.Worker.monitor import sendAlert, closeAlert

        mock_pd.create_alert.return_value = "medic-test-key"
        mock_pd.close_alert.return_value = True

        with patch("Medic.Worker.monitor.query_db") as mock_query:
            with patch("Medic.Worker.monitor.insert_db") as mock_insert:
                mock_query.return_value = []
                mock_insert.return_value = True

                # Send alert
                sendAlert(
                    service_id=1,
                    service_name="test-service",
                    heartbeat_name="test-hb",
                    last_seen="2024-01-01 00:00:00",
                    interval=5,
                    team="platform",
                    priority="p2",
                    muted=0,
                    current_time="2024-01-01 00:10:00"
                )

                mock_pd.create_alert.assert_called_once()
                mock_slack.send_message.assert_called()

                # Reset mocks
                mock_pd.create_alert.reset_mock()
                mock_slack.send_message.reset_mock()

                # Close alert
                mock_query.return_value = [(1, "test", 1, 1, "medic-test-key", 5)]

                closeAlert(
                    heartbeat_name="test-hb",
                    service_name="test-service",
                    service_id=1,
                    last_seen="2024-01-01 00:15:00",
                    team="platform",
                    muted=0,
                    current_time="2024-01-01 00:15:00"
                )

                mock_pd.close_alert.assert_called_once_with("medic-test-key")
                mock_slack.send_message.assert_called()
