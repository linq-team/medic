"""Playbook execution engine for Medic.

This module provides the core execution engine for running playbooks.
It processes steps sequentially, persists state after each step to survive
restarts, and supports wait steps for pausing execution.

The engine is designed to:
- Process steps sequentially
- Persist state after each step (survives restart)
- Support wait steps (pause execution for duration)
- Support webhook steps with variable substitution
- Support script steps with sandboxed execution
- Track execution status and step results in the database

Execution statuses:
- pending_approval: Waiting for human approval
- running: Currently executing steps
- waiting: Paused on a wait step
- completed: All steps finished successfully
- failed: Execution failed on a step
- cancelled: Execution was cancelled

Step result statuses:
- pending: Not yet started
- running: Currently executing
- completed: Finished successfully
- failed: Step failed
- skipped: Step was skipped
"""
import json
import logging
import os
import re
import resource
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import pytz
import requests

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.metrics import (
    record_playbook_execution,
    record_playbook_execution_duration,
    update_pending_approval_count,
)

# Import audit logging - use try/except for graceful degradation
try:
    from Medic.Core.audit_log import (
        log_execution_started,
        log_step_completed,
        log_step_failed,
        log_execution_completed,
        log_execution_failed,
    )
    AUDIT_LOG_AVAILABLE = True
except ImportError:
    AUDIT_LOG_AVAILABLE = False

from Medic.Core.playbook_parser import (
    ApprovalMode,
    ConditionStep,
    ConditionType,
    OnFailureAction,
    Playbook,
    PlaybookStep,
    ScriptStep,
    StepType,
    WaitStep,
    WebhookStep,
    parse_playbook_yaml,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


class ExecutionStatus(str, Enum):
    """Status of a playbook execution."""

    PENDING_APPROVAL = "pending_approval"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def is_terminal(cls, status: "ExecutionStatus") -> bool:
        """Check if status is a terminal state."""
        return status in (cls.COMPLETED, cls.FAILED, cls.CANCELLED)

    @classmethod
    def is_active(cls, status: "ExecutionStatus") -> bool:
        """Check if status is an active/resumable state."""
        return status in (cls.RUNNING, cls.WAITING)


class StepResultStatus(str, Enum):
    """Status of a step result."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a single step."""

    result_id: Optional[int]
    execution_id: int
    step_name: str
    step_index: int
    status: StepResultStatus
    output: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "result_id": self.result_id,
            "execution_id": self.execution_id,
            "step_name": self.step_name,
            "step_index": self.step_index,
            "status": self.status.value,
            "output": self.output,
            "error_message": self.error_message,
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class PlaybookExecution:
    """Represents a playbook execution instance."""

    execution_id: Optional[int]
    playbook_id: int
    service_id: Optional[int]
    status: ExecutionStatus
    current_step: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Loaded playbook (not persisted, loaded on demand)
    playbook: Optional[Playbook] = None
    # Step results (loaded on demand)
    step_results: List[StepResult] = field(default_factory=list)
    # Context variables for step execution
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "playbook_id": self.playbook_id,
            "service_id": self.service_id,
            "status": self.status.value,
            "current_step": self.current_step,
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
            "step_results": [sr.to_dict() for sr in self.step_results],
            "context": self.context,
        }


# Type alias for step executor functions
StepExecutor = Callable[[PlaybookStep, PlaybookExecution], StepResult]


def _now() -> datetime:
    """Get current time in Chicago timezone."""
    return datetime.now(pytz.timezone('America/Chicago'))


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse a datetime string in various formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


# ============================================================================
# Database Operations
# ============================================================================

def create_execution(
    playbook_id: int,
    service_id: Optional[int] = None,
    status: ExecutionStatus = ExecutionStatus.PENDING_APPROVAL,
    context: Optional[Dict[str, Any]] = None
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
    now = _now()

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
        show_columns=True
    )

    if not result or result == '[]':
        logger.log(
            level=40,
            msg=f"Failed to create playbook execution for playbook {playbook_id}"
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    execution_id = rows[0].get('execution_id')

    logger.log(
        level=20,
        msg=f"Created playbook execution {execution_id} for playbook "
            f"{playbook_id} (service: {service_id})"
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
        show_columns=True
    )

    if not result or result == '[]':
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return _parse_execution(rows[0])


def get_active_executions() -> List[PlaybookExecution]:
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
        show_columns=True
    )

    if not result or result == '[]':
        return []

    rows = json.loads(str(result))
    return [
        ex for ex in (_parse_execution(r) for r in rows if r) if ex is not None
    ]


def get_pending_approval_executions() -> List[PlaybookExecution]:
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
        show_columns=True
    )

    if not result or result == '[]':
        return []

    rows = json.loads(str(result))
    return [
        ex for ex in (_parse_execution(r) for r in rows if r) if ex is not None
    ]


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
        show_columns=True
    )

    if not result or result == '[]':
        return 0

    try:
        rows = json.loads(str(result))
        if rows:
            return rows[0].get('count', 0)
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    return 0


def _update_pending_approval_metric():
    """Update the pending approval gauge metric."""
    count = get_pending_approval_count()
    update_pending_approval_count(count)


def update_execution_status(
    execution_id: int,
    status: ExecutionStatus,
    current_step: Optional[int] = None,
    completed_at: Optional[datetime] = None
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
    now = _now()

    # Build dynamic update
    set_clauses = ["status = %s", "updated_at = %s"]
    params: List[Any] = [status.value, now]

    if current_step is not None:
        set_clauses.append("current_step = %s")
        params.append(current_step)

    if completed_at is not None:
        set_clauses.append("completed_at = %s")
        params.append(completed_at)

    # If transitioning to running and started_at is null, set it
    if status == ExecutionStatus.RUNNING:
        set_clauses.append(
            "started_at = COALESCE(started_at, %s)"
        )
        params.append(now)

    params.append(execution_id)

    result = db.insert_db(
        f"UPDATE medic.playbook_executions SET {', '.join(set_clauses)} "
        "WHERE execution_id = %s",
        tuple(params)
    )

    if result:
        logger.log(
            level=10,
            msg=f"Updated execution {execution_id} status to {status.value}"
        )

    return bool(result)


def _parse_execution(data: Dict[str, Any]) -> Optional[PlaybookExecution]:
    """Parse a database row into a PlaybookExecution object."""
    try:
        started_at = data.get('started_at')
        completed_at = data.get('completed_at')
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')

        # Parse datetime strings if needed
        if isinstance(started_at, str):
            started_at = _parse_datetime(started_at)
        if isinstance(completed_at, str):
            completed_at = _parse_datetime(completed_at)
        if isinstance(created_at, str):
            created_at = _parse_datetime(created_at)
        if isinstance(updated_at, str):
            updated_at = _parse_datetime(updated_at)

        return PlaybookExecution(
            execution_id=data['execution_id'],
            playbook_id=data['playbook_id'],
            service_id=data.get('service_id'),
            status=ExecutionStatus(data['status']),
            current_step=data.get('current_step', 0),
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
    status: StepResultStatus = StepResultStatus.PENDING
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
    now = _now()

    result = db.query_db(
        """
        INSERT INTO medic.playbook_step_results
        (execution_id, step_name, step_index, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING result_id
        """,
        (execution_id, step_name, step_index, status.value, now, now),
        show_columns=True
    )

    if not result or result == '[]':
        logger.log(
            level=40,
            msg=f"Failed to create step result for execution {execution_id}, "
                f"step {step_name}"
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    result_id = rows[0].get('result_id')

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
    completed_at: Optional[datetime] = None
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
    now = _now()

    set_clauses = ["status = %s", "updated_at = %s"]
    params: List[Any] = [status.value, now]

    if output is not None:
        set_clauses.append("output = %s")
        params.append(output[:4096] if len(output) > 4096 else output)

    if error_message is not None:
        set_clauses.append("error_message = %s")
        params.append(
            error_message[:2048] if len(error_message) > 2048 else error_message
        )

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
        tuple(params)
    )

    return bool(result)


def get_step_results_for_execution(
    execution_id: int
) -> List[StepResult]:
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
        show_columns=True
    )

    if not result or result == '[]':
        return []

    rows = json.loads(str(result))
    return [
        sr for sr in (_parse_step_result(r) for r in rows if r) if sr is not None
    ]


def _parse_step_result(data: Dict[str, Any]) -> Optional[StepResult]:
    """Parse a database row into a StepResult object."""
    try:
        started_at = data.get('started_at')
        completed_at = data.get('completed_at')

        if isinstance(started_at, str):
            started_at = _parse_datetime(started_at)
        if isinstance(completed_at, str):
            completed_at = _parse_datetime(completed_at)

        return StepResult(
            result_id=data['result_id'],
            execution_id=data['execution_id'],
            step_name=data['step_name'],
            step_index=data['step_index'],
            status=StepResultStatus(data['status']),
            output=data.get('output'),
            error_message=data.get('error_message'),
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
        show_columns=True
    )

    if not result or result == '[]':
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    playbook_data = rows[0]
    yaml_content = playbook_data.get('yaml_content')

    if not yaml_content:
        logger.log(
            level=30,
            msg=f"Playbook {playbook_id} has no YAML content"
        )
        return None

    try:
        return parse_playbook_yaml(yaml_content)
    except Exception as e:
        logger.log(
            level=40,
            msg=f"Failed to parse playbook {playbook_id}: {e}"
        )
        return None


# ============================================================================
# Step Executors
# ============================================================================

def execute_wait_step(
    step: WaitStep,
    execution: PlaybookExecution
) -> StepResult:
    """
    Execute a wait step by pausing for the specified duration.

    For persistence across restarts, wait steps update the execution
    status to 'waiting' and store the resume time. The engine should
    check wait completion before resuming.

    Args:
        step: The WaitStep to execute
        execution: The current execution context

    Returns:
        StepResult with completion status
    """
    now = _now()
    step_index = execution.current_step

    # Create step result as running
    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=step_index,
        status=StepResultStatus.RUNNING
    )

    if not result:
        return StepResult(
            result_id=None,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message="Failed to create step result record",
            started_at=now,
            completed_at=now,
        )

    # Update with start time
    update_step_result(
        result_id=result.result_id or 0,
        status=StepResultStatus.RUNNING,
        started_at=now,
    )

    # Calculate resume time
    resume_at = now + timedelta(seconds=step.duration_seconds)

    logger.log(
        level=20,
        msg=f"Wait step '{step.name}' starting: {step.duration_seconds}s "
            f"(resume at {resume_at.isoformat()})"
    )

    # For synchronous execution, sleep for the duration
    # In production, this would be async or scheduled
    time.sleep(step.duration_seconds)

    completed_at = _now()

    # Update result as completed
    update_step_result(
        result_id=result.result_id or 0,
        status=StepResultStatus.COMPLETED,
        output=f"Waited {step.duration_seconds} seconds",
        completed_at=completed_at,
    )

    logger.log(
        level=20,
        msg=f"Wait step '{step.name}' completed after {step.duration_seconds}s"
    )

    return StepResult(
        result_id=result.result_id,
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=step_index,
        status=StepResultStatus.COMPLETED,
        output=f"Waited {step.duration_seconds} seconds",
        started_at=now,
        completed_at=completed_at,
    )


# Maximum response body size to store (bytes)
MAX_RESPONSE_BODY_SIZE = 4096

# HTTP timeout for webhook requests (seconds)
DEFAULT_WEBHOOK_TIMEOUT = 30

# Variable pattern for substitution: ${VAR_NAME}
VARIABLE_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')


def substitute_variables(
    value: Any,
    context: Dict[str, Any]
) -> Any:
    """
    Substitute variables in a value using execution context.

    Supports ${VAR_NAME} syntax. Available variables include:
    - SERVICE_NAME: Name of the service
    - SERVICE_ID: ID of the service
    - ALERT_ID: ID of the alert that triggered the playbook
    - RUN_ID: ID of the current run
    - EXECUTION_ID: ID of the playbook execution
    - PLAYBOOK_NAME: Name of the playbook
    - Plus any custom variables in the context

    Args:
        value: Value to substitute (string, dict, list, or other)
        context: Dictionary of variable values

    Returns:
        Value with variables substituted
    """
    if isinstance(value, str):
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            replacement = context.get(var_name)
            if replacement is not None:
                return str(replacement)
            # If variable not found, keep original placeholder
            return match.group(0)

        return VARIABLE_PATTERN.sub(replace_var, value)

    elif isinstance(value, dict):
        return {
            substitute_variables(k, context): substitute_variables(v, context)
            for k, v in value.items()
        }

    elif isinstance(value, list):
        return [substitute_variables(item, context) for item in value]

    else:
        return value


def _build_webhook_context(
    execution: PlaybookExecution
) -> Dict[str, Any]:
    """
    Build the variable context for webhook substitution.

    Args:
        execution: The current playbook execution

    Returns:
        Dictionary of available variables
    """
    context = dict(execution.context)  # Copy execution context

    # Add standard variables
    context['EXECUTION_ID'] = execution.execution_id
    context['PLAYBOOK_ID'] = execution.playbook_id
    context['SERVICE_ID'] = execution.service_id

    # Add playbook name if available
    if execution.playbook:
        context['PLAYBOOK_NAME'] = execution.playbook.name

    # Get service name from database if we have service_id
    if execution.service_id:
        service_result = db.query_db(
            "SELECT name FROM services WHERE service_id = %s",
            (execution.service_id,),
            show_columns=True
        )
        if service_result and service_result != '[]':
            try:
                rows = json.loads(str(service_result))
                if rows:
                    context['SERVICE_NAME'] = rows[0].get('name', '')
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    return context


def execute_webhook_step(
    step: WebhookStep,
    execution: PlaybookExecution,
    http_client: Optional[Callable[..., requests.Response]] = None
) -> StepResult:
    """
    Execute a webhook step by making an HTTP request.

    Performs variable substitution on URL, headers, and body using the
    execution context. Variables use ${VAR_NAME} syntax.

    Available variables:
    - ${SERVICE_NAME}: Name of the service
    - ${SERVICE_ID}: ID of the service
    - ${ALERT_ID}: ID of the alert that triggered the playbook
    - ${RUN_ID}: ID of the current run
    - ${EXECUTION_ID}: ID of the playbook execution
    - ${PLAYBOOK_NAME}: Name of the playbook
    - Plus any custom variables passed in execution context

    Args:
        step: The WebhookStep to execute
        execution: The current execution context
        http_client: Optional custom HTTP client for testing

    Returns:
        StepResult with execution outcome
    """
    now = _now()
    step_index = execution.current_step

    # Create step result as running
    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=step_index,
        status=StepResultStatus.RUNNING
    )

    if not result:
        return StepResult(
            result_id=None,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message="Failed to create step result record",
            started_at=now,
            completed_at=now,
        )

    # Update with start time
    update_step_result(
        result_id=result.result_id or 0,
        status=StepResultStatus.RUNNING,
        started_at=now,
    )

    # Build variable context
    context = _build_webhook_context(execution)

    # Substitute variables in URL, headers, and body
    url = substitute_variables(step.url, context)
    headers = substitute_variables(step.headers, context)
    body = substitute_variables(step.body, context) if step.body else None

    logger.log(
        level=20,
        msg=f"Webhook step '{step.name}': {step.method} {url}"
    )

    # Prepare request headers
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    # Determine timeout
    timeout = step.timeout_seconds or DEFAULT_WEBHOOK_TIMEOUT

    # Use provided http_client or requests
    client = http_client or requests.request

    try:
        # Make the HTTP request
        response = client(
            method=step.method,
            url=url,
            headers=request_headers,
            json=body,
            timeout=timeout
        )

        # Truncate response body if too large
        response_body = response.text
        if len(response_body) > MAX_RESPONSE_BODY_SIZE:
            response_body = response_body[:MAX_RESPONSE_BODY_SIZE]
            response_body += "...[truncated]"

        # Check success condition (status code)
        is_success = response.status_code in step.success_codes

        completed_at = _now()

        # Build output message
        output_msg = (
            f"HTTP {step.method} {url}\n"
            f"Status: {response.status_code}\n"
            f"Response: {response_body}"
        )

        if is_success:
            logger.log(
                level=20,
                msg=f"Webhook step '{step.name}' completed successfully "
                    f"(status: {response.status_code})"
            )

            update_step_result(
                result_id=result.result_id or 0,
                status=StepResultStatus.COMPLETED,
                output=output_msg,
                completed_at=completed_at,
            )

            return StepResult(
                result_id=result.result_id,
                execution_id=execution.execution_id or 0,
                step_name=step.name,
                step_index=step_index,
                status=StepResultStatus.COMPLETED,
                output=output_msg,
                started_at=now,
                completed_at=completed_at,
            )
        else:
            error_msg = (
                f"Unexpected status code {response.status_code}. "
                f"Expected one of {step.success_codes}"
            )
            logger.log(
                level=30,
                msg=f"Webhook step '{step.name}' failed: {error_msg}"
            )

            update_step_result(
                result_id=result.result_id or 0,
                status=StepResultStatus.FAILED,
                output=output_msg,
                error_message=error_msg,
                completed_at=completed_at,
            )

            return StepResult(
                result_id=result.result_id,
                execution_id=execution.execution_id or 0,
                step_name=step.name,
                step_index=step_index,
                status=StepResultStatus.FAILED,
                output=output_msg,
                error_message=error_msg,
                started_at=now,
                completed_at=completed_at,
            )

    except requests.Timeout:
        completed_at = _now()
        error_msg = f"Request timed out after {timeout}s"
        logger.log(
            level=30,
            msg=f"Webhook step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    except requests.ConnectionError as e:
        completed_at = _now()
        error_msg = f"Connection error: {str(e)}"
        logger.log(
            level=30,
            msg=f"Webhook step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    except requests.RequestException as e:
        completed_at = _now()
        error_msg = f"Request failed: {str(e)}"
        logger.log(
            level=30,
            msg=f"Webhook step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )


# ============================================================================
# Script Step Execution
# ============================================================================

# Default timeout for script execution (seconds)
DEFAULT_SCRIPT_TIMEOUT = 30

# Maximum memory limit for script execution (bytes) - 256 MB
MAX_SCRIPT_MEMORY_BYTES = 256 * 1024 * 1024

# Maximum output size to capture (bytes)
MAX_SCRIPT_OUTPUT_SIZE = 8192


@dataclass
class RegisteredScript:
    """A pre-registered script from the database."""

    script_id: int
    name: str
    content: str
    interpreter: str
    timeout_seconds: int


def get_registered_script(script_name: str) -> Optional[RegisteredScript]:
    """
    Get a registered script by name from the database.

    Args:
        script_name: Name of the script to retrieve

    Returns:
        RegisteredScript object if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT script_id, name, content, interpreter, timeout_seconds
        FROM medic.registered_scripts
        WHERE name = %s
        """,
        (script_name,),
        show_columns=True
    )

    if not result or result == '[]':
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    row = rows[0]
    return RegisteredScript(
        script_id=row['script_id'],
        name=row['name'],
        content=row['content'],
        interpreter=row['interpreter'],
        timeout_seconds=row.get('timeout_seconds', DEFAULT_SCRIPT_TIMEOUT),
    )


def _substitute_script_variables(
    script_content: str,
    context: Dict[str, Any],
    parameters: Dict[str, Any]
) -> str:
    """
    Substitute variables in script content.

    Supports ${VAR_NAME} syntax from context and parameters.
    Parameters override context variables.

    Args:
        script_content: The script content with variables
        context: Execution context variables
        parameters: Step-specific parameters

    Returns:
        Script content with variables substituted
    """
    # Merge context and parameters (parameters take precedence)
    merged = dict(context)
    merged.update(parameters)

    # Use the existing substitute_variables function for string substitution
    return str(substitute_variables(script_content, merged))


def execute_script_step(
    step: ScriptStep,
    execution: PlaybookExecution
) -> StepResult:
    """
    Execute a script step by running a pre-registered script.

    Security measures:
    - Only pre-registered scripts can be executed (by name lookup)
    - Scripts run with resource limits (timeout, memory)
    - Output is captured and truncated if too large

    Args:
        step: The ScriptStep to execute
        execution: The current execution context

    Returns:
        StepResult with execution outcome
    """
    now = _now()
    step_index = execution.current_step

    # Create step result as running
    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=step_index,
        status=StepResultStatus.RUNNING
    )

    if not result:
        return StepResult(
            result_id=None,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message="Failed to create step result record",
            started_at=now,
            completed_at=now,
        )

    # Update with start time
    update_step_result(
        result_id=result.result_id or 0,
        status=StepResultStatus.RUNNING,
        started_at=now,
    )

    # Look up the registered script by name
    script = get_registered_script(step.script_name)
    if not script:
        completed_at = _now()
        error_msg = (
            f"Script '{step.script_name}' not found in registered scripts. "
            "Only pre-registered scripts can be executed for security."
        )
        logger.log(
            level=30,
            msg=f"Script step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    # Build variable context
    context = _build_webhook_context(execution)

    # Substitute variables in script content
    script_content = _substitute_script_variables(
        script.content,
        context,
        step.parameters
    )

    # Determine interpreter command
    if script.interpreter == 'python':
        interpreter_cmd = ['python3', '-u']
    elif script.interpreter == 'bash':
        interpreter_cmd = ['bash', '-e']
    else:
        completed_at = _now()
        error_msg = f"Unsupported interpreter: {script.interpreter}"
        logger.log(
            level=30,
            msg=f"Script step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    # Determine timeout (use step timeout or script timeout or default)
    timeout = step.timeout_seconds or script.timeout_seconds or DEFAULT_SCRIPT_TIMEOUT

    logger.log(
        level=20,
        msg=f"Script step '{step.name}': executing '{script.name}' "
            f"with {script.interpreter} (timeout: {timeout}s)"
    )

    try:
        # Write script to temporary file
        suffix = '.py' if script.interpreter == 'python' else '.sh'
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=suffix,
            delete=False
        ) as f:
            f.write(script_content)
            script_path = f.name

        # Set resource limits for the subprocess
        def set_limits():
            """Set resource limits for the child process."""
            try:
                # Set memory limit (virtual memory)
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (MAX_SCRIPT_MEMORY_BYTES, MAX_SCRIPT_MEMORY_BYTES)
                )
                # Set CPU time limit (as backup to timeout)
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (timeout + 5, timeout + 10)
                )
            except (ValueError, resource.error):
                # Resource limits may not be available on all platforms
                pass

        # Execute the script
        proc = subprocess.run(
            interpreter_cmd + [script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=set_limits,
            env={
                **dict(os.environ),
                'MEDIC_EXECUTION_ID': str(execution.execution_id or ''),
                'MEDIC_PLAYBOOK_ID': str(execution.playbook_id),
                'MEDIC_SERVICE_ID': str(execution.service_id or ''),
            }
        )

        # Clean up temp file
        try:
            os.unlink(script_path)
        except OSError:
            pass

        # Capture output (truncate if needed)
        stdout = proc.stdout or ''
        stderr = proc.stderr or ''
        combined_output = stdout + (f"\n[STDERR]\n{stderr}" if stderr else "")

        if len(combined_output) > MAX_SCRIPT_OUTPUT_SIZE:
            combined_output = combined_output[:MAX_SCRIPT_OUTPUT_SIZE]
            combined_output += "\n...[output truncated]"

        completed_at = _now()

        # Build output message
        output_msg = (
            f"Script: {script.name}\n"
            f"Interpreter: {script.interpreter}\n"
            f"Exit code: {proc.returncode}\n"
            f"Output:\n{combined_output}"
        )

        # Check exit code
        if proc.returncode == 0:
            logger.log(
                level=20,
                msg=f"Script step '{step.name}' completed successfully "
                    f"(exit code: 0)"
            )

            update_step_result(
                result_id=result.result_id or 0,
                status=StepResultStatus.COMPLETED,
                output=output_msg,
                completed_at=completed_at,
            )

            return StepResult(
                result_id=result.result_id,
                execution_id=execution.execution_id or 0,
                step_name=step.name,
                step_index=step_index,
                status=StepResultStatus.COMPLETED,
                output=output_msg,
                started_at=now,
                completed_at=completed_at,
            )
        else:
            error_msg = f"Script exited with code {proc.returncode}"
            logger.log(
                level=30,
                msg=f"Script step '{step.name}' failed: {error_msg}"
            )

            update_step_result(
                result_id=result.result_id or 0,
                status=StepResultStatus.FAILED,
                output=output_msg,
                error_message=error_msg,
                completed_at=completed_at,
            )

            return StepResult(
                result_id=result.result_id,
                execution_id=execution.execution_id or 0,
                step_name=step.name,
                step_index=step_index,
                status=StepResultStatus.FAILED,
                output=output_msg,
                error_message=error_msg,
                started_at=now,
                completed_at=completed_at,
            )

    except subprocess.TimeoutExpired:
        # Clean up temp file if it exists
        try:
            os.unlink(script_path)  # type: ignore[possibly-undefined]
        except (OSError, NameError):
            pass

        completed_at = _now()
        error_msg = f"Script execution timed out after {timeout}s"
        logger.log(
            level=30,
            msg=f"Script step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    except Exception as e:
        # Clean up temp file if it exists
        try:
            os.unlink(script_path)  # type: ignore[possibly-undefined]
        except (OSError, NameError):
            pass

        completed_at = _now()
        error_msg = f"Script execution failed: {str(e)}"
        logger.log(
            level=30,
            msg=f"Script step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )


# ============================================================================
# Condition Step Execution
# ============================================================================

# Default timeout for condition checks (seconds)
DEFAULT_CONDITION_TIMEOUT = 300  # 5 minutes

# Polling interval for condition checks (seconds)
CONDITION_POLL_INTERVAL = 5


def check_heartbeat_received(
    service_id: int,
    since: datetime,
    parameters: Dict[str, Any]
) -> tuple[bool, str]:
    """
    Check if a heartbeat has been received for a service since a given time.

    Args:
        service_id: The service ID to check
        since: Check for heartbeats received after this time
        parameters: Additional parameters (e.g., min_count, status filter)

    Returns:
        Tuple of (condition_met, message)
    """
    min_count = parameters.get('min_count', 1)
    status_filter = parameters.get('status')

    # Build query to check for heartbeats since the given time
    query = """
        SELECT COUNT(*) as count
        FROM medic.heartbeatEvents
        WHERE service_id = %s
          AND time >= %s
    """
    params: List[Any] = [service_id, since]

    # Add status filter if specified
    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)

    result = db.query_db(query, tuple(params), show_columns=True)

    if not result or result == '[]':
        return (False, "Failed to query heartbeat events")

    try:
        rows = json.loads(str(result))
        if not rows:
            return (False, "No heartbeat data returned")

        count = rows[0].get('count', 0)
        if count >= min_count:
            return (
                True,
                f"Heartbeat received: {count} heartbeat(s) since {since.isoformat()}"
            )
        else:
            return (
                False,
                f"Waiting for heartbeat: {count}/{min_count} received since "
                f"{since.isoformat()}"
            )
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        return (False, f"Error parsing heartbeat data: {e}")


def execute_condition_step(
    step: ConditionStep,
    execution: PlaybookExecution
) -> StepResult:
    """
    Execute a condition step by polling until condition is met or timeout.

    Supported condition types:
    - heartbeat_received: Check if service received a heartbeat

    The step will poll at regular intervals until:
    - Condition is met: Returns COMPLETED status
    - Timeout expires: Returns based on on_failure setting
      - fail: Returns FAILED status
      - continue: Returns COMPLETED status (allows playbook to continue)
      - escalate: Returns FAILED status with escalation flag

    Args:
        step: The ConditionStep to execute
        execution: The current execution context

    Returns:
        StepResult with execution outcome
    """
    now = _now()
    step_index = execution.current_step
    condition_start = now

    # Create step result as running
    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=step_index,
        status=StepResultStatus.RUNNING
    )

    if not result:
        return StepResult(
            result_id=None,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message="Failed to create step result record",
            started_at=now,
            completed_at=now,
        )

    # Update with start time
    update_step_result(
        result_id=result.result_id or 0,
        status=StepResultStatus.RUNNING,
        started_at=now,
    )

    # Get service ID from execution context
    service_id = execution.service_id
    if not service_id:
        # Try to get from parameters
        service_id = step.parameters.get('service_id')

    if not service_id:
        completed_at = _now()
        error_msg = (
            "No service_id available for condition check. "
            "Provide service_id in execution or step parameters."
        )
        logger.log(
            level=30,
            msg=f"Condition step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    # Determine timeout
    timeout = step.timeout_seconds or DEFAULT_CONDITION_TIMEOUT

    logger.log(
        level=20,
        msg=f"Condition step '{step.name}': checking {step.condition_type.value} "
            f"for service {service_id} (timeout: {timeout}s)"
    )

    # Poll for condition until timeout
    condition_met = False
    last_message = ""

    while True:
        # Check if timeout has expired
        elapsed = (_now() - condition_start).total_seconds()
        if elapsed >= timeout:
            break

        # Evaluate condition based on type
        if step.condition_type == ConditionType.HEARTBEAT_RECEIVED:
            condition_met, last_message = check_heartbeat_received(
                service_id=service_id,
                since=condition_start,
                parameters=step.parameters,
            )
        else:
            last_message = f"Unknown condition type: {step.condition_type.value}"
            break

        if condition_met:
            break

        # Sleep before next poll
        remaining = timeout - elapsed
        sleep_time = min(CONDITION_POLL_INTERVAL, remaining)
        if sleep_time > 0:
            time.sleep(sleep_time)

    completed_at = _now()
    elapsed_total = (completed_at - condition_start).total_seconds()

    if condition_met:
        # Condition was met
        output_msg = (
            f"Condition '{step.condition_type.value}' met after "
            f"{elapsed_total:.1f}s\n{last_message}"
        )
        logger.log(
            level=20,
            msg=f"Condition step '{step.name}' completed: {last_message}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.COMPLETED,
            output=output_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.COMPLETED,
            output=output_msg,
            started_at=now,
            completed_at=completed_at,
        )

    # Condition timed out - handle based on on_failure setting
    timeout_msg = (
        f"Condition '{step.condition_type.value}' timed out after "
        f"{elapsed_total:.1f}s\n{last_message}"
    )

    if step.on_failure == OnFailureAction.CONTINUE:
        # Allow playbook to continue despite condition not being met
        logger.log(
            level=30,
            msg=f"Condition step '{step.name}' timed out but continuing "
                f"(on_failure=continue): {last_message}"
        )

        output_msg = f"{timeout_msg}\n(Continuing due to on_failure=continue)"

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.COMPLETED,
            output=output_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.COMPLETED,
            output=output_msg,
            started_at=now,
            completed_at=completed_at,
        )

    elif step.on_failure == OnFailureAction.ESCALATE:
        # Fail and mark for escalation
        error_msg = (
            f"Condition timed out after {elapsed_total:.1f}s. "
            f"Escalating to on-call: {last_message}"
        )
        logger.log(
            level=40,
            msg=f"Condition step '{step.name}' failed, escalating: {error_msg}"
        )

        # Include escalation flag in output for downstream processing
        output_msg = f"{timeout_msg}\n[ESCALATE] Condition failure requires escalation"

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            output=output_msg,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            output=output_msg,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )

    else:
        # Default: fail the step (on_failure=fail)
        error_msg = f"Condition timed out after {elapsed_total:.1f}s: {last_message}"
        logger.log(
            level=30,
            msg=f"Condition step '{step.name}' failed: {error_msg}"
        )

        update_step_result(
            result_id=result.result_id or 0,
            status=StepResultStatus.FAILED,
            output=timeout_msg,
            error_message=error_msg,
            completed_at=completed_at,
        )

        return StepResult(
            result_id=result.result_id,
            execution_id=execution.execution_id or 0,
            step_name=step.name,
            step_index=step_index,
            status=StepResultStatus.FAILED,
            output=timeout_msg,
            error_message=error_msg,
            started_at=now,
            completed_at=completed_at,
        )


# ============================================================================
# Execution Engine
# ============================================================================

class PlaybookExecutionEngine:
    """
    Engine for executing playbook steps sequentially.

    The engine:
    - Processes steps in order
    - Persists state after each step
    - Supports wait steps (pauses execution)
    - Can resume after restart from last state

    Usage:
        engine = PlaybookExecutionEngine()
        result = engine.start_execution(playbook_id, service_id)
        # or
        engine.resume_execution(execution_id)
    """

    def __init__(self):
        """Initialize the execution engine."""
        self._step_executors: Dict[StepType, StepExecutor] = {
            StepType.WAIT: self._execute_wait,
            StepType.WEBHOOK: self._execute_webhook,
            StepType.SCRIPT: self._execute_script,
            StepType.CONDITION: self._execute_condition,
        }

    def start_execution(
        self,
        playbook_id: int,
        service_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        skip_approval: bool = False
    ) -> Optional[PlaybookExecution]:
        """
        Start a new playbook execution.

        Args:
            playbook_id: ID of the playbook to execute
            service_id: Optional service ID this execution is for
            context: Optional context variables for execution
            skip_approval: If True, skip approval even if playbook requires it

        Returns:
            PlaybookExecution object, or None on failure
        """
        # Load playbook
        playbook = get_playbook_by_id(playbook_id)
        if not playbook:
            logger.log(
                level=40,
                msg=f"Cannot start execution: playbook {playbook_id} not found"
            )
            return None

        # Determine initial status based on approval setting
        if skip_approval or playbook.approval == ApprovalMode.NONE:
            initial_status = ExecutionStatus.RUNNING
        else:
            initial_status = ExecutionStatus.PENDING_APPROVAL

        # Create execution record
        execution = create_execution(
            playbook_id=playbook_id,
            service_id=service_id,
            status=initial_status,
            context=context,
        )

        if not execution:
            return None

        execution.playbook = playbook
        execution.context = context or {}

        logger.log(
            level=20,
            msg=f"Started playbook execution {execution.execution_id} "
                f"for '{playbook.name}' (status: {initial_status.value})"
        )

        # Log execution started to audit log
        if AUDIT_LOG_AVAILABLE:
            # Get service name if we have service_id
            service_name = None
            if service_id:
                svc_result = db.query_db(
                    "SELECT name FROM services WHERE service_id = %s",
                    (service_id,),
                    show_columns=True
                )
                if svc_result and svc_result != '[]':
                    try:
                        rows = json.loads(str(svc_result))
                        if rows:
                            service_name = rows[0].get('name')
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass

            log_execution_started(
                execution_id=execution.execution_id or 0,
                playbook_id=playbook_id,
                playbook_name=playbook.name,
                service_id=service_id,
                service_name=service_name,
                trigger=context.get('trigger') if context else None,
                context=context,
            )

        # Update pending approval metric if applicable
        if initial_status == ExecutionStatus.PENDING_APPROVAL:
            _update_pending_approval_metric()

        # If running immediately, execute steps
        if initial_status == ExecutionStatus.RUNNING:
            self._execute_steps(execution)

        return execution

    def resume_execution(
        self,
        execution_id: int
    ) -> Optional[PlaybookExecution]:
        """
        Resume an existing execution from its current state.

        Used after restart or when wait step completes.

        Args:
            execution_id: The execution ID to resume

        Returns:
            PlaybookExecution object, or None if not found/resumable
        """
        execution = get_execution(execution_id)
        if not execution:
            logger.log(
                level=30,
                msg=f"Cannot resume execution {execution_id}: not found"
            )
            return None

        if ExecutionStatus.is_terminal(execution.status):
            logger.log(
                level=30,
                msg=f"Cannot resume execution {execution_id}: "
                    f"already in terminal state {execution.status.value}"
            )
            return execution

        # Load playbook
        playbook = get_playbook_by_id(execution.playbook_id)
        if not playbook:
            logger.log(
                level=40,
                msg=f"Cannot resume execution {execution_id}: "
                    f"playbook {execution.playbook_id} not found"
            )
            self._fail_execution(
                execution,
                "Playbook not found during resume"
            )
            return execution

        execution.playbook = playbook

        # Load existing step results
        execution.step_results = get_step_results_for_execution(execution_id)

        logger.log(
            level=20,
            msg=f"Resuming execution {execution_id} at step "
                f"{execution.current_step}"
        )

        # Continue execution
        if execution.status == ExecutionStatus.WAITING:
            update_execution_status(execution_id, ExecutionStatus.RUNNING)
            execution.status = ExecutionStatus.RUNNING

        self._execute_steps(execution)

        return execution

    def approve_execution(self, execution_id: int) -> bool:
        """
        Approve a pending execution and start it.

        Args:
            execution_id: The execution ID to approve

        Returns:
            True if approved and started, False otherwise
        """
        execution = get_execution(execution_id)
        if not execution:
            return False

        if execution.status != ExecutionStatus.PENDING_APPROVAL:
            logger.log(
                level=30,
                msg=f"Cannot approve execution {execution_id}: "
                    f"status is {execution.status.value}, not pending_approval"
            )
            return False

        # Update to running
        if not update_execution_status(execution_id, ExecutionStatus.RUNNING):
            return False

        logger.log(
            level=20,
            msg=f"Execution {execution_id} approved, starting execution"
        )

        # Update pending approval metric
        _update_pending_approval_metric()

        # Start execution
        self.resume_execution(execution_id)
        return True

    def cancel_execution(self, execution_id: int) -> bool:
        """
        Cancel an execution.

        Args:
            execution_id: The execution ID to cancel

        Returns:
            True if cancelled, False otherwise
        """
        execution = get_execution(execution_id)
        if not execution:
            return False

        if ExecutionStatus.is_terminal(execution.status):
            logger.log(
                level=30,
                msg=f"Cannot cancel execution {execution_id}: "
                    f"already in terminal state {execution.status.value}"
            )
            return False

        now = _now()
        success = update_execution_status(
            execution_id,
            ExecutionStatus.CANCELLED,
            completed_at=now
        )

        if success:
            logger.log(
                level=20,
                msg=f"Execution {execution_id} cancelled"
            )

            # Load playbook to get name for metrics
            playbook = get_playbook_by_id(execution.playbook_id)
            playbook_name = playbook.name if playbook else "unknown"
            record_playbook_execution(playbook_name, "cancelled")

            # Record duration if we have a start time
            if execution.started_at:
                duration = (now - execution.started_at).total_seconds()
                record_playbook_execution_duration(playbook_name, duration)

            # Update pending approval gauge
            _update_pending_approval_metric()

        return success

    def _execute_steps(self, execution: PlaybookExecution) -> None:
        """
        Execute playbook steps starting from current_step.

        Args:
            execution: The execution to process
        """
        if not execution.playbook:
            self._fail_execution(execution, "No playbook loaded")
            return

        playbook = execution.playbook
        total_steps = len(playbook.steps)

        while execution.current_step < total_steps:
            step = playbook.steps[execution.current_step]
            step_name = step.name

            logger.log(
                level=20,
                msg=f"Executing step {execution.current_step + 1}/{total_steps}: "
                    f"{step_name}"
            )

            # Execute the step
            result = self._execute_step(step, execution)
            execution.step_results.append(result)

            # Calculate step duration
            step_duration_ms = None
            if result.started_at and result.completed_at:
                step_duration_ms = int(
                    (result.completed_at - result.started_at).total_seconds()
                    * 1000
                )

            # Get step type for audit log
            step_type_str = self._get_step_type(step).value

            # Check result
            if result.status == StepResultStatus.FAILED:
                # Log step failure to audit log
                if AUDIT_LOG_AVAILABLE:
                    log_step_failed(
                        execution_id=execution.execution_id or 0,
                        step_name=step_name,
                        step_index=execution.current_step,
                        step_type=step_type_str,
                        error_message=result.error_message,
                        output=result.output,
                        duration_ms=step_duration_ms,
                    )

                self._fail_execution(
                    execution,
                    f"Step '{step_name}' failed: {result.error_message}"
                )
                return

            # Log step completion to audit log
            if AUDIT_LOG_AVAILABLE and result.status == StepResultStatus.COMPLETED:
                log_step_completed(
                    execution_id=execution.execution_id or 0,
                    step_name=step_name,
                    step_index=execution.current_step,
                    step_type=step_type_str,
                    output=result.output,
                    duration_ms=step_duration_ms,
                )

            if result.status == StepResultStatus.PENDING:
                # Step needs external completion (e.g., webhook not implemented)
                logger.log(
                    level=20,
                    msg=f"Step '{step_name}' pending external completion"
                )
                update_execution_status(
                    execution.execution_id or 0,
                    ExecutionStatus.WAITING,
                    current_step=execution.current_step
                )
                return

            # Move to next step
            execution.current_step += 1
            update_execution_status(
                execution.execution_id or 0,
                ExecutionStatus.RUNNING,
                current_step=execution.current_step
            )

        # All steps completed
        self._complete_execution(execution)

    def _execute_step(
        self,
        step: PlaybookStep,
        execution: PlaybookExecution
    ) -> StepResult:
        """
        Execute a single step based on its type.

        Args:
            step: The step to execute
            execution: The current execution context

        Returns:
            StepResult with execution outcome
        """
        step_type = self._get_step_type(step)

        executor = self._step_executors.get(step_type)
        if not executor:
            now = _now()
            return StepResult(
                result_id=None,
                execution_id=execution.execution_id or 0,
                step_name=step.name,
                step_index=execution.current_step,
                status=StepResultStatus.FAILED,
                error_message=f"No executor for step type: {step_type}",
                started_at=now,
                completed_at=now,
            )

        return executor(step, execution)

    def _get_step_type(self, step: PlaybookStep) -> StepType:
        """Get the StepType enum for a step object."""
        if isinstance(step, WaitStep):
            return StepType.WAIT
        elif isinstance(step, WebhookStep):
            return StepType.WEBHOOK
        elif isinstance(step, ScriptStep):
            return StepType.SCRIPT
        elif isinstance(step, ConditionStep):
            return StepType.CONDITION
        else:
            raise ValueError(f"Unknown step type: {type(step)}")

    def _execute_wait(
        self,
        step: PlaybookStep,
        execution: PlaybookExecution
    ) -> StepResult:
        """Execute a wait step."""
        if not isinstance(step, WaitStep):
            raise TypeError(f"Expected WaitStep, got {type(step)}")
        return execute_wait_step(step, execution)

    def _execute_webhook(
        self,
        step: PlaybookStep,
        execution: PlaybookExecution
    ) -> StepResult:
        """Execute a webhook step."""
        if not isinstance(step, WebhookStep):
            raise TypeError(f"Expected WebhookStep, got {type(step)}")
        return execute_webhook_step(step, execution)

    def _execute_script(
        self,
        step: PlaybookStep,
        execution: PlaybookExecution
    ) -> StepResult:
        """Execute a script step."""
        if not isinstance(step, ScriptStep):
            raise TypeError(f"Expected ScriptStep, got {type(step)}")
        return execute_script_step(step, execution)

    def _execute_condition(
        self,
        step: PlaybookStep,
        execution: PlaybookExecution
    ) -> StepResult:
        """Execute a condition step."""
        if not isinstance(step, ConditionStep):
            raise TypeError(f"Expected ConditionStep, got {type(step)}")
        return execute_condition_step(step, execution)

    def _fail_execution(
        self,
        execution: PlaybookExecution,
        error_message: str
    ) -> None:
        """Mark execution as failed."""
        now = _now()
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = now

        update_execution_status(
            execution.execution_id or 0,
            ExecutionStatus.FAILED,
            completed_at=now
        )

        logger.log(
            level=40,
            msg=f"Execution {execution.execution_id} failed: {error_message}"
        )

        # Record metrics
        playbook_name = (
            execution.playbook.name if execution.playbook else "unknown"
        )
        record_playbook_execution(playbook_name, "failed")

        # Record duration if we have a start time
        total_duration_ms = None
        if execution.started_at:
            duration = (now - execution.started_at).total_seconds()
            record_playbook_execution_duration(playbook_name, duration)
            total_duration_ms = int(duration * 1000)

        # Log execution failure to audit log
        if AUDIT_LOG_AVAILABLE:
            # Get service name if we have service_id
            service_name = None
            if execution.service_id:
                svc_result = db.query_db(
                    "SELECT name FROM services WHERE service_id = %s",
                    (execution.service_id,),
                    show_columns=True
                )
                if svc_result and svc_result != '[]':
                    try:
                        rows = json.loads(str(svc_result))
                        if rows:
                            service_name = rows[0].get('name')
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass

            # Get failed step info
            failed_step_name = None
            failed_step_index = None
            if execution.playbook and execution.current_step < len(
                execution.playbook.steps
            ):
                failed_step = execution.playbook.steps[execution.current_step]
                failed_step_name = failed_step.name
                failed_step_index = execution.current_step

            log_execution_failed(
                execution_id=execution.execution_id or 0,
                playbook_name=playbook_name,
                error_message=error_message,
                failed_step_name=failed_step_name,
                failed_step_index=failed_step_index,
                steps_completed=execution.current_step,
                total_duration_ms=total_duration_ms,
                service_name=service_name,
            )

        # Update pending approval gauge
        _update_pending_approval_metric()

    def _complete_execution(self, execution: PlaybookExecution) -> None:
        """Mark execution as completed successfully."""
        now = _now()
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = now

        update_execution_status(
            execution.execution_id or 0,
            ExecutionStatus.COMPLETED,
            completed_at=now
        )

        logger.log(
            level=20,
            msg=f"Execution {execution.execution_id} completed successfully"
        )

        # Record metrics
        playbook_name = (
            execution.playbook.name if execution.playbook else "unknown"
        )
        record_playbook_execution(playbook_name, "completed")

        # Record duration if we have a start time
        total_duration_ms = None
        if execution.started_at:
            duration = (now - execution.started_at).total_seconds()
            record_playbook_execution_duration(playbook_name, duration)
            total_duration_ms = int(duration * 1000)

        # Log execution completion to audit log
        if AUDIT_LOG_AVAILABLE:
            # Get service name if we have service_id
            service_name = None
            if execution.service_id:
                svc_result = db.query_db(
                    "SELECT name FROM services WHERE service_id = %s",
                    (execution.service_id,),
                    show_columns=True
                )
                if svc_result and svc_result != '[]':
                    try:
                        rows = json.loads(str(svc_result))
                        if rows:
                            service_name = rows[0].get('name')
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass

            log_execution_completed(
                execution_id=execution.execution_id or 0,
                playbook_name=playbook_name,
                steps_completed=execution.current_step,
                total_duration_ms=total_duration_ms,
                service_name=service_name,
            )

        # Update pending approval gauge
        _update_pending_approval_metric()


# ============================================================================
# Module-level convenience functions
# ============================================================================

# Global engine instance
_engine: Optional[PlaybookExecutionEngine] = None


def get_engine() -> PlaybookExecutionEngine:
    """Get the global playbook execution engine instance."""
    global _engine
    if _engine is None:
        _engine = PlaybookExecutionEngine()
    return _engine


def start_playbook_execution(
    playbook_id: int,
    service_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    skip_approval: bool = False
) -> Optional[PlaybookExecution]:
    """
    Convenience function to start a playbook execution.

    Args:
        playbook_id: ID of the playbook to execute
        service_id: Optional service ID
        context: Optional context variables
        skip_approval: Skip approval check

    Returns:
        PlaybookExecution object, or None on failure
    """
    return get_engine().start_execution(
        playbook_id=playbook_id,
        service_id=service_id,
        context=context,
        skip_approval=skip_approval
    )


def resume_playbook_execution(
    execution_id: int
) -> Optional[PlaybookExecution]:
    """
    Convenience function to resume a playbook execution.

    Args:
        execution_id: The execution ID to resume

    Returns:
        PlaybookExecution object, or None on failure
    """
    return get_engine().resume_execution(execution_id)


def approve_playbook_execution(execution_id: int) -> bool:
    """
    Convenience function to approve a playbook execution.

    Args:
        execution_id: The execution ID to approve

    Returns:
        True if approved and started, False otherwise
    """
    return get_engine().approve_execution(execution_id)


def cancel_playbook_execution(execution_id: int) -> bool:
    """
    Convenience function to cancel a playbook execution.

    Args:
        execution_id: The execution ID to cancel

    Returns:
        True if cancelled, False otherwise
    """
    return get_engine().cancel_execution(execution_id)
