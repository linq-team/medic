"""Unit tests for authentication middleware."""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from flask import Flask, g


class TestExtractBearerToken:
    """Tests for _extract_bearer_token function."""

    def test_extract_valid_bearer_token(self):
        """Test extracting a valid bearer token."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token("Bearer mdk_abc123")
        assert result == "mdk_abc123"

    def test_extract_bearer_token_case_insensitive(self):
        """Test that bearer scheme is case-insensitive."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token("bearer mdk_abc123")
        assert result == "mdk_abc123"

        result = _extract_bearer_token("BEARER mdk_abc123")
        assert result == "mdk_abc123"

    def test_extract_bearer_token_none_header(self):
        """Test with None header."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token(None)
        assert result is None

    def test_extract_bearer_token_empty_header(self):
        """Test with empty header."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token("")
        assert result is None

    def test_extract_bearer_token_wrong_scheme(self):
        """Test with wrong authentication scheme."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token("Basic abc123")
        assert result is None

    def test_extract_bearer_token_missing_token(self):
        """Test with scheme but missing token."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token("Bearer")
        assert result is None

    def test_extract_bearer_token_too_many_parts(self):
        """Test with too many parts in header."""
        from Medic.Core.auth_middleware import _extract_bearer_token

        result = _extract_bearer_token("Bearer token extra")
        assert result is None


class TestIsKeyExpired:
    """Tests for _is_key_expired function."""

    def test_key_not_expired_none(self):
        """Test that None expiration means not expired."""
        from Medic.Core.auth_middleware import _is_key_expired

        result = _is_key_expired(None)
        assert result is False

    def test_key_not_expired_future(self):
        """Test that future expiration means not expired."""
        from Medic.Core.auth_middleware import _is_key_expired

        future = datetime.now(timezone.utc) + timedelta(days=30)
        result = _is_key_expired(future.isoformat())
        assert result is False

    def test_key_expired_past(self):
        """Test that past expiration means expired."""
        from Medic.Core.auth_middleware import _is_key_expired

        past = datetime.now(timezone.utc) - timedelta(days=1)
        result = _is_key_expired(past.isoformat())
        assert result is True

    def test_key_expired_just_now(self):
        """Test expiration at current time."""
        from Medic.Core.auth_middleware import _is_key_expired

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        result = _is_key_expired(past.isoformat())
        assert result is True

    def test_key_expired_invalid_format(self):
        """Test that invalid format is treated as expired for safety."""
        from Medic.Core.auth_middleware import _is_key_expired

        result = _is_key_expired("not-a-date")
        assert result is True


class TestHasRequiredScopes:
    """Tests for _has_required_scopes function."""

    def test_no_required_scopes(self):
        """Test when no scopes are required."""
        from Medic.Core.auth_middleware import _has_required_scopes

        result = _has_required_scopes(["read"], [])
        assert result is True

    def test_has_required_scope(self):
        """Test when key has required scope."""
        from Medic.Core.auth_middleware import _has_required_scopes

        result = _has_required_scopes(["read", "write"], ["write"])
        assert result is True

    def test_missing_required_scope(self):
        """Test when key is missing required scope."""
        from Medic.Core.auth_middleware import _has_required_scopes

        result = _has_required_scopes(["read"], ["write"])
        assert result is False

    def test_admin_grants_all(self):
        """Test that admin scope grants all permissions."""
        from Medic.Core.auth_middleware import _has_required_scopes

        result = _has_required_scopes(["admin"], ["read", "write"])
        assert result is True

    def test_multiple_required_scopes(self):
        """Test with multiple required scopes."""
        from Medic.Core.auth_middleware import _has_required_scopes

        result = _has_required_scopes(["read", "write"], ["read", "write"])
        assert result is True

    def test_partial_scopes(self):
        """Test when only some required scopes are present."""
        from Medic.Core.auth_middleware import _has_required_scopes

        result = _has_required_scopes(["read"], ["read", "write"])
        assert result is False


class TestShouldBypassAuth:
    """Tests for _should_bypass_auth function."""

    def test_health_endpoint_bypass(self):
        """Test that /health endpoints bypass auth."""
        from Medic.Core.auth_middleware import _should_bypass_auth

        assert _should_bypass_auth("/health") is True
        assert _should_bypass_auth("/health/live") is True
        assert _should_bypass_auth("/health/ready") is True

    def test_healthcheck_endpoint_bypass(self):
        """Test that /v1/healthcheck endpoints bypass auth."""
        from Medic.Core.auth_middleware import _should_bypass_auth

        assert _should_bypass_auth("/v1/healthcheck/network") is True

    def test_metrics_endpoint_bypass(self):
        """Test that /metrics endpoint bypasses auth."""
        from Medic.Core.auth_middleware import _should_bypass_auth

        assert _should_bypass_auth("/metrics") is True

    def test_docs_endpoint_bypass(self):
        """Test that /docs endpoint bypasses auth."""
        from Medic.Core.auth_middleware import _should_bypass_auth

        assert _should_bypass_auth("/docs") is True
        assert _should_bypass_auth("/docs/swagger.json") is True

    def test_api_endpoints_require_auth(self):
        """Test that API endpoints require auth."""
        from Medic.Core.auth_middleware import _should_bypass_auth

        assert _should_bypass_auth("/heartbeat") is False
        assert _should_bypass_auth("/service") is False
        assert _should_bypass_auth("/alerts") is False


class TestAuthenticateRequestDecorator:
    """Tests for authenticate_request decorator."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def mock_db_key_valid(self):
        """Mock database returning a valid API key."""
        key_data = [
            {
                "api_key_id": 1,
                "name": "test-key",
                "key_hash": "$argon2id$v=19$m=65536,t=3,p=4$test",
                "scopes": ["read", "write"],
                "expires_at": None,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]
        with patch("Medic.Core.auth_middleware.db.query_db") as mock_query:
            mock_query.return_value = json.dumps(key_data)
            with patch("Medic.Core.auth_middleware.verify_api_key") as mock_verify:
                mock_verify.return_value = True
                yield mock_query, mock_verify

    @pytest.fixture
    def mock_db_key_expired(self):
        """Mock database returning an expired API key."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        key_data = [
            {
                "api_key_id": 1,
                "name": "test-key",
                "key_hash": "$argon2id$v=19$m=65536,t=3,p=4$test",
                "scopes": ["read", "write"],
                "expires_at": past.isoformat(),
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]
        with patch("Medic.Core.auth_middleware.db.query_db") as mock_query:
            mock_query.return_value = json.dumps(key_data)
            with patch("Medic.Core.auth_middleware.verify_api_key") as mock_verify:
                mock_verify.return_value = True
                yield mock_query, mock_verify

    def test_missing_auth_header_returns_401(self, app):
        """Test that missing Authorization header returns 401."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/test")
        @authenticate_request()
        def test_route():
            return "OK", 200

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 401
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Authorization" in data["message"]

    def test_invalid_auth_scheme_returns_401(self, app):
        """Test that non-Bearer scheme returns 401."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/test")
        @authenticate_request()
        def test_route():
            return "OK", 200

        with app.test_client() as client:
            response = client.get("/test", headers={"Authorization": "Basic abc123"})
            assert response.status_code == 401

    def test_invalid_key_returns_401(self, app):
        """Test that invalid API key returns 401."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/test")
        @authenticate_request()
        def test_route():
            return "OK", 200

        with patch("Medic.Core.auth_middleware.db.query_db") as mock_query:
            mock_query.return_value = json.dumps([])
            with app.test_client() as client:
                response = client.get(
                    "/test", headers={"Authorization": "Bearer invalid_key"}
                )
                assert response.status_code == 401
                data = json.loads(response.data)
                assert "Invalid API key" in data["message"]

    def test_expired_key_returns_401(self, app, mock_db_key_expired):
        """Test that expired API key returns 401."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/test")
        @authenticate_request()
        def test_route():
            return "OK", 200

        with app.test_client() as client:
            response = client.get(
                "/test", headers={"Authorization": "Bearer mdk_valid_key"}
            )
            assert response.status_code == 401
            data = json.loads(response.data)
            assert "expired" in data["message"]

    def test_insufficient_scopes_returns_403(self, app):
        """Test that insufficient scopes returns 403."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/test")
        @authenticate_request(required_scopes=["admin"])
        def test_route():
            return "OK", 200

        key_data = [
            {
                "api_key_id": 1,
                "name": "test-key",
                "key_hash": "$argon2id$v=19$m=65536,t=3,p=4$test",
                "scopes": ["read"],  # Missing admin scope
                "expires_at": None,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]
        with patch("Medic.Core.auth_middleware.db.query_db") as mock_query:
            mock_query.return_value = json.dumps(key_data)
            with patch("Medic.Core.auth_middleware.verify_api_key") as mock_verify:
                mock_verify.return_value = True
                with app.test_client() as client:
                    response = client.get(
                        "/test", headers={"Authorization": "Bearer mdk_valid_key"}
                    )
                    assert response.status_code == 403
                    data = json.loads(response.data)
                    assert "permissions" in data["message"]

    def test_valid_key_allows_access(self, app, mock_db_key_valid):
        """Test that valid API key with correct scopes allows access."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/test")
        @authenticate_request(required_scopes=["read"])
        def test_route():
            return "OK", 200

        with app.test_client() as client:
            response = client.get(
                "/test", headers={"Authorization": "Bearer mdk_valid_key"}
            )
            assert response.status_code == 200

    def test_health_endpoint_bypasses_auth(self, app):
        """Test that health endpoints bypass authentication."""
        from Medic.Core.auth_middleware import authenticate_request

        @app.route("/health/live")
        @authenticate_request()
        def health_live():
            return "OK", 200

        with app.test_client() as client:
            # No auth header, but should still succeed
            response = client.get("/health/live")
            assert response.status_code == 200

    def test_sets_flask_g_context(self, app, mock_db_key_valid):
        """Test that authenticated request sets Flask g context."""
        from Medic.Core.auth_middleware import authenticate_request

        captured_context = {}

        @app.route("/test")
        @authenticate_request()
        def test_route():
            captured_context["api_key_id"] = g.api_key_id
            captured_context["api_key_name"] = g.api_key_name
            captured_context["api_key_scopes"] = g.api_key_scopes
            return "OK", 200

        with app.test_client() as client:
            response = client.get(
                "/test", headers={"Authorization": "Bearer mdk_valid_key"}
            )
            assert response.status_code == 200
            assert captured_context["api_key_id"] == 1
            assert captured_context["api_key_name"] == "test-key"
            assert captured_context["api_key_scopes"] == ["read", "write"]


class TestRequireAuthAlias:
    """Tests for require_auth alias function."""

    def test_require_auth_is_alias(self):
        """Test that require_auth is an alias for authenticate_request."""
        from Medic.Core.auth_middleware import require_auth, authenticate_request

        # Both should return decorator functions
        decorator1 = require_auth(["read"])
        decorator2 = authenticate_request(required_scopes=["read"])

        # They should be functions
        assert callable(decorator1)
        assert callable(decorator2)


class TestVerifyRequestAuth:
    """Tests for verify_request_auth function."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_returns_none_on_success(self, app):
        """Test that successful auth returns None."""
        from Medic.Core.auth_middleware import verify_request_auth

        key_data = [
            {
                "api_key_id": 1,
                "name": "test-key",
                "key_hash": "$argon2id$v=19$m=65536,t=3,p=4$test",
                "scopes": ["read", "write"],
                "expires_at": None,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]

        with app.test_request_context(
            "/test", headers={"Authorization": "Bearer mdk_valid_key"}
        ):
            with patch("Medic.Core.auth_middleware.db.query_db") as mock_query:
                mock_query.return_value = json.dumps(key_data)
                with patch("Medic.Core.auth_middleware.verify_api_key") as mock_verify:
                    mock_verify.return_value = True
                    result = verify_request_auth()
                    assert result is None

    def test_returns_401_on_missing_auth(self, app):
        """Test that missing auth returns 401 tuple."""
        from Medic.Core.auth_middleware import verify_request_auth

        with app.test_request_context("/test"):
            result = verify_request_auth()
            assert result is not None
            body, status = result
            assert status == 401

    def test_bypasses_health_endpoints(self, app):
        """Test that health endpoints bypass auth."""
        from Medic.Core.auth_middleware import verify_request_auth

        with app.test_request_context("/health/live"):
            result = verify_request_auth()
            assert result is None
