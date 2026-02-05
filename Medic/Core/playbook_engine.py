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
from typing import Any, Optional

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.metrics import (
    record_playbook_execution,
    record_playbook_execution_duration,
    update_pending_approval_count,
)
from Medic.Core.utils.datetime_helpers import (
    now as get_now,
)

# Import models and database operations from playbook package
# Re-exports for backwards compatibility
from Medic.Core.playbook import (  # noqa: F401
    ExecutionStatus,
    StepResultStatus,
    StepResult,
    PlaybookExecution,
    StepExecutor,
    create_execution,
    get_execution,
    get_active_executions,
    get_pending_approval_executions,
    get_pending_approval_count,
    update_execution_status,
    create_step_result,
    update_step_result,
    get_step_results_for_execution,
    get_playbook_by_id,
)

# Import step executors from executors package
# Re-exports for backwards compatibility
from Medic.Core.playbook.executors import (  # noqa: F401
    execute_webhook_step,
    execute_script_step,
    execute_condition_step,
    execute_wait_step,
    # Re-export constants and helpers for backwards compatibility
    substitute_variables,
    substitute_all,
    VARIABLE_PATTERN,
    MAX_RESPONSE_BODY_SIZE,
    DEFAULT_WEBHOOK_TIMEOUT,
    get_registered_script,
    RegisteredScript,
    ALLOWED_SCRIPT_ENV_VARS,
    DEFAULT_SCRIPT_TIMEOUT,
    MAX_SCRIPT_MEMORY_BYTES,
    MAX_SCRIPT_OUTPUT_SIZE,
    check_heartbeat_received,
    DEFAULT_CONDITION_TIMEOUT,
    CONDITION_POLL_INTERVAL,
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

from Medic.Core.playbook_parser import (  # noqa: F401
    ApprovalMode,
    ConditionStep,
    OnFailureAction,
    Playbook,
    PlaybookStep,
    ScriptStep,
    StepType,
    WaitStep,
    WebhookStep,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


def _update_pending_approval_metric():
    """Update the pending approval gauge metric."""
    count = get_pending_approval_count()
    update_pending_approval_count(count)


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
        self._step_executors: dict[StepType, StepExecutor] = {
            StepType.WAIT: self._execute_wait,
            StepType.WEBHOOK: self._execute_webhook,
            StepType.SCRIPT: self._execute_script,
            StepType.CONDITION: self._execute_condition,
        }

    def start_execution(
        self,
        playbook_id: int,
        service_id: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
        skip_approval: bool = False,
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
                msg=f"Cannot start execution: playbook {playbook_id} not found",
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
            f"for '{playbook.name}' (status: {initial_status.value})",
        )

        # Log execution started to audit log
        if AUDIT_LOG_AVAILABLE:
            # Get service name if we have service_id
            service_name = None
            if service_id:
                svc_result = db.query_db(
                    "SELECT name FROM services WHERE service_id = %s",
                    (service_id,),
                    show_columns=True,
                )
                if svc_result and svc_result != "[]":
                    try:
                        rows = json.loads(str(svc_result))
                        if rows:
                            service_name = rows[0].get("name")
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass

            log_execution_started(
                execution_id=execution.execution_id or 0,
                playbook_id=playbook_id,
                playbook_name=playbook.name,
                service_id=service_id,
                service_name=service_name,
                trigger=context.get("trigger") if context else None,
                context=context,
            )

        # Update pending approval metric if applicable
        if initial_status == ExecutionStatus.PENDING_APPROVAL:
            _update_pending_approval_metric()

        # If running immediately, execute steps
        if initial_status == ExecutionStatus.RUNNING:
            self._execute_steps(execution)

        return execution

    def resume_execution(self, execution_id: int) -> Optional[PlaybookExecution]:
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
                level=30, msg=f"Cannot resume execution {execution_id}: not found"
            )
            return None

        if ExecutionStatus.is_terminal(execution.status):
            logger.log(
                level=30,
                msg=f"Cannot resume execution {execution_id}: "
                f"already in terminal state {execution.status.value}",
            )
            return execution

        # Load playbook
        playbook = get_playbook_by_id(execution.playbook_id)
        if not playbook:
            logger.log(
                level=40,
                msg=f"Cannot resume execution {execution_id}: "
                f"playbook {execution.playbook_id} not found",
            )
            self._fail_execution(execution, "Playbook not found during resume")
            return execution

        execution.playbook = playbook

        # Load existing step results
        execution.step_results = get_step_results_for_execution(execution_id)

        logger.log(
            level=20,
            msg=f"Resuming execution {execution_id} at step "
            f"{execution.current_step}",
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
                f"status is {execution.status.value}, not pending_approval",
            )
            return False

        # Update to running
        if not update_execution_status(execution_id, ExecutionStatus.RUNNING):
            return False

        logger.log(
            level=20, msg=f"Execution {execution_id} approved, starting execution"
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
                f"already in terminal state {execution.status.value}",
            )
            return False

        now = get_now()
        success = update_execution_status(
            execution_id, ExecutionStatus.CANCELLED, completed_at=now
        )

        if success:
            logger.log(level=20, msg=f"Execution {execution_id} cancelled")

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
                msg=f"Executing step {execution.current_step + 1}/"
                f"{total_steps}: {step_name}",
            )

            # Execute the step
            result = self._execute_step(step, execution)
            execution.step_results.append(result)

            # Calculate step duration
            step_duration_ms = None
            if result.started_at and result.completed_at:
                step_duration_ms = int(
                    (result.completed_at - result.started_at).total_seconds() * 1000
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
                    execution, f"Step '{step_name}' failed: {result.error_message}"
                )
                return

            # Log step completion to audit log
            is_completed = result.status == StepResultStatus.COMPLETED
            if AUDIT_LOG_AVAILABLE and is_completed:
                log_step_completed(
                    execution_id=execution.execution_id or 0,
                    step_name=step_name,
                    step_index=execution.current_step,
                    step_type=step_type_str,
                    output=result.output,
                    duration_ms=step_duration_ms,
                )

            if result.status == StepResultStatus.PENDING:
                # Step needs external completion (e.g., callback pending)
                logger.log(
                    level=20, msg=f"Step '{step_name}' pending external completion"
                )
                update_execution_status(
                    execution.execution_id or 0,
                    ExecutionStatus.WAITING,
                    current_step=execution.current_step,
                )
                return

            # Move to next step
            execution.current_step += 1
            update_execution_status(
                execution.execution_id or 0,
                ExecutionStatus.RUNNING,
                current_step=execution.current_step,
            )

        # All steps completed
        self._complete_execution(execution)

    def _execute_step(
        self, step: PlaybookStep, execution: PlaybookExecution
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
            now = get_now()
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
        self, step: PlaybookStep, execution: PlaybookExecution
    ) -> StepResult:
        """Execute a wait step."""
        if not isinstance(step, WaitStep):
            raise TypeError(f"Expected WaitStep, got {type(step)}")
        return execute_wait_step(step, execution)

    def _execute_webhook(
        self, step: PlaybookStep, execution: PlaybookExecution
    ) -> StepResult:
        """Execute a webhook step."""
        if not isinstance(step, WebhookStep):
            raise TypeError(f"Expected WebhookStep, got {type(step)}")
        return execute_webhook_step(step, execution)

    def _execute_script(
        self, step: PlaybookStep, execution: PlaybookExecution
    ) -> StepResult:
        """Execute a script step."""
        if not isinstance(step, ScriptStep):
            raise TypeError(f"Expected ScriptStep, got {type(step)}")
        return execute_script_step(step, execution)

    def _execute_condition(
        self, step: PlaybookStep, execution: PlaybookExecution
    ) -> StepResult:
        """Execute a condition step."""
        if not isinstance(step, ConditionStep):
            raise TypeError(f"Expected ConditionStep, got {type(step)}")
        return execute_condition_step(step, execution)

    def _fail_execution(self, execution: PlaybookExecution, error_message: str) -> None:
        """Mark execution as failed."""
        now = get_now()
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = now

        update_execution_status(
            execution.execution_id or 0, ExecutionStatus.FAILED, completed_at=now
        )

        logger.log(
            level=40, msg=f"Execution {execution.execution_id} failed: {error_message}"
        )

        # Record metrics
        playbook_name = execution.playbook.name if execution.playbook else "unknown"
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
                    show_columns=True,
                )
                if svc_result and svc_result != "[]":
                    try:
                        rows = json.loads(str(svc_result))
                        if rows:
                            service_name = rows[0].get("name")
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
        now = get_now()
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = now

        update_execution_status(
            execution.execution_id or 0, ExecutionStatus.COMPLETED, completed_at=now
        )

        logger.log(
            level=20, msg=f"Execution {execution.execution_id} completed successfully"
        )

        # Record metrics
        playbook_name = execution.playbook.name if execution.playbook else "unknown"
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
                    show_columns=True,
                )
                if svc_result and svc_result != "[]":
                    try:
                        rows = json.loads(str(svc_result))
                        if rows:
                            service_name = rows[0].get("name")
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
    context: Optional[dict[str, Any]] = None,
    skip_approval: bool = False,
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
        skip_approval=skip_approval,
    )


def resume_playbook_execution(execution_id: int) -> Optional[PlaybookExecution]:
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
