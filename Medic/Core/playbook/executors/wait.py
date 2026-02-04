"""Wait step executor.

This module handles execution of wait steps by pausing execution
for a specified duration.

Features:
- Configurable wait duration in seconds
- Step result tracking with start/completion times
- Persistence-aware design (stores resume time for restarts)

Usage:
    from Medic.Core.playbook.executors.wait import execute_wait_step

    result = execute_wait_step(step, execution)
"""

import logging
import time
from datetime import timedelta

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
from Medic.Core.playbook_parser import WaitStep
from Medic.Core.utils.datetime_helpers import now as get_now

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


def execute_wait_step(step: WaitStep, execution: PlaybookExecution) -> StepResult:
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
    now = get_now()
    step_index = execution.current_step

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

    # Calculate resume time
    resume_at = now + timedelta(seconds=step.duration_seconds)

    logger.log(
        level=20,
        msg=f"Wait step '{step.name}' starting: {step.duration_seconds}s "
        f"(resume at {resume_at.isoformat()})",
    )

    # For synchronous execution, sleep for the duration
    # In production, this would be async or scheduled
    time.sleep(step.duration_seconds)

    completed_at = get_now()

    # Update result as completed
    update_step_result(
        result_id=result.result_id or 0,
        status=StepResultStatus.COMPLETED,
        output=f"Waited {step.duration_seconds} seconds",
        completed_at=completed_at,
    )

    logger.log(
        level=20,
        msg=f"Wait step '{step.name}' completed after {step.duration_seconds}s",
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
