"""Pytest configuration and shared fixtures."""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set up required environment variables for testing.

    This fixture is autouse=True so it runs for all tests automatically,
    ensuring database and API credentials are always available.
    """
    env_vars = {
        "PG_USER": "test_user",
        "PG_PASS": "test_pass",
        "DB_NAME": "test_medic",
        "DB_HOST": "localhost",
        "PORT": "5000",
        "SLACK_API_TOKEN": "xoxb-test-token",
        "SLACK_CHANNEL_ID": "C12345678",
        "SLACK_SIGNING_SECRET": "test-signing-secret",
        "PAGERDUTY_ROUTING_KEY": "test-routing-key",
        "MEDIC_BASE_URL": "http://localhost:5000",
        "MEDIC_SECRETS_KEY": "dGVzdC1zZWNyZXQta2V5LWZvci10ZXN0aW5n",
        "MEDIC_WEBHOOK_SECRET": "test-webhook-secret",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield {
            "connect": mock_connect,
            "connection": mock_conn,
            "cursor": mock_cursor,
        }


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient."""
    with patch("slack_sdk.WebClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.chat_postMessage.return_value = {"ok": True}
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_requests():
    """Mock requests library for HTTP calls."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "success", "dedup_key": "test-key"}
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def app():
    """Create Flask test application."""
    from flask import Flask
    import Medic.Core.routes as routes

    app = Flask(__name__, static_folder=os.path.abspath("Medic/Docs"))
    app.config["TESTING"] = True
    routes.exposeRoutes(app)
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def sample_heartbeat_data():
    """Sample heartbeat data for testing."""
    return {
        "heartbeat_name": "test-service-heartbeat",
        "service_name": "test-service",
        "status": "UP",
    }


@pytest.fixture
def sample_service_data():
    """Sample service registration data for testing."""
    return {
        "heartbeat_name": "test-service-heartbeat",
        "service_name": "test-service",
        "alert_interval": 5,
        "threshold": 1,
        "team": "platform",
        "priority": "p2",
        "runbook": "https://docs.example.com/runbook",
    }
