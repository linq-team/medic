"""Playbook alert integration for Medic.

This module provides the integration between the alert system and the
playbook execution engine. When an alert fires, it checks for matching
playbook triggers and starts playbook executions accordingly.

Key functions:
- trigger_playbook_for_alert: Check for matching playbook and start execution
- should_trigger_playbook: Check if a playbook should be triggered for an alert

Usage:
    from Medic.Core.playbook_alert_integration import trigger_playbook_for_alert

    # When an alert fires
    execution = trigger_playbook_for_alert(
        service_id=123,
        service_name="worker-prod-01",
        consecutive_failures=3
    )
    if execution:
        print(f"Started playbook execution {execution.execution_id}")
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import Medic.Helpers.logSettings as logLevel
from Medic.Core.playbook_engine import (
    ApprovalMode,
    ExecutionStatus,
    PlaybookExecution,
    get_playbook_by_id,
    start_playbook_execution,
)
from Medic.Core.playbook_triggers import (
    MatchedPlaybook,
    find_playbook_for_alert,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


@dataclass
class PlaybookTriggerResult:
    """Result of attempting to trigger a playbook for an alert."""

    triggered: bool
    execution: Optional[PlaybookExecution] = None
    playbook: Optional[MatchedPlaybook] = None
    status: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "triggered": self.triggered,
            "execution_id": (
                self.execution.execution_id if self.execution else None
            ),
            "playbook_id": self.playbook.playbook_id if self.playbook else None,
            "playbook_name": (
                self.playbook.playbook_name if self.playbook else None
            ),
            "status": self.status,
            "message": self.message,
        }


def should_trigger_playbook(
    service_name: str,
    consecutive_failures: int
) -> Optional[MatchedPlaybook]:
    """
    Check if a playbook should be triggered for an alert.

    This function checks the playbook triggers to see if any match
    the given service name and failure count.

    Args:
        service_name: Name of the service that is alerting
        consecutive_failures: Number of consecutive alert cycles

    Returns:
        MatchedPlaybook if a trigger matches, None otherwise
    """
    return find_playbook_for_alert(service_name, consecutive_failures)


def trigger_playbook_for_alert(
    service_id: int,
    service_name: str,
    consecutive_failures: int,
    alert_context: Optional[Dict[str, Any]] = None
) -> PlaybookTriggerResult:
    """
    Trigger a playbook execution for an alerting service.

    This is the main function to call when an alert fires. It:
    1. Checks for a matching playbook trigger
    2. Loads the playbook and checks its approval setting
    3. Creates an execution with the appropriate status:
       - approval=none: Starts execution immediately (status=running)
       - approval=required: Creates pending_approval execution
       - approval=timeout:Xm: Creates pending_approval with auto-approve

    Args:
        service_id: ID of the alerting service
        service_name: Name of the alerting service
        consecutive_failures: Number of consecutive alert cycles
        alert_context: Optional additional context (alert_id, etc.)

    Returns:
        PlaybookTriggerResult with execution details
    """
    # Check for matching playbook
    matched = find_playbook_for_alert(service_name, consecutive_failures)

    if not matched:
        logger.log(
            level=10,
            msg=f"No playbook trigger matched for service '{service_name}' "
                f"with {consecutive_failures} consecutive failures"
        )
        return PlaybookTriggerResult(
            triggered=False,
            status="no_match",
            message=f"No playbook trigger matched for '{service_name}'"
        )

    logger.log(
        level=20,
        msg=f"Playbook '{matched.playbook_name}' matched for service "
            f"'{service_name}' (failures: {consecutive_failures}/"
            f"{matched.consecutive_failures})"
    )

    # Load the full playbook to check approval settings
    playbook = get_playbook_by_id(matched.playbook_id)
    if not playbook:
        logger.log(
            level=40,
            msg=f"Failed to load playbook {matched.playbook_id} for execution"
        )
        return PlaybookTriggerResult(
            triggered=False,
            playbook=matched,
            status="error",
            message=f"Failed to load playbook {matched.playbook_id}"
        )

    # Build execution context
    context = {
        "SERVICE_ID": service_id,
        "SERVICE_NAME": service_name,
        "CONSECUTIVE_FAILURES": consecutive_failures,
        "TRIGGER_ID": matched.trigger_id,
    }
    if alert_context:
        context.update(alert_context)

    # Determine if we should skip approval based on playbook settings
    skip_approval = playbook.approval == ApprovalMode.NONE

    # Start playbook execution
    execution = start_playbook_execution(
        playbook_id=matched.playbook_id,
        service_id=service_id,
        context=context,
        skip_approval=skip_approval
    )

    if not execution:
        logger.log(
            level=40,
            msg=f"Failed to start playbook execution for "
                f"'{matched.playbook_name}'"
        )
        return PlaybookTriggerResult(
            triggered=False,
            playbook=matched,
            status="error",
            message="Failed to create playbook execution"
        )

    # Determine appropriate status message
    if execution.status == ExecutionStatus.RUNNING:
        status = "running"
        message = (
            f"Playbook '{matched.playbook_name}' started immediately "
            f"(approval=none)"
        )
    elif execution.status == ExecutionStatus.PENDING_APPROVAL:
        if playbook.approval == ApprovalMode.TIMEOUT:
            status = "pending_approval"
            message = (
                f"Playbook '{matched.playbook_name}' awaiting approval "
                f"(auto-approve in {playbook.approval_timeout_minutes}m)"
            )
        else:
            status = "pending_approval"
            message = (
                f"Playbook '{matched.playbook_name}' awaiting approval"
            )
    else:
        status = execution.status.value
        message = f"Playbook '{matched.playbook_name}' status: {status}"

    logger.log(
        level=20,
        msg=f"Playbook execution {execution.execution_id} created for "
            f"'{matched.playbook_name}': {message}"
    )

    return PlaybookTriggerResult(
        triggered=True,
        execution=execution,
        playbook=matched,
        status=status,
        message=message
    )


def get_alert_consecutive_failures(alert_cycle: int) -> int:
    """
    Convert alert cycle count to consecutive failures for trigger matching.

    The alert_cycle in the alerts table tracks how many cycles an alert
    has been active. For playbook trigger purposes, we use this as the
    consecutive failure count.

    When an alert is first created, alert_cycle is 1.
    Each subsequent check increments it by 1.

    Args:
        alert_cycle: Current alert cycle count from alerts table

    Returns:
        Number to use for consecutive_failures matching
    """
    # alert_cycle starts at 1 when alert is created
    # For trigger matching, we use the cycle count directly
    return max(1, alert_cycle)
