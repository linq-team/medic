"""Secrets encryption and management module for Medic.

This module provides functionality to securely store and retrieve secrets
for use in playbook execution. Secrets are encrypted using AES-256-GCM
with a server-side encryption key.

Security features:
- AES-256-GCM authenticated encryption
- Unique nonce per secret (12 bytes)
- Server-side encryption key from environment variable
- Secrets are only decrypted at execution time
- Key material never logged

Usage in playbooks:
    steps:
      - name: call-api
        type: webhook
        url: https://api.example.com/restart
        headers:
          Authorization: "Bearer ${secrets.API_TOKEN}"
"""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.utils.datetime_helpers import now as get_now

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Environment variable for the encryption key
ENCRYPTION_KEY_ENV_VAR = "MEDIC_SECRETS_KEY"

# AES-256-GCM constants
NONCE_SIZE = 12  # 96 bits for GCM
TAG_SIZE = 16  # 128 bits authentication tag
KEY_SIZE = 32  # 256 bits for AES-256

# Pattern for secret references: ${secrets.SECRET_NAME}
SECRET_PATTERN = re.compile(r"\$\{secrets\.([A-Za-z_][A-Za-z0-9_]*)\}")

# Try to import cryptography, but allow graceful degradation
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography library not available. "
        "Secrets encryption/decryption will be disabled."
    )


class SecretsError(Exception):
    """Base exception for secrets-related errors."""

    pass


class EncryptionKeyError(SecretsError):
    """Raised when the encryption key is missing or invalid."""

    pass


class SecretNotFoundError(SecretsError):
    """Raised when a secret is not found."""

    pass


class DecryptionError(SecretsError):
    """Raised when decryption fails."""

    pass


@dataclass
class Secret:
    """A secret stored in the database."""

    secret_id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without encrypted value)."""
        return {
            "secret_id": self.secret_id,
            "name": self.name,
            "description": self.description,
            "created_at": (self.created_at.isoformat() if self.created_at else None),
            "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
            "created_by": self.created_by,
        }


def _get_encryption_key() -> bytes:
    """
    Get the encryption key from the environment.

    The key should be a 32-byte (256-bit) key encoded as base64.

    Returns:
        The 32-byte encryption key

    Raises:
        EncryptionKeyError: If the key is missing or invalid
    """
    key_b64 = os.environ.get(ENCRYPTION_KEY_ENV_VAR)

    if not key_b64:
        raise EncryptionKeyError(
            f"Encryption key not found. Set {ENCRYPTION_KEY_ENV_VAR} "
            "environment variable with a base64-encoded 32-byte key."
        )

    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise EncryptionKeyError(
            f"Invalid encryption key format: {e}. " "Key must be base64-encoded."
        )

    if len(key) != KEY_SIZE:
        raise EncryptionKeyError(
            f"Encryption key must be {KEY_SIZE} bytes ({KEY_SIZE * 8} bits). "
            f"Got {len(key)} bytes."
        )

    return key


def generate_encryption_key() -> str:
    """
    Generate a new random encryption key.

    Returns:
        Base64-encoded 32-byte key suitable for MEDIC_SECRETS_KEY

    Note:
        This is a utility function for generating keys.
        The generated key should be stored securely.
    """
    key = os.urandom(KEY_SIZE)
    return base64.b64encode(key).decode("utf-8")


def encrypt_secret(plaintext: str) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt a secret value using AES-256-GCM.

    Args:
        plaintext: The secret value to encrypt

    Returns:
        Tuple of (ciphertext, nonce, tag)

    Raises:
        EncryptionKeyError: If the encryption key is not configured
        SecretsError: If encryption fails
    """
    if not CRYPTO_AVAILABLE:
        raise SecretsError(
            "cryptography library not available. "
            "Install with: pip install cryptography"
        )

    key = _get_encryption_key()

    # Generate a unique nonce for this encryption
    nonce = os.urandom(NONCE_SIZE)

    try:
        aesgcm = AESGCM(key)
        # Encrypt and get ciphertext with appended tag
        ciphertext_with_tag = aesgcm.encrypt(
            nonce, plaintext.encode("utf-8"), None  # No additional authenticated data
        )

        # Split ciphertext and tag (tag is last 16 bytes)
        ciphertext = ciphertext_with_tag[:-TAG_SIZE]
        tag = ciphertext_with_tag[-TAG_SIZE:]

        return ciphertext, nonce, tag

    except Exception as e:
        raise SecretsError(f"Encryption failed: {e}")


def decrypt_secret(ciphertext: bytes, nonce: bytes, tag: bytes) -> str:
    """
    Decrypt a secret value using AES-256-GCM.

    Args:
        ciphertext: The encrypted value
        nonce: The nonce used during encryption
        tag: The GCM authentication tag

    Returns:
        The decrypted plaintext value

    Raises:
        EncryptionKeyError: If the encryption key is not configured
        DecryptionError: If decryption fails (tampering or wrong key)
    """
    if not CRYPTO_AVAILABLE:
        raise SecretsError(
            "cryptography library not available. "
            "Install with: pip install cryptography"
        )

    key = _get_encryption_key()

    try:
        aesgcm = AESGCM(key)
        # Reconstruct ciphertext with tag appended
        ciphertext_with_tag = ciphertext + tag
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext_bytes.decode("utf-8")

    except Exception as e:
        raise DecryptionError(
            f"Decryption failed: {e}. "
            "This may indicate tampering or an incorrect encryption key."
        )


# ============================================================================
# Database Operations
# ============================================================================


def create_secret(
    name: str,
    value: str,
    description: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[Secret]:
    """
    Create a new secret in the database.

    Args:
        name: Unique name for the secret (e.g., "API_TOKEN")
        value: The plaintext secret value (will be encrypted)
        description: Optional description
        created_by: Optional user/system that created this secret

    Returns:
        Secret object on success, None on failure

    Raises:
        EncryptionKeyError: If encryption key is not configured
        SecretsError: If encryption fails
    """
    # Validate name format
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        logger.error(
            f"Invalid secret name format: '{name}'. "
            "Must match [A-Za-z_][A-Za-z0-9_]*"
        )
        return None

    # Encrypt the value
    ciphertext, nonce, tag = encrypt_secret(value)

    now = get_now()

    result = db.query_db(
        """
        INSERT INTO medic.secrets
        (name, encrypted_value, nonce, tag, description, created_by,
         created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING secret_id
        """,
        (name, ciphertext, nonce, tag, description, created_by, now, now),
        show_columns=True,
    )

    if not result or result == "[]":
        logger.error(f"Failed to create secret '{name}'")
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    secret_id = rows[0].get("secret_id")

    logger.info(f"Created secret '{name}' (id: {secret_id})")

    return Secret(
        secret_id=secret_id,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
        created_by=created_by,
    )


def update_secret(name: str, value: str, description: Optional[str] = None) -> bool:
    """
    Update an existing secret's value.

    Args:
        name: Name of the secret to update
        value: New plaintext value (will be encrypted)
        description: Optional new description (None to keep existing)

    Returns:
        True if updated, False otherwise

    Raises:
        EncryptionKeyError: If encryption key is not configured
        SecretsError: If encryption fails
    """
    # Encrypt the new value
    ciphertext, nonce, tag = encrypt_secret(value)

    now = get_now()

    # Build update query
    if description is not None:
        result = db.insert_db(
            """
            UPDATE medic.secrets
            SET encrypted_value = %s, nonce = %s, tag = %s,
                description = %s, updated_at = %s
            WHERE name = %s
            """,
            (ciphertext, nonce, tag, description, now, name),
        )
    else:
        result = db.insert_db(
            """
            UPDATE medic.secrets
            SET encrypted_value = %s, nonce = %s, tag = %s, updated_at = %s
            WHERE name = %s
            """,
            (ciphertext, nonce, tag, now, name),
        )

    if result:
        logger.info(f"Updated secret '{name}'")

    return bool(result)


def delete_secret(name: str) -> bool:
    """
    Delete a secret from the database.

    Args:
        name: Name of the secret to delete

    Returns:
        True if deleted, False otherwise
    """
    result = db.insert_db("DELETE FROM medic.secrets WHERE name = %s", (name,))

    if result:
        logger.info(f"Deleted secret '{name}'")

    return bool(result)


def get_secret(name: str) -> Optional[Secret]:
    """
    Get a secret's metadata by name (without decrypted value).

    Args:
        name: Name of the secret

    Returns:
        Secret object if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT secret_id, name, description, created_at, updated_at, created_by
        FROM medic.secrets
        WHERE name = %s
        """,
        (name,),
        show_columns=True,
    )

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return _parse_secret(rows[0])


def get_secret_value(name: str) -> str:
    """
    Get and decrypt a secret's value.

    This should only be called at playbook execution time.

    Args:
        name: Name of the secret

    Returns:
        The decrypted secret value

    Raises:
        SecretNotFoundError: If the secret doesn't exist
        DecryptionError: If decryption fails
    """
    result = db.query_db(
        """
        SELECT encrypted_value, nonce, tag
        FROM medic.secrets
        WHERE name = %s
        """,
        (name,),
        show_columns=True,
    )

    if not result or result == "[]":
        raise SecretNotFoundError(f"Secret '{name}' not found")

    rows = json.loads(str(result))
    if not rows:
        raise SecretNotFoundError(f"Secret '{name}' not found")

    row = rows[0]

    # Handle bytes that may have been JSON-serialized
    encrypted_value = row["encrypted_value"]
    nonce = row["nonce"]
    tag = row["tag"]

    # If stored as memoryview or string, convert to bytes
    if isinstance(encrypted_value, memoryview):
        encrypted_value = bytes(encrypted_value)
    elif isinstance(encrypted_value, str):
        # Handle hex-encoded bytes from JSON serialization
        encrypted_value = bytes.fromhex(encrypted_value.replace("\\x", ""))

    if isinstance(nonce, memoryview):
        nonce = bytes(nonce)
    elif isinstance(nonce, str):
        nonce = bytes.fromhex(nonce.replace("\\x", ""))

    if isinstance(tag, memoryview):
        tag = bytes(tag)
    elif isinstance(tag, str):
        tag = bytes.fromhex(tag.replace("\\x", ""))

    return decrypt_secret(encrypted_value, nonce, tag)


def list_secrets() -> list[Secret]:
    """
    List all secrets (metadata only, no decrypted values).

    Returns:
        List of Secret objects
    """
    result = db.query_db(
        """
        SELECT secret_id, name, description, created_at, updated_at, created_by
        FROM medic.secrets
        ORDER BY name ASC
        """,
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [sec for sec in (_parse_secret(r) for r in rows if r) if sec is not None]


def secret_exists(name: str) -> bool:
    """
    Check if a secret with the given name exists.

    Args:
        name: Name of the secret to check

    Returns:
        True if the secret exists, False otherwise
    """
    result = db.query_db(
        "SELECT 1 FROM medic.secrets WHERE name = %s", (name,), show_columns=True
    )

    if not result or result == "[]":
        return False

    rows = json.loads(str(result))
    return len(rows) > 0


def _parse_secret(data: dict[str, Any]) -> Optional[Secret]:
    """Parse a database row into a Secret object."""
    try:
        created_at_raw = data.get("created_at")
        updated_at_raw = data.get("updated_at")

        # Parse datetime strings if needed
        created_at: datetime
        updated_at: datetime

        if isinstance(created_at_raw, str):
            created_at = datetime.fromisoformat(
                created_at_raw.replace(" ", "T").replace(" CST", "-06:00")
            )
        elif isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        else:
            created_at = get_now()

        if isinstance(updated_at_raw, str):
            updated_at = datetime.fromisoformat(
                updated_at_raw.replace(" ", "T").replace(" CST", "-06:00")
            )
        elif isinstance(updated_at_raw, datetime):
            updated_at = updated_at_raw
        else:
            updated_at = get_now()

        return Secret(
            secret_id=data["secret_id"],
            name=data["name"],
            description=data.get("description"),
            created_at=created_at,
            updated_at=updated_at,
            created_by=data.get("created_by"),
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Failed to parse secret data: {e}")
        return None


# ============================================================================
# Secret Substitution for Playbooks
# ============================================================================


def substitute_secrets(value: Any, context: Optional[dict[str, str]] = None) -> Any:
    """
    Substitute secret references in a value.

    Handles ${secrets.SECRET_NAME} syntax. The value is decrypted
    from the database at the time of substitution.

    Args:
        value: Value to substitute (string, dict, list, or other)
        context: Optional pre-resolved secrets cache to avoid repeated DB calls

    Returns:
        Value with secrets substituted

    Raises:
        SecretNotFoundError: If a referenced secret doesn't exist
        DecryptionError: If decryption fails
    """
    # Use provided context or create a new cache
    secrets_cache = context if context is not None else {}

    if isinstance(value, str):

        def replace_secret(match: re.Match) -> str:
            secret_name = match.group(1)

            # Check cache first
            if secret_name in secrets_cache:
                return secrets_cache[secret_name]

            # Fetch and decrypt from database
            try:
                secret_value = get_secret_value(secret_name)
                secrets_cache[secret_name] = secret_value
                return secret_value
            except (SecretNotFoundError, DecryptionError):
                # Re-raise to let caller handle
                raise

        return SECRET_PATTERN.sub(replace_secret, value)

    elif isinstance(value, dict):
        return {k: substitute_secrets(v, secrets_cache) for k, v in value.items()}

    elif isinstance(value, list):
        return [substitute_secrets(item, secrets_cache) for item in value]

    else:
        return value


def find_secret_references(value: Any) -> list[str]:
    """
    Find all secret references in a value without resolving them.

    Args:
        value: Value to search (string, dict, list, or other)

    Returns:
        List of unique secret names referenced
    """
    references: set = set()

    if isinstance(value, str):
        matches = SECRET_PATTERN.findall(value)
        references.update(matches)

    elif isinstance(value, dict):
        for v in value.values():
            references.update(find_secret_references(v))

    elif isinstance(value, list):
        for item in value:
            references.update(find_secret_references(item))

    return list(references)


def validate_secret_references(value: Any) -> list[str]:
    """
    Validate that all secret references in a value exist.

    Args:
        value: Value to validate (string, dict, list, or other)

    Returns:
        List of secret names that are referenced but don't exist
    """
    references = find_secret_references(value)
    missing = []

    for name in references:
        if not secret_exists(name):
            missing.append(name)

    return missing
