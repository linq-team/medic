"""Unit tests for Flask routes."""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestHealthcheck:
    """Tests for healthcheck endpoint."""

    def test_healthcheck_returns_204(self, client, mock_env_vars):
        """Test healthcheck endpoint returns 204."""
        response = client.get("/v1/healthcheck/network")
        assert response.status_code == 204


class TestHeartbeatEndpoint:
    """Tests for heartbeat endpoint."""

    @patch("Medic.Core.routes.db")
    @patch("Medic.Core.routes.hbeat")
    def test_post_heartbeat_success(self, mock_hbeat, mock_db, client, mock_env_vars, sample_heartbeat_data):
        """Test successful heartbeat post."""
        mock_db.query_db.return_value = json.dumps([{
            "service_id": 1,
            "active": 1,
            "heartbeat_name": "test-service-heartbeat"
        }])
        mock_hbeat.addHeartbeat.return_value = True
        mock_hbeat.Heartbeat = MagicMock()

        response = client.post(
            "/heartbeat",
            data=json.dumps(sample_heartbeat_data),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True

    @patch("Medic.Core.routes.db")
    def test_post_heartbeat_not_registered(self, mock_db, client, mock_env_vars, sample_heartbeat_data):
        """Test heartbeat post for unregistered service."""
        mock_db.query_db.return_value = "[]"

        response = client.post(
            "/heartbeat",
            data=json.dumps(sample_heartbeat_data),
            content_type="application/json"
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_post_heartbeat_invalid_data(self, client, mock_env_vars):
        """Test heartbeat post with invalid data."""
        response = client.post(
            "/heartbeat",
            data=json.dumps({"invalid": "data"}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    @patch("Medic.Core.routes.db")
    def test_get_heartbeats(self, mock_db, client, mock_env_vars):
        """Test getting heartbeat list."""
        mock_db.query_db.return_value = json.dumps([{
            "heartbeat_id": 1,
            "heartbeat_name": "test",
            "status": "UP"
        }])

        response = client.get("/heartbeat")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert isinstance(data["results"], list)

    @patch("Medic.Core.routes.db")
    def test_get_heartbeats_with_filters(self, mock_db, client, mock_env_vars):
        """Test getting heartbeats with filters."""
        mock_db.query_db.return_value = "[]"

        response = client.get(
            "/heartbeat?heartbeat_name=test&service_name=test-service&maxCount=50"
        )

        assert response.status_code == 200
        # Verify parameterized query was used
        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]


class TestServiceEndpoint:
    """Tests for service endpoint."""

    @patch("Medic.Core.routes.db")
    def test_register_service_success(self, mock_db, client, mock_env_vars, sample_service_data):
        """Test successful service registration."""
        mock_db.query_db.return_value = [(0,)]  # Count = 0, not registered
        mock_db.insert_db.return_value = True

        response = client.post(
            "/service",
            data=json.dumps(sample_service_data),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["success"] is True

    @patch("Medic.Core.routes.db")
    def test_register_service_already_exists(self, mock_db, client, mock_env_vars, sample_service_data):
        """Test registering already existing service."""
        mock_db.query_db.return_value = [(1,)]  # Count = 1, already registered

        response = client.post(
            "/service",
            data=json.dumps(sample_service_data),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "already registered" in data["message"]

    @patch("Medic.Core.routes.db")
    def test_get_services(self, mock_db, client, mock_env_vars):
        """Test getting service list."""
        mock_db.query_db.return_value = json.dumps([{
            "service_id": 1,
            "heartbeat_name": "test",
            "active": 1
        }])

        response = client.get("/service")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True


class TestServiceByNameEndpoint:
    """Tests for service by name endpoint."""

    @patch("Medic.Core.routes.db")
    def test_get_service_by_name(self, mock_db, client, mock_env_vars):
        """Test getting service by name."""
        mock_db.query_db.return_value = json.dumps([{
            "service_id": 1,
            "heartbeat_name": "test-heartbeat"
        }])

        response = client.get("/service/test-heartbeat")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @patch("Medic.Core.routes.db")
    def test_update_service(self, mock_db, client, mock_env_vars):
        """Test updating service."""
        mock_db.query_db.return_value = json.dumps([{"service_id": 1}])
        mock_db.insert_db.return_value = True

        response = client.post(
            "/service/test-heartbeat",
            data=json.dumps({"muted": 1}),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True


class TestAlertsEndpoint:
    """Tests for alerts endpoint."""

    @patch("Medic.Core.routes.db")
    def test_get_alerts(self, mock_db, client, mock_env_vars):
        """Test getting alert list."""
        mock_db.query_db.return_value = json.dumps([{
            "alert_id": 1,
            "alert_name": "test alert",
            "active": 1
        }])

        response = client.get("/alerts")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @patch("Medic.Core.routes.db")
    def test_get_alerts_filtered(self, mock_db, client, mock_env_vars):
        """Test getting filtered alerts."""
        mock_db.query_db.return_value = "[]"

        response = client.get("/alerts?active=1")

        assert response.status_code == 200
        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]
        assert call_args[0][1] == (1,)


class TestSqlInjectionPrevention:
    """Tests to verify SQL injection prevention."""

    @patch("Medic.Core.routes.db")
    def test_heartbeat_name_injection_prevention(self, mock_db, client, mock_env_vars):
        """Test that SQL injection via heartbeat_name is prevented."""
        mock_db.query_db.return_value = "[]"

        malicious_name = "'; DROP TABLE services; --"
        response = client.get(f"/heartbeat?heartbeat_name={malicious_name}")

        # Verify the query used parameterized approach
        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]
        # The malicious string should be passed as a parameter, not concatenated
        assert malicious_name in str(call_args[0][1])

    @patch("Medic.Core.routes.db")
    def test_service_name_injection_prevention(self, mock_db, client, mock_env_vars):
        """Test that SQL injection via service_name is prevented."""
        mock_db.query_db.return_value = "[]"

        malicious_name = "test' OR '1'='1"
        response = client.get(f"/service?service_name={malicious_name}")

        call_args = mock_db.query_db.call_args
        assert "%s" in call_args[0][0]
