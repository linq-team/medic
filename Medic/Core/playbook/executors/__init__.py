"""Playbook step executors package.

This package contains the step executor functions for different step types:
- webhook: Execute HTTP webhook requests
- script: Execute registered scripts
- condition: Wait for conditions to be met
- wait: Pause execution for a duration

Each executor module provides an `execute_*_step` function that takes a step
and execution context, and returns a StepResult.

Usage:
    from Medic.Core.playbook.executors import (
        execute_webhook_step,
        execute_script_step,
        execute_condition_step,
        execute_wait_step,
    )

    # Execute a webhook step
    result = execute_webhook_step(step, execution)
"""

# Webhook executor
from Medic.Core.playbook.executors.webhook import (
    execute_webhook_step,
    substitute_variables,
    substitute_all,
    VARIABLE_PATTERN,
    MAX_RESPONSE_BODY_SIZE,
    DEFAULT_WEBHOOK_TIMEOUT,
)

# Script executor
from Medic.Core.playbook.executors.script import (
    execute_script_step,
    get_registered_script,
    RegisteredScript,
    ALLOWED_SCRIPT_ENV_VARS,
    DEFAULT_SCRIPT_TIMEOUT,
    MAX_SCRIPT_MEMORY_BYTES,
    MAX_SCRIPT_OUTPUT_SIZE,
)

# Condition executor
from Medic.Core.playbook.executors.condition import (
    execute_condition_step,
    check_heartbeat_received,
    DEFAULT_CONDITION_TIMEOUT,
    CONDITION_POLL_INTERVAL,
)

# Wait executor
from Medic.Core.playbook.executors.wait import (
    execute_wait_step,
)

__all__ = [
    # Webhook
    "execute_webhook_step",
    "substitute_variables",
    "substitute_all",
    "VARIABLE_PATTERN",
    "MAX_RESPONSE_BODY_SIZE",
    "DEFAULT_WEBHOOK_TIMEOUT",
    # Script
    "execute_script_step",
    "get_registered_script",
    "RegisteredScript",
    "ALLOWED_SCRIPT_ENV_VARS",
    "DEFAULT_SCRIPT_TIMEOUT",
    "MAX_SCRIPT_MEMORY_BYTES",
    "MAX_SCRIPT_OUTPUT_SIZE",
    # Condition
    "execute_condition_step",
    "check_heartbeat_received",
    "DEFAULT_CONDITION_TIMEOUT",
    "CONDITION_POLL_INTERVAL",
    # Wait
    "execute_wait_step",
]
