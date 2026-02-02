"""Integration tests for Medic API."""
import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for the full API flow."""

    @patch("Medic.Core.database.connect_db")
    def test_full_heartbeat_flow(self, mock_connect, app, mock_env_vars):
        """Test the full heartbeat registration and posting flow."""
        client = app.test_client()

        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Step 1: Register a service
        mock_cursor.fetchall.return_value = [(0,)]  # Not registered
        response = client.post(
            "/service",
            data=json.dumps({
                "heartbeat_name": "integration-test-hb",
                "service_name": "integration-test-service",
                "alert_interval": 5,
                "team": "platform"
            }),
            content_type="application/json"
        )
        assert response.status_code == 201

        # Step 2: Post a heartbeat
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [
            ("service_id",), ("heartbeat_name",), ("active",),
            ("alert_interval",), ("team",), ("priority",)
        ]
        # Return service info for heartbeat lookup
        mock_cursor.fetchall.return_value = [(1, "integration-test-hb", 1, 5, "platform", "p3")]

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([{
                "service_id": 1,
                "heartbeat_name": "integration-test-hb",
                "active": 1
            }])

            with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                mock_add.return_value = True
                with patch("Medic.Core.routes.hbeat.Heartbeat"):
                    response = client.post(
                        "/heartbeat",
                        data=json.dumps({
                            "heartbeat_name": "integration-test-hb",
                            "status": "UP"
                        }),
                        content_type="application/json"
                    )
                    assert response.status_code == 201

    @patch("Medic.Core.database.connect_db")
    def test_service_update_flow(self, mock_connect, app, mock_env_vars):
        """Test service update operations."""
        client = app.test_client()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            # Service exists
            mock_query.return_value = json.dumps([{"service_id": 1}])

            with patch("Medic.Core.routes.db.insert_db") as mock_insert:
                mock_insert.return_value = True

                # Mute the service
                response = client.post(
                    "/service/test-heartbeat",
                    data=json.dumps({"muted": 1}),
                    content_type="application/json"
                )
                assert response.status_code == 200

                # Update priority
                response = client.post(
                    "/service/test-heartbeat",
                    data=json.dumps({"priority": "p1"}),
                    content_type="application/json"
                )
                assert response.status_code == 200


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @patch("Medic.Core.database.connect_db")
    def test_parameterized_queries_prevent_injection(self, mock_connect, mock_env_vars):
        """Test that parameterized queries properly escape dangerous input."""
        from Medic.Core.database import query_db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = [("id",)]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Attempt SQL injection
        malicious_input = "'; DROP TABLE services; --"
        query_db(
            "SELECT * FROM services WHERE heartbeat_name = %s",
            (malicious_input,),
            show_columns=True
        )

        # Verify the dangerous input was passed as a parameter, not interpolated
        call_args = mock_cursor.execute.call_args
        assert call_args[0][0] == "SELECT * FROM services WHERE heartbeat_name = %s"
        assert call_args[0][1] == (malicious_input,)
        # The actual query string should NOT contain the malicious content
        assert "DROP TABLE" not in call_args[0][0]
