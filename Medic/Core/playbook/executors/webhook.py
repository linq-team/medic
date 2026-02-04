"""Webhook step executor.

This module handles execution of webhook steps by making HTTP requests
with variable and secret substitution.

Features:
- Variable substitution using ${VAR_NAME} syntax
- Secret substitution using ${secrets.SECRET_NAME} syntax
- URL validation for SSRF prevention
- Configurable timeouts and success codes
- Response truncation for large responses

Usage:
    from Medic.Core.playbook.executors.webhook import execute_webhook_step

    result = execute_webhook_step(step, execution)
"""

import json
import logging
import re
from typing import Any, Callable, Dict, Optional

import requests

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
from Medic.Core.playbook_parser import WebhookStep
from Medic.Core.url_validator import InvalidURLError, validate_url
from Medic.Core.utils.datetime_helpers import now as get_now

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


# Maximum response body size to store (bytes)
MAX_RESPONSE_BODY_SIZE = 4096

# HTTP timeout for webhook requests (seconds)
DEFAULT_WEBHOOK_TIMEOUT = 30

# Variable pattern for substitution: ${VAR_NAME}
VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Import secrets module - use try/except for graceful degradation
try:
    from Medic.Core.secrets import substitute_secrets

    SECRETS_AVAILABLE = True
except ImportError:
    SECRETS_AVAILABLE = False


def substitute_variables(value: Any, context: Dict[str, Any]) -> Any:
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


def substitute_all(
    value: Any, context: Dict[str, Any], secrets_cache: Optional[Dict[str, str]] = None
) -> Any:
    """
    Substitute both variables and secrets in a value.

    First substitutes ${VAR_NAME} variables from context, then
    substitutes ${secrets.SECRET_NAME} secrets from the database.

    Args:
        value: Value to substitute (string, dict, list, or other)
        context: Dictionary of variable values
        secrets_cache: Optional cache for resolved secrets

    Returns:
        Value with all substitutions applied

    Raises:
        SecretNotFoundError: If a referenced secret doesn't exist
        DecryptionError: If secret decryption fails
    """
    # First substitute regular variables
    result = substitute_variables(value, context)

    # Then substitute secrets if available
    if SECRETS_AVAILABLE:
        cache = secrets_cache if secrets_cache is not None else {}
        result = substitute_secrets(result, cache)

    return result


def _build_webhook_context(execution: PlaybookExecution) -> Dict[str, Any]:
    """
    Build the variable context for webhook substitution.

    Args:
        execution: The current playbook execution

    Returns:
        Dictionary of available variables
    """
    context = dict(execution.context)  # Copy execution context

    # Add standard variables
    context["EXECUTION_ID"] = execution.execution_id
    context["PLAYBOOK_ID"] = execution.playbook_id
    context["SERVICE_ID"] = execution.service_id

    # Add playbook name if available
    if execution.playbook:
        context["PLAYBOOK_NAME"] = execution.playbook.name

    # Get service name from database if we have service_id
    if execution.service_id:
        service_result = db.query_db(
            "SELECT name FROM services WHERE service_id = %s",
            (execution.service_id,),
            show_columns=True,
        )
        if service_result and service_result != "[]":
            try:
                rows = json.loads(str(service_result))
                if rows:
                    context["SERVICE_NAME"] = rows[0].get("name", "")
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    return context


def execute_webhook_step(
    step: WebhookStep,
    execution: PlaybookExecution,
    http_client: Optional[Callable[..., requests.Response]] = None,
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

    # Build variable context
    context = _build_webhook_context(execution)

    # Substitute variables and secrets in URL, headers, and body
    # Secrets use ${secrets.SECRET_NAME} syntax
    try:
        url = substitute_all(step.url, context)
        headers = substitute_all(step.headers, context)
        body = substitute_all(step.body, context) if step.body else None
    except Exception as e:
        # Handle secret substitution errors
        completed_at = get_now()
        error_msg = f"Variable/secret substitution failed: {e}"
        logger.log(level=30, msg=f"Webhook step '{step.name}' failed: {error_msg}")

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

    # Validate URL for SSRF prevention
    try:
        validate_url(url)
    except InvalidURLError:
        completed_at = get_now()
        error_msg = "Invalid webhook URL"
        logger.log(
            level=30, msg=f"Webhook step '{step.name}' failed: URL validation failed"
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

    logger.log(level=20, msg=f"Webhook step '{step.name}': {step.method} {url}")

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
            timeout=timeout,
        )

        # Truncate response body if too large
        response_body = response.text
        if len(response_body) > MAX_RESPONSE_BODY_SIZE:
            response_body = response_body[:MAX_RESPONSE_BODY_SIZE]
            response_body += "...[truncated]"

        # Check success condition (status code)
        is_success = response.status_code in step.success_codes

        completed_at = get_now()

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
                f"(status: {response.status_code})",
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
            logger.log(level=30, msg=f"Webhook step '{step.name}' failed: {error_msg}")

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
        completed_at = get_now()
        error_msg = f"Request timed out after {timeout}s"
        logger.log(level=30, msg=f"Webhook step '{step.name}' failed: {error_msg}")

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
        completed_at = get_now()
        error_msg = f"Connection error: {str(e)}"
        logger.log(level=30, msg=f"Webhook step '{step.name}' failed: {error_msg}")

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
        completed_at = get_now()
        error_msg = f"Request failed: {str(e)}"
        logger.log(level=30, msg=f"Webhook step '{step.name}' failed: {error_msg}")

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
