#!/usr/bin/env python3
"""
Initialize API keys from environment variables.

This script is called on application startup to sync API keys from environment
variables into the database. It supports both production (secrets from External
Secrets/AWS) and local development (auto-generated keys).

Environment Variables:
    MEDIC_ADMIN_API_KEY: Admin API key to sync (from External Secrets in prod)
    MEDIC_AUTO_CREATE_ADMIN_KEY: If "true", auto-create admin key for local dev

Usage:
    # Called automatically on app startup, or manually:
    python -m scripts.init_api_keys

    # Programmatically:
    from scripts.init_api_keys import init_api_keys
    init_api_keys()
"""

import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def _get_db():
    """Import database module (lazy to avoid import errors during collection)."""
    import Medic.Core.database as db

    return db


def _get_api_keys():
    """Import api_keys module (lazy)."""
    from Medic.Core.api_keys import hash_api_key, generate_api_key

    return hash_api_key, generate_api_key


def key_exists(db, name: str) -> bool:
    """Check if an API key with the given name exists."""
    result = db.query_db(
        "SELECT 1 FROM medic.api_keys WHERE name = %s", (name,), show_columns=False
    )
    return result is not None and len(result) > 0


def upsert_api_key(
    db, name: str, key_hash: str, scopes: list[str], expires_at: str | None = None
) -> bool:
    """Upsert an API key into the database."""
    if expires_at:
        query = """
            INSERT INTO medic.api_keys (name, key_hash, scopes, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                key_hash = EXCLUDED.key_hash,
                scopes = EXCLUDED.scopes,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
        """
        params = (name, key_hash, scopes, expires_at)
    else:
        query = """
            INSERT INTO medic.api_keys (name, key_hash, scopes)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                key_hash = EXCLUDED.key_hash,
                scopes = EXCLUDED.scopes,
                updated_at = NOW()
        """
        params = (name, key_hash, scopes)

    return db.insert_db(query, params)


def sync_admin_key_from_env() -> bool:
    """
    Sync admin API key from MEDIC_ADMIN_API_KEY environment variable.

    Returns:
        True if key was synced, False if env var not set or sync failed
    """
    admin_key = os.environ.get("MEDIC_ADMIN_API_KEY", "").strip()
    if not admin_key:
        logger.debug("MEDIC_ADMIN_API_KEY not set, skipping admin key sync")
        return False

    logger.info("Syncing admin API key from environment")

    try:
        db = _get_db()
        hash_api_key, _ = _get_api_keys()

        key_hash = hash_api_key(admin_key)
        success = upsert_api_key(
            db, name="admin", key_hash=key_hash, scopes=["read", "write", "admin"]
        )

        if success:
            logger.info("Admin API key synced successfully")
        else:
            logger.error("Failed to sync admin API key to database")

        return success

    except Exception as e:
        logger.error(f"Error syncing admin API key: {e}")
        return False


def auto_create_admin_key() -> str | None:
    """
    Auto-create an admin API key for local development.

    Only creates a key if:
    - MEDIC_AUTO_CREATE_ADMIN_KEY is "true"
    - No admin key exists in the database

    Returns:
        The generated API key if created, None otherwise
    """
    auto_create = os.environ.get("MEDIC_AUTO_CREATE_ADMIN_KEY", "").lower() == "true"
    if not auto_create:
        logger.debug("MEDIC_AUTO_CREATE_ADMIN_KEY not set, skipping auto-create")
        return None

    try:
        db = _get_db()
        hash_api_key, generate_api_key = _get_api_keys()

        # Check if admin key already exists
        if key_exists(db, "admin"):
            logger.info("Admin key already exists, skipping auto-create")
            return None

        # Generate new key
        api_key, key_hash = generate_api_key()

        success = upsert_api_key(
            db, name="admin", key_hash=key_hash, scopes=["read", "write", "admin"]
        )

        if success:
            logger.info("=" * 60)
            logger.info("AUTO-CREATED ADMIN API KEY FOR LOCAL DEVELOPMENT")
            logger.info("=" * 60)
            logger.info(f"API Key: {api_key}")
            logger.info("=" * 60)
            logger.info("Use this key to log into the Medic UI")
            logger.info("This key is only shown once!")
            logger.info("=" * 60)
            return api_key
        else:
            logger.error("Failed to auto-create admin API key")
            return None

    except Exception as e:
        logger.error(f"Error auto-creating admin API key: {e}")
        return None


def init_api_keys() -> bool:
    """
    Initialize API keys on application startup.

    Priority:
    1. Sync admin key from MEDIC_ADMIN_API_KEY (production)
    2. Auto-create admin key if MEDIC_AUTO_CREATE_ADMIN_KEY=true (local dev)

    Returns:
        True if initialization succeeded, False otherwise
    """
    logger.info("Initializing API keys...")

    # Try to sync from env var first (production path)
    if sync_admin_key_from_env():
        return True

    # Fall back to auto-create for local dev
    if auto_create_admin_key():
        return True

    logger.info("No API key initialization performed")
    return True  # Not an error if no keys to sync


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    success = init_api_keys()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
