#!/usr/bin/env python3
"""
CLI tool for creating Medic API keys.

Usage:
    python -m scripts.create_api_key --name "my-key" --scopes read write
    python -m scripts.create_api_key --name "admin" --scopes admin
"""

import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Medic.Core.api_keys import generate_api_key
import Medic.Core.database as db


VALID_SCOPES = {"read", "write", "admin"}


def create_api_key(name: str, scopes: list[str], expires_at: str | None = None) -> str:
    """
    Create a new API key and store it in the database.

    Args:
        name: Unique name for the API key
        scopes: List of scopes (read, write, admin)
        expires_at: Optional expiration timestamp (ISO format)

    Returns:
        The plaintext API key (only shown once)
    """
    # Validate scopes
    invalid_scopes = set(scopes) - VALID_SCOPES
    if invalid_scopes:
        raise ValueError(
            f"Invalid scopes: {invalid_scopes}. Valid scopes: {VALID_SCOPES}"
        )

    # Generate the key
    api_key, key_hash = generate_api_key()

    # Build the insert query
    if expires_at:
        query = """
            INSERT INTO medic.api_keys (name, key_hash, scopes, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                key_hash = EXCLUDED.key_hash,
                scopes = EXCLUDED.scopes,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            RETURNING api_key_id
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
            RETURNING api_key_id
        """
        params = (name, key_hash, scopes)

    result = db.insert_db(query, params)
    if not result:
        raise RuntimeError("Failed to insert API key into database")

    return api_key


def key_exists(name: str) -> bool:
    """Check if an API key with the given name already exists."""
    result = db.query_db(
        "SELECT 1 FROM medic.api_keys WHERE name = %s", (name,), show_columns=False
    )
    return result is not None and len(result) > 0


def main():
    parser = argparse.ArgumentParser(
        description="Create a Medic API key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Create a read-only key:
    python -m scripts.create_api_key --name "readonly-key" --scopes read

  Create an admin key:
    python -m scripts.create_api_key --name "admin" --scopes admin

  Create a key with multiple scopes:
    python -m scripts.create_api_key --name "service-key" --scopes read write

  Create a key with expiration:
    python -m scripts.create_api_key --name "temp-key" --scopes read --expires "2024-12-31T23:59:59Z"
        """,
    )
    parser.add_argument(
        "--name", "-n", required=True, help="Unique name for the API key"
    )
    parser.add_argument(
        "--scopes",
        "-s",
        nargs="+",
        choices=["read", "write", "admin"],
        default=["read"],
        help="Permission scopes for the key (default: read)",
    )
    parser.add_argument(
        "--expires",
        help="Expiration timestamp in ISO format (e.g., 2024-12-31T23:59:59Z)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing key with the same name",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output the API key (for scripting)",
    )

    args = parser.parse_args()

    try:
        # Check if key exists
        if not args.force and key_exists(args.name):
            print(
                f"Error: API key '{args.name}' already exists. Use --force to overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Create the key
        api_key = create_api_key(args.name, args.scopes, args.expires)

        if args.quiet:
            print(api_key)
        else:
            print("\n" + "=" * 60)
            print("API KEY CREATED SUCCESSFULLY")
            print("=" * 60)
            print(f"Name:   {args.name}")
            print(f"Scopes: {', '.join(args.scopes)}")
            if args.expires:
                print(f"Expires: {args.expires}")
            print("-" * 60)
            print(f"API Key: {api_key}")
            print("-" * 60)
            print("⚠️  IMPORTANT: Save this key now! It cannot be retrieved later.")
            print("=" * 60 + "\n")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
