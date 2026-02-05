"""API key generation, hashing, and verification module for Medic."""

import secrets
import logging
# typing imports removed - using built-in types for Python 3.14+

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Argon2 hasher with secure defaults
_hasher = PasswordHasher()

# API key prefix for easy identification
API_KEY_PREFIX = "mdk_"

# Minimum key length in bytes (32 bytes = 256 bits)
MIN_KEY_BYTES = 32


def generate_api_key() -> tuple[str, str]:
    """
    Generate a cryptographically secure API key.

    Returns:
        Tuple of (full_key, key_hash) where:
        - full_key: The complete API key to give to the user (only shown once)
        - key_hash: The argon2 hash to store in the database
    """
    # Generate URL-safe base64 key from 32 bytes (256 bits) of random data
    key_body = secrets.token_urlsafe(MIN_KEY_BYTES)

    # Prefix the key for easy identification
    full_key = f"{API_KEY_PREFIX}{key_body}"

    # Hash the key for storage
    key_hash = hash_api_key(full_key)

    logger.debug("Generated new API key")

    return full_key, key_hash


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using Argon2.

    Args:
        api_key: The plain text API key to hash

    Returns:
        The argon2 hash string
    """
    return _hasher.hash(api_key)


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its stored hash.

    Args:
        api_key: The plain text API key to verify
        key_hash: The stored argon2 hash to verify against

    Returns:
        True if the key matches, False otherwise
    """
    try:
        _hasher.verify(key_hash, api_key)
        return True
    except VerifyMismatchError:
        logger.debug("API key verification failed: key mismatch")
        return False
    except InvalidHashError:
        logger.warning("API key verification failed: invalid hash format")
        return False


def needs_rehash(key_hash: str) -> bool:
    """
    Check if an API key hash needs to be rehashed.

    This can happen when argon2 parameters are updated.

    Args:
        key_hash: The stored argon2 hash to check

    Returns:
        True if the hash should be regenerated, False otherwise
    """
    return _hasher.check_needs_rehash(key_hash)
