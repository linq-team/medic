"""Rate limiting middleware for Medic API.

All endpoints are rate limited to prevent abuse and DoS attacks.
Endpoint-specific rate limits can be configured via environment variables.
"""

import json
import logging
import os
from functools import wraps
from collections.abc import Callable
from typing import Any, Optional

from flask import request, g, Response

from Medic.Core.rate_limiter import (
    check_rate_limit,
    RateLimitConfig,
    RateLimitResult,
)
import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Endpoint-specific rate limits (requests per minute).
# These can be configured via environment variables.
RATE_LIMIT_HEALTH_REQUESTS: int = int(
    os.environ.get("RATE_LIMIT_HEALTH_REQUESTS", "1000")
)
RATE_LIMIT_METRICS_REQUESTS: int = int(
    os.environ.get("RATE_LIMIT_METRICS_REQUESTS", "100")
)
RATE_LIMIT_DOCS_REQUESTS: int = int(os.environ.get("RATE_LIMIT_DOCS_REQUESTS", "60"))

# Endpoint types for rate limiting
ENDPOINT_TYPE_HEALTH: str = "health"
ENDPOINT_TYPE_METRICS: str = "metrics"
ENDPOINT_TYPE_DOCS: str = "docs"

# NOTE: No endpoints bypass rate limiting. All endpoints have rate limits
# applied, including health, metrics, and docs endpoints. This is a security
# best practice to prevent abuse and DoS attacks.


def _get_endpoint_rate_limit_config(endpoint_type: str) -> RateLimitConfig:
    """
    Get rate limit configuration for a specific endpoint type.

    Args:
        endpoint_type: The type of endpoint (health, metrics, docs, etc.)

    Returns:
        RateLimitConfig with appropriate limits for the endpoint type
    """
    if endpoint_type == ENDPOINT_TYPE_HEALTH:
        return RateLimitConfig(
            management_limit=RATE_LIMIT_HEALTH_REQUESTS,
            heartbeat_limit=RATE_LIMIT_HEALTH_REQUESTS,
        )
    elif endpoint_type == ENDPOINT_TYPE_METRICS:
        return RateLimitConfig(
            management_limit=RATE_LIMIT_METRICS_REQUESTS,
            heartbeat_limit=RATE_LIMIT_METRICS_REQUESTS,
        )
    elif endpoint_type == ENDPOINT_TYPE_DOCS:
        return RateLimitConfig(
            management_limit=RATE_LIMIT_DOCS_REQUESTS,
            heartbeat_limit=RATE_LIMIT_DOCS_REQUESTS,
        )
    # For heartbeat and management, use the default config
    return RateLimitConfig()


def _get_api_key_id() -> Optional[str]:
    """
    Get the API key ID from Flask's g context.

    The auth middleware should have already set this.

    Returns:
        API key ID if authenticated, None otherwise
    """
    return getattr(g, "api_key_id", None)


def _create_rate_limit_response(
    result: RateLimitResult,
) -> tuple[str, int, dict]:
    """
    Create a 429 Too Many Requests response.

    Args:
        result: The rate limit result with metadata

    Returns:
        Tuple of (response_body, status_code, headers)
    """
    headers = _create_rate_limit_headers(result)

    body = json.dumps(
        {
            "success": False,
            "message": "Rate limit exceeded. Please try again later.",
            "results": "",
            "retry_after": result.retry_after,
        }
    )

    return body, 429, headers


def _create_rate_limit_headers(result: RateLimitResult) -> dict:
    """
    Create rate limit headers from a RateLimitResult.

    Args:
        result: The rate limit result

    Returns:
        Dictionary of rate limit headers
    """
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(int(result.reset_at)),
    }

    if result.retry_after is not None:
        headers["Retry-After"] = str(result.retry_after)

    return headers


def _determine_endpoint_type(path: str) -> str:
    """
    Determine the endpoint type for rate limiting purposes.

    Args:
        path: The request path

    Returns:
        One of: "health", "metrics", "docs", "heartbeat", or "management"
    """
    # Health endpoints (high rate limit for monitoring)
    health_prefixes = (
        "/health",
        "/v1/healthcheck",
    )
    if any(path.startswith(prefix) for prefix in health_prefixes):
        return ENDPOINT_TYPE_HEALTH

    # Metrics endpoint (moderate rate limit for scraping)
    if path.startswith("/metrics"):
        return ENDPOINT_TYPE_METRICS

    # Documentation endpoints (low rate limit)
    if path.startswith("/docs"):
        return ENDPOINT_TYPE_DOCS

    # Heartbeat endpoints (default heartbeat rate limit)
    heartbeat_prefixes = (
        "/heartbeat",
        "/v1/heartbeat",
        "/v2/heartbeat",
    )
    if any(path.startswith(prefix) for prefix in heartbeat_prefixes):
        return "heartbeat"

    return "management"


def rate_limit(
    endpoint_type: Optional[str] = None,
    config: Optional[RateLimitConfig] = None,
) -> Callable:
    """
    Decorator to apply rate limiting to API endpoints.

    Should be applied AFTER authentication middleware so that
    the API key ID is available in Flask's g context.

    All endpoints are rate limited - there are no bypasses. Different endpoint
    types have different rate limits configured via environment variables.

    Args:
        endpoint_type: Type of endpoint - "health", "metrics", "docs",
                      "heartbeat", or "management". If None, auto-detects.
        config: Optional custom rate limit configuration

    Returns:
        Decorator function

    Usage:
        @authenticate_request()
        @rate_limit()
        def my_endpoint():
            ...

        @authenticate_request()
        @rate_limit(endpoint_type="heartbeat")
        def heartbeat_endpoint():
            ...
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            # Get API key ID for rate limiting bucket
            api_key_id = _get_api_key_id()

            if api_key_id is None:
                # No API key - use IP address as fallback for rate limiting.
                # This handles unauthenticated requests.
                api_key_id = f"ip:{request.remote_addr}"
                logger.debug(f"No API key, using IP for rate limiting: {api_key_id}")

            # Determine endpoint type
            etype = endpoint_type
            if etype is None:
                etype = _determine_endpoint_type(request.path)

            # Use custom config if provided, else get endpoint-specific config
            effective_config = config
            if effective_config is None:
                effective_config = _get_endpoint_rate_limit_config(etype)

            # Check rate limit
            result = check_rate_limit(str(api_key_id), etype, effective_config)

            if not result.allowed:
                logger.debug(
                    f"Rate limit exceeded for {api_key_id} on {etype}. "
                    f"Limit: {result.limit}, Reset: {result.reset_at}"
                )
                body, status, headers = _create_rate_limit_response(result)
                response = Response(body, status=status, mimetype="application/json")
                for key, value in headers.items():
                    response.headers[key] = value
                return response

            # Request allowed - execute the handler
            response = f(*args, **kwargs)

            # Add rate limit headers to successful response
            # Handle both tuple responses and Response objects
            if isinstance(response, tuple):
                body = response[0]
                status = response[1] if len(response) > 1 else 200
                existing_headers = response[2] if len(response) > 2 else {}

                # Merge rate limit headers with existing headers
                headers = _create_rate_limit_headers(result)
                if isinstance(existing_headers, dict):
                    headers.update(existing_headers)

                return body, status, headers
            elif isinstance(response, Response):
                # Add headers to Response object
                headers = _create_rate_limit_headers(result)
                for key, value in headers.items():
                    response.headers[key] = value
                return response
            else:
                # Plain string response - wrap it
                headers = _create_rate_limit_headers(result)
                resp = Response(response, status=200, mimetype="application/json")
                for key, value in headers.items():
                    resp.headers[key] = value
                return resp

        return decorated_function

    return decorator


def require_rate_limit(
    endpoint_type: Optional[str] = None,
    config: Optional[RateLimitConfig] = None,
) -> Callable:
    """
    Alias for rate_limit for cleaner syntax.

    Usage:
        @authenticate_request()
        @require_rate_limit()
        def my_endpoint():
            ...
    """
    return rate_limit(endpoint_type=endpoint_type, config=config)


def verify_rate_limit(
    endpoint_type: Optional[str] = None,
    config: Optional[RateLimitConfig] = None,
    key_override: Optional[str] = None,
) -> Optional[tuple[str, int, dict]]:
    """
    Verify rate limit for the current request without using decorator.

    This can be called directly in route handlers for more control.
    All endpoints are rate limited - no bypasses.

    Args:
        endpoint_type: Type of endpoint - "health", "metrics", "docs",
                      "heartbeat", or "management"
        config: Optional custom rate limit configuration
        key_override: Optional override for the rate limit key (e.g., for
                     webhook endpoints that don't use API keys)

    Returns:
        None if rate limit not exceeded,
        tuple of (response_body, status_code, headers) if exceeded
    """
    # Determine rate limit key
    if key_override is not None:
        rate_key = key_override
    else:
        # Get API key ID for rate limiting bucket
        api_key_id = _get_api_key_id()
        if api_key_id is None:
            rate_key = f"ip:{request.remote_addr}"
        else:
            rate_key = str(api_key_id)

    # Determine endpoint type
    etype = endpoint_type
    if etype is None:
        etype = _determine_endpoint_type(request.path)

    # Use custom config if provided, otherwise get endpoint-specific config
    effective_config = config
    if effective_config is None:
        effective_config = _get_endpoint_rate_limit_config(etype)

    # Check rate limit
    result = check_rate_limit(rate_key, etype, effective_config)

    if not result.allowed:
        return _create_rate_limit_response(result)

    # Store result in g for later header addition
    g.rate_limit_result = result

    return None


def get_rate_limit_headers() -> dict:
    """
    Get rate limit headers for the current request.

    Should be called after verify_rate_limit() to get headers
    for adding to the response.

    Returns:
        Dictionary of rate limit headers, or empty dict if no result
    """
    result = getattr(g, "rate_limit_result", None)
    if result is None:
        return {}
    return _create_rate_limit_headers(result)
