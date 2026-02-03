"""Playbook execution engine for Medic.

This module provides the core execution engine for running playbooks.
It processes steps sequentially, persists state after each step to survive
restarts, and supports wait steps for pausing execution.

The engine is designed to:
- Process steps sequentially
- Persist state after each step (survives restart)
- Support wait steps (pause execution for duration)
- Support webhook steps with variable substitution
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
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import pytz
import requests

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.playbook_parser import (
    ApprovalMode,
    ConditionStep,
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


def execute_script_step_placeholder(
    step: ScriptStep,
    execution: PlaybookExecution
) -> StepResult:
    """
    Placeholder for script step execution.

    This will be implemented in US-031.

    Args:
        step: The ScriptStep to execute
        execution: The current execution context

    Returns:
        StepResult (placeholder - always returns pending)
    """
    now = _now()

    logger.log(
        level=20,
        msg=f"Script step '{step.name}' execution not yet implemented"
    )

    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=execution.current_step,
        status=StepResultStatus.PENDING
    )

    return StepResult(
        result_id=result.result_id if result else None,
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=execution.current_step,
        status=StepResultStatus.PENDING,
        output="Script execution not yet implemented",
        started_at=now,
    )


def execute_condition_step_placeholder(
    step: ConditionStep,
    execution: PlaybookExecution
) -> StepResult:
    """
    Placeholder for condition step execution.

    This will be implemented in US-032.

    Args:
        step: The ConditionStep to execute
        execution: The current execution context

    Returns:
        StepResult (placeholder - always returns pending)
    """
    now = _now()

    logger.log(
        level=20,
        msg=f"Condition step '{step.name}' execution not yet implemented"
    )

    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=execution.current_step,
        status=StepResultStatus.PENDING
    )

    return StepResult(
        result_id=result.result_id if result else None,
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=execution.current_step,
        status=StepResultStatus.PENDING,
        output="Condition check not yet implemented",
        started_at=now,
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

            # Check result
            if result.status == StepResultStatus.FAILED:
                self._fail_execution(
                    execution,
                    f"Step '{step_name}' failed: {result.error_message}"
                )
                return

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
        """Execute a script step (placeholder)."""
        if not isinstance(step, ScriptStep):
            raise TypeError(f"Expected ScriptStep, got {type(step)}")
        return execute_script_step_placeholder(step, execution)

    def _execute_condition(
        self,
        step: PlaybookStep,
        execution: PlaybookExecution
    ) -> StepResult:
        """Execute a condition step (placeholder)."""
        if not isinstance(step, ConditionStep):
            raise TypeError(f"Expected ConditionStep, got {type(step)}")
        return execute_condition_step_placeholder(step, execution)

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
