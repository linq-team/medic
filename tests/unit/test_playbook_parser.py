"""Unit tests for playbook_parser module."""
import pytest


class TestStepType:
    """Tests for StepType enum."""

    def test_step_type_values(self):
        """Test StepType enum has expected values."""
        from Medic.Core.playbook_parser import StepType

        assert StepType.WEBHOOK.value == "webhook"
        assert StepType.SCRIPT.value == "script"
        assert StepType.WAIT.value == "wait"
        assert StepType.CONDITION.value == "condition"

    def test_is_valid_returns_true_for_valid_types(self):
        """Test is_valid returns True for valid step types."""
        from Medic.Core.playbook_parser import StepType

        assert StepType.is_valid("webhook") is True
        assert StepType.is_valid("script") is True
        assert StepType.is_valid("wait") is True
        assert StepType.is_valid("condition") is True
        # Case insensitive
        assert StepType.is_valid("WEBHOOK") is True
        assert StepType.is_valid("Script") is True

    def test_is_valid_returns_false_for_invalid_types(self):
        """Test is_valid returns False for invalid step types."""
        from Medic.Core.playbook_parser import StepType

        assert StepType.is_valid("invalid") is False
        assert StepType.is_valid("") is False
        assert StepType.is_valid("http") is False


class TestApprovalMode:
    """Tests for ApprovalMode enum."""

    def test_parse_none(self):
        """Test parsing 'none' approval setting."""
        from Medic.Core.playbook_parser import ApprovalMode

        mode, timeout = ApprovalMode.parse("none")
        assert mode == ApprovalMode.NONE
        assert timeout is None

    def test_parse_required(self):
        """Test parsing 'required' approval setting."""
        from Medic.Core.playbook_parser import ApprovalMode

        mode, timeout = ApprovalMode.parse("required")
        assert mode == ApprovalMode.REQUIRED
        assert timeout is None

    def test_parse_timeout_format(self):
        """Test parsing 'timeout:Xm' format."""
        from Medic.Core.playbook_parser import ApprovalMode

        mode, timeout = ApprovalMode.parse("timeout:5m")
        assert mode == ApprovalMode.TIMEOUT
        assert timeout == 5

        mode, timeout = ApprovalMode.parse("timeout:30m")
        assert mode == ApprovalMode.TIMEOUT
        assert timeout == 30

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive."""
        from Medic.Core.playbook_parser import ApprovalMode

        mode, _ = ApprovalMode.parse("NONE")
        assert mode == ApprovalMode.NONE

        mode, _ = ApprovalMode.parse("Required")
        assert mode == ApprovalMode.REQUIRED

        mode, timeout = ApprovalMode.parse("TIMEOUT:10m")
        assert mode == ApprovalMode.TIMEOUT
        assert timeout == 10

    def test_parse_invalid_raises_error(self):
        """Test parsing invalid values raises ValueError."""
        from Medic.Core.playbook_parser import ApprovalMode

        with pytest.raises(ValueError, match="Invalid approval setting"):
            ApprovalMode.parse("invalid")

        with pytest.raises(ValueError, match="Invalid approval setting"):
            ApprovalMode.parse("maybe")

    def test_parse_invalid_timeout_format(self):
        """Test parsing invalid timeout format raises ValueError."""
        from Medic.Core.playbook_parser import ApprovalMode

        with pytest.raises(ValueError, match="Invalid timeout format"):
            ApprovalMode.parse("timeout:abc")

        with pytest.raises(ValueError, match="Invalid timeout format"):
            ApprovalMode.parse("timeout:5h")  # Only minutes supported

        with pytest.raises(ValueError, match="Invalid timeout format"):
            ApprovalMode.parse("timeout:")

    def test_parse_zero_timeout_raises_error(self):
        """Test parsing zero timeout raises ValueError."""
        from Medic.Core.playbook_parser import ApprovalMode

        with pytest.raises(ValueError, match="positive number"):
            ApprovalMode.parse("timeout:0m")

    def test_parse_empty_raises_error(self):
        """Test parsing empty string raises ValueError."""
        from Medic.Core.playbook_parser import ApprovalMode

        with pytest.raises(ValueError, match="non-empty string"):
            ApprovalMode.parse("")

        with pytest.raises(ValueError, match="non-empty string"):
            ApprovalMode.parse(None)


class TestParseDuration:
    """Tests for _parse_duration function."""

    def test_parse_seconds(self):
        """Test parsing seconds format."""
        from Medic.Core.playbook_parser import _parse_duration

        assert _parse_duration("30s") == 30
        assert _parse_duration("1s") == 1
        assert _parse_duration("120s") == 120

    def test_parse_minutes(self):
        """Test parsing minutes format."""
        from Medic.Core.playbook_parser import _parse_duration

        assert _parse_duration("5m") == 300
        assert _parse_duration("1m") == 60
        assert _parse_duration("10m") == 600

    def test_parse_hours(self):
        """Test parsing hours format."""
        from Medic.Core.playbook_parser import _parse_duration

        assert _parse_duration("1h") == 3600
        assert _parse_duration("2h") == 7200

    def test_parse_plain_integer(self):
        """Test parsing plain integer (assumes seconds)."""
        from Medic.Core.playbook_parser import _parse_duration

        assert _parse_duration("30") == 30
        assert _parse_duration("60") == 60

    def test_parse_with_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        from Medic.Core.playbook_parser import _parse_duration

        assert _parse_duration("  30s  ") == 30
        assert _parse_duration(" 5m ") == 300

    def test_parse_invalid_raises_error(self):
        """Test parsing invalid format raises ValueError."""
        from Medic.Core.playbook_parser import _parse_duration

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("abc")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("5x")

        with pytest.raises(ValueError, match="cannot be empty"):
            _parse_duration("")


class TestWebhookStep:
    """Tests for WebhookStep dataclass."""

    def test_webhook_step_initialization(self):
        """Test WebhookStep object creation with defaults."""
        from Medic.Core.playbook_parser import WebhookStep

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api"
        )

        assert step.name == "test-webhook"
        assert step.url == "https://example.com/api"
        assert step.method == "POST"
        assert step.headers == {}
        assert step.body is None
        assert step.success_codes == [200, 201, 202]
        assert step.timeout_seconds == 30

    def test_webhook_step_to_dict(self):
        """Test WebhookStep to_dict method."""
        from Medic.Core.playbook_parser import WebhookStep, StepType

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
            method="PUT",
            headers={"Authorization": "Bearer token"},
            body={"action": "restart"},
            success_codes=[200, 204],
            timeout_seconds=60
        )

        result = step.to_dict()

        assert result["name"] == "test-webhook"
        assert result["type"] == StepType.WEBHOOK.value
        assert result["url"] == "https://example.com/api"
        assert result["method"] == "PUT"
        assert result["headers"] == {"Authorization": "Bearer token"}
        assert result["body"] == {"action": "restart"}
        assert result["success_codes"] == [200, 204]
        assert result["timeout_seconds"] == 60


class TestScriptStep:
    """Tests for ScriptStep dataclass."""

    def test_script_step_initialization(self):
        """Test ScriptStep object creation with defaults."""
        from Medic.Core.playbook_parser import ScriptStep

        step = ScriptStep(
            name="restart-service",
            script_name="restart.sh"
        )

        assert step.name == "restart-service"
        assert step.script_name == "restart.sh"
        assert step.parameters == {}
        assert step.timeout_seconds == 60

    def test_script_step_to_dict(self):
        """Test ScriptStep to_dict method."""
        from Medic.Core.playbook_parser import ScriptStep, StepType

        step = ScriptStep(
            name="restart-service",
            script_name="restart.sh",
            parameters={"service": "worker"},
            timeout_seconds=120
        )

        result = step.to_dict()

        assert result["name"] == "restart-service"
        assert result["type"] == StepType.SCRIPT.value
        assert result["script_name"] == "restart.sh"
        assert result["parameters"] == {"service": "worker"}
        assert result["timeout_seconds"] == 120


class TestWaitStep:
    """Tests for WaitStep dataclass."""

    def test_wait_step_initialization(self):
        """Test WaitStep object creation."""
        from Medic.Core.playbook_parser import WaitStep

        step = WaitStep(
            name="wait-for-restart",
            duration_seconds=30
        )

        assert step.name == "wait-for-restart"
        assert step.duration_seconds == 30

    def test_wait_step_to_dict(self):
        """Test WaitStep to_dict method."""
        from Medic.Core.playbook_parser import WaitStep, StepType

        step = WaitStep(
            name="wait-for-restart",
            duration_seconds=60
        )

        result = step.to_dict()

        assert result["name"] == "wait-for-restart"
        assert result["type"] == StepType.WAIT.value
        assert result["duration_seconds"] == 60


class TestConditionStep:
    """Tests for ConditionStep dataclass."""

    def test_condition_step_initialization_defaults(self):
        """Test ConditionStep object creation with defaults."""
        from Medic.Core.playbook_parser import (
            ConditionStep,
            ConditionType,
            OnFailureAction
        )

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED
        )

        assert step.name == "check-heartbeat"
        assert step.condition_type == ConditionType.HEARTBEAT_RECEIVED
        assert step.timeout_seconds == 300  # 5 minutes default
        assert step.on_failure == OnFailureAction.FAIL
        assert step.parameters == {}

    def test_condition_step_to_dict(self):
        """Test ConditionStep to_dict method."""
        from Medic.Core.playbook_parser import (
            ConditionStep,
            ConditionType,
            OnFailureAction,
            StepType
        )

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=600,
            on_failure=OnFailureAction.ESCALATE,
            parameters={"service_id": 123}
        )

        result = step.to_dict()

        assert result["name"] == "check-heartbeat"
        assert result["type"] == StepType.CONDITION.value
        assert result["condition_type"] == "heartbeat_received"
        assert result["timeout_seconds"] == 600
        assert result["on_failure"] == "escalate"
        assert result["parameters"] == {"service_id": 123}


class TestPlaybook:
    """Tests for Playbook dataclass."""

    def test_playbook_initialization_defaults(self):
        """Test Playbook object creation with defaults."""
        from Medic.Core.playbook_parser import (
            Playbook,
            ApprovalMode,
            WaitStep
        )

        step = WaitStep(name="wait", duration_seconds=30)
        playbook = Playbook(
            name="test-playbook",
            description="A test playbook",
            steps=[step]
        )

        assert playbook.name == "test-playbook"
        assert playbook.description == "A test playbook"
        assert len(playbook.steps) == 1
        assert playbook.approval == ApprovalMode.NONE
        assert playbook.approval_timeout_minutes is None
        assert playbook.version == 1
        assert playbook.metadata == {}

    def test_playbook_to_dict(self):
        """Test Playbook to_dict method."""
        from Medic.Core.playbook_parser import (
            Playbook,
            ApprovalMode,
            WaitStep
        )

        step = WaitStep(name="wait", duration_seconds=30)
        playbook = Playbook(
            name="test-playbook",
            description="A test playbook",
            steps=[step],
            approval=ApprovalMode.REQUIRED,
            version=2,
            metadata={"author": "test"}
        )

        result = playbook.to_dict()

        assert result["name"] == "test-playbook"
        assert result["description"] == "A test playbook"
        assert result["approval"] == "required"
        assert result["version"] == 2
        assert len(result["steps"]) == 1
        assert result["metadata"] == {"author": "test"}

    def test_playbook_to_dict_with_timeout(self):
        """Test Playbook to_dict with timeout approval."""
        from Medic.Core.playbook_parser import Playbook, ApprovalMode, WaitStep

        step = WaitStep(name="wait", duration_seconds=30)
        playbook = Playbook(
            name="test-playbook",
            description="A test playbook",
            steps=[step],
            approval=ApprovalMode.TIMEOUT,
            approval_timeout_minutes=10
        )

        result = playbook.to_dict()

        assert result["approval"] == "timeout:10m"


class TestParsePlaybookYaml:
    """Tests for parse_playbook_yaml function."""

    def test_parse_minimal_playbook(self):
        """Test parsing minimal valid playbook."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            ApprovalMode
        )

        yaml_content = """
name: minimal-playbook
steps:
  - name: wait-step
    type: wait
    duration: 30s
"""
        playbook = parse_playbook_yaml(yaml_content)

        assert playbook.name == "minimal-playbook"
        assert playbook.description == ""
        assert len(playbook.steps) == 1
        assert playbook.approval == ApprovalMode.NONE

    def test_parse_complete_playbook(self):
        """Test parsing a complete playbook with all fields."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            ApprovalMode,
            StepType
        )

        yaml_content = """
name: complete-playbook
description: A comprehensive test playbook
approval: required
version: 2
steps:
  - name: call-api
    type: webhook
    url: https://api.example.com/restart
    method: POST
    headers:
      Authorization: Bearer ${API_KEY}
    body:
      service: ${SERVICE_NAME}
    success_codes: [200, 201]
    timeout: 60s
  - name: wait-for-restart
    type: wait
    duration: 30s
  - name: run-healthcheck
    type: script
    script: healthcheck.py
    parameters:
      target: ${SERVICE_NAME}
    timeout: 2m
  - name: verify-heartbeat
    type: condition
    check: heartbeat_received
    timeout: 5m
    on_failure: escalate
"""
        playbook = parse_playbook_yaml(yaml_content)

        assert playbook.name == "complete-playbook"
        assert playbook.description == "A comprehensive test playbook"
        assert playbook.approval == ApprovalMode.REQUIRED
        assert playbook.version == 2
        assert len(playbook.steps) == 4

        # Check webhook step
        webhook_step = playbook.steps[0]
        assert webhook_step.name == "call-api"
        assert webhook_step.to_dict()["type"] == StepType.WEBHOOK.value
        assert webhook_step.url == "https://api.example.com/restart"
        assert webhook_step.method == "POST"
        assert webhook_step.success_codes == [200, 201]

        # Check wait step
        wait_step = playbook.steps[1]
        assert wait_step.name == "wait-for-restart"
        assert wait_step.duration_seconds == 30

        # Check script step
        script_step = playbook.steps[2]
        assert script_step.name == "run-healthcheck"
        assert script_step.script_name == "healthcheck.py"
        assert script_step.timeout_seconds == 120  # 2m

        # Check condition step
        condition_step = playbook.steps[3]
        assert condition_step.name == "verify-heartbeat"
        assert condition_step.timeout_seconds == 300  # 5m

    def test_parse_playbook_with_timeout_approval(self):
        """Test parsing playbook with timeout approval."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            ApprovalMode
        )

        yaml_content = """
name: auto-approve-playbook
approval: timeout:15m
steps:
  - name: wait
    type: wait
    duration: 10s
"""
        playbook = parse_playbook_yaml(yaml_content)

        assert playbook.approval == ApprovalMode.TIMEOUT
        assert playbook.approval_timeout_minutes == 15

    def test_parse_empty_yaml_raises_error(self):
        """Test parsing empty YAML raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        with pytest.raises(PlaybookParseError, match="cannot be empty"):
            parse_playbook_yaml("")

        with pytest.raises(PlaybookParseError, match="cannot be empty"):
            parse_playbook_yaml("   ")

    def test_parse_invalid_yaml_syntax_raises_error(self):
        """Test parsing invalid YAML syntax raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        with pytest.raises(PlaybookParseError, match="Invalid YAML syntax"):
            parse_playbook_yaml("name: test\n  invalid: indent")

    def test_parse_missing_name_raises_error(self):
        """Test parsing playbook without name raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
steps:
  - name: wait
    type: wait
    duration: 30s
"""
        with pytest.raises(PlaybookParseError, match="name is required"):
            parse_playbook_yaml(yaml_content)

    def test_parse_missing_steps_raises_error(self):
        """Test parsing playbook without steps raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: no-steps-playbook
"""
        with pytest.raises(PlaybookParseError, match="at least one step"):
            parse_playbook_yaml(yaml_content)

    def test_parse_empty_steps_raises_error(self):
        """Test parsing playbook with empty steps raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: empty-steps-playbook
steps: []
"""
        with pytest.raises(PlaybookParseError, match="at least one step"):
            parse_playbook_yaml(yaml_content)

    def test_parse_duplicate_step_names_raises_error(self):
        """Test parsing playbook with duplicate step names raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: duplicate-steps
steps:
  - name: my-step
    type: wait
    duration: 10s
  - name: my-step
    type: wait
    duration: 20s
"""
        with pytest.raises(PlaybookParseError, match="Duplicate step name"):
            parse_playbook_yaml(yaml_content)

    def test_parse_invalid_step_type_raises_error(self):
        """Test parsing step with invalid type raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: invalid-step-type
steps:
  - name: bad-step
    type: invalid_type
"""
        with pytest.raises(PlaybookParseError, match="Invalid step type"):
            parse_playbook_yaml(yaml_content)

    def test_parse_step_missing_type_raises_error(self):
        """Test parsing step without type raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: missing-type
steps:
  - name: no-type-step
"""
        with pytest.raises(PlaybookParseError, match="Step type is required"):
            parse_playbook_yaml(yaml_content)

    def test_parse_step_missing_name_raises_error(self):
        """Test parsing step without name raises PlaybookParseError."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: missing-step-name
steps:
  - type: wait
    duration: 30s
"""
        with pytest.raises(PlaybookParseError, match="Step name is required"):
            parse_playbook_yaml(yaml_content)


class TestParseWebhookStep:
    """Tests for webhook step parsing."""

    def test_parse_webhook_step_minimal(self):
        """Test parsing minimal webhook step."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        yaml_content = """
name: webhook-test
steps:
  - name: call-api
    type: webhook
    url: https://api.example.com/endpoint
"""
        playbook = parse_playbook_yaml(yaml_content)
        step = playbook.steps[0]

        assert step.name == "call-api"
        assert step.url == "https://api.example.com/endpoint"
        assert step.method == "POST"  # Default

    def test_parse_webhook_step_with_variable_url(self):
        """Test parsing webhook step with variable in URL."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        yaml_content = """
name: webhook-test
steps:
  - name: call-api
    type: webhook
    url: ${WEBHOOK_URL}
"""
        playbook = parse_playbook_yaml(yaml_content)
        step = playbook.steps[0]

        assert step.url == "${WEBHOOK_URL}"

    def test_parse_webhook_step_missing_url_raises_error(self):
        """Test parsing webhook step without URL raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: webhook-test
steps:
  - name: call-api
    type: webhook
"""
        with pytest.raises(PlaybookParseError, match="URL is required"):
            parse_playbook_yaml(yaml_content)

    def test_parse_webhook_step_invalid_url_raises_error(self):
        """Test parsing webhook step with invalid URL raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: webhook-test
steps:
  - name: call-api
    type: webhook
    url: not-a-valid-url
"""
        with pytest.raises(PlaybookParseError, match="URL must start with"):
            parse_playbook_yaml(yaml_content)

    def test_parse_webhook_step_invalid_method_raises_error(self):
        """Test parsing webhook step with invalid method raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: webhook-test
steps:
  - name: call-api
    type: webhook
    url: https://api.example.com
    method: INVALID
"""
        with pytest.raises(PlaybookParseError, match="Invalid HTTP method"):
            parse_playbook_yaml(yaml_content)

    def test_parse_webhook_step_all_methods(self):
        """Test parsing webhook step with all valid methods."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            yaml_content = f"""
name: webhook-test
steps:
  - name: call-api
    type: webhook
    url: https://api.example.com
    method: {method}
"""
            playbook = parse_playbook_yaml(yaml_content)
            assert playbook.steps[0].method == method


class TestParseScriptStep:
    """Tests for script step parsing."""

    def test_parse_script_step(self):
        """Test parsing script step."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        yaml_content = """
name: script-test
steps:
  - name: run-script
    type: script
    script: restart-service.sh
    parameters:
      service: worker
      env: production
    timeout: 2m
"""
        playbook = parse_playbook_yaml(yaml_content)
        step = playbook.steps[0]

        assert step.name == "run-script"
        assert step.script_name == "restart-service.sh"
        assert step.parameters == {"service": "worker", "env": "production"}
        assert step.timeout_seconds == 120

    def test_parse_script_step_missing_script_raises_error(self):
        """Test parsing script step without script name raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: script-test
steps:
  - name: run-script
    type: script
"""
        with pytest.raises(
            PlaybookParseError, match="Script name is required"
        ):
            parse_playbook_yaml(yaml_content)


class TestParseWaitStep:
    """Tests for wait step parsing."""

    def test_parse_wait_step_seconds(self):
        """Test parsing wait step with seconds."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        yaml_content = """
name: wait-test
steps:
  - name: wait-step
    type: wait
    duration: 30s
"""
        playbook = parse_playbook_yaml(yaml_content)
        step = playbook.steps[0]

        assert step.name == "wait-step"
        assert step.duration_seconds == 30

    def test_parse_wait_step_minutes(self):
        """Test parsing wait step with minutes."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        yaml_content = """
name: wait-test
steps:
  - name: wait-step
    type: wait
    duration: 5m
"""
        playbook = parse_playbook_yaml(yaml_content)
        assert playbook.steps[0].duration_seconds == 300

    def test_parse_wait_step_missing_duration_raises_error(self):
        """Test parsing wait step without duration raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: wait-test
steps:
  - name: wait-step
    type: wait
"""
        with pytest.raises(PlaybookParseError, match="duration is required"):
            parse_playbook_yaml(yaml_content)


class TestParseConditionStep:
    """Tests for condition step parsing."""

    def test_parse_condition_step_heartbeat_received(self):
        """Test parsing condition step with heartbeat_received check."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            ConditionType,
            OnFailureAction
        )

        yaml_content = """
name: condition-test
steps:
  - name: check-heartbeat
    type: condition
    check: heartbeat_received
    timeout: 5m
    on_failure: escalate
"""
        playbook = parse_playbook_yaml(yaml_content)
        step = playbook.steps[0]

        assert step.name == "check-heartbeat"
        assert step.condition_type == ConditionType.HEARTBEAT_RECEIVED
        assert step.timeout_seconds == 300
        assert step.on_failure == OnFailureAction.ESCALATE

    def test_parse_condition_step_on_failure_options(self):
        """Test parsing condition step with different on_failure values."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            OnFailureAction
        )

        for action_str, expected in [
            ("fail", OnFailureAction.FAIL),
            ("continue", OnFailureAction.CONTINUE),
            ("escalate", OnFailureAction.ESCALATE)
        ]:
            yaml_content = f"""
name: condition-test
steps:
  - name: check
    type: condition
    check: heartbeat_received
    on_failure: {action_str}
"""
            playbook = parse_playbook_yaml(yaml_content)
            assert playbook.steps[0].on_failure == expected

    def test_parse_condition_step_missing_check_raises_error(self):
        """Test parsing condition step without check type raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: condition-test
steps:
  - name: check
    type: condition
"""
        with pytest.raises(PlaybookParseError, match="check type is required"):
            parse_playbook_yaml(yaml_content)

    def test_parse_condition_step_invalid_check_raises_error(self):
        """Test parsing condition step with invalid check type raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: condition-test
steps:
  - name: check
    type: condition
    check: invalid_condition
"""
        with pytest.raises(PlaybookParseError, match="Invalid condition type"):
            parse_playbook_yaml(yaml_content)

    def test_parse_condition_step_invalid_on_failure_raises_error(self):
        """Test parsing condition step with invalid on_failure raises error."""
        from Medic.Core.playbook_parser import (
            parse_playbook_yaml,
            PlaybookParseError
        )

        yaml_content = """
name: condition-test
steps:
  - name: check
    type: condition
    check: heartbeat_received
    on_failure: invalid_action
"""
        with pytest.raises(PlaybookParseError, match="Invalid on_failure"):
            parse_playbook_yaml(yaml_content)


class TestValidatePlaybookYaml:
    """Tests for validate_playbook_yaml function."""

    def test_validate_valid_playbook_returns_empty_list(self):
        """Test validating valid playbook returns empty error list."""
        from Medic.Core.playbook_parser import validate_playbook_yaml

        yaml_content = """
name: valid-playbook
steps:
  - name: wait
    type: wait
    duration: 30s
"""
        errors = validate_playbook_yaml(yaml_content)

        assert errors == []

    def test_validate_invalid_playbook_returns_error_list(self):
        """Test validating invalid playbook returns error list."""
        from Medic.Core.playbook_parser import validate_playbook_yaml

        yaml_content = """
steps:
  - name: wait
    type: wait
"""
        errors = validate_playbook_yaml(yaml_content)

        assert len(errors) == 1
        assert "name is required" in errors[0]


class TestIsValidPlaybookYaml:
    """Tests for is_valid_playbook_yaml function."""

    def test_is_valid_returns_true_for_valid_playbook(self):
        """Test is_valid_playbook_yaml returns True for valid playbook."""
        from Medic.Core.playbook_parser import is_valid_playbook_yaml

        yaml_content = """
name: valid-playbook
steps:
  - name: wait
    type: wait
    duration: 30s
"""
        assert is_valid_playbook_yaml(yaml_content) is True

    def test_is_valid_returns_false_for_invalid_playbook(self):
        """Test is_valid_playbook_yaml returns False for invalid playbook."""
        from Medic.Core.playbook_parser import is_valid_playbook_yaml

        yaml_content = """
# Missing name
steps:
  - type: wait
    duration: 30s
"""
        assert is_valid_playbook_yaml(yaml_content) is False


class TestPlaybookParseError:
    """Tests for PlaybookParseError exception."""

    def test_error_with_field(self):
        """Test PlaybookParseError with field context."""
        from Medic.Core.playbook_parser import PlaybookParseError

        error = PlaybookParseError("Invalid value", field="name")

        assert error.field == "name"
        assert error.message == "Invalid value"
        assert "Field 'name'" in str(error)

    def test_error_without_field(self):
        """Test PlaybookParseError without field context."""
        from Medic.Core.playbook_parser import PlaybookParseError

        error = PlaybookParseError("General error")

        assert error.field is None
        assert error.message == "General error"
        assert str(error) == "General error"


class TestMetadataPreservation:
    """Tests for metadata preservation in playbooks."""

    def test_extra_fields_preserved_as_metadata(self):
        """Test that extra YAML fields are preserved as metadata."""
        from Medic.Core.playbook_parser import parse_playbook_yaml

        yaml_content = """
name: metadata-playbook
description: Test playbook
author: test-user
team: sre
custom_field: custom_value
steps:
  - name: wait
    type: wait
    duration: 30s
"""
        playbook = parse_playbook_yaml(yaml_content)

        assert playbook.metadata["author"] == "test-user"
        assert playbook.metadata["team"] == "sre"
        assert playbook.metadata["custom_field"] == "custom_value"
        # Reserved fields should NOT be in metadata
        assert "name" not in playbook.metadata
        assert "description" not in playbook.metadata
        assert "steps" not in playbook.metadata
