"""Playbook execution database operations.

This module contains all database operations for playbook executions:
- create_execution: Create a new execution record
- get_execution: Retrieve an execution by ID
- get_active_executions: Get all running/waiting executions
- get_pending_approval_executions: Get executions awaiting approval
- get_pending_approval_count: Count pending executions
- update_execution_status: Update execution state
- create_step_result: Create a step result record
- update_step_result: Update a step result
- get_step_results_for_execution: Get all step results for an execution
- get_playbook_by_id: Load a playbook from the database

Usage:
    from Medic.Core.playbook.db import (
        create_execution,
        get_execution,
        update_execution_status,
    )

    # Create a new execution
    execution = create_execution(
        playbook_id=10,
        service_id=5,
        status=ExecutionStatus.RUNNING,
    )
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.playbook.models import (
    ExecutionStatus,
    PlaybookExecution,
    StepResult,
    StepResultStatus,
)
from Medic.Core.playbook_parser import Playbook, parse_playbook_yaml
from Medic.Core.utils.datetime_helpers import (
    now as get_now,
    parse_datetime,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


# ============================================================================
# Execution Database Operations
# ============================================================================


def create_execution(
    playbook_id: int,
    service_id: Optional[int] = None,
    status: ExecutionStatus = ExecutionStatus.PENDING_APPROVAL,
    context: Optional[dict[str, Any]] = None,
) -> Optional[PlaybookExecution]:
    """
    Create a new playbook execution record.

    Args:
        playbook_id: ID of the playbook to execute
        service_id: Optional service ID this execution is for
        status: Initial status (default: pending_approval)
        context: Optional context variables for execution

    Returns:
        PlaybookExecution object on success, None on failure
    """
    now = get_now()

    # Determine started_at based on status
    started_at = now if status == ExecutionStatus.RUNNING else None

    result = db.query_db(
        """
        INSERT INTO medic.playbook_executions
        (playbook_id, service_id, status, current_step, started_at,
         created_at, updated_at)
        VALUES (%s, %s, %s, 0, %s, %s, %s)
        RETURNING execution_id
        """,
        (playbook_id, service_id, status.value, started_at, now, now),
        show_columns=True,
    )

    if not result or result == "[]":
        logger.log(
            level=40, msg=f"Failed to create execution for playbook {playbook_id}"
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    execution_id = rows[0].get("execution_id")

    logger.log(
        level=20,
        msg=f"Created playbook execution {execution_id} for playbook "
        f"{playbook_id} (service: {service_id})",
    )

    return PlaybookExecution(
        execution_id=execution_id,
        playbook_id=playbook_id,
        service_id=service_id,
        status=status,
        current_step=0,
        started_at=started_at,
        created_at=now,
        updated_at=now,
        context=context or {},
    )


def get_execution(execution_id: int) -> Optional[PlaybookExecution]:
    """
    Get a playbook execution by ID.

    Args:
        execution_id: The execution ID

    Returns:
        PlaybookExecution object if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT execution_id, playbook_id, service_id, status, current_step,
               started_at, completed_at, created_at, updated_at
        FROM medic.playbook_executions
        WHERE execution_id = %s
        """,
        (execution_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return _parse_execution(rows[0])


def get_active_executions() -> list[PlaybookExecution]:
    """
    Get all active (running/waiting) executions.

    Used for resuming executions after restart.

    Returns:
        List of active PlaybookExecution objects
    """
    result = db.query_db(
        """
        SELECT execution_id, playbook_id, service_id, status, current_step,
               started_at, completed_at, created_at, updated_at
        FROM medic.playbook_executions
        WHERE status IN ('running', 'waiting')
        ORDER BY started_at ASC
        """,
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [ex for ex in (_parse_execution(r) for r in rows if r) if ex is not None]


def get_pending_approval_executions() -> list[PlaybookExecution]:
    """
    Get all executions waiting for approval.

    Returns:
        List of pending PlaybookExecution objects
    """
    result = db.query_db(
        """
        SELECT execution_id, playbook_id, service_id, status, current_step,
               started_at, completed_at, created_at, updated_at
        FROM medic.playbook_executions
        WHERE status = 'pending_approval'
        ORDER BY created_at ASC
        """,
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [ex for ex in (_parse_execution(r) for r in rows if r) if ex is not None]


def get_pending_approval_count() -> int:
    """
    Get the count of executions pending approval.

    Returns:
        Number of pending executions
    """
    result = db.query_db(
        """
        SELECT COUNT(*) as count
        FROM medic.playbook_executions
        WHERE status = 'pending_approval'
        """,
        show_columns=True,
    )

    if not result or result == "[]":
        return 0

    try:
        rows = json.loads(str(result))
        if rows:
            return rows[0].get("count", 0)
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return 0


def update_execution_status(
    execution_id: int,
    status: ExecutionStatus,
    current_step: Optional[int] = None,
    completed_at: Optional[datetime] = None,
) -> bool:
    """
    Update an execution's status and optionally step/completion time.

    Args:
        execution_id: The execution ID
        status: New status
        current_step: Optional new current step index
        completed_at: Optional completion time

    Returns:
        True if updated, False otherwise
    """
    now = get_now()

    # Build dynamic update
    set_clauses = ["status = %s", "updated_at = %s"]
    params: list[Any] = [status.value, now]

    if current_step is not None:
        set_clauses.append("current_step = %s")
        params.append(current_step)

    if completed_at is not None:
        set_clauses.append("completed_at = %s")
        params.append(completed_at)

    # If transitioning to running and started_at is null, set it
    if status == ExecutionStatus.RUNNING:
        set_clauses.append("started_at = COALESCE(started_at, %s)")
        params.append(now)

    params.append(execution_id)

    result = db.insert_db(
        f"UPDATE medic.playbook_executions SET {', '.join(set_clauses)} "
        "WHERE execution_id = %s",
        tuple(params),
    )

    if result:
        logger.log(
            level=10, msg=f"Updated execution {execution_id} status to {status.value}"
        )

    return bool(result)


def _parse_execution(data: dict[str, Any]) -> Optional[PlaybookExecution]:
    """Parse a database row into a PlaybookExecution object."""
    try:
        started_at = data.get("started_at")
        completed_at = data.get("completed_at")
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        # Parse datetime strings if needed
        if isinstance(started_at, str):
            started_at = parse_datetime(started_at)
        if isinstance(completed_at, str):
            completed_at = parse_datetime(completed_at)
        if isinstance(created_at, str):
            created_at = parse_datetime(created_at)
        if isinstance(updated_at, str):
            updated_at = parse_datetime(updated_at)

        return PlaybookExecution(
            execution_id=data["execution_id"],
            playbook_id=data["playbook_id"],
            service_id=data.get("service_id"),
            status=ExecutionStatus(data["status"]),
            current_step=data.get("current_step", 0),
            started_at=started_at,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=updated_at,
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.log(level=30, msg=f"Failed to parse execution data: {e}")
        return None


# ============================================================================
# Step Result Database Operations
# ============================================================================


def create_step_result(
    execution_id: int,
    step_name: str,
    step_index: int,
    status: StepResultStatus = StepResultStatus.PENDING,
) -> Optional[StepResult]:
    """
    Create a new step result record.

    Args:
        execution_id: The execution ID
        step_name: Name of the step
        step_index: Zero-based index of the step
        status: Initial status (default: pending)

    Returns:
        StepResult object on success, None on failure
    """
    now = get_now()

    result = db.query_db(
        """
        INSERT INTO medic.playbook_step_results
        (execution_id, step_name, step_index, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING result_id
        """,
        (execution_id, step_name, step_index, status.value, now, now),
        show_columns=True,
    )

    if not result or result == "[]":
        logger.log(
            level=40,
            msg=f"Failed to create step result for execution {execution_id}, "
            f"step {step_name}",
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    result_id = rows[0].get("result_id")

    return StepResult(
        result_id=result_id,
        execution_id=execution_id,
        step_name=step_name,
        step_index=step_index,
        status=status,
    )


def update_step_result(
    result_id: int,
    status: StepResultStatus,
    output: Optional[str] = None,
    error_message: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> bool:
    """
    Update a step result record.

    Args:
        result_id: The step result ID
        status: New status
        output: Optional output text
        error_message: Optional error message
        started_at: Optional start time
        completed_at: Optional completion time

    Returns:
        True if updated, False otherwise
    """
    now = get_now()

    set_clauses = ["status = %s", "updated_at = %s"]
    params: list[Any] = [status.value, now]

    if output is not None:
        set_clauses.append("output = %s")
        params.append(output[:4096] if len(output) > 4096 else output)

    if error_message is not None:
        set_clauses.append("error_message = %s")
        truncated = error_message[:2048] if len(error_message) > 2048 else None
        params.append(truncated if truncated else error_message)

    if started_at is not None:
        set_clauses.append("started_at = %s")
        params.append(started_at)

    if completed_at is not None:
        set_clauses.append("completed_at = %s")
        params.append(completed_at)

    params.append(result_id)

    result = db.insert_db(
        f"UPDATE medic.playbook_step_results SET {', '.join(set_clauses)} "
        "WHERE result_id = %s",
        tuple(params),
    )

    return bool(result)


def get_step_results_for_execution(execution_id: int) -> list[StepResult]:
    """
    Get all step results for an execution.

    Args:
        execution_id: The execution ID

    Returns:
        List of StepResult objects ordered by step_index
    """
    result = db.query_db(
        """
        SELECT result_id, execution_id, step_name, step_index, status,
               output, error_message, started_at, completed_at
        FROM medic.playbook_step_results
        WHERE execution_id = %s
        ORDER BY step_index ASC
        """,
        (execution_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    parsed = (_parse_step_result(r) for r in rows if r)
    return [sr for sr in parsed if sr is not None]


def _parse_step_result(data: dict[str, Any]) -> Optional[StepResult]:
    """Parse a database row into a StepResult object."""
    try:
        started_at = data.get("started_at")
        completed_at = data.get("completed_at")

        if isinstance(started_at, str):
            started_at = parse_datetime(started_at)
        if isinstance(completed_at, str):
            completed_at = parse_datetime(completed_at)

        return StepResult(
            result_id=data["result_id"],
            execution_id=data["execution_id"],
            step_name=data["step_name"],
            step_index=data["step_index"],
            status=StepResultStatus(data["status"]),
            output=data.get("output"),
            error_message=data.get("error_message"),
            started_at=started_at,
            completed_at=completed_at,
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.log(level=30, msg=f"Failed to parse step result data: {e}")
        return None


# ============================================================================
# Playbook Loading
# ============================================================================


def get_playbook_by_id(playbook_id: int) -> Optional[Playbook]:
    """
    Load a playbook from the database by ID.

    Args:
        playbook_id: The playbook ID

    Returns:
        Parsed Playbook object if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT playbook_id, name, description, yaml_content, version
        FROM medic.playbooks
        WHERE playbook_id = %s
        """,
        (playbook_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    playbook_data = rows[0]
    yaml_content = playbook_data.get("yaml_content")

    if not yaml_content:
        logger.log(level=30, msg=f"Playbook {playbook_id} has no YAML content")
        return None

    try:
        return parse_playbook_yaml(yaml_content)
    except Exception as e:
        logger.log(level=40, msg=f"Failed to parse playbook {playbook_id}: {e}")
        return None
