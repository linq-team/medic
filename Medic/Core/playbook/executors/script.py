"""Script step executor.

This module handles execution of script steps by running pre-registered
scripts with sandboxed environment and resource limits.

Features:
- Only pre-registered scripts can be executed (security)
- Variable and secret substitution in script content
- Environment variable filtering (allowlist-based)
- Resource limits (timeout, memory)
- Output capture and truncation

Security Model:
    Scripts run in a restricted environment with:
    - Only allowlisted environment variables passed
    - Memory and CPU limits enforced
    - Output size limits

Usage:
    from Medic.Core.playbook.executors.script import execute_script_step

    result = execute_script_step(step, execution)
"""

import json
import logging
import os
import resource
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Optional

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
from Medic.Core.playbook_parser import ScriptStep
from Medic.Core.utils.datetime_helpers import now as get_now

# Import substitute_all from webhook module to avoid duplication
from Medic.Core.playbook.executors.webhook import (
    substitute_all,
    _build_webhook_context,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


# Default timeout for script execution (seconds)
DEFAULT_SCRIPT_TIMEOUT = 30

# Maximum memory limit for script execution (bytes) - 256 MB
MAX_SCRIPT_MEMORY_BYTES = 256 * 1024 * 1024

# Maximum output size to capture (bytes)
MAX_SCRIPT_OUTPUT_SIZE = 8192

# Allowlist of environment variables that can be passed to scripts.
# SECURITY: This prevents secrets (DATABASE_URL, MEDIC_SECRETS_KEY, API keys,
# etc.) from leaking to script execution environments. Only basic system
# variables and explicit MEDIC context variables are allowed.
ALLOWED_SCRIPT_ENV_VARS: list[str] = [
    "PATH",  # Required for finding executables
    "HOME",  # User home directory
    "USER",  # Current user name
    "LANG",  # Locale settings
    "LC_ALL",  # Locale override
    "TZ",  # Timezone
]


def _get_script_env(execution: "PlaybookExecution") -> dict[str, str]:
    """
    Build a safe environment dictionary for script execution.

    SECURITY MODEL:
    - Only allowlisted environment variables from parent process are passed
    - This prevents secrets (DATABASE_URL, MEDIC_SECRETS_KEY, AWS creds,
      etc.) from leaking to scripts
    - Explicit MEDIC context variables are added for script awareness
    - Additional vars can be added via MEDIC_ADDITIONAL_SCRIPT_ENV_VARS

    Args:
        execution: The current playbook execution context

    Returns:
        Dictionary of safe environment variables for subprocess execution
    """
    # Start with only allowlisted environment variables
    safe_env: dict[str, str] = {}

    # Get the base allowlist
    allowed_vars = set(ALLOWED_SCRIPT_ENV_VARS)

    # Allow extending the allowlist via environment variable
    # MEDIC_ADDITIONAL_SCRIPT_ENV_VARS is comma-separated list of var names
    additional_vars = os.environ.get("MEDIC_ADDITIONAL_SCRIPT_ENV_VARS", "")
    if additional_vars:
        for var_name in additional_vars.split(","):
            var_name = var_name.strip()
            if var_name:
                allowed_vars.add(var_name)

    # Copy only allowed variables from the current environment
    for var_name in allowed_vars:
        if var_name in os.environ:
            safe_env[var_name] = os.environ[var_name]

    # Add explicit MEDIC context variables (these are always safe to expose)
    safe_env["MEDIC_EXECUTION_ID"] = str(execution.execution_id or "")
    safe_env["MEDIC_PLAYBOOK_ID"] = str(execution.playbook_id)
    safe_env["MEDIC_SERVICE_ID"] = str(execution.service_id or "")

    return safe_env


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
        show_columns=True,
    )

    if not result or result == "[]":
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    row = rows[0]
    return RegisteredScript(
        script_id=row["script_id"],
        name=row["name"],
        content=row["content"],
        interpreter=row["interpreter"],
        timeout_seconds=row.get("timeout_seconds", DEFAULT_SCRIPT_TIMEOUT),
    )


def _substitute_script_variables(
    script_content: str, context: dict[str, Any], parameters: dict[str, Any]
) -> str:
    """
    Substitute variables and secrets in script content.

    Supports ${VAR_NAME} syntax from context and parameters,
    and ${secrets.SECRET_NAME} syntax for encrypted secrets.
    Parameters override context variables.

    Args:
        script_content: The script content with variables
        context: Execution context variables
        parameters: Step-specific parameters

    Returns:
        Script content with variables and secrets substituted

    Raises:
        SecretNotFoundError: If a referenced secret doesn't exist
        DecryptionError: If secret decryption fails
    """
    # Merge context and parameters (parameters take precedence)
    merged = dict(context)
    merged.update(parameters)

    # Use substitute_all to handle both variables and secrets
    return str(substitute_all(script_content, merged))


def execute_script_step(step: ScriptStep, execution: PlaybookExecution) -> StepResult:
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

    # Look up the registered script by name
    script = get_registered_script(step.script_name)
    if not script:
        completed_at = get_now()
        error_msg = (
            f"Script '{step.script_name}' not found in registered scripts. "
            "Only pre-registered scripts can be executed for security."
        )
        logger.log(level=30, msg=f"Script step '{step.name}' failed: {error_msg}")

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

    # Substitute variables and secrets in script content
    try:
        script_content = _substitute_script_variables(
            script.content, context, step.parameters
        )
    except Exception as e:
        # Handle secret substitution errors
        completed_at = get_now()
        error_msg = f"Variable/secret substitution failed: {e}"
        logger.log(level=30, msg=f"Script step '{step.name}' failed: {error_msg}")

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

    # Determine interpreter command
    if script.interpreter == "python":
        interpreter_cmd = ["python3", "-u"]
    elif script.interpreter == "bash":
        interpreter_cmd = ["bash", "-e"]
    else:
        completed_at = get_now()
        error_msg = f"Unsupported interpreter: {script.interpreter}"
        logger.log(level=30, msg=f"Script step '{step.name}' failed: {error_msg}")

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
    timeout = step.timeout_seconds or script.timeout_seconds
    timeout = timeout or DEFAULT_SCRIPT_TIMEOUT

    logger.log(
        level=20,
        msg=f"Script step '{step.name}': executing '{script.name}' "
        f"with {script.interpreter} (timeout: {timeout}s)",
    )

    try:
        # Write script to temporary file
        suffix = ".py" if script.interpreter == "python" else ".sh"
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(script_content)
            script_path = f.name

        # Set resource limits for the subprocess
        def set_limits():
            """Set resource limits for the child process."""
            try:
                # Set memory limit (virtual memory)
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (MAX_SCRIPT_MEMORY_BYTES, MAX_SCRIPT_MEMORY_BYTES),
                )
                # Set CPU time limit (as backup to timeout)
                resource.setrlimit(resource.RLIMIT_CPU, (timeout + 5, timeout + 10))
            except (ValueError, resource.error):
                # Resource limits may not be available on all platforms
                pass

        # Execute the script
        # Build safe environment (allowlisted vars only)
        script_env = _get_script_env(execution)

        proc = subprocess.run(
            interpreter_cmd + [script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=set_limits,
            env=script_env,
        )

        # Clean up temp file
        try:
            os.unlink(script_path)
        except OSError:
            pass

        # Capture output (truncate if needed)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        combined_output = stdout + (f"\n[STDERR]\n{stderr}" if stderr else "")

        if len(combined_output) > MAX_SCRIPT_OUTPUT_SIZE:
            combined_output = combined_output[:MAX_SCRIPT_OUTPUT_SIZE]
            combined_output += "\n...[output truncated]"

        completed_at = get_now()

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
                f"(exit code: 0)",
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
            logger.log(level=30, msg=f"Script step '{step.name}' failed: {error_msg}")

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

        completed_at = get_now()
        error_msg = f"Script execution timed out after {timeout}s"
        logger.log(level=30, msg=f"Script step '{step.name}' failed: {error_msg}")

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

        completed_at = get_now()
        error_msg = f"Script execution failed: {str(e)}"
        logger.log(level=30, msg=f"Script step '{step.name}' failed: {error_msg}")

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
