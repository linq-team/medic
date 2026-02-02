"""End-to-end tests for Medic service."""
import pytest
import json
import os
from unittest.mock import patch, MagicMock


@pytest.mark.e2e
@pytest.mark.skipif(
    not os.environ.get("E2E_TEST_URL"),
    reason="E2E_TEST_URL not set - skipping end-to-end tests"
)
class TestEndToEndWithRealService:
    """
    End-to-end tests with a real Medic service.

    These tests require a running Medic instance.
    Set E2E_TEST_URL environment variable to run these tests.

    Example:
        export E2E_TEST_URL=http://localhost:5000
    """

    @pytest.fixture
    def base_url(self):
        return os.environ.get("E2E_TEST_URL")

    def test_full_service_lifecycle(self, base_url):
        """Test complete service lifecycle: register -> heartbeat -> alert -> resolve."""
        import requests
        import time

        # Step 1: Register a service
        register_response = requests.post(
            f"{base_url}/service",
            json={
                "heartbeat_name": "e2e-test-heartbeat",
                "service_name": "e2e-test-service",
                "alert_interval": 1,
                "threshold": 1,
                "team": "platform",
                "priority": "p3"
            }
        )
        assert register_response.status_code in [200, 201]

        # Step 2: Post heartbeats
        for _ in range(3):
            hb_response = requests.post(
                f"{base_url}/heartbeat",
                json={
                    "heartbeat_name": "e2e-test-heartbeat",
                    "status": "UP"
                }
            )
            assert hb_response.status_code == 201
            time.sleep(1)

        # Step 3: Query heartbeats
        query_response = requests.get(
            f"{base_url}/heartbeat",
            params={"heartbeat_name": "e2e-test-heartbeat"}
        )
        assert query_response.status_code == 200
        data = query_response.json()
        assert data["success"] is True
        assert len(data["results"]) >= 3

        # Step 4: Mute the service (cleanup)
        mute_response = requests.post(
            f"{base_url}/service/e2e-test-heartbeat",
            json={"muted": 1, "active": 0}
        )
        assert mute_response.status_code == 200


@pytest.mark.e2e
class TestEndToEndMocked:
    """End-to-end tests with mocked external services."""

    @patch("Medic.Worker.pagerduty_client.requests.post")
    @patch("Medic.Worker.slack_client.WebClient")
    def test_complete_alert_flow(self, mock_slack, mock_pd_post, app, mock_env_vars, mock_db_connection):
        """Test the complete alert flow from registration to resolution."""
        client = app.test_client()

        # Mock PagerDuty response
        mock_pd_response = MagicMock()
        mock_pd_response.status_code = 202
        mock_pd_response.json.return_value = {"status": "success"}
        mock_pd_post.return_value = mock_pd_response

        # Mock Slack
        mock_slack_instance = MagicMock()
        mock_slack_instance.chat_postMessage.return_value = {"ok": True}
        mock_slack.return_value = mock_slack_instance

        with patch("Medic.Core.routes.db.query_db") as mock_query:
            with patch("Medic.Core.routes.db.insert_db") as mock_insert:
                mock_insert.return_value = True

                # Step 1: Register service
                mock_query.return_value = [(0,)]  # Not registered
                response = client.post(
                    "/service",
                    data=json.dumps({
                        "heartbeat_name": "e2e-mock-heartbeat",
                        "service_name": "e2e-mock-service",
                        "alert_interval": 5,
                        "team": "platform"
                    }),
                    content_type="application/json"
                )
                assert response.status_code == 201

                # Step 2: Post heartbeat
                mock_query.return_value = json.dumps([{
                    "service_id": 1,
                    "heartbeat_name": "e2e-mock-heartbeat",
                    "active": 1
                }])

                with patch("Medic.Core.routes.hbeat.addHeartbeat") as mock_add:
                    mock_add.return_value = True
                    with patch("Medic.Core.routes.hbeat.Heartbeat"):
                        response = client.post(
                            "/heartbeat",
                            data=json.dumps({
                                "heartbeat_name": "e2e-mock-heartbeat",
                                "status": "UP"
                            }),
                            content_type="application/json"
                        )
                        assert response.status_code == 201

                # Step 3: Get service info
                mock_query.return_value = json.dumps([{
                    "service_id": 1,
                    "heartbeat_name": "e2e-mock-heartbeat",
                    "active": 1,
                    "muted": 0
                }])

                response = client.get("/service/e2e-mock-heartbeat")
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True

                # Step 4: Check alerts endpoint
                mock_query.return_value = json.dumps([])
                response = client.get("/alerts")
                assert response.status_code == 200

    def test_api_error_handling(self, app, mock_env_vars):
        """Test API error handling for invalid requests."""
        client = app.test_client()

        # Invalid heartbeat (missing required fields)
        response = client.post(
            "/heartbeat",
            data=json.dumps({"invalid": "data"}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

        # Invalid service registration
        response = client.post(
            "/service",
            data=json.dumps({"heartbeat_name": "test"}),  # Missing required fields
            content_type="application/json"
        )
        assert response.status_code == 400
