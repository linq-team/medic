"""Database cleanup job for Medic - removes old heartbeat events."""

import psycopg2
import os

from Medic.Core.logging_config import configure_logging, get_logger

# Log Setup
configure_logging()
logger = get_logger(__name__)


def connect_db():
    """Create a connection to the PostgreSQL database."""
    user = os.environ["PG_USER"]
    password = os.environ["PG_PASS"]
    dbname = os.environ["DB_NAME"]
    dbhost = os.environ["DB_HOST"]
    try:
        conn = psycopg2.connect(
            user=user, password=password, host=dbhost, port="5432", database=dbname
        )
        logger.log(
            level=20,
            msg=f"Connected to {dbhost}:5432\\{dbname} with user: {user} successfully.",
        )
        return conn
    except psycopg2.Error as e:
        logger.log(
            level=50,
            msg=f"Failed to connect to {dbname} with supplied credentials. "
            f"Is it running and do you have access? Error: {str(e)}",
        )
        raise ConnectionError(str(e))


def cleanup_old_heartbeats(days: int = 30) -> int:
    """
    Delete heartbeat entries older than specified days.

    Args:
        days: Number of days to retain (default 30)

    Returns:
        Number of rows deleted
    """
    client = None
    cur = None
    try:
        client = connect_db()
        cur = client.cursor()
        # Use parameterized interval - note: psycopg2 handles interval properly
        cur.execute(
            'DELETE FROM "heartbeatEvents" WHERE time <= (NOW() - INTERVAL %s)',
            (f"{days} days",),
        )
        rows_deleted = cur.rowcount
        client.commit()
        logger.log(
            level=20,
            msg=f"DB Cleanup: Deleted {rows_deleted} heartbeat events older than {days} days",
        )
        return rows_deleted
    except psycopg2.Error as e:
        logger.log(level=40, msg=f"Unable to perform cleanup: {str(e)}")
        return 0
    finally:
        if cur:
            cur.close()
        if client:
            client.close()


if __name__ == "__main__":
    # Delete heartbeat entries older than 30 days
    rows = cleanup_old_heartbeats(30)
    if rows > 0:
        logger.log(level=20, msg=f"DB Cleanup Results: {rows} rows deleted")
    else:
        logger.log(level=20, msg="DB Cleanup: No old records to delete")
