"""Authentication middleware for Medic API."""
import json
import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Optional, List, Callable, Any

from flask import request, g

import Medic.Core.database as db
from Medic.Core.api_keys import verify_api_key
from Medic.Core.metrics import record_auth_failure
import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Paths that bypass authentication
AUTH_BYPASS_PREFIXES = (
    "/health",
    "/v1/healthcheck",
    "/metrics",
    "/docs",
)


class AuthError(Exception):
    """Authentication error with status code."""

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _extract_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """
    Extract bearer token from Authorization header.

    Args:
        auth_header: The Authorization header value

    Returns:
        The token if valid Bearer format, None otherwise
    """
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2:
        return None

    scheme, token = parts
    if scheme.lower() != "bearer":
        return None

    return token


def _get_api_key_from_db(api_key: str) -> Optional[dict]:
    """
    Look up API key in database and return key data if found and valid.

    Args:
        api_key: The plain text API key to look up

    Returns:
        Dictionary with key data if found, None otherwise
    """
    # Query all active keys (we need to verify against each hash since we can't
    # do a direct lookup on the hashed value)
    result = db.query_db(
        """
        SELECT api_key_id, name, key_hash, scopes, expires_at, created_at, updated_at
        FROM medic.api_keys
        """,
        show_columns=True,
    )

    if not result:
        return None

    # result is a JSON string when show_columns=True
    keys = json.loads(str(result))

    # SECURITY: Timing attack mitigation
    # We must iterate through ALL keys regardless of whether a match is found.
    # If we returned early on match, an attacker could measure response times
    # to determine when their key matched one stored in the database (faster
    # responses would indicate the matched key appears earlier in the list).
    # By always iterating through all keys, the response time is consistent
    # regardless of whether/when a match occurs.
    matched_key: Optional[dict] = None
    for key_record in keys:
        if verify_api_key(api_key, key_record["key_hash"]):
            matched_key = key_record
            # Continue iterating - do NOT return early

    return matched_key


def _is_key_expired(expires_at: Optional[str]) -> bool:
    """
    Check if an API key is expired.

    Args:
        expires_at: ISO format expiration timestamp or None

    Returns:
        True if expired, False otherwise
    """
    if expires_at is None:
        return False

    # Parse ISO format timestamp
    try:
        if isinstance(expires_at, str):
            # Handle various ISO formats
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            expiry = expires_at

        # Ensure timezone awareness
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        return now > expiry
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse expiration date: {expires_at}, error: {e}")
        # If we can't parse the date, treat it as expired for safety
        return True


def _has_required_scopes(key_scopes: List[str], required_scopes: List[str]) -> bool:
    """
    Check if the API key has all required scopes.

    Args:
        key_scopes: List of scopes the key has
        required_scopes: List of scopes required for the operation

    Returns:
        True if all required scopes are present, False otherwise
    """
    if not required_scopes:
        return True

    # Admin scope grants all permissions
    if "admin" in key_scopes:
        return True

    # Check if all required scopes are present
    return all(scope in key_scopes for scope in required_scopes)


def _should_bypass_auth(path: str) -> bool:
    """
    Check if the request path should bypass authentication.

    Args:
        path: The request path

    Returns:
        True if authentication should be bypassed, False otherwise
    """
    return any(path.startswith(prefix) for prefix in AUTH_BYPASS_PREFIXES)


def authenticate_request(required_scopes: Optional[List[str]] = None) -> Callable:
    """
    Decorator to authenticate API requests using API keys.

    Args:
        required_scopes: List of scopes required for this endpoint.
                        If None, only valid key is required.

    Returns:
        Decorator function

    Usage:
        @authenticate_request(required_scopes=["write"])
        def my_endpoint():
            ...
    """
    if required_scopes is None:
        required_scopes = []

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            # Check if path should bypass authentication
            if _should_bypass_auth(request.path):
                return f(*args, **kwargs)

            # Extract bearer token
            auth_header = request.headers.get("Authorization")
            token = _extract_bearer_token(auth_header)

            if not token:
                logger.debug("No valid bearer token provided")
                return (
                    json.dumps(
                        {
                            "success": False,
                            "message": "Missing or invalid Authorization header. Expected: Bearer <api_key>",
                            "results": "",
                        }
                    ),
                    401,
                )

            # Look up and verify API key
            key_data = _get_api_key_from_db(token)

            if not key_data:
                logger.debug("Invalid API key provided")
                record_auth_failure("invalid_key")
                return (
                    json.dumps(
                        {
                            "success": False,
                            "message": "Invalid API key",
                            "results": "",
                        }
                    ),
                    401,
                )

            # Check expiration
            if _is_key_expired(key_data.get("expires_at")):
                logger.debug(f"Expired API key used: {key_data.get('name')}")
                record_auth_failure("expired_key")
                return (
                    json.dumps(
                        {
                            "success": False,
                            "message": "API key has expired",
                            "results": "",
                        }
                    ),
                    401,
                )

            # Check scopes
            key_scopes = key_data.get("scopes", [])
            if not _has_required_scopes(key_scopes, required_scopes):
                logger.debug(
                    f"Insufficient scopes. Has: {key_scopes}, needs: {required_scopes}"
                )
                record_auth_failure("insufficient_scope")
                return (
                    json.dumps(
                        {
                            "success": False,
                            "message": f"Insufficient permissions. Required scopes: {required_scopes}",
                            "results": "",
                        }
                    ),
                    403,
                )

            # Store key data in Flask's g object for access in route handlers
            g.api_key_id = key_data.get("api_key_id")
            g.api_key_name = key_data.get("name")
            g.api_key_scopes = key_scopes

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_auth(required_scopes: Optional[List[str]] = None) -> Callable:
    """
    Alias for authenticate_request for cleaner syntax.

    Usage:
        @require_auth(["write"])
        def my_endpoint():
            ...
    """
    return authenticate_request(required_scopes=required_scopes)


def verify_request_auth(required_scopes: Optional[List[str]] = None) -> Optional[tuple]:
    """
    Verify authentication for the current request without using decorator.

    This can be called directly in route handlers for more control.

    Args:
        required_scopes: List of scopes required for this operation

    Returns:
        None if authentication successful, tuple of (response_body, status_code) on failure
    """
    if required_scopes is None:
        required_scopes = []

    # Check if path should bypass authentication
    if _should_bypass_auth(request.path):
        return None

    # Extract bearer token
    auth_header = request.headers.get("Authorization")
    token = _extract_bearer_token(auth_header)

    if not token:
        return (
            json.dumps(
                {
                    "success": False,
                    "message": "Missing or invalid Authorization header. Expected: Bearer <api_key>",
                    "results": "",
                }
            ),
            401,
        )

    # Look up and verify API key
    key_data = _get_api_key_from_db(token)

    if not key_data:
        record_auth_failure("invalid_key")
        return (
            json.dumps(
                {
                    "success": False,
                    "message": "Invalid API key",
                    "results": "",
                }
            ),
            401,
        )

    # Check expiration
    if _is_key_expired(key_data.get("expires_at")):
        record_auth_failure("expired_key")
        return (
            json.dumps(
                {
                    "success": False,
                    "message": "API key has expired",
                    "results": "",
                }
            ),
            401,
        )

    # Check scopes
    key_scopes = key_data.get("scopes", [])
    if not _has_required_scopes(key_scopes, required_scopes):
        record_auth_failure("insufficient_scope")
        return (
            json.dumps(
                {
                    "success": False,
                    "message": f"Insufficient permissions. Required scopes: {required_scopes}",
                    "results": "",
                }
            ),
            403,
        )

    # Store key data in Flask's g object
    g.api_key_id = key_data.get("api_key_id")
    g.api_key_name = key_data.get("name")
    g.api_key_scopes = key_scopes

    return None
