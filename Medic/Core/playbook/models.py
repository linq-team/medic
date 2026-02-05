"""Playbook execution data models.

This module contains the core data models for playbook execution:
- ExecutionStatus: Enum for playbook execution states
- StepResultStatus: Enum for individual step result states
- StepResult: Dataclass representing a single step's execution result
- PlaybookExecution: Dataclass representing a full playbook execution instance

Usage:
    from Medic.Core.playbook.models import (
        ExecutionStatus,
        StepResultStatus,
        StepResult,
        PlaybookExecution,
    )

    # Create a new execution
    execution = PlaybookExecution(
        execution_id=1,
        playbook_id=10,
        service_id=5,
        status=ExecutionStatus.RUNNING,
    )

    # Create a step result
    result = StepResult(
        result_id=1,
        execution_id=1,
        step_name="notify_slack",
        step_index=0,
        status=StepResultStatus.COMPLETED,
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from Medic.Core.playbook_parser import Playbook, PlaybookStep


class ExecutionStatus(str, Enum):
    """Status of a playbook execution.

    States:
        PENDING_APPROVAL: Waiting for human approval before execution
        RUNNING: Currently executing steps
        WAITING: Paused on a wait step
        COMPLETED: All steps finished successfully
        FAILED: Execution failed on a step
        CANCELLED: Execution was cancelled
    """

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
    """Status of a step result.

    States:
        PENDING: Not yet started
        RUNNING: Currently executing
        COMPLETED: Finished successfully
        FAILED: Step failed
        SKIPPED: Step was skipped
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a single step.

    Attributes:
        result_id: Database ID for this result record
        execution_id: ID of the parent execution
        step_name: Name of the step
        step_index: Zero-based index of the step in the playbook
        status: Current status of the step
        output: Output text from the step execution
        error_message: Error message if the step failed
        started_at: When the step started executing
        completed_at: When the step finished executing
    """

    result_id: Optional[int]
    execution_id: int
    step_name: str
    step_index: int
    status: StepResultStatus
    output: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "result_id": self.result_id,
            "execution_id": self.execution_id,
            "step_name": self.step_name,
            "step_index": self.step_index,
            "status": self.status.value,
            "output": self.output,
            "error_message": self.error_message,
            "started_at": (self.started_at.isoformat() if self.started_at else None),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class PlaybookExecution:
    """Represents a playbook execution instance.

    Attributes:
        execution_id: Database ID for this execution record
        playbook_id: ID of the playbook being executed
        service_id: Optional ID of the service this execution is for
        status: Current execution status
        current_step: Index of the current/next step to execute
        started_at: When execution started
        completed_at: When execution finished
        created_at: When the record was created
        updated_at: When the record was last updated
        playbook: Loaded playbook object (not persisted, loaded on demand)
        step_results: List of step results (loaded on demand)
        context: Context variables for step execution
    """

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
    playbook: Optional["Playbook"] = None
    # Step results (loaded on demand)
    step_results: list[StepResult] = field(default_factory=list)
    # Context variables for step execution
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "playbook_id": self.playbook_id,
            "service_id": self.service_id,
            "status": self.status.value,
            "current_step": self.current_step,
            "started_at": (self.started_at.isoformat() if self.started_at else None),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "created_at": (self.created_at.isoformat() if self.created_at else None),
            "updated_at": (self.updated_at.isoformat() if self.updated_at else None),
            "step_results": [sr.to_dict() for sr in self.step_results],
            "context": self.context,
        }


# Type alias for step executor functions
StepExecutor = Callable[["PlaybookStep", PlaybookExecution], StepResult]
