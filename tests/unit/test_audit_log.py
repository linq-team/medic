"""Unit tests for audit_log module."""
import json
from datetime import datetime
from unittest.mock import patch

import pytz


class TestAuditActionType:
    """Tests for AuditActionType enum."""

    def test_action_type_values(self):
        """Test AuditActionType enum has expected values."""
        from Medic.Core.audit_log import AuditActionType

        assert AuditActionType.EXECUTION_STARTED.value == "execution_started"
        assert AuditActionType.STEP_COMPLETED.value == "step_completed"
        assert AuditActionType.STEP_FAILED.value == "step_failed"
        assert AuditActionType.APPROVAL_REQUESTED.value == "approval_requested"
        assert AuditActionType.APPROVED.value == "approved"
        assert AuditActionType.REJECTED.value == "rejected"
        assert AuditActionType.EXECUTION_COMPLETED.value == "execution_completed"
        assert AuditActionType.EXECUTION_FAILED.value == "execution_failed"

    def test_is_valid_for_valid_values(self):
        """Test is_valid returns True for valid action types."""
        from Medic.Core.audit_log import AuditActionType

        assert AuditActionType.is_valid("execution_started") is True
        assert AuditActionType.is_valid("step_completed") is True
        assert AuditActionType.is_valid("step_failed") is True
        assert AuditActionType.is_valid("approval_requested") is True
        assert AuditActionType.is_valid("approved") is True
        assert AuditActionType.is_valid("rejected") is True
        assert AuditActionType.is_valid("execution_completed") is True
        assert AuditActionType.is_valid("execution_failed") is True

    def test_is_valid_for_invalid_values(self):
        """Test is_valid returns False for invalid action types."""
        from Medic.Core.audit_log import AuditActionType

        assert AuditActionType.is_valid("invalid") is False
        assert AuditActionType.is_valid("EXECUTION_STARTED") is False
        assert AuditActionType.is_valid("") is False
        assert AuditActionType.is_valid("step") is False


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""

    def test_audit_log_entry_creation(self):
        """Test creating an AuditLogEntry object."""
        from Medic.Core.audit_log import AuditActionType, AuditLogEntry

        now = datetime.now(pytz.timezone('America/Chicago'))
        entry = AuditLogEntry(
            log_id=1,
            execution_id=100,
            action_type=AuditActionType.EXECUTION_STARTED,
            details={"playbook_name": "test-playbook"},
            actor=None,
            timestamp=now,
            created_at=now,
        )

        assert entry.log_id == 1
        assert entry.execution_id == 100
        assert entry.action_type == AuditActionType.EXECUTION_STARTED
        assert entry.details == {"playbook_name": "test-playbook"}
        assert entry.actor is None
        assert entry.timestamp == now

    def test_audit_log_entry_to_dict(self):
        """Test converting AuditLogEntry to dictionary."""
        from Medic.Core.audit_log import AuditActionType, AuditLogEntry

        now = datetime.now(pytz.timezone('America/Chicago'))
        entry = AuditLogEntry(
            log_id=1,
            execution_id=100,
            action_type=AuditActionType.APPROVED,
            details={"playbook_name": "test"},
            actor="user123",
            timestamp=now,
            created_at=now,
        )

        result = entry.to_dict()

        assert result["log_id"] == 1
        assert result["execution_id"] == 100
        assert result["action_type"] == "approved"
        assert result["details"] == {"playbook_name": "test"}
        assert result["actor"] == "user123"
        assert result["timestamp"] == now.isoformat()


class TestCreateAuditLogEntry:
    """Tests for create_audit_log_entry function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_create_audit_log_entry_success(self, mock_query_db):
        """Test successful creation of audit log entry."""
        from Medic.Core.audit_log import (
            AuditActionType,
            create_audit_log_entry,
        )

        mock_query_db.return_value = json.dumps([{"log_id": 42}])

        result = create_audit_log_entry(
            execution_id=100,
            action_type=AuditActionType.EXECUTION_STARTED,
            details={"playbook_id": 1, "playbook_name": "test"},
        )

        assert result is not None
        assert result.log_id == 42
        assert result.execution_id == 100
        assert result.action_type == AuditActionType.EXECUTION_STARTED
        assert result.details == {"playbook_id": 1, "playbook_name": "test"}
        assert result.actor is None

        # Verify query was called
        mock_query_db.assert_called_once()
        call_args = mock_query_db.call_args
        assert "INSERT INTO medic.remediation_audit_log" in call_args[0][0]

    @patch("Medic.Core.audit_log.db.query_db")
    def test_create_audit_log_entry_with_actor(self, mock_query_db):
        """Test creating audit log entry with actor."""
        from Medic.Core.audit_log import (
            AuditActionType,
            create_audit_log_entry,
        )

        mock_query_db.return_value = json.dumps([{"log_id": 43}])

        result = create_audit_log_entry(
            execution_id=100,
            action_type=AuditActionType.APPROVED,
            details={},
            actor="user123",
        )

        assert result is not None
        assert result.log_id == 43
        assert result.actor == "user123"

    @patch("Medic.Core.audit_log.db.query_db")
    def test_create_audit_log_entry_db_failure(self, mock_query_db):
        """Test handling database failure."""
        from Medic.Core.audit_log import (
            AuditActionType,
            create_audit_log_entry,
        )

        mock_query_db.return_value = None

        result = create_audit_log_entry(
            execution_id=100,
            action_type=AuditActionType.EXECUTION_STARTED,
            details={},
        )

        assert result is None

    @patch("Medic.Core.audit_log.db.query_db")
    def test_create_audit_log_entry_empty_result(self, mock_query_db):
        """Test handling empty result."""
        from Medic.Core.audit_log import (
            AuditActionType,
            create_audit_log_entry,
        )

        mock_query_db.return_value = "[]"

        result = create_audit_log_entry(
            execution_id=100,
            action_type=AuditActionType.EXECUTION_STARTED,
            details={},
        )

        assert result is None


class TestLogExecutionStarted:
    """Tests for log_execution_started function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_started_minimal(self, mock_query_db):
        """Test logging execution started with minimal info."""
        from Medic.Core.audit_log import log_execution_started

        mock_query_db.return_value = json.dumps([{"log_id": 1}])

        result = log_execution_started(
            execution_id=100,
            playbook_id=1,
            playbook_name="test-playbook",
        )

        assert result is not None
        assert result.log_id == 1
        assert result.details["playbook_id"] == 1
        assert result.details["playbook_name"] == "test-playbook"
        assert "service_id" not in result.details

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_started_with_all_fields(self, mock_query_db):
        """Test logging execution started with all fields."""
        from Medic.Core.audit_log import log_execution_started

        mock_query_db.return_value = json.dumps([{"log_id": 2}])

        result = log_execution_started(
            execution_id=100,
            playbook_id=1,
            playbook_name="test-playbook",
            service_id=42,
            service_name="worker-prod-01",
            trigger="heartbeat_failure",
            context={"custom_key": "custom_value"},
        )

        assert result is not None
        assert result.details["playbook_id"] == 1
        assert result.details["playbook_name"] == "test-playbook"
        assert result.details["service_id"] == 42
        assert result.details["service_name"] == "worker-prod-01"
        assert result.details["trigger"] == "heartbeat_failure"
        assert result.details["context"]["custom_key"] == "custom_value"


class TestLogStepCompleted:
    """Tests for log_step_completed function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_step_completed_minimal(self, mock_query_db):
        """Test logging step completed with minimal info."""
        from Medic.Core.audit_log import log_step_completed

        mock_query_db.return_value = json.dumps([{"log_id": 3}])

        result = log_step_completed(
            execution_id=100,
            step_name="restart",
            step_index=0,
        )

        assert result is not None
        assert result.details["step_name"] == "restart"
        assert result.details["step_index"] == 0
        assert "step_type" not in result.details

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_step_completed_with_all_fields(self, mock_query_db):
        """Test logging step completed with all fields."""
        from Medic.Core.audit_log import log_step_completed

        mock_query_db.return_value = json.dumps([{"log_id": 4}])

        result = log_step_completed(
            execution_id=100,
            step_name="restart",
            step_index=0,
            step_type="script",
            output="Service restarted successfully",
            duration_ms=1500,
        )

        assert result is not None
        assert result.details["step_name"] == "restart"
        assert result.details["step_type"] == "script"
        assert result.details["output"] == "Service restarted successfully"
        assert result.details["duration_ms"] == 1500

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_step_completed_truncates_long_output(self, mock_query_db):
        """Test that long output is truncated."""
        from Medic.Core.audit_log import log_step_completed

        mock_query_db.return_value = json.dumps([{"log_id": 5}])

        long_output = "x" * 5000  # Over 4096 limit

        result = log_step_completed(
            execution_id=100,
            step_name="restart",
            step_index=0,
            output=long_output,
        )

        assert result is not None
        assert len(result.details["output"]) == 4096


class TestLogStepFailed:
    """Tests for log_step_failed function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_step_failed_minimal(self, mock_query_db):
        """Test logging step failed with minimal info."""
        from Medic.Core.audit_log import log_step_failed

        mock_query_db.return_value = json.dumps([{"log_id": 6}])

        result = log_step_failed(
            execution_id=100,
            step_name="restart",
            step_index=1,
        )

        assert result is not None
        assert result.details["step_name"] == "restart"
        assert result.details["step_index"] == 1

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_step_failed_with_all_fields(self, mock_query_db):
        """Test logging step failed with all fields."""
        from Medic.Core.audit_log import log_step_failed

        mock_query_db.return_value = json.dumps([{"log_id": 7}])

        result = log_step_failed(
            execution_id=100,
            step_name="webhook-call",
            step_index=2,
            step_type="webhook",
            error_message="Connection refused",
            output="Failed to connect to endpoint",
            duration_ms=500,
        )

        assert result is not None
        assert result.details["step_name"] == "webhook-call"
        assert result.details["step_type"] == "webhook"
        assert result.details["error_message"] == "Connection refused"
        assert result.details["output"] == "Failed to connect to endpoint"
        assert result.details["duration_ms"] == 500

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_step_failed_truncates_long_error_message(self, mock_query_db):
        """Test that long error messages are truncated."""
        from Medic.Core.audit_log import log_step_failed

        mock_query_db.return_value = json.dumps([{"log_id": 8}])

        long_error = "e" * 3000  # Over 2048 limit

        result = log_step_failed(
            execution_id=100,
            step_name="restart",
            step_index=0,
            error_message=long_error,
        )

        assert result is not None
        assert len(result.details["error_message"]) == 2048


class TestLogApprovalRequested:
    """Tests for log_approval_requested function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_approval_requested_minimal(self, mock_query_db):
        """Test logging approval requested with minimal info."""
        from Medic.Core.audit_log import log_approval_requested

        mock_query_db.return_value = json.dumps([{"log_id": 9}])

        result = log_approval_requested(
            execution_id=100,
            playbook_name="restart-service",
        )

        assert result is not None
        assert result.details["playbook_name"] == "restart-service"
        assert "service_name" not in result.details

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_approval_requested_with_all_fields(self, mock_query_db):
        """Test logging approval requested with all fields."""
        from Medic.Core.audit_log import log_approval_requested

        mock_query_db.return_value = json.dumps([{"log_id": 10}])

        expires_at = datetime.now(pytz.timezone('America/Chicago'))

        result = log_approval_requested(
            execution_id=100,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            expires_at=expires_at,
            channel_id="C1234567890",
        )

        assert result is not None
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["service_name"] == "worker-prod-01"
        assert result.details["expires_at"] == expires_at.isoformat()
        assert result.details["channel_id"] == "C1234567890"


class TestLogApproved:
    """Tests for log_approved function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_approved_minimal(self, mock_query_db):
        """Test logging approval with minimal info."""
        from Medic.Core.audit_log import log_approved

        mock_query_db.return_value = json.dumps([{"log_id": 11}])

        result = log_approved(
            execution_id=100,
            approved_by="user123",
        )

        assert result is not None
        assert result.actor == "user123"
        assert "playbook_name" not in result.details

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_approved_with_all_fields(self, mock_query_db):
        """Test logging approval with all fields."""
        from Medic.Core.audit_log import log_approved

        mock_query_db.return_value = json.dumps([{"log_id": 12}])

        result = log_approved(
            execution_id=100,
            approved_by="user123",
            playbook_name="restart-service",
            service_name="worker-prod-01",
        )

        assert result is not None
        assert result.actor == "user123"
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["service_name"] == "worker-prod-01"


class TestLogRejected:
    """Tests for log_rejected function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_rejected_minimal(self, mock_query_db):
        """Test logging rejection with minimal info."""
        from Medic.Core.audit_log import log_rejected

        mock_query_db.return_value = json.dumps([{"log_id": 13}])

        result = log_rejected(
            execution_id=100,
            rejected_by="user456",
        )

        assert result is not None
        assert result.actor == "user456"

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_rejected_with_all_fields(self, mock_query_db):
        """Test logging rejection with all fields."""
        from Medic.Core.audit_log import log_rejected

        mock_query_db.return_value = json.dumps([{"log_id": 14}])

        result = log_rejected(
            execution_id=100,
            rejected_by="user456",
            playbook_name="restart-service",
            service_name="worker-prod-01",
            reason="Not safe during peak hours",
        )

        assert result is not None
        assert result.actor == "user456"
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["reason"] == "Not safe during peak hours"


class TestLogExecutionCompleted:
    """Tests for log_execution_completed function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_completed_minimal(self, mock_query_db):
        """Test logging execution completed with minimal info."""
        from Medic.Core.audit_log import log_execution_completed

        mock_query_db.return_value = json.dumps([{"log_id": 15}])

        result = log_execution_completed(
            execution_id=100,
            playbook_name="restart-service",
            steps_completed=3,
        )

        assert result is not None
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["steps_completed"] == 3
        assert "total_duration_ms" not in result.details

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_completed_with_all_fields(self, mock_query_db):
        """Test logging execution completed with all fields."""
        from Medic.Core.audit_log import log_execution_completed

        mock_query_db.return_value = json.dumps([{"log_id": 16}])

        result = log_execution_completed(
            execution_id=100,
            playbook_name="restart-service",
            steps_completed=3,
            total_duration_ms=15000,
            service_name="worker-prod-01",
        )

        assert result is not None
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["steps_completed"] == 3
        assert result.details["total_duration_ms"] == 15000
        assert result.details["service_name"] == "worker-prod-01"


class TestLogExecutionFailed:
    """Tests for log_execution_failed function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_failed_minimal(self, mock_query_db):
        """Test logging execution failed with minimal info."""
        from Medic.Core.audit_log import log_execution_failed

        mock_query_db.return_value = json.dumps([{"log_id": 17}])

        result = log_execution_failed(
            execution_id=100,
            playbook_name="restart-service",
            error_message="Step 'restart' failed",
        )

        assert result is not None
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["error_message"] == "Step 'restart' failed"
        assert "failed_step_name" not in result.details

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_failed_with_all_fields(self, mock_query_db):
        """Test logging execution failed with all fields."""
        from Medic.Core.audit_log import log_execution_failed

        mock_query_db.return_value = json.dumps([{"log_id": 18}])

        result = log_execution_failed(
            execution_id=100,
            playbook_name="restart-service",
            error_message="Step 'restart' failed: Service unavailable",
            failed_step_name="restart",
            failed_step_index=2,
            steps_completed=2,
            total_duration_ms=10000,
            service_name="worker-prod-01",
        )

        assert result is not None
        assert result.details["playbook_name"] == "restart-service"
        assert result.details["error_message"] == (
            "Step 'restart' failed: Service unavailable"
        )
        assert result.details["failed_step_name"] == "restart"
        assert result.details["failed_step_index"] == 2
        assert result.details["steps_completed"] == 2
        assert result.details["total_duration_ms"] == 10000
        assert result.details["service_name"] == "worker-prod-01"

    @patch("Medic.Core.audit_log.db.query_db")
    def test_log_execution_failed_truncates_long_error(self, mock_query_db):
        """Test that long error messages are truncated."""
        from Medic.Core.audit_log import log_execution_failed

        mock_query_db.return_value = json.dumps([{"log_id": 19}])

        long_error = "e" * 3000  # Over 2048 limit

        result = log_execution_failed(
            execution_id=100,
            playbook_name="test",
            error_message=long_error,
        )

        assert result is not None
        assert len(result.details["error_message"]) == 2048


class TestGetAuditLogsForExecution:
    """Tests for get_audit_logs_for_execution function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_get_audit_logs_for_execution_success(self, mock_query_db):
        """Test retrieving audit logs for an execution."""
        from Medic.Core.audit_log import (
            AuditActionType,
            get_audit_logs_for_execution,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_query_db.return_value = json.dumps([
            {
                "log_id": 1,
                "execution_id": 100,
                "action_type": "execution_started",
                "details": {"playbook_name": "test"},
                "actor": None,
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
            },
            {
                "log_id": 2,
                "execution_id": 100,
                "action_type": "step_completed",
                "details": {"step_name": "restart"},
                "actor": None,
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
            },
        ])

        result = get_audit_logs_for_execution(100)

        assert len(result) == 2
        assert result[0].log_id == 1
        assert result[0].action_type == AuditActionType.EXECUTION_STARTED
        assert result[1].log_id == 2
        assert result[1].action_type == AuditActionType.STEP_COMPLETED

    @patch("Medic.Core.audit_log.db.query_db")
    def test_get_audit_logs_for_execution_empty(self, mock_query_db):
        """Test retrieving audit logs when none exist."""
        from Medic.Core.audit_log import get_audit_logs_for_execution

        mock_query_db.return_value = "[]"

        result = get_audit_logs_for_execution(999)

        assert result == []

    @patch("Medic.Core.audit_log.db.query_db")
    def test_get_audit_logs_for_execution_with_limit(self, mock_query_db):
        """Test retrieving audit logs with limit."""
        from Medic.Core.audit_log import get_audit_logs_for_execution

        mock_query_db.return_value = "[]"

        get_audit_logs_for_execution(100, limit=50)

        # Verify the limit was passed in the query
        call_args = mock_query_db.call_args
        assert 50 in call_args[0][1]


class TestGetAuditLogsByActionType:
    """Tests for get_audit_logs_by_action_type function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_get_audit_logs_by_action_type_success(self, mock_query_db):
        """Test retrieving audit logs by action type."""
        from Medic.Core.audit_log import (
            AuditActionType,
            get_audit_logs_by_action_type,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_query_db.return_value = json.dumps([
            {
                "log_id": 1,
                "execution_id": 100,
                "action_type": "approved",
                "details": {},
                "actor": "user123",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
            },
        ])

        result = get_audit_logs_by_action_type(AuditActionType.APPROVED)

        assert len(result) == 1
        assert result[0].action_type == AuditActionType.APPROVED
        assert result[0].actor == "user123"


class TestGetAuditLogsByActor:
    """Tests for get_audit_logs_by_actor function."""

    @patch("Medic.Core.audit_log.db.query_db")
    def test_get_audit_logs_by_actor_success(self, mock_query_db):
        """Test retrieving audit logs by actor."""
        from Medic.Core.audit_log import get_audit_logs_by_actor

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_query_db.return_value = json.dumps([
            {
                "log_id": 1,
                "execution_id": 100,
                "action_type": "approved",
                "details": {},
                "actor": "user123",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
            },
            {
                "log_id": 2,
                "execution_id": 101,
                "action_type": "rejected",
                "details": {},
                "actor": "user123",
                "timestamp": now.isoformat(),
                "created_at": now.isoformat(),
            },
        ])

        result = get_audit_logs_by_actor("user123")

        assert len(result) == 2
        assert all(entry.actor == "user123" for entry in result)

    @patch("Medic.Core.audit_log.db.query_db")
    def test_get_audit_logs_by_actor_empty(self, mock_query_db):
        """Test retrieving audit logs for actor with no entries."""
        from Medic.Core.audit_log import get_audit_logs_by_actor

        mock_query_db.return_value = "[]"

        result = get_audit_logs_by_actor("unknown_user")

        assert result == []


class TestParseAuditLogEntry:
    """Tests for _parse_audit_log_entry function."""

    def test_parse_audit_log_entry_with_json_details(self):
        """Test parsing entry with JSON string details."""
        from Medic.Core.audit_log import _parse_audit_log_entry

        now = datetime.now(pytz.timezone('America/Chicago'))
        data = {
            "log_id": 1,
            "execution_id": 100,
            "action_type": "execution_started",
            "details": '{"playbook_name": "test"}',  # JSON string
            "actor": None,
            "timestamp": now.isoformat(),
            "created_at": now.isoformat(),
        }

        result = _parse_audit_log_entry(data)

        assert result is not None
        assert result.details == {"playbook_name": "test"}

    def test_parse_audit_log_entry_with_dict_details(self):
        """Test parsing entry with dict details."""
        from Medic.Core.audit_log import _parse_audit_log_entry

        now = datetime.now(pytz.timezone('America/Chicago'))
        data = {
            "log_id": 1,
            "execution_id": 100,
            "action_type": "step_completed",
            "details": {"step_name": "restart"},  # Already a dict
            "actor": None,
            "timestamp": now.isoformat(),
            "created_at": now.isoformat(),
        }

        result = _parse_audit_log_entry(data)

        assert result is not None
        assert result.details == {"step_name": "restart"}

    def test_parse_audit_log_entry_invalid_action_type(self):
        """Test parsing entry with invalid action type."""
        from Medic.Core.audit_log import _parse_audit_log_entry

        now = datetime.now(pytz.timezone('America/Chicago'))
        data = {
            "log_id": 1,
            "execution_id": 100,
            "action_type": "invalid_type",
            "details": {},
            "actor": None,
            "timestamp": now.isoformat(),
            "created_at": now.isoformat(),
        }

        result = _parse_audit_log_entry(data)

        assert result is None

    def test_parse_audit_log_entry_missing_required_field(self):
        """Test parsing entry with missing required field."""
        from Medic.Core.audit_log import _parse_audit_log_entry

        data = {
            "log_id": 1,
            # Missing execution_id
            "action_type": "execution_started",
            "details": {},
            "actor": None,
        }

        result = _parse_audit_log_entry(data)

        assert result is None
