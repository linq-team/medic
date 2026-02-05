"""Remediation audit log module for Medic.

This module provides functionality to record an immutable audit trail of all
actions during playbook execution. Every significant action is logged for
compliance, debugging, and analytics purposes.

Action types:
- execution_started: Playbook execution was initiated
- step_completed: A step finished successfully
- step_failed: A step failed
- approval_requested: Approval was requested for execution
- approved: Execution was approved by a user
- rejected: Execution was rejected by a user
- execution_completed: Playbook execution completed successfully
- execution_failed: Playbook execution failed

Usage:
    from Medic.Core.audit_log import (
        log_execution_started,
        log_step_completed,
        log_step_failed,
        log_approval_requested,
        log_approved,
        log_rejected,
        log_execution_completed,
        log_execution_failed,
        get_audit_logs_for_execution,
        query_audit_logs,
    )

    # Log execution start
    log_execution_started(
        execution_id=123,
        playbook_id=1,
        playbook_name="restart-service",
        service_id=42,
        service_name="worker-prod-01",
        trigger="heartbeat_failure",
    )

    # Log step completion
    log_step_completed(
        execution_id=123,
        step_name="restart",
        step_index=0,
        output="Service restarted successfully",
        duration_ms=1500,
    )

    # Query audit logs with filters
    results = query_audit_logs(
        execution_id=123,
        action_type="step_completed",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 31),
        limit=50,
        offset=0,
    )
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
    parse_datetime,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


class AuditActionType(str, Enum):
    """Types of audit log actions."""

    EXECUTION_STARTED = "execution_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid action type."""
        return value in [m.value for m in cls]


@dataclass
class AuditLogEntry:
    """Represents an audit log entry."""

    log_id: Optional[int]
    execution_id: int
    action_type: AuditActionType
    details: dict[str, Any]
    actor: Optional[str]
    timestamp: datetime
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "log_id": self.log_id,
            "execution_id": self.execution_id,
            "action_type": self.action_type.value,
            "details": self.details,
            "actor": self.actor,
            "timestamp": (self.timestamp.isoformat() if self.timestamp else None),
            "created_at": (self.created_at.isoformat() if self.created_at else None),
        }


# ============================================================================
# Core Logging Function
# ============================================================================


def create_audit_log_entry(
    execution_id: int,
    action_type: AuditActionType,
    details: dict[str, Any],
    actor: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Optional[AuditLogEntry]:
    """
    Create an audit log entry in the database.

    Args:
        execution_id: ID of the playbook execution
        action_type: Type of action being logged
        details: Action-specific details as a dictionary
        actor: User or system that performed the action (None for automated)
        timestamp: Time of the action (defaults to now)

    Returns:
        AuditLogEntry object on success, None on failure
    """
    now = timestamp or get_now()
    created_at = get_now()

    # Serialize details to JSON
    details_json = json.dumps(details)

    result = db.query_db(
        """
        INSERT INTO medic.remediation_audit_log
        (execution_id, action_type, details, actor, timestamp, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING log_id
        """,
        (execution_id, action_type.value, details_json, actor, now, created_at),
        show_columns=True,
    )

    if not result or result == "[]":
        logger.log(
            level=40,
            msg=f"Failed to create audit log entry for execution {execution_id}, "
            f"action {action_type.value}",
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    log_id = rows[0].get("log_id")

    logger.log(
        level=10,
        msg=f"Created audit log entry {log_id}: execution={execution_id}, "
        f"action={action_type.value}",
    )

    return AuditLogEntry(
        log_id=log_id,
        execution_id=execution_id,
        action_type=action_type,
        details=details,
        actor=actor,
        timestamp=now,
        created_at=created_at,
    )


# ============================================================================
# Convenience Logging Functions
# ============================================================================


def log_execution_started(
    execution_id: int,
    playbook_id: int,
    playbook_name: str,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None,
    trigger: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook execution has started.

    Args:
        execution_id: ID of the playbook execution
        playbook_id: ID of the playbook
        playbook_name: Name of the playbook
        service_id: Optional service ID
        service_name: Optional service name
        trigger: What triggered the execution (e.g., "heartbeat_failure", "manual")
        context: Optional execution context variables

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {
        "playbook_id": playbook_id,
        "playbook_name": playbook_name,
    }

    if service_id is not None:
        details["service_id"] = service_id
    if service_name:
        details["service_name"] = service_name
    if trigger:
        details["trigger"] = trigger
    if context:
        details["context"] = context

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.EXECUTION_STARTED,
        details=details,
    )


def log_step_completed(
    execution_id: int,
    step_name: str,
    step_index: int,
    step_type: Optional[str] = None,
    output: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook step completed successfully.

    Args:
        execution_id: ID of the playbook execution
        step_name: Name of the step
        step_index: Zero-based index of the step
        step_type: Type of step (webhook, script, wait, condition)
        output: Step output (may be truncated)
        duration_ms: Step duration in milliseconds

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {
        "step_name": step_name,
        "step_index": step_index,
    }

    if step_type:
        details["step_type"] = step_type
    if output:
        # Truncate output to prevent excessive storage
        details["output"] = output[:4096] if len(output) > 4096 else output
    if duration_ms is not None:
        details["duration_ms"] = duration_ms

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.STEP_COMPLETED,
        details=details,
    )


def log_step_failed(
    execution_id: int,
    step_name: str,
    step_index: int,
    step_type: Optional[str] = None,
    error_message: Optional[str] = None,
    output: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook step failed.

    Args:
        execution_id: ID of the playbook execution
        step_name: Name of the step
        step_index: Zero-based index of the step
        step_type: Type of step (webhook, script, wait, condition)
        error_message: Error message describing the failure
        output: Step output (may be truncated)
        duration_ms: Step duration in milliseconds

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {
        "step_name": step_name,
        "step_index": step_index,
    }

    if step_type:
        details["step_type"] = step_type
    if error_message:
        details["error_message"] = (
            error_message[:2048] if len(error_message) > 2048 else error_message
        )
    if output:
        details["output"] = output[:4096] if len(output) > 4096 else output
    if duration_ms is not None:
        details["duration_ms"] = duration_ms

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.STEP_FAILED,
        details=details,
    )


def log_approval_requested(
    execution_id: int,
    playbook_name: str,
    service_name: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    channel_id: Optional[str] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that approval was requested for a playbook execution.

    Args:
        execution_id: ID of the playbook execution
        playbook_name: Name of the playbook
        service_name: Optional service name
        expires_at: Optional expiration time for the request
        channel_id: Slack channel where approval was requested

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {
        "playbook_name": playbook_name,
    }

    if service_name:
        details["service_name"] = service_name
    if expires_at:
        details["expires_at"] = expires_at.isoformat()
    if channel_id:
        details["channel_id"] = channel_id

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.APPROVAL_REQUESTED,
        details=details,
    )


def log_approved(
    execution_id: int,
    approved_by: str,
    playbook_name: Optional[str] = None,
    service_name: Optional[str] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook execution was approved.

    Args:
        execution_id: ID of the playbook execution
        approved_by: User ID who approved
        playbook_name: Optional playbook name
        service_name: Optional service name

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {}

    if playbook_name:
        details["playbook_name"] = playbook_name
    if service_name:
        details["service_name"] = service_name

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.APPROVED,
        details=details,
        actor=approved_by,
    )


def log_rejected(
    execution_id: int,
    rejected_by: str,
    playbook_name: Optional[str] = None,
    service_name: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook execution was rejected.

    Args:
        execution_id: ID of the playbook execution
        rejected_by: User ID who rejected
        playbook_name: Optional playbook name
        service_name: Optional service name
        reason: Optional rejection reason

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {}

    if playbook_name:
        details["playbook_name"] = playbook_name
    if service_name:
        details["service_name"] = service_name
    if reason:
        details["reason"] = reason

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.REJECTED,
        details=details,
        actor=rejected_by,
    )


def log_execution_completed(
    execution_id: int,
    playbook_name: str,
    steps_completed: int,
    total_duration_ms: Optional[int] = None,
    service_name: Optional[str] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook execution completed successfully.

    Args:
        execution_id: ID of the playbook execution
        playbook_name: Name of the playbook
        steps_completed: Number of steps that were completed
        total_duration_ms: Total execution duration in milliseconds
        service_name: Optional service name

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {
        "playbook_name": playbook_name,
        "steps_completed": steps_completed,
    }

    if total_duration_ms is not None:
        details["total_duration_ms"] = total_duration_ms
    if service_name:
        details["service_name"] = service_name

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.EXECUTION_COMPLETED,
        details=details,
    )


def log_execution_failed(
    execution_id: int,
    playbook_name: str,
    error_message: str,
    failed_step_name: Optional[str] = None,
    failed_step_index: Optional[int] = None,
    steps_completed: Optional[int] = None,
    total_duration_ms: Optional[int] = None,
    service_name: Optional[str] = None,
) -> Optional[AuditLogEntry]:
    """
    Log that a playbook execution failed.

    Args:
        execution_id: ID of the playbook execution
        playbook_name: Name of the playbook
        error_message: Error message describing the failure
        failed_step_name: Name of the step that failed
        failed_step_index: Index of the step that failed
        steps_completed: Number of steps completed before failure
        total_duration_ms: Total execution duration in milliseconds
        service_name: Optional service name

    Returns:
        AuditLogEntry on success, None on failure
    """
    details: dict[str, Any] = {
        "playbook_name": playbook_name,
        "error_message": (
            error_message[:2048] if len(error_message) > 2048 else error_message
        ),
    }

    if failed_step_name:
        details["failed_step_name"] = failed_step_name
    if failed_step_index is not None:
        details["failed_step_index"] = failed_step_index
    if steps_completed is not None:
        details["steps_completed"] = steps_completed
    if total_duration_ms is not None:
        details["total_duration_ms"] = total_duration_ms
    if service_name:
        details["service_name"] = service_name

    return create_audit_log_entry(
        execution_id=execution_id,
        action_type=AuditActionType.EXECUTION_FAILED,
        details=details,
    )


# ============================================================================
# Query Functions
# ============================================================================


def get_audit_logs_for_execution(
    execution_id: int, limit: int = 100
) -> list[AuditLogEntry]:
    """
    Get all audit log entries for an execution.

    Args:
        execution_id: The execution ID
        limit: Maximum number of entries to return

    Returns:
        List of AuditLogEntry objects ordered by timestamp
    """
    result = db.query_db(
        """
        SELECT log_id, execution_id, action_type, details, actor, timestamp,
               created_at
        FROM medic.remediation_audit_log
        WHERE execution_id = %s
        ORDER BY timestamp ASC
        LIMIT %s
        """,
        (execution_id, limit),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [
        entry
        for entry in (_parse_audit_log_entry(r) for r in rows if r)
        if entry is not None
    ]


def get_audit_logs_by_action_type(
    action_type: AuditActionType, limit: int = 100
) -> list[AuditLogEntry]:
    """
    Get audit log entries by action type.

    Args:
        action_type: The action type to filter by
        limit: Maximum number of entries to return

    Returns:
        List of AuditLogEntry objects ordered by timestamp (newest first)
    """
    result = db.query_db(
        """
        SELECT log_id, execution_id, action_type, details, actor, timestamp,
               created_at
        FROM medic.remediation_audit_log
        WHERE action_type = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (action_type.value, limit),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [
        entry
        for entry in (_parse_audit_log_entry(r) for r in rows if r)
        if entry is not None
    ]


def get_audit_logs_by_actor(actor: str, limit: int = 100) -> list[AuditLogEntry]:
    """
    Get audit log entries by actor (user who performed the action).

    Args:
        actor: The actor ID to filter by
        limit: Maximum number of entries to return

    Returns:
        List of AuditLogEntry objects ordered by timestamp (newest first)
    """
    result = db.query_db(
        """
        SELECT log_id, execution_id, action_type, details, actor, timestamp,
               created_at
        FROM medic.remediation_audit_log
        WHERE actor = %s
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (actor, limit),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [
        entry
        for entry in (_parse_audit_log_entry(r) for r in rows if r)
        if entry is not None
    ]


def _parse_audit_log_entry(data: dict[str, Any]) -> Optional[AuditLogEntry]:
    """Parse a database row into an AuditLogEntry object."""
    try:
        timestamp = data.get("timestamp")
        created_at = data.get("created_at")
        details = data.get("details", {})

        # Parse timestamps
        if isinstance(timestamp, str):
            timestamp = parse_datetime(timestamp)
        if isinstance(created_at, str):
            created_at = parse_datetime(created_at)

        # Parse details from JSON if needed
        if isinstance(details, str):
            details = json.loads(details)

        # timestamp should always be set; if parsing failed, use current time
        if timestamp is None:
            timestamp = get_now()

        return AuditLogEntry(
            log_id=data["log_id"],
            execution_id=data["execution_id"],
            action_type=AuditActionType(data["action_type"]),
            details=details,
            actor=data.get("actor"),
            timestamp=timestamp,
            created_at=created_at,
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        logger.log(level=30, msg=f"Failed to parse audit log entry data: {e}")
        return None


# ============================================================================
# Comprehensive Query Functions for API
# ============================================================================


@dataclass
class AuditLogQueryResult:
    """Result of an audit log query with pagination info."""

    entries: list[AuditLogEntry]
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


def query_audit_logs(
    execution_id: Optional[int] = None,
    service_id: Optional[int] = None,
    action_type: Optional[str] = None,
    actor: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditLogQueryResult:
    """
    Query audit logs with flexible filtering and pagination.

    Args:
        execution_id: Filter by execution ID
        service_id: Filter by service ID (via details->>'service_id')
        action_type: Filter by action type (must be a valid AuditActionType value)
        actor: Filter by actor (user who performed action)
        start_date: Filter logs on or after this date
        end_date: Filter logs on or before this date
        limit: Maximum number of entries to return (default 50, max 250)
        offset: Number of entries to skip for pagination (default 0)

    Returns:
        AuditLogQueryResult with entries, total count, and pagination info
    """
    # Validate and cap limits
    limit = min(max(1, limit), 250)
    offset = max(0, offset)

    # Build the WHERE clause dynamically
    conditions: list[str] = []
    params: list[Any] = []

    if execution_id is not None:
        conditions.append("execution_id = %s")
        params.append(execution_id)

    if service_id is not None:
        # Service ID is stored in the details JSONB field
        conditions.append("(details->>'service_id')::int = %s")
        params.append(service_id)

    if action_type is not None:
        # Validate action type
        if AuditActionType.is_valid(action_type):
            conditions.append("action_type = %s")
            params.append(action_type)

    if actor is not None:
        conditions.append("actor = %s")
        params.append(actor)

    if start_date is not None:
        conditions.append("timestamp >= %s")
        params.append(start_date)

    if end_date is not None:
        conditions.append("timestamp <= %s")
        params.append(end_date)

    # Build WHERE clause
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Get total count for pagination
    count_query = f"""
        SELECT COUNT(*) as total
        FROM medic.remediation_audit_log
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
        SELECT log_id, execution_id, action_type, details, actor, timestamp,
               created_at
        FROM medic.remediation_audit_log
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT %s OFFSET %s
    """

    data_params = list(params) + [limit, offset]
    data_result = db.query_db(data_query, tuple(data_params), show_columns=True)

    entries: list[AuditLogEntry] = []
    if data_result and data_result != "[]":
        rows = json.loads(str(data_result))
        entries = [
            entry
            for entry in (_parse_audit_log_entry(r) for r in rows if r)
            if entry is not None
        ]

    has_more = (offset + len(entries)) < total_count

    return AuditLogQueryResult(
        entries=entries,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


def audit_logs_to_csv(entries: list[AuditLogEntry]) -> str:
    """
    Convert audit log entries to CSV format.

    Args:
        entries: List of AuditLogEntry objects

    Returns:
        CSV string with headers and data rows
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "log_id",
            "execution_id",
            "action_type",
            "actor",
            "timestamp",
            "created_at",
            "details",
        ]
    )

    # Write data rows
    for entry in entries:
        writer.writerow(
            [
                entry.log_id,
                entry.execution_id,
                entry.action_type.value,
                entry.actor or "",
                entry.timestamp.isoformat() if entry.timestamp else "",
                entry.created_at.isoformat() if entry.created_at else "",
                json.dumps(entry.details) if entry.details else "",
            ]
        )

    return output.getvalue()


def get_service_id_for_execution(execution_id: int) -> Optional[int]:
    """
    Get the service ID associated with a playbook execution.

    Args:
        execution_id: The playbook execution ID

    Returns:
        Service ID if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT service_id
        FROM medic.playbook_executions
        WHERE execution_id = %s
        LIMIT 1
        """,
        (execution_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return rows[0].get("service_id")
