"""Playbook YAML parser for Medic.

This module provides functionality to parse and validate playbook YAML
definitions. Playbooks define automated remediation steps that can be
triggered by alerts.

Supported step types:
- webhook: HTTP request to external URL
- script: Execute pre-registered script
- wait: Pause execution for duration
- condition: Check condition before proceeding

Approval settings:
- none: Execute immediately without approval
- required: Require human approval before execution
- timeout:Xm: Auto-approve after X minutes if no response
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    """Supported playbook step types."""

    WEBHOOK = "webhook"
    SCRIPT = "script"
    WAIT = "wait"
    CONDITION = "condition"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid step type."""
        try:
            cls(value.lower())
            return True
        except ValueError:
            return False


class ApprovalMode(str, Enum):
    """Approval mode for playbook execution."""

    NONE = "none"
    REQUIRED = "required"
    TIMEOUT = "timeout"  # timeout:Xm format

    @classmethod
    def parse(cls, value: str) -> tuple["ApprovalMode", Optional[int]]:
        """
        Parse an approval setting string.

        Args:
            value: Approval setting string (e.g., "none", "required",
                   "timeout:5m")

        Returns:
            Tuple of (ApprovalMode, timeout_minutes or None)

        Raises:
            ValueError: If the value is invalid
        """
        if not value or not isinstance(value, str):
            raise ValueError("Approval setting must be a non-empty string")

        value = value.strip().lower()

        if value == "none":
            return (cls.NONE, None)
        elif value == "required":
            return (cls.REQUIRED, None)
        elif value.startswith("timeout:"):
            # Parse timeout:Xm format
            timeout_str = value[8:]  # Remove "timeout:"
            match = re.match(r"^(\d+)m$", timeout_str)
            if not match:
                raise ValueError(
                    f"Invalid timeout format: '{value}'. "
                    "Expected 'timeout:Xm' where X is minutes"
                )
            minutes = int(match.group(1))
            if minutes <= 0:
                raise ValueError("Timeout must be a positive number")
            return (cls.TIMEOUT, minutes)
        else:
            raise ValueError(
                f"Invalid approval setting: '{value}'. "
                "Must be 'none', 'required', or 'timeout:Xm'"
            )


class OnFailureAction(str, Enum):
    """Action to take when a step fails."""

    FAIL = "fail"  # Stop playbook execution
    CONTINUE = "continue"  # Continue to next step
    ESCALATE = "escalate"  # Escalate to on-call


class ConditionType(str, Enum):
    """Supported condition types for condition steps."""

    HEARTBEAT_RECEIVED = "heartbeat_received"


@dataclass
class WebhookStep:
    """Webhook step configuration."""

    name: str
    url: str
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict[str, Any]] = None
    success_codes: list[int] = field(default_factory=lambda: [200, 201, 202])
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": StepType.WEBHOOK.value,
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "body": self.body,
            "success_codes": self.success_codes,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class ScriptStep:
    """Script step configuration."""

    name: str
    script_name: str  # Name of pre-registered script
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 60

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": StepType.SCRIPT.value,
            "script_name": self.script_name,
            "parameters": self.parameters,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class WaitStep:
    """Wait step configuration."""

    name: str
    duration_seconds: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": StepType.WAIT.value,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ConditionStep:
    """Condition step configuration."""

    name: str
    condition_type: ConditionType
    timeout_seconds: int = 300  # 5 minutes default
    on_failure: OnFailureAction = OnFailureAction.FAIL
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": StepType.CONDITION.value,
            "condition_type": self.condition_type.value,
            "timeout_seconds": self.timeout_seconds,
            "on_failure": self.on_failure.value,
            "parameters": self.parameters,
        }


# Union type for all step types
PlaybookStep = Union[WebhookStep, ScriptStep, WaitStep, ConditionStep]


@dataclass
class Playbook:
    """Parsed playbook definition."""

    name: str
    description: str
    steps: list[PlaybookStep]
    approval: ApprovalMode = ApprovalMode.NONE
    approval_timeout_minutes: Optional[int] = None
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        approval_str = self.approval.value
        has_timeout = (
            self.approval == ApprovalMode.TIMEOUT and self.approval_timeout_minutes
        )
        if has_timeout:
            approval_str = f"timeout:{self.approval_timeout_minutes}m"

        return {
            "name": self.name,
            "description": self.description,
            "approval": approval_str,
            "version": self.version,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }


class PlaybookParseError(Exception):
    """Exception raised when playbook parsing fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        self.message = message
        super().__init__(f"{message}" if not field else f"Field '{field}': {message}")


def _parse_duration(duration_str: str) -> int:
    """
    Parse a duration string to seconds.

    Supports formats:
    - "30s" or "30" -> 30 seconds
    - "5m" -> 300 seconds (5 minutes)
    - "1h" -> 3600 seconds (1 hour)

    Args:
        duration_str: Duration string to parse

    Returns:
        Duration in seconds

    Raises:
        ValueError: If format is invalid
    """
    if not duration_str:
        raise ValueError("Duration cannot be empty")

    duration_str = str(duration_str).strip().lower()

    # Plain integer - assume seconds
    if duration_str.isdigit():
        return int(duration_str)

    # Parse with unit suffix
    match = re.match(r"^(\d+)(s|m|h)?$", duration_str)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. "
            "Expected number with optional unit (s/m/h)"
        )

    value = int(match.group(1))
    unit = match.group(2) or "s"

    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    else:
        raise ValueError(f"Unknown duration unit: {unit}")


def _parse_webhook_step(step_data: dict[str, Any]) -> WebhookStep:
    """
    Parse a webhook step definition.

    Args:
        step_data: Step configuration dictionary

    Returns:
        WebhookStep object

    Raises:
        PlaybookParseError: If required fields missing or invalid
    """
    name = step_data.get("name")
    if not name:
        raise PlaybookParseError("Step name is required", "name")

    url = step_data.get("url")
    if not url:
        raise PlaybookParseError("Webhook URL is required", "url")

    # Validate URL format (basic check)
    if not url.startswith(("http://", "https://", "${")):
        raise PlaybookParseError(
            "URL must start with http://, https://, or be a variable", "url"
        )

    method = step_data.get("method", "POST").upper()
    valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    if method not in valid_methods:
        raise PlaybookParseError(
            f"Invalid HTTP method: {method}. Must be one of {valid_methods}", "method"
        )

    headers = step_data.get("headers", {})
    if not isinstance(headers, dict):
        raise PlaybookParseError("Headers must be a dictionary", "headers")

    body = step_data.get("body")
    if body is not None and not isinstance(body, dict):
        raise PlaybookParseError("Body must be a dictionary", "body")

    success_codes = step_data.get("success_codes", [200, 201, 202])
    if not isinstance(success_codes, list):
        raise PlaybookParseError(
            "success_codes must be a list of integers", "success_codes"
        )

    timeout = step_data.get("timeout", "30s")
    try:
        timeout_seconds = _parse_duration(str(timeout))
    except ValueError as e:
        raise PlaybookParseError(str(e), "timeout")

    return WebhookStep(
        name=str(name),
        url=str(url),
        method=method,
        headers={str(k): str(v) for k, v in headers.items()},
        body=body,
        success_codes=[int(c) for c in success_codes],
        timeout_seconds=timeout_seconds,
    )


def _parse_script_step(step_data: dict[str, Any]) -> ScriptStep:
    """
    Parse a script step definition.

    Args:
        step_data: Step configuration dictionary

    Returns:
        ScriptStep object

    Raises:
        PlaybookParseError: If required fields missing or invalid
    """
    name = step_data.get("name")
    if not name:
        raise PlaybookParseError("Step name is required", "name")

    script_name = step_data.get("script") or step_data.get("script_name")
    if not script_name:
        raise PlaybookParseError(
            "Script name is required (use 'script' field)", "script"
        )

    parameters = step_data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PlaybookParseError("Parameters must be a dictionary", "parameters")

    timeout = step_data.get("timeout", "60s")
    try:
        timeout_seconds = _parse_duration(str(timeout))
    except ValueError as e:
        raise PlaybookParseError(str(e), "timeout")

    return ScriptStep(
        name=str(name),
        script_name=str(script_name),
        parameters=parameters,
        timeout_seconds=timeout_seconds,
    )


def _parse_wait_step(step_data: dict[str, Any]) -> WaitStep:
    """
    Parse a wait step definition.

    Args:
        step_data: Step configuration dictionary

    Returns:
        WaitStep object

    Raises:
        PlaybookParseError: If required fields missing or invalid
    """
    name = step_data.get("name")
    if not name:
        raise PlaybookParseError("Step name is required", "name")

    duration = step_data.get("duration")
    if not duration:
        raise PlaybookParseError(
            "Wait duration is required (e.g., '30s', '5m')", "duration"
        )

    try:
        duration_seconds = _parse_duration(str(duration))
    except ValueError as e:
        raise PlaybookParseError(str(e), "duration")

    if duration_seconds <= 0:
        raise PlaybookParseError("Wait duration must be positive", "duration")

    return WaitStep(
        name=str(name),
        duration_seconds=duration_seconds,
    )


def _parse_condition_step(step_data: dict[str, Any]) -> ConditionStep:
    """
    Parse a condition step definition.

    Args:
        step_data: Step configuration dictionary

    Returns:
        ConditionStep object

    Raises:
        PlaybookParseError: If required fields missing or invalid
    """
    name = step_data.get("name")
    if not name:
        raise PlaybookParseError("Step name is required", "name")

    check = step_data.get("check")
    if not check:
        raise PlaybookParseError(
            "Condition check type is required (e.g., 'heartbeat_received')", "check"
        )

    try:
        condition_type = ConditionType(str(check).lower())
    except ValueError:
        valid_types = [ct.value for ct in ConditionType]
        raise PlaybookParseError(
            f"Invalid condition type: {check}. Must be one of {valid_types}", "check"
        )

    timeout = step_data.get("timeout", "5m")
    try:
        timeout_seconds = _parse_duration(str(timeout))
    except ValueError as e:
        raise PlaybookParseError(str(e), "timeout")

    on_failure_str = step_data.get("on_failure", "fail")
    try:
        on_failure = OnFailureAction(str(on_failure_str).lower())
    except ValueError:
        valid_actions = [a.value for a in OnFailureAction]
        raise PlaybookParseError(
            f"Invalid on_failure action: {on_failure_str}. "
            f"Must be one of {valid_actions}",
            "on_failure",
        )

    parameters = step_data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PlaybookParseError("Parameters must be a dictionary", "parameters")

    return ConditionStep(
        name=str(name),
        condition_type=condition_type,
        timeout_seconds=timeout_seconds,
        on_failure=on_failure,
        parameters=parameters,
    )


def _parse_step(step_data: dict[str, Any]) -> PlaybookStep:
    """
    Parse a single step definition.

    Args:
        step_data: Step configuration dictionary

    Returns:
        Appropriate step object based on type

    Raises:
        PlaybookParseError: If step is invalid
    """
    if not isinstance(step_data, dict):
        raise PlaybookParseError("Step must be a dictionary")

    step_type_str = step_data.get("type")
    if not step_type_str:
        raise PlaybookParseError("Step type is required", "type")

    if not StepType.is_valid(str(step_type_str)):
        valid_types = [st.value for st in StepType]
        raise PlaybookParseError(
            f"Invalid step type: {step_type_str}. " f"Must be one of {valid_types}",
            "type",
        )

    step_type = StepType(str(step_type_str).lower())

    if step_type == StepType.WEBHOOK:
        return _parse_webhook_step(step_data)
    elif step_type == StepType.SCRIPT:
        return _parse_script_step(step_data)
    elif step_type == StepType.WAIT:
        return _parse_wait_step(step_data)
    elif step_type == StepType.CONDITION:
        return _parse_condition_step(step_data)
    else:
        raise PlaybookParseError(f"Unsupported step type: {step_type}")


def parse_playbook_yaml(yaml_content: str) -> Playbook:
    """
    Parse a playbook YAML definition.

    Args:
        yaml_content: YAML string containing playbook definition

    Returns:
        Playbook object

    Raises:
        PlaybookParseError: If YAML is invalid or missing required fields

    Example YAML format:
        name: restart-service
        description: Restart a failed service
        approval: required
        steps:
          - name: call-restart-api
            type: webhook
            url: https://api.example.com/restart
            method: POST
            body:
              service: ${SERVICE_NAME}
          - name: wait-for-restart
            type: wait
            duration: 30s
          - name: verify-heartbeat
            type: condition
            check: heartbeat_received
            timeout: 5m
            on_failure: escalate
    """
    if not yaml_content or not yaml_content.strip():
        raise PlaybookParseError("Playbook YAML content cannot be empty")

    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise PlaybookParseError(f"Invalid YAML syntax: {e}")

    if not isinstance(data, dict):
        raise PlaybookParseError("Playbook must be a YAML dictionary/object")

    # Required fields
    name = data.get("name")
    if not name:
        raise PlaybookParseError("Playbook name is required", "name")

    description = data.get("description", "")

    # Parse steps
    steps_data = data.get("steps", [])
    if not steps_data:
        raise PlaybookParseError("Playbook must have at least one step", "steps")

    if not isinstance(steps_data, list):
        raise PlaybookParseError("Steps must be a list", "steps")

    steps: list[PlaybookStep] = []
    step_names: set = set()

    for i, step_data in enumerate(steps_data):
        try:
            step = _parse_step(step_data)
            # Check for duplicate step names
            if step.name in step_names:
                raise PlaybookParseError(
                    f"Duplicate step name: '{step.name}'", f"steps[{i}].name"
                )
            step_names.add(step.name)
            steps.append(step)
        except PlaybookParseError as e:
            # Add step index to error for context
            raise PlaybookParseError(f"Step {i + 1}: {e.message}", e.field)

    # Parse approval setting
    approval_str = data.get("approval", "none")
    try:
        approval, approval_timeout = ApprovalMode.parse(str(approval_str))
    except ValueError as e:
        raise PlaybookParseError(str(e), "approval")

    # Parse version
    version = data.get("version", 1)
    try:
        version = int(version)
    except (ValueError, TypeError):
        raise PlaybookParseError("Version must be an integer", "version")

    # Collect any additional metadata
    reserved_keys = {"name", "description", "steps", "approval", "version"}
    metadata = {k: v for k, v in data.items() if k not in reserved_keys}

    return Playbook(
        name=str(name),
        description=str(description),
        steps=steps,
        approval=approval,
        approval_timeout_minutes=approval_timeout,
        version=version,
        metadata=metadata,
    )


def validate_playbook_yaml(yaml_content: str) -> list[str]:
    """
    Validate a playbook YAML definition without returning the parsed result.

    Args:
        yaml_content: YAML string containing playbook definition

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    try:
        parse_playbook_yaml(yaml_content)
    except PlaybookParseError as e:
        errors.append(str(e))

    return errors


def is_valid_playbook_yaml(yaml_content: str) -> bool:
    """
    Check if a playbook YAML definition is valid.

    Args:
        yaml_content: YAML string containing playbook definition

    Returns:
        True if valid, False otherwise
    """
    return len(validate_playbook_yaml(yaml_content)) == 0
