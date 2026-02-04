"""Playbook execution package.

This package provides the core functionality for playbook execution:
- Data models (ExecutionStatus, StepResultStatus, StepResult, etc.)
- Database operations (create/get/update executions and step results)

Usage:
    from Medic.Core.playbook import (
        # Models
        ExecutionStatus,
        StepResultStatus,
        StepResult,
        PlaybookExecution,
        StepExecutor,

        # Database operations
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
"""

# Models
from Medic.Core.playbook.models import (
    ExecutionStatus,
    StepResultStatus,
    StepResult,
    PlaybookExecution,
    StepExecutor,
)

# Database operations
from Medic.Core.playbook.db import (
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

__all__ = [
    # Models
    "ExecutionStatus",
    "StepResultStatus",
    "StepResult",
    "PlaybookExecution",
    "StepExecutor",
    # Database operations
    "create_execution",
    "get_execution",
    "get_active_executions",
    "get_pending_approval_executions",
    "get_pending_approval_count",
    "update_execution_status",
    "create_step_result",
    "update_step_result",
    "get_step_results_for_execution",
    "get_playbook_by_id",
]
