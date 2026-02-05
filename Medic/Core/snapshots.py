"""Service snapshots module for Medic.

This module provides functionality for creating and restoring service snapshots.
Snapshots capture the complete state of a service before destructive actions,
enabling users to restore previous configurations.

Features:
- Create snapshots before destructive actions (deactivate, activate, mute, unmute, edit, etc.)
- Query snapshots with filters (service_id, action_type, date range)
- Restore services to snapshot state
- Paginated query results

Usage:
    from Medic.Core.snapshots import (
        create_snapshot,
        get_snapshot_by_id,
        query_snapshots,
        restore_snapshot,
        SnapshotActionType,
    )

    # Create a snapshot before a destructive action
    snapshot = create_snapshot(
        service_id=1,
        action_type=SnapshotActionType.DEACTIVATE,
        actor="user@example.com",
    )

    # Query snapshots with pagination
    result = query_snapshots(
        service_id=1,
        action_type="deactivate",
        limit=50,
        offset=0,
    )

    # Restore a snapshot
    success = restore_snapshot(snapshot_id=123, actor="user@example.com")
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.utils.datetime_helpers import (
    now as get_now,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Constants
MAX_SNAPSHOT_QUERY_LIMIT = 250  # Maximum number of snapshots returned per query
MAX_ACTOR_LENGTH = 255  # Maximum length for actor string


class SnapshotActionType(str, Enum):
    """Types of actions that trigger snapshots."""

    DEACTIVATE = "deactivate"
    ACTIVATE = "activate"
    MUTE = "mute"
    UNMUTE = "unmute"
    EDIT = "edit"
    BULK_EDIT = "bulk_edit"
    PRIORITY_CHANGE = "priority_change"
    TEAM_CHANGE = "team_change"
    DELETE = "delete"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid action type."""
        return value in [m.value for m in cls]

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid action type values."""
        return [m.value for m in cls]


@dataclass
class ServiceSnapshot:
    """Represents a service snapshot."""

    snapshot_id: Optional[int]
    service_id: int
    snapshot_data: dict[str, Any]
    action_type: str
    actor: Optional[str]
    created_at: Optional[datetime]
    restored_at: Optional[datetime]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshot_id": self.snapshot_id,
            "service_id": self.service_id,
            "snapshot_data": self.snapshot_data,
            "action_type": self.action_type,
            "actor": self.actor,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "restored_at": (
                self.restored_at.isoformat() if self.restored_at else None
            ),
        }


@dataclass
class SnapshotQueryResult:
    """Result of a snapshot query with pagination info."""

    entries: list[ServiceSnapshot]
    total_count: int
    limit: int
    offset: int
    has_more: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "total_count": self.total_count,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
        }


# ============================================================================
# Snapshot Creation
# ============================================================================


def get_service_data(service_id: int) -> Optional[dict[str, Any]]:
    """
    Get the current service data for snapshot creation.

    Args:
        service_id: The ID of the service to snapshot

    Returns:
        Dictionary with service data, or None if service not found
    """
    query = """
        SELECT service_id, heartbeat_name, service_name, active, alert_interval,
               threshold, team, priority, muted, down, runbook,
               date_added, date_modified, date_muted
        FROM medic.services
        WHERE service_id = %s
        LIMIT 1
    """

    result = db.query_db(query, (service_id,), show_columns=True)

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return rows[0]


def create_snapshot(
    service_id: int,
    action_type: SnapshotActionType,
    actor: Optional[str] = None,
) -> Optional[ServiceSnapshot]:
    """
    Create a snapshot of the current service state.

    Args:
        service_id: The ID of the service to snapshot
        action_type: The type of action triggering the snapshot
        actor: User or system that triggered the action (None for automated)

    Returns:
        ServiceSnapshot object on success, None on failure
    """
    # Get current service data
    service_data = get_service_data(service_id)
    if not service_data:
        logger.log(
            level=30,
            msg=f"Cannot create snapshot: service {service_id} not found",
        )
        return None

    # Insert snapshot
    insert_query = """
        INSERT INTO medic.service_snapshots
            (service_id, snapshot_data, action_type, actor, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING snapshot_id
    """

    created_at = get_now()
    snapshot_data_json = json.dumps(service_data)

    try:
        # Use insert_db to insert and get the ID via a separate query
        success = db.insert_db(
            insert_query,
            (
                service_id,
                snapshot_data_json,
                action_type.value if isinstance(action_type, SnapshotActionType) else action_type,
                actor,
                created_at,
            ),
        )

        if not success:
            logger.log(
                level=40,
                msg=f"Failed to insert snapshot for service {service_id}",
            )
            return None

        # Get the last inserted snapshot ID
        id_query = """
            SELECT snapshot_id FROM medic.service_snapshots
            WHERE service_id = %s
            ORDER BY snapshot_id DESC
            LIMIT 1
        """
        id_result = db.query_db(id_query, (service_id,), show_columns=True)

        snapshot_id = None
        if id_result and id_result != "[]":
            rows = json.loads(str(id_result))
            if rows:
                snapshot_id = rows[0].get("snapshot_id")

        snapshot = ServiceSnapshot(
            snapshot_id=snapshot_id,
            service_id=service_id,
            snapshot_data=service_data,
            action_type=action_type.value if isinstance(action_type, SnapshotActionType) else action_type,
            actor=actor,
            created_at=created_at,
            restored_at=None,
        )

        logger.log(
            level=10,
            msg=f"Created snapshot {snapshot_id} for service {service_id} "
            f"(action: {action_type})",
        )

        return snapshot

    except Exception as e:
        logger.log(
            level=40,
            msg=f"Error creating snapshot for service {service_id}: {e}",
        )
        return None


# ============================================================================
# Snapshot Query
# ============================================================================


def _parse_snapshot(row: dict[str, Any]) -> Optional[ServiceSnapshot]:
    """
    Parse a database row into a ServiceSnapshot object.

    Args:
        row: Dictionary from database query result

    Returns:
        ServiceSnapshot object, or None if parsing fails
    """
    try:
        # Parse snapshot_data - it may be a string or already a dict
        snapshot_data = row.get("snapshot_data", {})
        if isinstance(snapshot_data, str):
            snapshot_data = json.loads(snapshot_data)

        # Parse datetime fields
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        restored_at = row.get("restored_at")
        if isinstance(restored_at, str):
            restored_at = datetime.fromisoformat(restored_at.replace("Z", "+00:00"))

        service_id = row.get("service_id")
        if service_id is None:
            logger.log(
                level=30,
                msg="Snapshot row missing service_id",
            )
            return None

        return ServiceSnapshot(
            snapshot_id=row.get("snapshot_id"),
            service_id=int(service_id),
            snapshot_data=snapshot_data,
            action_type=row.get("action_type", ""),
            actor=row.get("actor"),
            created_at=created_at,
            restored_at=restored_at,
        )
    except Exception as e:
        logger.log(
            level=30,
            msg=f"Error parsing snapshot row: {e}",
        )
        return None


def get_snapshot_by_id(snapshot_id: int) -> Optional[ServiceSnapshot]:
    """
    Get a snapshot by its ID.

    Args:
        snapshot_id: The ID of the snapshot to retrieve

    Returns:
        ServiceSnapshot object, or None if not found
    """
    query = """
        SELECT snapshot_id, service_id, snapshot_data, action_type, actor,
               created_at, restored_at
        FROM medic.service_snapshots
        WHERE snapshot_id = %s
        LIMIT 1
    """

    result = db.query_db(query, (snapshot_id,), show_columns=True)

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return _parse_snapshot(rows[0])


def query_snapshots(
    service_id: Optional[int] = None,
    action_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> SnapshotQueryResult:
    """
    Query snapshots with flexible filtering and pagination.

    Args:
        service_id: Filter by service ID
        action_type: Filter by action type (must be a valid SnapshotActionType value)
        start_date: Filter snapshots on or after this date
        end_date: Filter snapshots on or before this date
        limit: Maximum number of entries to return (default 50, max 250)
        offset: Number of entries to skip for pagination (default 0)

    Returns:
        SnapshotQueryResult with entries, total count, and pagination info
    """
    # Validate and cap limits
    limit = min(max(1, limit), MAX_SNAPSHOT_QUERY_LIMIT)
    offset = max(0, offset)

    # Build the WHERE clause dynamically
    conditions: list[str] = []
    params: list[Any] = []

    if service_id is not None:
        conditions.append("service_id = %s")
        params.append(service_id)

    if action_type is not None:
        # Validate action type
        if SnapshotActionType.is_valid(action_type):
            conditions.append("action_type = %s")
            params.append(action_type)

    if start_date is not None:
        conditions.append("created_at >= %s")
        params.append(start_date)

    if end_date is not None:
        conditions.append("created_at <= %s")
        params.append(end_date)

    # Build WHERE clause
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Get total count for pagination
    count_query = f"""
        SELECT COUNT(*) as total
        FROM medic.service_snapshots
        {where_clause}
    """

    count_result = db.query_db(count_query, tuple(params), show_columns=True)
    total_count = 0
    if count_result and count_result != "[]":
        count_rows = json.loads(str(count_result))
        if count_rows:
            total_count = count_rows[0].get("total", 0)

    # Get the actual entries
    data_query = f"""
        SELECT snapshot_id, service_id, snapshot_data, action_type, actor,
               created_at, restored_at
        FROM medic.service_snapshots
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    data_params = list(params) + [limit, offset]
    data_result = db.query_db(data_query, tuple(data_params), show_columns=True)

    entries: list[ServiceSnapshot] = []
    if data_result and data_result != "[]":
        rows = json.loads(str(data_result))
        entries = [
            entry
            for entry in (_parse_snapshot(r) for r in rows if r)
            if entry is not None
        ]

    has_more = (offset + len(entries)) < total_count

    return SnapshotQueryResult(
        entries=entries,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


# ============================================================================
# Snapshot Restore
# ============================================================================


def restore_snapshot(
    snapshot_id: int,
    actor: Optional[str] = None,
) -> Optional[ServiceSnapshot]:
    """
    Restore a service to a snapshot state.

    This will:
    1. Retrieve the snapshot
    2. Update the service with the snapshot's data
    3. Mark the snapshot as restored

    Args:
        snapshot_id: The ID of the snapshot to restore
        actor: User or system performing the restore (for logging)

    Returns:
        Updated ServiceSnapshot object on success, None on failure
    """
    # Get the snapshot
    snapshot = get_snapshot_by_id(snapshot_id)
    if not snapshot:
        logger.log(
            level=30,
            msg=f"Cannot restore: snapshot {snapshot_id} not found",
        )
        return None

    # Check if snapshot has already been restored
    if snapshot.restored_at is not None:
        logger.log(
            level=30,
            msg=f"Snapshot {snapshot_id} has already been restored",
        )
        return None

    service_id = snapshot.service_id
    data = snapshot.snapshot_data

    # Update the service with snapshot data
    update_query = """
        UPDATE medic.services SET
            service_name = %s,
            active = %s,
            alert_interval = %s,
            threshold = %s,
            team = %s,
            priority = %s,
            muted = %s,
            down = %s,
            runbook = %s,
            date_modified = %s
        WHERE service_id = %s
    """

    now = get_now()
    update_params = (
        data.get("service_name"),
        data.get("active"),
        data.get("alert_interval"),
        data.get("threshold"),
        data.get("team"),
        data.get("priority"),
        data.get("muted"),
        data.get("down"),
        data.get("runbook"),
        now,
        service_id,
    )

    try:
        success = db.insert_db(update_query, update_params)
        if not success:
            logger.log(
                level=40,
                msg=f"Failed to restore service {service_id} from snapshot {snapshot_id}",
            )
            return None

        # Mark snapshot as restored
        restore_query = """
            UPDATE medic.service_snapshots
            SET restored_at = %s
            WHERE snapshot_id = %s
        """
        db.insert_db(restore_query, (now, snapshot_id))

        # Return updated snapshot
        snapshot.restored_at = now

        logger.log(
            level=20,
            msg=f"Restored service {service_id} from snapshot {snapshot_id} "
            f"(actor: {actor})",
        )

        return snapshot

    except Exception as e:
        logger.log(
            level=40,
            msg=f"Error restoring snapshot {snapshot_id}: {e}",
        )
        return None
