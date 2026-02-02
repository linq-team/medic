"""Unit tests for PagerDuty client."""
import pytest
from unittest.mock import patch, MagicMock


class TestGetRoutingKey:
    """Tests for get_routing_key function."""

    def test_get_routing_key_from_env(self, mock_env_vars):
        """Test getting routing key from environment."""
        from Medic.Worker.pagerduty_client import get_routing_key

        result = get_routing_key()
        assert result == "test-routing-key"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_routing_key_missing(self):
        """Test handling missing routing key."""
        from Medic.Worker.pagerduty_client import get_routing_key

        result = get_routing_key()
        assert result == ""


class TestGetSeverity:
    """Tests for get_severity function."""

    def test_severity_mapping(self):
        """Test priority to severity mapping."""
        from Medic.Worker.pagerduty_client import get_severity

        assert get_severity("p1") == "critical"
        assert get_severity("P1") == "critical"
        assert get_severity("p2") == "error"
        assert get_severity("p3") == "warning"
        assert get_severity("p4") == "info"
        assert get_severity("p5") == "info"
        assert get_severity("unknown") == "warning"


class TestCreateAlert:
    """Tests for create_alert function."""

    @patch("Medic.Worker.pagerduty_client.requests.post")
    def test_create_alert_success(self, mock_post, mock_env_vars):
        """Test successful alert creation."""
        from Medic.Worker.pagerduty_client import create_alert

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        result = create_alert(
            alert_message="Test alert",
            service_name="test-service",
            heartbeat_name="test-heartbeat",
            team="platform",
            priority="p2"
        )

        assert result == "medic-test-heartbeat"
        mock_post.assert_called_once()

        # Verify the payload structure
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["event_action"] == "trigger"
        assert payload["dedup_key"] == "medic-test-heartbeat"
        assert payload["payload"]["severity"] == "error"

    @patch("Medic.Worker.pagerduty_client.requests.post")
    def test_create_alert_with_runbook(self, mock_post, mock_env_vars):
        """Test alert creation with runbook link."""
        from Medic.Worker.pagerduty_client import create_alert

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        result = create_alert(
            alert_message="Test alert",
            service_name="test-service",
            heartbeat_name="test-heartbeat",
            team="platform",
            runbook="https://docs.example.com/runbook"
        )

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert "links" in payload
        assert payload["links"][0]["href"] == "https://docs.example.com/runbook"

    @patch("Medic.Worker.pagerduty_client.requests.post")
    def test_create_alert_failure(self, mock_post, mock_env_vars):
        """Test alert creation failure."""
        from Medic.Worker.pagerduty_client import create_alert

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        result = create_alert(
            alert_message="Test alert",
            service_name="test-service",
            heartbeat_name="test-heartbeat",
            team="platform"
        )

        assert result is None

    @patch.dict("os.environ", {}, clear=True)
    def test_create_alert_no_routing_key(self):
        """Test alert creation without routing key."""
        from Medic.Worker.pagerduty_client import create_alert

        result = create_alert(
            alert_message="Test alert",
            service_name="test-service",
            heartbeat_name="test-heartbeat",
            team="platform"
        )

        assert result is None


class TestCloseAlert:
    """Tests for close_alert function."""

    @patch("Medic.Worker.pagerduty_client.requests.post")
    def test_close_alert_success(self, mock_post, mock_env_vars):
        """Test successful alert resolution."""
        from Medic.Worker.pagerduty_client import close_alert

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        result = close_alert("medic-test-heartbeat")

        assert result is True
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["event_action"] == "resolve"
        assert payload["dedup_key"] == "medic-test-heartbeat"

    @patch("Medic.Worker.pagerduty_client.requests.post")
    def test_close_alert_failure(self, mock_post, mock_env_vars):
        """Test alert resolution failure."""
        from Medic.Worker.pagerduty_client import close_alert

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = close_alert("medic-test-heartbeat")

        assert result is False

    def test_close_alert_null_key(self, mock_env_vars):
        """Test closing alert with NULL key."""
        from Medic.Worker.pagerduty_client import close_alert

        result = close_alert("NULL")
        assert result is False

    def test_close_alert_empty_key(self, mock_env_vars):
        """Test closing alert with empty key."""
        from Medic.Worker.pagerduty_client import close_alert

        result = close_alert("")
        assert result is False


class TestAcknowledgeAlert:
    """Tests for acknowledge_alert function."""

    @patch("Medic.Worker.pagerduty_client.requests.post")
    def test_acknowledge_alert_success(self, mock_post, mock_env_vars):
        """Test successful alert acknowledgment."""
        from Medic.Worker.pagerduty_client import acknowledge_alert

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        result = acknowledge_alert("medic-test-heartbeat")

        assert result is True
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["event_action"] == "acknowledge"
