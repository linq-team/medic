"""Condition step executor.

This module handles execution of condition steps by polling until
a condition is met or timeout expires.

Features:
- Heartbeat received condition checking
- Configurable timeout and polling intervals
- Flexible on_failure handling (fail, continue, escalate)

Supported Condition Types:
    - heartbeat_received: Check if a service has received a heartbeat

Usage:
    from Medic.Core.playbook.executors.condition import execute_condition_step

    result = execute_condition_step(step, execution)
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.playbook.models import (
    PlaybookExecution,
    StepResult,
    StepResultStatus,
)
from Medic.Core.playbook.db import (
    create_step_result,
    update_step_result,
)
from Medic.Core.playbook_parser import (
    ConditionStep,
    ConditionType,
    OnFailureAction,
)
from Medic.Core.utils.datetime_helpers import now as get_now

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


# Default timeout for condition checks (seconds)
DEFAULT_CONDITION_TIMEOUT = 300  # 5 minutes

# Polling interval for condition checks (seconds)
CONDITION_POLL_INTERVAL = 5


def check_heartbeat_received(
    service_id: int, since: datetime, parameters: Dict[str, Any]
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
    min_count = parameters.get("min_count", 1)
    status_filter = parameters.get("status")

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

    if not result or result == "[]":
        return (False, "Failed to query heartbeat events")

    try:
        rows = json.loads(str(result))
        if not rows:
            return (False, "No heartbeat data returned")

        count = rows[0].get("count", 0)
        if count >= min_count:
            return (
                True,
                f"Heartbeat received: {count} heartbeat(s) since "
                f"{since.isoformat()}",
            )
        else:
            return (
                False,
                f"Waiting for heartbeat: {count}/{min_count} received since "
                f"{since.isoformat()}",
            )
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        return (False, f"Error parsing heartbeat data: {e}")


def execute_condition_step(
    step: ConditionStep, execution: PlaybookExecution
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
    now = get_now()
    step_index = execution.current_step
    condition_start = now

    # Create step result as running
    result = create_step_result(
        execution_id=execution.execution_id or 0,
        step_name=step.name,
        step_index=step_index,
        status=StepResultStatus.RUNNING,
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
        service_id = step.parameters.get("service_id")

    if not service_id:
        completed_at = get_now()
        error_msg = (
            "No service_id available for condition check. "
            "Provide service_id in execution or step parameters."
        )
        logger.log(level=30, msg=f"Condition step '{step.name}' failed: {error_msg}")

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
        msg=f"Condition step '{step.name}': "
        f"checking {step.condition_type.value} "
        f"for service {service_id} (timeout: {timeout}s)",
    )

    # Poll for condition until timeout
    condition_met = False
    last_message = ""

    while True:
        # Check if timeout has expired
        elapsed = (get_now() - condition_start).total_seconds()
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
            cond_type = step.condition_type.value
            last_message = f"Unknown condition type: {cond_type}"
            break

        if condition_met:
            break

        # Sleep before next poll
        remaining = timeout - elapsed
        sleep_time = min(CONDITION_POLL_INTERVAL, remaining)
        if sleep_time > 0:
            time.sleep(sleep_time)

    completed_at = get_now()
    elapsed_total = (completed_at - condition_start).total_seconds()

    if condition_met:
        # Condition was met
        output_msg = (
            f"Condition '{step.condition_type.value}' met after "
            f"{elapsed_total:.1f}s\n{last_message}"
        )
        logger.log(
            level=20, msg=f"Condition step '{step.name}' completed: {last_message}"
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
            f"(on_failure=continue): {last_message}",
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
            msg=f"Condition step '{step.name}' failed, escalating: {error_msg}",
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
        logger.log(level=30, msg=f"Condition step '{step.name}' failed: {error_msg}")

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
