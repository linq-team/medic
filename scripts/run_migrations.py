#!/usr/bin/env python3
"""
Database Migration Runner for Medic

Applies SQL migrations from the migrations/ directory in order.
Tracks applied migrations in a `schema_migrations` table.

Usage:
    python -m scripts.run_migrations [--dry-run] [--verbose]

Environment Variables:
    PG_USER: PostgreSQL username
    PG_PASS: PostgreSQL password
    DB_NAME: Database name
    DB_HOST: Database host
    DATABASE_URL: Alternative to individual vars (postgresql://user:pass@host/db)
"""

import os
import sys
import glob
import logging
import argparse
import re
from pathlib import Path
from typing import List, Tuple, Optional
from urllib.parse import urlparse

import psycopg2
from psycopg2 import sql

from Medic.Core.logging_config import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)


def parse_database_url(url: str) -> dict:
    """Parse DATABASE_URL into connection parameters."""
    parsed = urlparse(url)
    return {
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/')
    }


def get_connection_params() -> dict:
    """Get database connection parameters from environment."""
    # Check for DATABASE_URL first (common in containerized environments)
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return parse_database_url(database_url)

    # Fall back to individual environment variables
    return {
        'user': os.environ['PG_USER'],
        'password': os.environ['PG_PASS'],
        'host': os.environ['DB_HOST'],
        'port': int(os.environ.get('DB_PORT', '5432')),
        'database': os.environ['DB_NAME']
    }


def connect_db() -> psycopg2.extensions.connection:
    """Create a database connection."""
    params = get_connection_params()
    logger.info(f"Connecting to database {params['database']} on {params['host']}")
    return psycopg2.connect(**params)


def ensure_migrations_table(conn: psycopg2.extensions.connection) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
    conn.commit()
    logger.info("Ensured schema_migrations table exists")


def get_applied_migrations(conn: psycopg2.extensions.connection) -> set:
    """Get set of already applied migration versions."""
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        return {row[0] for row in cur.fetchall()}


def get_pending_migrations(migrations_dir: Path) -> List[Tuple[str, Path]]:
    """
    Get list of migration files in order.

    Returns list of (version, filepath) tuples sorted by version.
    Migration files should be named: NNN_description.sql
    """
    migrations = []
    pattern = re.compile(r'^(\d+)_.*\.sql$')

    for filepath in sorted(migrations_dir.glob('*.sql')):
        match = pattern.match(filepath.name)
        if match:
            version = match.group(1)
            migrations.append((version, filepath))

    return migrations


def apply_migration(
    conn: psycopg2.extensions.connection,
    version: str,
    filepath: Path,
    dry_run: bool = False
) -> bool:
    """
    Apply a single migration.

    Args:
        conn: Database connection
        version: Migration version (e.g., "001")
        filepath: Path to the SQL file
        dry_run: If True, don't actually apply the migration

    Returns:
        True if migration was applied (or would be in dry-run mode)
    """
    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Applying migration {version}: {filepath.name}")

    migration_sql = filepath.read_text()

    if dry_run:
        logger.debug(f"Migration SQL:\n{migration_sql[:500]}...")
        return True

    try:
        with conn.cursor() as cur:
            # Execute the migration
            cur.execute(migration_sql)

            # Record the migration as applied
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,)
            )

        conn.commit()
        logger.info(f"Successfully applied migration {version}")
        return True

    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Failed to apply migration {version}: {e}")
        raise


def run_migrations(
    migrations_dir: Optional[Path] = None,
    dry_run: bool = False,
    verbose: bool = False
) -> int:
    """
    Run all pending migrations.

    Args:
        migrations_dir: Directory containing migration files
        dry_run: If True, show what would be done without applying
        verbose: If True, enable debug logging

    Returns:
        Number of migrations applied (or would be applied in dry-run)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Default migrations directory
    if migrations_dir is None:
        # Look for migrations relative to the repository root
        repo_root = Path(__file__).parent.parent
        migrations_dir = repo_root / 'migrations'

    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    logger.info(f"Looking for migrations in: {migrations_dir}")

    conn = None
    try:
        conn = connect_db()

        # Acquire an advisory lock to prevent concurrent migration runs.
        # Only one process can hold this lock at a time; others will block
        # until it's released (automatically when the connection closes).
        MIGRATION_LOCK_ID = 8439215  # Arbitrary unique ID for medic migrations
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        logger.info("Acquired migration advisory lock")

        # Ensure migrations table exists
        ensure_migrations_table(conn)

        # Get applied and pending migrations
        applied = get_applied_migrations(conn)
        logger.info(f"Found {len(applied)} previously applied migrations")

        all_migrations = get_pending_migrations(migrations_dir)
        pending = [(v, p) for v, p in all_migrations if v not in applied]

        if not pending:
            logger.info("No pending migrations to apply")
            return 0

        logger.info(f"Found {len(pending)} pending migrations")

        # Apply each pending migration
        applied_count = 0
        for version, filepath in pending:
            apply_migration(conn, version, filepath, dry_run)
            applied_count += 1

        if dry_run:
            logger.info(f"[DRY-RUN] Would apply {applied_count} migrations")
        else:
            logger.info(f"Successfully applied {applied_count} migrations")

        return applied_count

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


def main():
    """Main entry point for the migration runner."""
    parser = argparse.ArgumentParser(
        description='Run database migrations for Medic'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without applying migrations'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--migrations-dir',
        type=Path,
        help='Directory containing migration files (default: migrations/)'
    )

    args = parser.parse_args()

    logger.info("Starting Medic database migration runner")
    logger.info(f"Pod: {os.environ.get('POD_NAME', 'unknown')}")
    logger.info(f"Namespace: {os.environ.get('POD_NAMESPACE', 'unknown')}")

    count = run_migrations(
        migrations_dir=args.migrations_dir,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    sys.exit(0 if count >= 0 else 1)


if __name__ == '__main__':
    main()
