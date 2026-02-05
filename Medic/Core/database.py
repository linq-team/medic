"""Database connection and query module for Medic."""

import psycopg2
import psycopg2.extras
import os
import logging
import json
from typing import Optional, List, Tuple, Union

import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


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
            level=10,
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


def query_db(
    query: str, params: Optional[Tuple] = None, show_columns: bool = True
) -> Optional[Union[str, List]]:
    """
    Execute a SELECT query and return results.

    Args:
        query: SQL query with %s placeholders for parameters
        params: Tuple of parameters to safely substitute into query
        show_columns: If True, return JSON string; if False, return raw rows

    Returns:
        JSON string of results (if show_columns=True) or list of tuples
    """
    client = None
    cur = None
    try:
        client = connect_db()
        cur = client.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        if show_columns:
            col_names = [elt[0] for elt in cur.description]
            data = []
            for r in rows:
                d = {}
                for c in range(len(col_names)):
                    val = r[c]
                    # Handle datetime serialization
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    d[col_names[c]] = val
                data.append(d)
            return json.dumps(data)
        else:
            return rows
    except (psycopg2.Error, ConnectionError) as e:
        logger.log(
            level=30, msg=f"Unable to perform query. An Error has occurred: {str(e)}"
        )
        return None
    finally:
        if cur:
            cur.close()
        if client:
            client.close()


def insert_db(query: str, params: Optional[Tuple] = None) -> bool:
    """
    Execute an INSERT/UPDATE query.

    Args:
        query: SQL query with %s placeholders for parameters
        params: Tuple of parameters to safely substitute into query

    Returns:
        True on success, False on failure
    """
    client = None
    cur = None
    try:
        client = connect_db()
        cur = client.cursor()
        cur.execute(query, params)
        client.commit()
        return True
    except (psycopg2.Error, ConnectionError) as e:
        logger.log(level=30, msg=f"Unable to perform insert: {str(e)}")
        return False
    finally:
        if cur:
            cur.close()
        if client:
            client.close()
