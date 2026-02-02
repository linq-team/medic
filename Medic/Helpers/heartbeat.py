"""Heartbeat model and database operations."""
import Medic.Core.database as db
from datetime import datetime
from typing import Optional
import pytz


class Heartbeat:
    """
    Heartbeat payload representation.

    Sample Heartbeat Payload:
        {
            "heartbeat_name": "my_heartbeat_name",
            "environment": "staging/production",
            "service": "my_service",
            "status": "UP"
        }
    """

    def __init__(self, s_id: int, name: str, current_status: str):
        self.service_id = s_id
        self.heartbeat_name = name
        self.time = datetime.now(pytz.timezone('America/Chicago')).strftime("%Y-%m-%d %H:%M:%S %Z")
        self.status = current_status


def addHeartbeat(heartbeat_obj: Heartbeat) -> bool:
    """
    Add a heartbeat to the database.

    Args:
        heartbeat_obj: Heartbeat object to persist

    Returns:
        True on success, False on failure
    """
    result = db.insert_db(
        'INSERT INTO "heartbeatEvents"(service_id, time, status) VALUES(%s, %s, %s)',
        (heartbeat_obj.service_id, heartbeat_obj.time, heartbeat_obj.status)
    )
    return result


def queryHeartbeats(h_name: str, starttime: Optional[str] = None, endtime: Optional[str] = None) -> Optional[str]:
    """
    Query heartbeats by name and optional time range.

    Args:
        h_name: Heartbeat name to query
        starttime: Optional start time filter
        endtime: Optional end time filter

    Returns:
        JSON string of results or error message
    """
    base_query = """
        SELECT heartbeat_id, services.heartbeat_name, services.service_name,
               time, status, team, priority
        FROM "heartbeatEvents" h
        JOIN services ON services.service_id = h.service_id
        WHERE heartbeat_name = %s
    """

    if starttime is None and endtime is None:
        query = base_query + " ORDER BY time DESC LIMIT 250"
        result = db.query_db(query, (h_name,), show_columns=True)
        return result
    elif starttime is None and endtime is not None:
        return "You must enter an end_time"
    elif starttime is not None and endtime is None:
        return "You must enter a start_time"
    else:
        query = base_query + " AND time >= %s AND time <= %s ORDER BY time DESC LIMIT 250"
        result = db.query_db(query, (h_name, starttime, endtime), show_columns=True)
        return result


def queryLastHeartbeat(heartbeat_name: str) -> Optional[str]:
    """
    Query the most recent heartbeat by name.

    Args:
        heartbeat_name: Heartbeat name to query

    Returns:
        JSON string of the most recent heartbeat
    """
    query = """
        SELECT heartbeat_id, services.heartbeat_name, services.service_name,
               time, status, team, priority
        FROM "heartbeatEvents" h
        JOIN services ON services.service_id = h.service_id
        WHERE services.heartbeat_name = %s
        ORDER BY time DESC
        LIMIT 1
    """
    result = db.query_db(query, (heartbeat_name,), show_columns=True)
    return result
