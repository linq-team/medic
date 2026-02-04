"""Unit tests for rate limiting middleware."""
import json
import time
import pytest
from unittest.mock import patch
from flask import Flask, g


class TestEndpointSpecificRateLimits:
    """Tests for endpoint-specific rate limit configurations."""

    def test_health_endpoint_rate_limit_config(self):
        """Test that health endpoints use RATE_LIMIT_HEALTH_REQUESTS."""
        from Medic.Core.rate_limit_middleware import (
            _get_endpoint_rate_limit_config,
            RATE_LIMIT_HEALTH_REQUESTS,
            ENDPOINT_TYPE_HEALTH,
        )

        config = _get_endpoint_rate_limit_config(ENDPOINT_TYPE_HEALTH)
        assert config.management_limit == RATE_LIMIT_HEALTH_REQUESTS
        assert config.heartbeat_limit == RATE_LIMIT_HEALTH_REQUESTS

    def test_metrics_endpoint_rate_limit_config(self):
        """Test that metrics endpoints use RATE_LIMIT_METRICS_REQUESTS."""
        from Medic.Core.rate_limit_middleware import (
            _get_endpoint_rate_limit_config,
            RATE_LIMIT_METRICS_REQUESTS,
            ENDPOINT_TYPE_METRICS,
        )

        config = _get_endpoint_rate_limit_config(ENDPOINT_TYPE_METRICS)
        assert config.management_limit == RATE_LIMIT_METRICS_REQUESTS
        assert config.heartbeat_limit == RATE_LIMIT_METRICS_REQUESTS

    def test_docs_endpoint_rate_limit_config(self):
        """Test that docs endpoints use RATE_LIMIT_DOCS_REQUESTS."""
        from Medic.Core.rate_limit_middleware import (
            _get_endpoint_rate_limit_config,
            RATE_LIMIT_DOCS_REQUESTS,
            ENDPOINT_TYPE_DOCS,
        )

        config = _get_endpoint_rate_limit_config(ENDPOINT_TYPE_DOCS)
        assert config.management_limit == RATE_LIMIT_DOCS_REQUESTS
        assert config.heartbeat_limit == RATE_LIMIT_DOCS_REQUESTS

    def test_management_endpoint_uses_default_config(self):
        """Test that management endpoints use default config."""
        from Medic.Core.rate_limit_middleware import _get_endpoint_rate_limit_config
        from Medic.Core.rate_limiter import RateLimitConfig

        config = _get_endpoint_rate_limit_config("management")
        default_config = RateLimitConfig()
        assert config.management_limit == default_config.management_limit

    def test_heartbeat_endpoint_uses_default_config(self):
        """Test that heartbeat endpoints use default config."""
        from Medic.Core.rate_limit_middleware import _get_endpoint_rate_limit_config
        from Medic.Core.rate_limiter import RateLimitConfig

        config = _get_endpoint_rate_limit_config("heartbeat")
        default_config = RateLimitConfig()
        assert config.heartbeat_limit == default_config.heartbeat_limit


class TestNoEndpointsBypassRateLimiting:
    """Tests verifying that NO endpoints bypass rate limiting."""

    def test_health_endpoints_are_rate_limited(self):
        """Test that /health endpoints are rate limited."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        # Health endpoints return a specific type (not bypassed)
        assert _determine_endpoint_type("/health") == "health"
        assert _determine_endpoint_type("/health/live") == "health"
        assert _determine_endpoint_type("/health/ready") == "health"

    def test_healthcheck_endpoints_are_rate_limited(self):
        """Test that /v1/healthcheck endpoints are rate limited."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/v1/healthcheck/network") == "health"

    def test_metrics_endpoint_is_rate_limited(self):
        """Test that /metrics endpoint is rate limited."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/metrics") == "metrics"

    def test_docs_endpoint_is_rate_limited(self):
        """Test that /docs endpoint is rate limited."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/docs") == "docs"
        assert _determine_endpoint_type("/docs/swagger.json") == "docs"

    def test_api_endpoints_are_rate_limited(self):
        """Test that regular API endpoints are rate limited."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/heartbeat") == "heartbeat"
        assert _determine_endpoint_type("/service") == "management"
        assert _determine_endpoint_type("/alerts") == "management"


class TestDetermineEndpointType:
    """Tests for _determine_endpoint_type function."""

    def test_health_endpoints(self):
        """Test that health endpoints return 'health' type."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/health") == "health"
        assert _determine_endpoint_type("/health/live") == "health"
        assert _determine_endpoint_type("/health/ready") == "health"
        assert _determine_endpoint_type("/v1/healthcheck") == "health"
        assert _determine_endpoint_type("/v1/healthcheck/network") == "health"

    def test_metrics_endpoints(self):
        """Test that metrics endpoints return 'metrics' type."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/metrics") == "metrics"
        assert _determine_endpoint_type("/metrics/custom") == "metrics"

    def test_docs_endpoints(self):
        """Test that docs endpoints return 'docs' type."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/docs") == "docs"
        assert _determine_endpoint_type("/docs/swagger.json") == "docs"
        assert _determine_endpoint_type("/docs/openapi.yaml") == "docs"

    def test_heartbeat_endpoints(self):
        """Test that heartbeat endpoints return 'heartbeat' type."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/heartbeat") == "heartbeat"
        assert _determine_endpoint_type("/heartbeat/test-service") == "heartbeat"
        assert _determine_endpoint_type("/v1/heartbeat/test") == "heartbeat"
        assert _determine_endpoint_type("/v2/heartbeat/test/start") == "heartbeat"

    def test_management_endpoints(self):
        """Test that non-special endpoints return 'management' type."""
        from Medic.Core.rate_limit_middleware import _determine_endpoint_type

        assert _determine_endpoint_type("/service") == "management"
        assert _determine_endpoint_type("/alerts") == "management"
        assert _determine_endpoint_type("/v1/service/register") == "management"
        assert _determine_endpoint_type("/api/users") == "management"


class TestCreateRateLimitHeaders:
    """Tests for _create_rate_limit_headers function."""

    def test_creates_basic_headers(self):
        """Test that basic rate limit headers are created."""
        from Medic.Core.rate_limit_middleware import _create_rate_limit_headers
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=95,
            reset_at=time.time() + 60,
        )

        headers = _create_rate_limit_headers(result)

        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert "X-RateLimit-Remaining" in headers
        assert headers["X-RateLimit-Remaining"] == "95"
        assert "X-RateLimit-Reset" in headers
        assert "Retry-After" not in headers

    def test_includes_retry_after_when_limited(self):
        """Test that Retry-After header is included when rate limited."""
        from Medic.Core.rate_limit_middleware import _create_rate_limit_headers
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=30,
        )

        headers = _create_rate_limit_headers(result)

        assert "Retry-After" in headers
        assert headers["Retry-After"] == "30"


class TestCreateRateLimitResponse:
    """Tests for _create_rate_limit_response function."""

    def test_creates_429_response(self):
        """Test that 429 response is created correctly."""
        from Medic.Core.rate_limit_middleware import _create_rate_limit_response
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=30,
        )

        body, status, headers = _create_rate_limit_response(result)

        assert status == 429
        data = json.loads(body)
        assert data["success"] is False
        assert "Rate limit exceeded" in data["message"]
        assert data["retry_after"] == 30
        assert "X-RateLimit-Limit" in headers


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def mock_rate_limiter_allowed(self):
        """Mock rate limiter that allows requests."""
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )
        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            yield mock_check

    @pytest.fixture
    def mock_rate_limiter_blocked(self):
        """Mock rate limiter that blocks requests."""
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=30,
        )
        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            yield mock_check

    def test_allows_request_under_limit(self, app, mock_rate_limiter_allowed):
        """Test that requests under limit are allowed."""
        from Medic.Core.rate_limit_middleware import rate_limit

        @app.route("/test")
        @rate_limit()
        def test_route():
            return json.dumps({"success": True}), 200

        with app.test_client() as client:
            # Set API key in g context
            with app.test_request_context():
                g.api_key_id = "test-key-1"

            response = client.get("/test")
            assert response.status_code == 200

    def test_blocks_request_over_limit(self, app, mock_rate_limiter_blocked):
        """Test that requests over limit return 429."""
        from Medic.Core.rate_limit_middleware import rate_limit

        @app.route("/test")
        @rate_limit()
        def test_route():
            return json.dumps({"success": True}), 200

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 429
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Rate limit exceeded" in data["message"]

    def test_adds_rate_limit_headers_on_success(self, app, mock_rate_limiter_allowed):
        """Test that rate limit headers are added to successful responses."""
        from Medic.Core.rate_limit_middleware import rate_limit

        @app.route("/test")
        @rate_limit()
        def test_route():
            return json.dumps({"success": True}), 200

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert response.headers["X-RateLimit-Limit"] == "100"
            assert "X-RateLimit-Remaining" in response.headers
            assert response.headers["X-RateLimit-Remaining"] == "99"
            assert "X-RateLimit-Reset" in response.headers

    def test_adds_rate_limit_headers_on_block(self, app, mock_rate_limiter_blocked):
        """Test that rate limit headers are added to blocked responses."""
        from Medic.Core.rate_limit_middleware import rate_limit

        @app.route("/test")
        @rate_limit()
        def test_route():
            return json.dumps({"success": True}), 200

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 429
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert response.headers["X-RateLimit-Remaining"] == "0"
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == "30"

    def test_health_endpoints_are_rate_limited(self, app):
        """Test that health endpoints ARE rate limited (not bypassed)."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=1000,
            remaining=999,
            reset_at=time.time() + 60,
        )

        @app.route("/health/live")
        @rate_limit()
        def health_live():
            return json.dumps({"status": "ok"}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            # Rate limit check SHOULD be called for health endpoints
            with app.test_client() as client:
                response = client.get("/health/live")
                assert response.status_code == 200
                mock_check.assert_called_once()
                # Verify endpoint type is "health"
                call_args = mock_check.call_args
                assert call_args[0][1] == "health"

    def test_metrics_endpoints_are_rate_limited(self, app):
        """Test that metrics endpoints ARE rate limited (not bypassed)."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        @app.route("/metrics")
        @rate_limit()
        def metrics_route():
            return "# metrics\n", 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with app.test_client() as client:
                response = client.get("/metrics")
                assert response.status_code == 200
                mock_check.assert_called_once()
                # Verify endpoint type is "metrics"
                call_args = mock_check.call_args
                assert call_args[0][1] == "metrics"

    def test_docs_endpoints_are_rate_limited(self, app):
        """Test that docs endpoints ARE rate limited (not bypassed)."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=60,
            remaining=59,
            reset_at=time.time() + 60,
        )

        @app.route("/docs")
        @rate_limit()
        def docs_route():
            return json.dumps({"docs": "here"}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with app.test_client() as client:
                response = client.get("/docs")
                assert response.status_code == 200
                mock_check.assert_called_once()
                # Verify endpoint type is "docs"
                call_args = mock_check.call_args
                assert call_args[0][1] == "docs"

    def test_uses_api_key_id_for_bucket(self, app):
        """Test that API key ID is used for rate limit bucket."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        @app.route("/test")
        @rate_limit()
        def test_route():
            return json.dumps({"success": True}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = "test-api-key-123"
                with app.test_client() as client:
                    response = client.get("/test")
                    assert response.status_code == 200
                    # Verify the API key was used as the bucket key
                    mock_check.assert_called_once()
                    call_args = mock_check.call_args
                    assert call_args[0][0] == "test-api-key-123"

    def test_uses_ip_address_without_api_key(self, app):
        """Test that IP address is used when no API key is present."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        @app.route("/test")
        @rate_limit()
        def test_route():
            return json.dumps({"success": True}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = None  # No API key
                with app.test_client() as client:
                    response = client.get("/test")
                    assert response.status_code == 200
                    mock_check.assert_called_once()
                    call_args = mock_check.call_args
                    # Should use IP-based key
                    assert call_args[0][0].startswith("ip:")

    def test_auto_detects_heartbeat_endpoint_type(self, app):
        """Test that heartbeat endpoints use heartbeat rate limit."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        @app.route("/heartbeat/test-service")
        @rate_limit()  # No explicit endpoint_type
        def heartbeat_route():
            return json.dumps({"success": True}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = "test-key"
                with app.test_client() as client:
                    response = client.get("/heartbeat/test-service")
                    assert response.status_code == 200
                    mock_check.assert_called_once()
                    call_args = mock_check.call_args
                    # Should detect heartbeat endpoint type
                    assert call_args[0][1] == "heartbeat"

    def test_explicit_endpoint_type_override(self, app):
        """Test that explicit endpoint type overrides auto-detection."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        @app.route("/custom")
        @rate_limit(endpoint_type="heartbeat")  # Explicit override
        def custom_route():
            return json.dumps({"success": True}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = "test-key"
                with app.test_client() as client:
                    response = client.get("/custom")
                    assert response.status_code == 200
                    mock_check.assert_called_once()
                    call_args = mock_check.call_args
                    assert call_args[0][1] == "heartbeat"

    def test_custom_config(self, app):
        """Test that custom config is passed to rate limiter."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitResult, RateLimitConfig

        result = RateLimitResult(
            allowed=True,
            limit=50,
            remaining=49,
            reset_at=time.time() + 60,
        )

        custom_config = RateLimitConfig(management_limit=50)

        @app.route("/test")
        @rate_limit(config=custom_config)
        def test_route():
            return json.dumps({"success": True}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = "test-key"
                with app.test_client() as client:
                    response = client.get("/test")
                    assert response.status_code == 200
                    mock_check.assert_called_once()
                    call_args = mock_check.call_args
                    # Custom config should be passed
                    assert call_args[0][2] == custom_config


class TestRequireRateLimitAlias:
    """Tests for require_rate_limit alias function."""

    def test_require_rate_limit_is_alias(self):
        """Test that require_rate_limit is an alias for rate_limit."""
        from Medic.Core.rate_limit_middleware import (
            require_rate_limit,
            rate_limit,
        )

        # Both should return decorator functions
        decorator1 = require_rate_limit()
        decorator2 = rate_limit()

        assert callable(decorator1)
        assert callable(decorator2)


class TestVerifyRateLimit:
    """Tests for verify_rate_limit function."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_returns_none_when_allowed(self, app):
        """Test that None is returned when request is allowed."""
        from Medic.Core.rate_limit_middleware import verify_rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        with app.test_request_context("/test"):
            with patch(
                "Medic.Core.rate_limit_middleware.check_rate_limit"
            ) as mock_check:
                mock_check.return_value = result
                with patch(
                    "Medic.Core.rate_limit_middleware._get_api_key_id"
                ) as mock_get_key:
                    mock_get_key.return_value = "test-key"
                    response = verify_rate_limit()
                    assert response is None

    def test_returns_429_when_blocked(self, app):
        """Test that 429 response is returned when blocked."""
        from Medic.Core.rate_limit_middleware import verify_rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=30,
        )

        with app.test_request_context("/test"):
            with patch(
                "Medic.Core.rate_limit_middleware.check_rate_limit"
            ) as mock_check:
                mock_check.return_value = result
                with patch(
                    "Medic.Core.rate_limit_middleware._get_api_key_id"
                ) as mock_get_key:
                    mock_get_key.return_value = "test-key"
                    response = verify_rate_limit()
                    assert response is not None
                    body, status, headers = response
                    assert status == 429

    def test_health_endpoints_are_rate_limited(self, app):
        """Test that health endpoints ARE rate limited (not bypassed)."""
        from Medic.Core.rate_limit_middleware import verify_rate_limit
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=1000,
            remaining=999,
            reset_at=time.time() + 60,
        )

        with app.test_request_context("/health/live"):
            with patch(
                "Medic.Core.rate_limit_middleware.check_rate_limit"
            ) as mock_check:
                mock_check.return_value = result
                with patch(
                    "Medic.Core.rate_limit_middleware._get_api_key_id"
                ) as mock_get_key:
                    mock_get_key.return_value = "test-key"
                    response = verify_rate_limit()
                    assert response is None  # Allowed
                    # Rate limit check SHOULD be called
                    mock_check.assert_called_once()
                    call_args = mock_check.call_args
                    # Verify endpoint type is "health"
                    assert call_args[0][1] == "health"

    def test_stores_result_in_g(self, app):
        """Test that result is stored in Flask g for header retrieval."""
        from Medic.Core.rate_limit_middleware import (
            verify_rate_limit,
            get_rate_limit_headers,
        )
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        with app.test_request_context("/test"):
            with patch(
                "Medic.Core.rate_limit_middleware.check_rate_limit"
            ) as mock_check:
                mock_check.return_value = result
                with patch(
                    "Medic.Core.rate_limit_middleware._get_api_key_id"
                ) as mock_get_key:
                    mock_get_key.return_value = "test-key"
                    verify_rate_limit()
                    headers = get_rate_limit_headers()
                    assert "X-RateLimit-Limit" in headers


class TestGetRateLimitHeaders:
    """Tests for get_rate_limit_headers function."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_returns_empty_dict_without_result(self, app):
        """Test that empty dict is returned when no result in g."""
        from Medic.Core.rate_limit_middleware import get_rate_limit_headers

        with app.test_request_context("/test"):
            headers = get_rate_limit_headers()
            assert headers == {}

    def test_returns_headers_with_result(self, app):
        """Test that headers are returned when result is in g."""
        from Medic.Core.rate_limit_middleware import get_rate_limit_headers
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        with app.test_request_context("/test"):
            g.rate_limit_result = result
            headers = get_rate_limit_headers()
            assert "X-RateLimit-Limit" in headers
            assert headers["X-RateLimit-Limit"] == "100"


class TestIntegrationWithRateLimiter:
    """Integration tests with the actual rate limiter."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def fresh_rate_limiter(self):
        """Set up a fresh rate limiter for testing."""
        from Medic.Core.rate_limiter import (
            set_rate_limiter,
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=5, heartbeat_limit=10)
        )
        set_rate_limiter(limiter)
        yield limiter
        set_rate_limiter(None)

    def test_rate_limit_enforced(self, app, fresh_rate_limiter):
        """Test that rate limit is actually enforced."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitConfig

        # Use explicit config to test with specific limits
        custom_config = RateLimitConfig(management_limit=5, heartbeat_limit=10)

        @app.route("/test")
        @rate_limit(config=custom_config)
        def test_route():
            return json.dumps({"success": True}), 200

        with patch(
            "Medic.Core.rate_limit_middleware._get_api_key_id"
        ) as mock_get_key:
            mock_get_key.return_value = "integration-test-key"

            with app.test_client() as client:
                # Should allow first 5 requests (management limit)
                for i in range(5):
                    response = client.get("/test")
                    assert response.status_code == 200, f"Request {i+1} failed"

                # 6th request should be blocked
                response = client.get("/test")
                assert response.status_code == 429
                assert "Retry-After" in response.headers

    def test_different_keys_have_separate_limits(self, app, fresh_rate_limiter):
        """Test that different API keys have separate rate limits."""
        from Medic.Core.rate_limit_middleware import rate_limit
        from Medic.Core.rate_limiter import RateLimitConfig

        # Use explicit config to test with specific limits
        custom_config = RateLimitConfig(management_limit=5, heartbeat_limit=10)

        @app.route("/test")
        @rate_limit(config=custom_config)
        def test_route():
            return json.dumps({"success": True}), 200

        with app.test_client() as client:
            # Exhaust limit for key1
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = "key1"
                for _ in range(5):
                    response = client.get("/test")
                    assert response.status_code == 200

                # key1 should be blocked
                response = client.get("/test")
                assert response.status_code == 429

            # key2 should still have quota
            with patch(
                "Medic.Core.rate_limit_middleware._get_api_key_id"
            ) as mock_get_key:
                mock_get_key.return_value = "key2"
                response = client.get("/test")
                assert response.status_code == 200


class TestEnvironmentVariableConfiguration:
    """Tests for environment variable rate limit configuration."""

    def test_health_rate_limit_env_var_default(self):
        """Test default value for RATE_LIMIT_HEALTH_REQUESTS."""
        import Medic.Core.rate_limit_middleware as middleware

        # Default should be 1000
        assert middleware.RATE_LIMIT_HEALTH_REQUESTS == 1000

    def test_metrics_rate_limit_env_var_default(self):
        """Test default value for RATE_LIMIT_METRICS_REQUESTS."""
        import Medic.Core.rate_limit_middleware as middleware

        # Default should be 100
        assert middleware.RATE_LIMIT_METRICS_REQUESTS == 100

    def test_docs_rate_limit_env_var_default(self):
        """Test default value for RATE_LIMIT_DOCS_REQUESTS."""
        import Medic.Core.rate_limit_middleware as middleware

        # Default should be 60
        assert middleware.RATE_LIMIT_DOCS_REQUESTS == 60


class TestAllEndpointsRateLimited:
    """Tests verifying ALL endpoints have rate limiting applied."""

    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_no_bypass_prefixes_constant_exists(self):
        """Test that RATE_LIMIT_BYPASS_PREFIXES no longer exists."""
        import Medic.Core.rate_limit_middleware as middleware

        # The bypass constant should no longer exist
        assert not hasattr(middleware, "RATE_LIMIT_BYPASS_PREFIXES")

    def test_no_bypass_function_exists(self):
        """Test that _should_bypass_rate_limit no longer exists."""
        import Medic.Core.rate_limit_middleware as middleware

        # The bypass function should no longer exist
        assert not hasattr(middleware, "_should_bypass_rate_limit")

    def test_health_endpoint_uses_endpoint_specific_config(self, app):
        """Test that health endpoints use endpoint-specific rate limit config."""
        from Medic.Core.rate_limit_middleware import (
            rate_limit,
            RATE_LIMIT_HEALTH_REQUESTS,
        )
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=RATE_LIMIT_HEALTH_REQUESTS,
            remaining=RATE_LIMIT_HEALTH_REQUESTS - 1,
            reset_at=time.time() + 60,
        )

        @app.route("/health/live")
        @rate_limit()
        def health_route():
            return json.dumps({"status": "ok"}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with app.test_client() as client:
                response = client.get("/health/live")
                assert response.status_code == 200
                mock_check.assert_called_once()
                # Verify endpoint-specific config was passed
                call_args = mock_check.call_args
                config_arg = call_args[0][2]
                assert config_arg.management_limit == RATE_LIMIT_HEALTH_REQUESTS

    def test_metrics_endpoint_uses_endpoint_specific_config(self, app):
        """Test that metrics endpoints use endpoint-specific rate limit config."""
        from Medic.Core.rate_limit_middleware import (
            rate_limit,
            RATE_LIMIT_METRICS_REQUESTS,
        )
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=RATE_LIMIT_METRICS_REQUESTS,
            remaining=RATE_LIMIT_METRICS_REQUESTS - 1,
            reset_at=time.time() + 60,
        )

        @app.route("/metrics")
        @rate_limit()
        def metrics_route():
            return "# metrics\n", 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with app.test_client() as client:
                response = client.get("/metrics")
                assert response.status_code == 200
                mock_check.assert_called_once()
                # Verify endpoint-specific config was passed
                call_args = mock_check.call_args
                config_arg = call_args[0][2]
                assert config_arg.management_limit == RATE_LIMIT_METRICS_REQUESTS

    def test_docs_endpoint_uses_endpoint_specific_config(self, app):
        """Test that docs endpoints use endpoint-specific rate limit config."""
        from Medic.Core.rate_limit_middleware import (
            rate_limit,
            RATE_LIMIT_DOCS_REQUESTS,
        )
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=RATE_LIMIT_DOCS_REQUESTS,
            remaining=RATE_LIMIT_DOCS_REQUESTS - 1,
            reset_at=time.time() + 60,
        )

        @app.route("/docs")
        @rate_limit()
        def docs_route():
            return json.dumps({"docs": "here"}), 200

        with patch(
            "Medic.Core.rate_limit_middleware.check_rate_limit"
        ) as mock_check:
            mock_check.return_value = result
            with app.test_client() as client:
                response = client.get("/docs")
                assert response.status_code == 200
                mock_check.assert_called_once()
                # Verify endpoint-specific config was passed
                call_args = mock_check.call_args
                config_arg = call_args[0][2]
                assert config_arg.management_limit == RATE_LIMIT_DOCS_REQUESTS
