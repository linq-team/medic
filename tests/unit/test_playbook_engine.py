"""Unit tests for playbook_engine module."""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytz


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_execution_status_values(self):
        """Test ExecutionStatus enum has expected values."""
        from Medic.Core.playbook_engine import ExecutionStatus

        assert ExecutionStatus.PENDING_APPROVAL.value == "pending_approval"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.WAITING.value == "waiting"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"

    def test_is_terminal_for_terminal_states(self):
        """Test is_terminal returns True for terminal states."""
        from Medic.Core.playbook_engine import ExecutionStatus

        assert ExecutionStatus.is_terminal(ExecutionStatus.COMPLETED) is True
        assert ExecutionStatus.is_terminal(ExecutionStatus.FAILED) is True
        assert ExecutionStatus.is_terminal(ExecutionStatus.CANCELLED) is True

    def test_is_terminal_for_non_terminal_states(self):
        """Test is_terminal returns False for non-terminal states."""
        from Medic.Core.playbook_engine import ExecutionStatus

        assert ExecutionStatus.is_terminal(
            ExecutionStatus.PENDING_APPROVAL
        ) is False
        assert ExecutionStatus.is_terminal(ExecutionStatus.RUNNING) is False
        assert ExecutionStatus.is_terminal(ExecutionStatus.WAITING) is False

    def test_is_active_for_active_states(self):
        """Test is_active returns True for active states."""
        from Medic.Core.playbook_engine import ExecutionStatus

        assert ExecutionStatus.is_active(ExecutionStatus.RUNNING) is True
        assert ExecutionStatus.is_active(ExecutionStatus.WAITING) is True

    def test_is_active_for_inactive_states(self):
        """Test is_active returns False for inactive states."""
        from Medic.Core.playbook_engine import ExecutionStatus

        assert ExecutionStatus.is_active(
            ExecutionStatus.PENDING_APPROVAL
        ) is False
        assert ExecutionStatus.is_active(ExecutionStatus.COMPLETED) is False
        assert ExecutionStatus.is_active(ExecutionStatus.FAILED) is False


class TestStepResultStatus:
    """Tests for StepResultStatus enum."""

    def test_step_result_status_values(self):
        """Test StepResultStatus enum has expected values."""
        from Medic.Core.playbook_engine import StepResultStatus

        assert StepResultStatus.PENDING.value == "pending"
        assert StepResultStatus.RUNNING.value == "running"
        assert StepResultStatus.COMPLETED.value == "completed"
        assert StepResultStatus.FAILED.value == "failed"
        assert StepResultStatus.SKIPPED.value == "skipped"


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_step_result_creation(self):
        """Test creating a StepResult object."""
        from Medic.Core.playbook_engine import StepResult, StepResultStatus

        now = datetime.now(pytz.timezone('America/Chicago'))
        result = StepResult(
            result_id=1,
            execution_id=100,
            step_name="test-step",
            step_index=0,
            status=StepResultStatus.COMPLETED,
            output="Test output",
            error_message=None,
            started_at=now,
            completed_at=now,
        )

        assert result.result_id == 1
        assert result.execution_id == 100
        assert result.step_name == "test-step"
        assert result.step_index == 0
        assert result.status == StepResultStatus.COMPLETED
        assert result.output == "Test output"

    def test_step_result_to_dict(self):
        """Test StepResult.to_dict() method."""
        from Medic.Core.playbook_engine import StepResult, StepResultStatus

        now = datetime.now(pytz.timezone('America/Chicago'))
        result = StepResult(
            result_id=1,
            execution_id=100,
            step_name="test-step",
            step_index=0,
            status=StepResultStatus.COMPLETED,
            output="Test output",
            started_at=now,
            completed_at=now,
        )

        data = result.to_dict()
        assert data["result_id"] == 1
        assert data["execution_id"] == 100
        assert data["step_name"] == "test-step"
        assert data["status"] == "completed"
        assert data["output"] == "Test output"


class TestPlaybookExecution:
    """Tests for PlaybookExecution dataclass."""

    def test_playbook_execution_creation(self):
        """Test creating a PlaybookExecution object."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=100,
            status=ExecutionStatus.RUNNING,
            current_step=0,
            started_at=now,
            created_at=now,
        )

        assert execution.execution_id == 1
        assert execution.playbook_id == 10
        assert execution.service_id == 100
        assert execution.status == ExecutionStatus.RUNNING
        assert execution.current_step == 0

    def test_playbook_execution_to_dict(self):
        """Test PlaybookExecution.to_dict() method."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=100,
            status=ExecutionStatus.RUNNING,
            current_step=2,
            started_at=now,
        )

        data = execution.to_dict()
        assert data["execution_id"] == 1
        assert data["playbook_id"] == 10
        assert data["service_id"] == 100
        assert data["status"] == "running"
        assert data["current_step"] == 2

    def test_playbook_execution_default_values(self):
        """Test PlaybookExecution has expected defaults."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
        )

        execution = PlaybookExecution(
            execution_id=None,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.PENDING_APPROVAL,
        )

        assert execution.execution_id is None
        assert execution.service_id is None
        assert execution.current_step == 0
        assert execution.playbook is None
        assert execution.step_results == []
        assert execution.context == {}


class TestCreateExecution:
    """Tests for create_execution function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_create_execution_success(self, mock_db):
        """Test creating an execution record successfully."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            create_execution,
        )

        mock_db.query_db.return_value = json.dumps([{"execution_id": 1}])

        execution = create_execution(
            playbook_id=10,
            service_id=100,
            status=ExecutionStatus.RUNNING,
        )

        assert execution is not None
        assert execution.execution_id == 1
        assert execution.playbook_id == 10
        assert execution.service_id == 100
        assert execution.status == ExecutionStatus.RUNNING

    @patch('Medic.Core.playbook_engine.db')
    def test_create_execution_failure(self, mock_db):
        """Test create_execution returns None on failure."""
        from Medic.Core.playbook_engine import create_execution

        mock_db.query_db.return_value = "[]"

        execution = create_execution(playbook_id=10)

        assert execution is None

    @patch('Medic.Core.playbook_engine.db')
    def test_create_execution_with_context(self, mock_db):
        """Test create_execution stores context."""
        from Medic.Core.playbook_engine import create_execution

        mock_db.query_db.return_value = json.dumps([{"execution_id": 1}])

        context = {"SERVICE_NAME": "test-service", "ALERT_ID": "alert-123"}
        execution = create_execution(
            playbook_id=10,
            context=context,
        )

        assert execution is not None
        assert execution.context == context


class TestGetExecution:
    """Tests for get_execution function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_get_execution_found(self, mock_db):
        """Test getting an existing execution."""
        from Medic.Core.playbook_engine import ExecutionStatus, get_execution

        mock_db.query_db.return_value = json.dumps([{
            "execution_id": 1,
            "playbook_id": 10,
            "service_id": 100,
            "status": "running",
            "current_step": 2,
            "started_at": "2026-02-03T10:00:00-06:00",
            "completed_at": None,
            "created_at": "2026-02-03T10:00:00-06:00",
            "updated_at": "2026-02-03T10:00:00-06:00",
        }])

        execution = get_execution(1)

        assert execution is not None
        assert execution.execution_id == 1
        assert execution.playbook_id == 10
        assert execution.status == ExecutionStatus.RUNNING
        assert execution.current_step == 2

    @patch('Medic.Core.playbook_engine.db')
    def test_get_execution_not_found(self, mock_db):
        """Test get_execution returns None for missing execution."""
        from Medic.Core.playbook_engine import get_execution

        mock_db.query_db.return_value = "[]"

        execution = get_execution(999)

        assert execution is None


class TestGetActiveExecutions:
    """Tests for get_active_executions function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_get_active_executions_with_results(self, mock_db):
        """Test getting active executions."""
        from Medic.Core.playbook_engine import get_active_executions

        mock_db.query_db.return_value = json.dumps([
            {
                "execution_id": 1,
                "playbook_id": 10,
                "service_id": 100,
                "status": "running",
                "current_step": 0,
                "started_at": "2026-02-03T10:00:00-06:00",
                "completed_at": None,
                "created_at": "2026-02-03T10:00:00-06:00",
                "updated_at": "2026-02-03T10:00:00-06:00",
            },
            {
                "execution_id": 2,
                "playbook_id": 20,
                "service_id": 200,
                "status": "waiting",
                "current_step": 1,
                "started_at": "2026-02-03T09:00:00-06:00",
                "completed_at": None,
                "created_at": "2026-02-03T09:00:00-06:00",
                "updated_at": "2026-02-03T09:30:00-06:00",
            },
        ])

        executions = get_active_executions()

        assert len(executions) == 2
        assert executions[0].execution_id == 1
        assert executions[1].execution_id == 2

    @patch('Medic.Core.playbook_engine.db')
    def test_get_active_executions_empty(self, mock_db):
        """Test get_active_executions returns empty list when none."""
        from Medic.Core.playbook_engine import get_active_executions

        mock_db.query_db.return_value = "[]"

        executions = get_active_executions()

        assert executions == []


class TestUpdateExecutionStatus:
    """Tests for update_execution_status function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_update_execution_status_success(self, mock_db):
        """Test updating execution status successfully."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            update_execution_status,
        )

        mock_db.insert_db.return_value = True

        result = update_execution_status(
            execution_id=1,
            status=ExecutionStatus.COMPLETED,
        )

        assert result is True
        mock_db.insert_db.assert_called_once()

    @patch('Medic.Core.playbook_engine.db')
    def test_update_execution_status_with_step(self, mock_db):
        """Test updating execution with current_step."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            update_execution_status,
        )

        mock_db.insert_db.return_value = True

        result = update_execution_status(
            execution_id=1,
            status=ExecutionStatus.RUNNING,
            current_step=3,
        )

        assert result is True
        # Verify current_step was included in update
        call_args = mock_db.insert_db.call_args
        assert "current_step = %s" in call_args[0][0]


class TestStepResultOperations:
    """Tests for step result database operations."""

    @patch('Medic.Core.playbook_engine.db')
    def test_create_step_result_success(self, mock_db):
        """Test creating a step result successfully."""
        from Medic.Core.playbook_engine import (
            StepResultStatus,
            create_step_result,
        )

        mock_db.query_db.return_value = json.dumps([{"result_id": 1}])

        result = create_step_result(
            execution_id=100,
            step_name="test-step",
            step_index=0,
        )

        assert result is not None
        assert result.result_id == 1
        assert result.execution_id == 100
        assert result.step_name == "test-step"
        assert result.status == StepResultStatus.PENDING

    @patch('Medic.Core.playbook_engine.db')
    def test_update_step_result_success(self, mock_db):
        """Test updating a step result."""
        from Medic.Core.playbook_engine import (
            StepResultStatus,
            update_step_result,
        )

        mock_db.insert_db.return_value = True

        result = update_step_result(
            result_id=1,
            status=StepResultStatus.COMPLETED,
            output="Step completed successfully",
        )

        assert result is True

    @patch('Medic.Core.playbook_engine.db')
    def test_update_step_result_truncates_long_output(self, mock_db):
        """Test that long output is truncated."""
        from Medic.Core.playbook_engine import (
            StepResultStatus,
            update_step_result,
        )

        mock_db.insert_db.return_value = True

        # Create output longer than 4096 chars
        long_output = "x" * 5000

        update_step_result(
            result_id=1,
            status=StepResultStatus.COMPLETED,
            output=long_output,
        )

        # Check that output was truncated in the call
        call_args = mock_db.insert_db.call_args
        params = call_args[0][1]
        # Find the output param (third param after status and updated_at)
        for param in params:
            if isinstance(param, str) and len(param) > 100:
                assert len(param) == 4096


class TestGetStepResultsForExecution:
    """Tests for get_step_results_for_execution function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_get_step_results_with_results(self, mock_db):
        """Test getting step results for execution."""
        from Medic.Core.playbook_engine import get_step_results_for_execution

        mock_db.query_db.return_value = json.dumps([
            {
                "result_id": 1,
                "execution_id": 100,
                "step_name": "step-1",
                "step_index": 0,
                "status": "completed",
                "output": "Done",
                "error_message": None,
                "started_at": "2026-02-03T10:00:00-06:00",
                "completed_at": "2026-02-03T10:01:00-06:00",
            },
            {
                "result_id": 2,
                "execution_id": 100,
                "step_name": "step-2",
                "step_index": 1,
                "status": "running",
                "output": None,
                "error_message": None,
                "started_at": "2026-02-03T10:01:00-06:00",
                "completed_at": None,
            },
        ])

        results = get_step_results_for_execution(100)

        assert len(results) == 2
        assert results[0].step_name == "step-1"
        assert results[1].step_name == "step-2"


class TestGetPlaybookById:
    """Tests for get_playbook_by_id function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_get_playbook_by_id_found(self, mock_db):
        """Test getting a playbook by ID."""
        from Medic.Core.playbook_engine import get_playbook_by_id

        yaml_content = """
name: test-playbook
description: A test playbook
steps:
  - name: wait-step
    type: wait
    duration: 5s
"""
        mock_db.query_db.return_value = json.dumps([{
            "playbook_id": 1,
            "name": "test-playbook",
            "description": "A test playbook",
            "yaml_content": yaml_content,
            "version": 1,
        }])

        playbook = get_playbook_by_id(1)

        assert playbook is not None
        assert playbook.name == "test-playbook"
        assert len(playbook.steps) == 1

    @patch('Medic.Core.playbook_engine.db')
    def test_get_playbook_by_id_not_found(self, mock_db):
        """Test get_playbook_by_id returns None when not found."""
        from Medic.Core.playbook_engine import get_playbook_by_id

        mock_db.query_db.return_value = "[]"

        playbook = get_playbook_by_id(999)

        assert playbook is None


class TestExecuteWaitStep:
    """Tests for execute_wait_step function."""

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_wait_step_success(
        self,
        mock_create,
        mock_update,
        mock_sleep
    ):
        """Test executing a wait step successfully."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_wait_step,
        )
        from Medic.Core.playbook_parser import WaitStep

        # Mock step result creation
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        step = WaitStep(name="test-wait", duration_seconds=5)
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_wait_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        assert "5 seconds" in result.output
        mock_sleep.assert_called_once_with(5)

    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_wait_step_creation_failure(self, mock_create):
        """Test execute_wait_step handles creation failure."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_wait_step,
        )
        from Medic.Core.playbook_parser import WaitStep

        mock_create.return_value = None

        step = WaitStep(name="test-wait", duration_seconds=5)
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_wait_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "Failed to create step result" in result.error_message


class TestPlaybookExecutionEngine:
    """Tests for PlaybookExecutionEngine class."""

    def test_engine_creation(self):
        """Test creating an execution engine."""
        from Medic.Core.playbook_engine import PlaybookExecutionEngine

        engine = PlaybookExecutionEngine()
        assert engine is not None
        assert len(engine._step_executors) == 4

    @patch('Medic.Core.playbook_engine.get_playbook_by_id')
    @patch('Medic.Core.playbook_engine.create_execution')
    def test_start_execution_playbook_not_found(
        self,
        mock_create,
        mock_get_playbook
    ):
        """Test start_execution returns None if playbook not found."""
        from Medic.Core.playbook_engine import PlaybookExecutionEngine

        mock_get_playbook.return_value = None

        engine = PlaybookExecutionEngine()
        result = engine.start_execution(playbook_id=999)

        assert result is None
        mock_create.assert_not_called()

    @patch('Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE', False)
    @patch('Medic.Core.playbook_engine._update_pending_approval_metric')
    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.get_playbook_by_id')
    @patch('Medic.Core.playbook_engine.create_execution')
    def test_start_execution_with_approval(
        self,
        mock_create,
        mock_get_playbook,
        mock_update,
        mock_update_pending
    ):
        """Test start_execution respects approval setting."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import ApprovalMode, Playbook, WaitStep

        playbook = Playbook(
            name="test",
            description="test",
            steps=[WaitStep(name="wait", duration_seconds=1)],
            approval=ApprovalMode.REQUIRED,
        )
        mock_get_playbook.return_value = playbook

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        mock_create.return_value = execution

        engine = PlaybookExecutionEngine()
        result = engine.start_execution(playbook_id=10)

        assert result is not None
        assert result.status == ExecutionStatus.PENDING_APPROVAL
        # Should not execute steps when pending approval
        mock_update.assert_not_called()
        # Should update pending approval metric
        mock_update_pending.assert_called_once()

    @patch('Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE', False)
    @patch('Medic.Core.playbook_engine._update_pending_approval_metric')
    @patch('Medic.Core.playbook_engine.record_playbook_execution_duration')
    @patch('Medic.Core.playbook_engine.record_playbook_execution')
    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine.get_playbook_by_id')
    @patch('Medic.Core.playbook_engine.create_execution')
    def test_start_execution_runs_immediately_when_no_approval(
        self,
        mock_create_exec,
        mock_get_playbook,
        mock_create_step,
        mock_update_step,
        mock_sleep,
        mock_update_exec,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test execution runs immediately when approval=none."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import ApprovalMode, Playbook, WaitStep

        playbook = Playbook(
            name="test",
            description="test",
            steps=[WaitStep(name="wait", duration_seconds=1)],
            approval=ApprovalMode.NONE,
        )
        mock_get_playbook.return_value = playbook

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
        )
        mock_create_exec.return_value = execution
        mock_create_step.return_value = MagicMock(result_id=1)
        mock_update_step.return_value = True
        mock_update_exec.return_value = True

        engine = PlaybookExecutionEngine()
        result = engine.start_execution(playbook_id=10)

        assert result is not None
        # Should have executed wait step
        mock_sleep.assert_called_once_with(1)

    @patch('Medic.Core.playbook_engine.get_execution')
    def test_resume_execution_not_found(self, mock_get):
        """Test resume_execution returns None if not found."""
        from Medic.Core.playbook_engine import PlaybookExecutionEngine

        mock_get.return_value = None

        engine = PlaybookExecutionEngine()
        result = engine.resume_execution(999)

        assert result is None

    @patch('Medic.Core.playbook_engine.get_execution')
    def test_resume_execution_terminal_state(self, mock_get):
        """Test resume_execution returns execution if already terminal."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.COMPLETED,
        )
        mock_get.return_value = execution

        engine = PlaybookExecutionEngine()
        result = engine.resume_execution(1)

        assert result is not None
        assert result.status == ExecutionStatus.COMPLETED

    @patch('Medic.Core.playbook_engine._update_pending_approval_metric')
    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.get_execution')
    def test_approve_execution_success(
        self, mock_get, mock_update, mock_update_pending
    ):
        """Test approving an execution."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        mock_get.return_value = execution
        mock_update.return_value = True

        engine = PlaybookExecutionEngine()

        # Patch resume to avoid full execution
        with patch.object(engine, 'resume_execution'):
            result = engine.approve_execution(1)

        assert result is True
        mock_update.assert_called()
        mock_update_pending.assert_called_once()

    @patch('Medic.Core.playbook_engine.get_execution')
    def test_approve_execution_wrong_status(self, mock_get):
        """Test approve_execution fails if not pending_approval."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
        )
        mock_get.return_value = execution

        engine = PlaybookExecutionEngine()
        result = engine.approve_execution(1)

        assert result is False

    @patch('Medic.Core.playbook_engine._update_pending_approval_metric')
    @patch('Medic.Core.playbook_engine.record_playbook_execution_duration')
    @patch('Medic.Core.playbook_engine.record_playbook_execution')
    @patch('Medic.Core.playbook_engine.get_playbook_by_id')
    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.get_execution')
    def test_cancel_execution_success(
        self,
        mock_get,
        mock_update,
        mock_get_playbook,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test cancelling an execution."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import Playbook

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
        )
        playbook = Playbook(
            name="test-playbook",
            description="test",
            steps=[],
        )
        mock_get.return_value = execution
        mock_update.return_value = True
        mock_get_playbook.return_value = playbook

        engine = PlaybookExecutionEngine()
        result = engine.cancel_execution(1)

        assert result is True
        mock_record_exec.assert_called_once_with("test-playbook", "cancelled")
        mock_update_pending.assert_called_once()

    @patch('Medic.Core.playbook_engine.get_execution')
    def test_cancel_execution_already_terminal(self, mock_get):
        """Test cancel_execution fails if already terminal."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.COMPLETED,
        )
        mock_get.return_value = execution

        engine = PlaybookExecutionEngine()
        result = engine.cancel_execution(1)

        assert result is False


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_engine_returns_singleton(self):
        """Test get_engine returns same instance."""
        from Medic.Core.playbook_engine import get_engine

        engine1 = get_engine()
        engine2 = get_engine()

        assert engine1 is engine2

    @patch('Medic.Core.playbook_engine.get_engine')
    def test_start_playbook_execution(self, mock_get_engine):
        """Test start_playbook_execution convenience function."""
        from Medic.Core.playbook_engine import start_playbook_execution

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        start_playbook_execution(
            playbook_id=10,
            service_id=100,
            context={"key": "value"},
        )

        mock_engine.start_execution.assert_called_once_with(
            playbook_id=10,
            service_id=100,
            context={"key": "value"},
            skip_approval=False,
        )

    @patch('Medic.Core.playbook_engine.get_engine')
    def test_resume_playbook_execution(self, mock_get_engine):
        """Test resume_playbook_execution convenience function."""
        from Medic.Core.playbook_engine import resume_playbook_execution

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        resume_playbook_execution(1)

        mock_engine.resume_execution.assert_called_once_with(1)

    @patch('Medic.Core.playbook_engine.get_engine')
    def test_approve_playbook_execution(self, mock_get_engine):
        """Test approve_playbook_execution convenience function."""
        from Medic.Core.playbook_engine import approve_playbook_execution

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        approve_playbook_execution(1)

        mock_engine.approve_execution.assert_called_once_with(1)

    @patch('Medic.Core.playbook_engine.get_engine')
    def test_cancel_playbook_execution(self, mock_get_engine):
        """Test cancel_playbook_execution convenience function."""
        from Medic.Core.playbook_engine import cancel_playbook_execution

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        cancel_playbook_execution(1)

        mock_engine.cancel_execution.assert_called_once_with(1)


class TestParseDateTime:
    """Tests for _parse_datetime helper function."""

    def test_parse_datetime_iso_format(self):
        """Test parsing ISO format with timezone."""
        from Medic.Core.playbook_engine import _parse_datetime

        result = _parse_datetime("2026-02-03T10:00:00-06:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 3

    def test_parse_datetime_no_timezone(self):
        """Test parsing format without timezone."""
        from Medic.Core.playbook_engine import _parse_datetime

        result = _parse_datetime("2026-02-03 10:00:00")
        assert result is not None
        assert result.year == 2026

    def test_parse_datetime_invalid(self):
        """Test parsing invalid format returns None."""
        from Medic.Core.playbook_engine import _parse_datetime

        result = _parse_datetime("invalid-date")
        assert result is None


class TestExecutionWithMultipleSteps:
    """Tests for execution with multiple steps."""

    @patch('Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE', False)
    @patch('Medic.Core.playbook_engine._update_pending_approval_metric')
    @patch('Medic.Core.playbook_engine.record_playbook_execution_duration')
    @patch('Medic.Core.playbook_engine.record_playbook_execution')
    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine.get_playbook_by_id')
    @patch('Medic.Core.playbook_engine.create_execution')
    def test_multiple_wait_steps_execute_in_order(
        self,
        mock_create_exec,
        mock_get_playbook,
        mock_create_step,
        mock_update_step,
        mock_sleep,
        mock_update_exec,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test multiple wait steps execute in sequence."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import ApprovalMode, Playbook, WaitStep

        playbook = Playbook(
            name="multi-step",
            description="test",
            steps=[
                WaitStep(name="wait-1", duration_seconds=1),
                WaitStep(name="wait-2", duration_seconds=2),
                WaitStep(name="wait-3", duration_seconds=3),
            ],
            approval=ApprovalMode.NONE,
        )
        mock_get_playbook.return_value = playbook

        execution = PlaybookExecution(
            execution_id=1,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
        )
        mock_create_exec.return_value = execution
        mock_create_step.return_value = MagicMock(result_id=1)
        mock_update_step.return_value = True
        mock_update_exec.return_value = True

        engine = PlaybookExecutionEngine()
        result = engine.start_execution(playbook_id=10)

        # Should have slept 3 times: 1s, 2s, 3s
        assert mock_sleep.call_count == 3
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert calls == [1, 2, 3]

        # Execution should be completed
        # Check that COMPLETED status was set
        completed_calls = [
            call for call in mock_update_exec.call_args_list
            if call[0][1] == ExecutionStatus.COMPLETED
        ]
        assert len(completed_calls) >= 1


class TestSubstituteVariables:
    """Tests for substitute_variables function."""

    def test_substitute_simple_string(self):
        """Test variable substitution in a simple string."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {"SERVICE_NAME": "my-service"}
        result = substitute_variables(
            "Restarting ${SERVICE_NAME}",
            context
        )
        assert result == "Restarting my-service"

    def test_substitute_multiple_variables(self):
        """Test multiple variable substitution."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {
            "SERVICE_NAME": "my-service",
            "ALERT_ID": "alert-123",
            "RUN_ID": "run-456",
        }
        result = substitute_variables(
            "${SERVICE_NAME}: ${ALERT_ID} (${RUN_ID})",
            context
        )
        assert result == "my-service: alert-123 (run-456)"

    def test_substitute_in_dict(self):
        """Test variable substitution in dictionary."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {"SERVICE_NAME": "worker-1", "SERVICE_ID": 42}
        input_dict = {
            "name": "${SERVICE_NAME}",
            "id": "${SERVICE_ID}",
            "action": "restart",
        }
        result = substitute_variables(input_dict, context)
        assert result == {
            "name": "worker-1",
            "id": "42",
            "action": "restart",
        }

    def test_substitute_in_nested_dict(self):
        """Test variable substitution in nested dictionary."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {"SERVICE_NAME": "api-server"}
        input_dict = {
            "body": {
                "service": "${SERVICE_NAME}",
                "metadata": {
                    "source": "${SERVICE_NAME}-alerts"
                }
            }
        }
        result = substitute_variables(input_dict, context)
        assert result["body"]["service"] == "api-server"
        assert result["body"]["metadata"]["source"] == "api-server-alerts"

    def test_substitute_in_list(self):
        """Test variable substitution in list."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {"SERVICE_NAME": "worker", "HOST": "localhost"}
        input_list = ["${SERVICE_NAME}", "${HOST}", "static"]
        result = substitute_variables(input_list, context)
        assert result == ["worker", "localhost", "static"]

    def test_substitute_missing_variable_unchanged(self):
        """Test missing variable keeps original placeholder."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {"SERVICE_NAME": "my-service"}
        result = substitute_variables(
            "${SERVICE_NAME}: ${UNKNOWN_VAR}",
            context
        )
        assert result == "my-service: ${UNKNOWN_VAR}"

    def test_substitute_non_string_unchanged(self):
        """Test non-string values pass through unchanged."""
        from Medic.Core.playbook_engine import substitute_variables

        context = {"FOO": "bar"}
        assert substitute_variables(123, context) == 123
        assert substitute_variables(True, context) is True
        assert substitute_variables(None, context) is None

    def test_substitute_empty_context(self):
        """Test substitution with empty context."""
        from Medic.Core.playbook_engine import substitute_variables

        result = substitute_variables("${SERVICE_NAME}", {})
        assert result == "${SERVICE_NAME}"


class TestBuildWebhookContext:
    """Tests for _build_webhook_context function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_build_context_includes_execution_info(self, mock_db):
        """Test context includes execution information."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            _build_webhook_context,
        )

        mock_db.query_db.return_value = "[]"  # No service found

        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
        )
        context = _build_webhook_context(execution)

        assert context['EXECUTION_ID'] == 100
        assert context['PLAYBOOK_ID'] == 10
        assert context['SERVICE_ID'] == 42

    def test_build_context_includes_playbook_name(self):
        """Test context includes playbook name when available."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            _build_webhook_context,
        )
        from Medic.Core.playbook_parser import ApprovalMode, Playbook, WaitStep

        playbook = Playbook(
            name="restart-service",
            description="Restart a service",
            steps=[WaitStep(name="wait", duration_seconds=1)],
            approval=ApprovalMode.NONE,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
        )
        execution.playbook = playbook

        context = _build_webhook_context(execution)

        assert context['PLAYBOOK_NAME'] == "restart-service"

    def test_build_context_preserves_existing_context(self):
        """Test existing execution context is preserved."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            _build_webhook_context,
        )

        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            context={
                "ALERT_ID": "alert-123",
                "RUN_ID": "run-456",
                "CUSTOM_VAR": "custom-value",
            }
        )
        context = _build_webhook_context(execution)

        assert context['ALERT_ID'] == "alert-123"
        assert context['RUN_ID'] == "run-456"
        assert context['CUSTOM_VAR'] == "custom-value"

    @patch('Medic.Core.playbook_engine.db')
    def test_build_context_fetches_service_name(self, mock_db):
        """Test context fetches service name from database."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            _build_webhook_context,
        )

        mock_db.query_db.return_value = json.dumps([{"name": "worker-service"}])

        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
        )
        context = _build_webhook_context(execution)

        assert context['SERVICE_NAME'] == "worker-service"


class TestExecuteWebhookStep:
    """Tests for execute_webhook_step function."""

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_success(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test successful webhook execution."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {"SERVICE_NAME": "test"}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'

        def mock_request(**kwargs):
            return mock_response

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
            method="POST",
            body={"action": "restart"},
            success_codes=[200, 201],
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.COMPLETED
        assert "Status: 200" in result.output

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_failure_status_code(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook execution fails on unexpected status code."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock HTTP client returning 500
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'

        def mock_request(**kwargs):
            return mock_response

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
            success_codes=[200],
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.FAILED
        assert "Unexpected status code 500" in result.error_message

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_variable_substitution(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook step performs variable substitution."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {
            "SERVICE_NAME": "my-service",
            "ALERT_ID": "alert-123",
        }
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Capture the request
        captured_kwargs = {}

        def mock_request(**kwargs):
            captured_kwargs.update(kwargs)
            response = MagicMock()
            response.status_code = 200
            response.text = "OK"
            return response

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api/${SERVICE_NAME}",
            method="POST",
            headers={"X-Alert-Id": "${ALERT_ID}"},
            body={"service": "${SERVICE_NAME}"},
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.COMPLETED
        assert captured_kwargs['url'] == "https://example.com/api/my-service"
        assert "X-Alert-Id" in captured_kwargs['headers']
        assert captured_kwargs['headers']['X-Alert-Id'] == "alert-123"
        assert captured_kwargs['json']['service'] == "my-service"

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_timeout(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook step handles timeout."""
        import requests
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        def mock_request(**kwargs):
            raise requests.Timeout("Connection timed out")

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
            timeout_seconds=5,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.FAILED
        assert "timed out" in result.error_message.lower()

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_connection_error(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook step handles connection error."""
        import requests
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        def mock_request(**kwargs):
            raise requests.ConnectionError("Failed to connect")

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.FAILED
        assert "connection error" in result.error_message.lower()

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_custom_success_codes(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook step uses custom success codes."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock HTTP client returning 204
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ''

        def mock_request(**kwargs):
            return mock_response

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
            success_codes=[200, 204],  # Include 204 as success
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.COMPLETED

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_truncates_long_response(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook step truncates long response body."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
            MAX_RESPONSE_BODY_SIZE,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock HTTP client returning large response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'x' * (MAX_RESPONSE_BODY_SIZE + 1000)

        def mock_request(**kwargs):
            return mock_response

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.COMPLETED
        assert "[truncated]" in result.output

    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_creation_failure(
        self,
        mock_build_context,
        mock_create
    ):
        """Test webhook step handles step result creation failure."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = None  # Simulate creation failure

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "Failed to create step result" in result.error_message

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    def test_execute_webhook_step_get_method(
        self,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test webhook step with GET method."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        captured_kwargs = {}

        def mock_request(**kwargs):
            captured_kwargs.update(kwargs)
            response = MagicMock()
            response.status_code = 200
            response.text = '{"data": []}'
            return response

        step = WebhookStep(
            name="test-webhook",
            url="https://example.com/api/status",
            method="GET",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_webhook_step(step, execution, http_client=mock_request)

        assert result.status == StepResultStatus.COMPLETED
        assert captured_kwargs['method'] == "GET"


class TestRegisteredScript:
    """Tests for RegisteredScript dataclass."""

    def test_registered_script_creation(self):
        """Test creating a RegisteredScript object."""
        from Medic.Core.playbook_engine import RegisteredScript

        script = RegisteredScript(
            script_id=1,
            name="test-script",
            content="echo 'Hello World'",
            interpreter="bash",
            timeout_seconds=30,
        )

        assert script.script_id == 1
        assert script.name == "test-script"
        assert script.content == "echo 'Hello World'"
        assert script.interpreter == "bash"
        assert script.timeout_seconds == 30


class TestGetRegisteredScript:
    """Tests for get_registered_script function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_get_registered_script_found(self, mock_db):
        """Test getting a registered script by name."""
        from Medic.Core.playbook_engine import get_registered_script

        mock_db.query_db.return_value = json.dumps([{
            "script_id": 1,
            "name": "restart-service",
            "content": "#!/bin/bash\necho 'Restarting'",
            "interpreter": "bash",
            "timeout_seconds": 60,
        }])

        script = get_registered_script("restart-service")

        assert script is not None
        assert script.script_id == 1
        assert script.name == "restart-service"
        assert script.interpreter == "bash"
        assert script.timeout_seconds == 60

    @patch('Medic.Core.playbook_engine.db')
    def test_get_registered_script_not_found(self, mock_db):
        """Test get_registered_script returns None when not found."""
        from Medic.Core.playbook_engine import get_registered_script

        mock_db.query_db.return_value = "[]"

        script = get_registered_script("nonexistent-script")

        assert script is None

    @patch('Medic.Core.playbook_engine.db')
    def test_get_registered_script_default_timeout(self, mock_db):
        """Test get_registered_script uses default timeout if not set."""
        from Medic.Core.playbook_engine import (
            DEFAULT_SCRIPT_TIMEOUT,
            get_registered_script,
        )

        mock_db.query_db.return_value = json.dumps([{
            "script_id": 1,
            "name": "test-script",
            "content": "echo 'test'",
            "interpreter": "bash",
        }])

        script = get_registered_script("test-script")

        assert script is not None
        assert script.timeout_seconds == DEFAULT_SCRIPT_TIMEOUT


class TestSubstituteScriptVariables:
    """Tests for _substitute_script_variables function."""

    def test_substitute_context_variables(self):
        """Test substituting context variables in script."""
        from Medic.Core.playbook_engine import _substitute_script_variables

        script = "echo 'Service: ${SERVICE_NAME}'"
        context = {"SERVICE_NAME": "my-service"}
        parameters = {}

        result = _substitute_script_variables(script, context, parameters)

        assert result == "echo 'Service: my-service'"

    def test_substitute_parameter_variables(self):
        """Test substituting parameter variables in script."""
        from Medic.Core.playbook_engine import _substitute_script_variables

        script = "echo 'Target: ${TARGET}'"
        context = {}
        parameters = {"TARGET": "production"}

        result = _substitute_script_variables(script, context, parameters)

        assert result == "echo 'Target: production'"

    def test_parameters_override_context(self):
        """Test that parameters override context variables."""
        from Medic.Core.playbook_engine import _substitute_script_variables

        script = "echo '${VALUE}'"
        context = {"VALUE": "from-context"}
        parameters = {"VALUE": "from-params"}

        result = _substitute_script_variables(script, context, parameters)

        assert result == "echo 'from-params'"

    def test_multiple_variable_substitution(self):
        """Test substituting multiple variables."""
        from Medic.Core.playbook_engine import _substitute_script_variables

        script = "curl -X POST ${URL}/restart -d '{\"service\": \"${SERVICE}\"}'"
        context = {"SERVICE": "api"}
        parameters = {"URL": "http://localhost:8080"}

        result = _substitute_script_variables(script, context, parameters)

        assert "http://localhost:8080" in result
        assert "api" in result


class TestExecuteScriptStep:
    """Tests for execute_script_step function."""

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_success(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test successful script execution."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="test-script",
            content="echo 'Hello World'",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock successful subprocess execution
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Hello World\n"
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="test-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        assert "Exit code: 0" in result.output
        assert "Hello World" in result.output

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_not_found(
        self,
        mock_get_script,
        mock_create,
        mock_update
    ):
        """Test script step fails when script not found."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = None  # Script not found
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        step = ScriptStep(
            name="test-step",
            script_name="nonexistent-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "not found in registered scripts" in result.error_message

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_nonzero_exit(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step fails on non-zero exit code."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="failing-script",
            content="exit 1",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock failed subprocess execution
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Error: Something went wrong"
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="failing-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "exited with code 1" in result.error_message
        assert "Error: Something went wrong" in result.output

    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_timeout(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess
    ):
        """Test script step handles timeout."""
        import subprocess
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="slow-script",
            content="sleep 100",
            interpreter="bash",
            timeout_seconds=5,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock timeout
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd="bash",
            timeout=5
        )

        step = ScriptStep(
            name="test-step",
            script_name="slow-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "timed out" in result.error_message.lower()

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_with_python(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step with Python interpreter."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="python-script",
            content="print('Hello from Python')",
            interpreter="python",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock successful subprocess execution
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Hello from Python\n"
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="python-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        # Verify python3 was used
        call_args = mock_subprocess.call_args
        assert 'python3' in call_args[0][0]

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_unsupported_interpreter(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update
    ):
        """Test script step fails with unsupported interpreter."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="ruby-script",
            content="puts 'Hello'",
            interpreter="ruby",  # Not supported
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        step = ScriptStep(
            name="test-step",
            script_name="ruby-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "Unsupported interpreter" in result.error_message

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_variable_substitution(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step performs variable substitution."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="restart-script",
            content="echo 'Restarting ${SERVICE_NAME}'",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {"SERVICE_NAME": "api-server"}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock successful subprocess execution
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Restarting api-server\n"
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="restart-script",
            parameters={"SERVICE_NAME": "api-server"},
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED

    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_creation_failure(
        self,
        mock_get_script,
        mock_create
    ):
        """Test script step handles step result creation failure."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="test-script",
            content="echo 'test'",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_create.return_value = None  # Simulate creation failure

        step = ScriptStep(
            name="test-step",
            script_name="test-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "Failed to create step result" in result.error_message

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_truncates_long_output(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step truncates long output."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            MAX_SCRIPT_OUTPUT_SIZE,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="verbose-script",
            content="for i in {1..10000}; do echo 'Line $i'; done",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock subprocess with large output
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "x" * (MAX_SCRIPT_OUTPUT_SIZE + 1000)
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="verbose-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        assert "[output truncated]" in result.output

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_captures_stderr(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step captures stderr in output."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="warn-script",
            content="echo 'output' && echo 'warning' >&2",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock subprocess with stderr
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "output\n"
        mock_proc.stderr = "warning\n"
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="warn-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        assert "output" in result.output
        assert "[STDERR]" in result.output
        assert "warning" in result.output

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_uses_step_timeout(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step uses step-level timeout over script timeout."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="test-script",
            content="echo 'test'",
            interpreter="bash",
            timeout_seconds=60,  # Script default timeout
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "test\n"
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="test-script",
            timeout_seconds=15,  # Step-level timeout override
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        execute_script_step(step, execution)

        # Verify the subprocess was called with step timeout
        call_kwargs = mock_subprocess.call_args[1]
        assert call_kwargs['timeout'] == 15

    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_generic_exception(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess
    ):
        """Test script step handles generic exceptions."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            StepResultStatus,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="test-script",
            content="echo 'test'",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        # Mock generic exception
        mock_subprocess.side_effect = Exception("Unexpected error")

        step = ScriptStep(
            name="test-step",
            script_name="test-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "Unexpected error" in result.error_message

    @patch('Medic.Core.playbook_engine.os.unlink')
    @patch('Medic.Core.playbook_engine.subprocess.run')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    @patch('Medic.Core.playbook_engine._build_webhook_context')
    @patch('Medic.Core.playbook_engine.get_registered_script')
    def test_execute_script_step_sets_env_vars(
        self,
        mock_get_script,
        mock_build_context,
        mock_create,
        mock_update,
        mock_subprocess,
        mock_unlink
    ):
        """Test script step sets MEDIC environment variables."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            RegisteredScript,
            execute_script_step,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_get_script.return_value = RegisteredScript(
            script_id=1,
            name="test-script",
            content="echo $MEDIC_EXECUTION_ID",
            interpreter="bash",
            timeout_seconds=30,
        )
        mock_build_context.return_value = {}
        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "100\n"
        mock_proc.stderr = ""
        mock_subprocess.return_value = mock_proc

        step = ScriptStep(
            name="test-step",
            script_name="test-script",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        execute_script_step(step, execution)

        # Verify environment variables were set
        call_kwargs = mock_subprocess.call_args[1]
        env = call_kwargs['env']
        assert env['MEDIC_EXECUTION_ID'] == '100'
        assert env['MEDIC_PLAYBOOK_ID'] == '10'
        assert env['MEDIC_SERVICE_ID'] == '42'


class TestCheckHeartbeatReceived:
    """Tests for check_heartbeat_received function."""

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_success(self, mock_db):
        """Test heartbeat received check when heartbeat exists."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = json.dumps([{"count": 1}])

        now = datetime.now(pytz.timezone('America/Chicago'))
        met, message = check_heartbeat_received(
            service_id=42,
            since=now - timedelta(minutes=5),
            parameters={},
        )

        assert met is True
        assert "Heartbeat received" in message

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_not_found(self, mock_db):
        """Test heartbeat received check when no heartbeat found."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = json.dumps([{"count": 0}])

        now = datetime.now(pytz.timezone('America/Chicago'))
        met, message = check_heartbeat_received(
            service_id=42,
            since=now,
            parameters={},
        )

        assert met is False
        assert "Waiting for heartbeat" in message

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_min_count(self, mock_db):
        """Test heartbeat check with min_count parameter."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = json.dumps([{"count": 2}])

        now = datetime.now(pytz.timezone('America/Chicago'))
        met, message = check_heartbeat_received(
            service_id=42,
            since=now - timedelta(minutes=10),
            parameters={"min_count": 3},
        )

        assert met is False
        assert "2/3" in message

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_min_count_met(self, mock_db):
        """Test heartbeat check when min_count is met."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = json.dumps([{"count": 3}])

        now = datetime.now(pytz.timezone('America/Chicago'))
        met, message = check_heartbeat_received(
            service_id=42,
            since=now - timedelta(minutes=10),
            parameters={"min_count": 3},
        )

        assert met is True
        assert "3 heartbeat(s)" in message

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_with_status_filter(self, mock_db):
        """Test heartbeat check with status filter."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = json.dumps([{"count": 1}])

        now = datetime.now(pytz.timezone('America/Chicago'))
        check_heartbeat_received(
            service_id=42,
            since=now,
            parameters={"status": "UP"},
        )

        # Verify status filter was included in query
        call_args = mock_db.query_db.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "status = %s" in query
        assert "UP" in params

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_db_failure(self, mock_db):
        """Test heartbeat check handles DB failure."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = None

        now = datetime.now(pytz.timezone('America/Chicago'))
        met, message = check_heartbeat_received(
            service_id=42,
            since=now,
            parameters={},
        )

        assert met is False
        assert "Failed to query" in message

    @patch('Medic.Core.playbook_engine.db')
    def test_check_heartbeat_received_json_error(self, mock_db):
        """Test heartbeat check handles JSON parse error."""
        from Medic.Core.playbook_engine import check_heartbeat_received

        mock_db.query_db.return_value = "invalid json"

        now = datetime.now(pytz.timezone('America/Chicago'))
        met, message = check_heartbeat_received(
            service_id=42,
            since=now,
            parameters={},
        )

        assert met is False
        assert "Error parsing" in message


class TestExecuteConditionStep:
    """Tests for execute_condition_step function."""

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_success_immediately(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step succeeds when condition met immediately."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (True, "Heartbeat received: 1")

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=60,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        assert "Condition 'heartbeat_received' met" in result.output

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_timeout_fail(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step fails on timeout with on_failure=fail."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import (
            ConditionStep,
            ConditionType,
            OnFailureAction,
        )

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (False, "No heartbeat found")

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=1,  # Very short timeout for test
            on_failure=OnFailureAction.FAIL,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "timed out" in result.output

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_timeout_continue(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step continues on timeout with on_failure=continue."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import (
            ConditionStep,
            ConditionType,
            OnFailureAction,
        )

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (False, "No heartbeat found")

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=1,
            on_failure=OnFailureAction.CONTINUE,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED  # Continues!
        assert "on_failure=continue" in result.output

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_timeout_escalate(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step escalates on timeout with on_failure=escalate."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import (
            ConditionStep,
            ConditionType,
            OnFailureAction,
        )

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (False, "No heartbeat found")

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=1,
            on_failure=OnFailureAction.ESCALATE,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "[ESCALATE]" in result.output
        assert "escalating" in result.error_message.lower()

    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_no_service_id(
        self,
        mock_create,
        mock_update
    ):
        """Test condition step fails when no service_id available."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=60,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,  # No service_id
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "No service_id" in result.error_message

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_service_id_from_parameters(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step uses service_id from parameters."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (True, "Heartbeat received")

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=60,
            parameters={"service_id": 99},  # From parameters
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,  # No service_id on execution
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        # Verify check was called with service_id from parameters
        mock_check_heartbeat.assert_called_once()
        call_args = mock_check_heartbeat.call_args
        assert call_args[1]["service_id"] == 99

    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_creation_failure(self, mock_create):
        """Test condition step handles step result creation failure."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = None  # Simulate creation failure

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=60,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.FAILED
        assert "Failed to create step result" in result.error_message

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_polls_until_success(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step polls until condition is met."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        # Fail first two times, succeed third time
        mock_check_heartbeat.side_effect = [
            (False, "Waiting"),
            (False, "Still waiting"),
            (True, "Got it!"),
        ]

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=30,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        assert result.status == StepResultStatus.COMPLETED
        assert mock_check_heartbeat.call_count == 3
        assert mock_sleep.call_count == 2  # Slept twice

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_uses_custom_timeout(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step respects custom timeout."""
        from Medic.Core.playbook_engine import (
            DEFAULT_CONDITION_TIMEOUT,
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (True, "Got it!")

        custom_timeout = DEFAULT_CONDITION_TIMEOUT + 60
        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=custom_timeout,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step(step, execution)

        # Step should complete without timeout
        assert result.status == StepResultStatus.COMPLETED

    @patch('Medic.Core.playbook_engine.time.sleep')
    @patch('Medic.Core.playbook_engine.check_heartbeat_received')
    @patch('Medic.Core.playbook_engine.update_step_result')
    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_execute_condition_step_passes_parameters(
        self,
        mock_create,
        mock_update,
        mock_check_heartbeat,
        mock_sleep
    ):
        """Test condition step passes parameters to check function."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            execute_condition_step,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)
        mock_update.return_value = True
        mock_check_heartbeat.return_value = (True, "Success")

        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=60,
            parameters={"min_count": 5, "status": "UP"},
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        execute_condition_step(step, execution)

        # Verify parameters were passed
        call_args = mock_check_heartbeat.call_args
        assert call_args[1]["parameters"]["min_count"] == 5
        assert call_args[1]["parameters"]["status"] == "UP"


class TestEngineExecuteCondition:
    """Tests for engine _execute_condition method."""

    @patch('Medic.Core.playbook_engine.execute_condition_step')
    def test_engine_execute_condition_calls_step_function(
        self,
        mock_execute_condition
    ):
        """Test engine _execute_condition calls execute_condition_step."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
            StepResult,
            StepResultStatus,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_execute_condition.return_value = StepResult(
            result_id=1,
            execution_id=100,
            step_name="test",
            step_index=0,
            status=StepResultStatus.COMPLETED,
            started_at=now,
            completed_at=now,
        )

        engine = PlaybookExecutionEngine()
        step = ConditionStep(
            name="check-heartbeat",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
            timeout_seconds=60,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = engine._execute_condition(step, execution)

        mock_execute_condition.assert_called_once_with(step, execution)
        assert result.status == StepResultStatus.COMPLETED

    def test_engine_execute_condition_wrong_type_raises(self):
        """Test engine _execute_condition raises TypeError for wrong step type."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import WaitStep

        engine = PlaybookExecutionEngine()
        step = WaitStep(
            name="wait-step",
            duration_seconds=10,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        with pytest.raises(TypeError) as exc_info:
            engine._execute_condition(step, execution)

        assert "Expected ConditionStep" in str(exc_info.value)


class TestPendingApprovalCount:
    """Tests for pending approval count functions."""

    @patch("Medic.Core.playbook_engine.db.query_db")
    def test_get_pending_approval_count_returns_count(self, mock_query_db):
        """Test get_pending_approval_count returns correct count."""
        from Medic.Core.playbook_engine import get_pending_approval_count

        mock_query_db.return_value = json.dumps([{"count": 5}])

        count = get_pending_approval_count()

        assert count == 5
        mock_query_db.assert_called_once()

    @patch("Medic.Core.playbook_engine.db.query_db")
    def test_get_pending_approval_count_returns_zero_on_empty(
        self, mock_query_db
    ):
        """Test get_pending_approval_count returns 0 when no results."""
        from Medic.Core.playbook_engine import get_pending_approval_count

        mock_query_db.return_value = "[]"

        count = get_pending_approval_count()

        assert count == 0

    @patch("Medic.Core.playbook_engine.db.query_db")
    def test_get_pending_approval_count_returns_zero_on_error(
        self, mock_query_db
    ):
        """Test get_pending_approval_count returns 0 on parse error."""
        from Medic.Core.playbook_engine import get_pending_approval_count

        mock_query_db.return_value = "invalid json"

        count = get_pending_approval_count()

        assert count == 0

    @patch("Medic.Core.playbook_engine.update_pending_approval_count")
    @patch("Medic.Core.playbook_engine.get_pending_approval_count")
    def test_update_pending_approval_metric(
        self, mock_get_count, mock_update_count
    ):
        """Test _update_pending_approval_metric calls update function."""
        from Medic.Core.playbook_engine import _update_pending_approval_metric

        mock_get_count.return_value = 3

        _update_pending_approval_metric()

        mock_get_count.assert_called_once()
        mock_update_count.assert_called_once_with(3)


class TestPlaybookExecutionMetrics:
    """Tests for playbook execution metrics recording."""

    @patch("Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE", False)
    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.record_playbook_execution_duration")
    @patch("Medic.Core.playbook_engine.record_playbook_execution")
    @patch("Medic.Core.playbook_engine.update_execution_status")
    def test_complete_execution_records_metrics(
        self,
        mock_update_status,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test _complete_execution records execution metrics."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import Playbook

        now = datetime.now(pytz.timezone('America/Chicago'))
        playbook = Playbook(
            name="test-playbook",
            description="test description",
            steps=[],
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
            started_at=now - timedelta(seconds=10),
            playbook=playbook,
        )

        engine = PlaybookExecutionEngine()
        engine._complete_execution(execution)

        # Verify metrics were recorded
        mock_record_exec.assert_called_once_with("test-playbook", "completed")
        mock_record_duration.assert_called_once()
        # Duration should be approximately 10 seconds
        call_args = mock_record_duration.call_args
        assert call_args[0][0] == "test-playbook"
        assert call_args[0][1] >= 10
        mock_update_pending.assert_called_once()

    @patch("Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE", False)
    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.record_playbook_execution_duration")
    @patch("Medic.Core.playbook_engine.record_playbook_execution")
    @patch("Medic.Core.playbook_engine.update_execution_status")
    def test_fail_execution_records_metrics(
        self,
        mock_update_status,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test _fail_execution records execution metrics."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import Playbook

        now = datetime.now(pytz.timezone('America/Chicago'))
        playbook = Playbook(
            name="failing-playbook",
            description="test description",
            steps=[],
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
            started_at=now - timedelta(seconds=5),
            playbook=playbook,
        )

        engine = PlaybookExecutionEngine()
        engine._fail_execution(execution, "Test error message")

        # Verify metrics were recorded
        mock_record_exec.assert_called_once_with("failing-playbook", "failed")
        mock_record_duration.assert_called_once()
        call_args = mock_record_duration.call_args
        assert call_args[0][0] == "failing-playbook"
        mock_update_pending.assert_called_once()

    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.record_playbook_execution_duration")
    @patch("Medic.Core.playbook_engine.record_playbook_execution")
    @patch("Medic.Core.playbook_engine.get_playbook_by_id")
    @patch("Medic.Core.playbook_engine.update_execution_status")
    @patch("Medic.Core.playbook_engine.get_execution")
    def test_cancel_execution_records_metrics(
        self,
        mock_get_exec,
        mock_update_status,
        mock_get_playbook,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test cancel_execution records execution metrics."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import Playbook

        now = datetime.now(pytz.timezone('America/Chicago'))
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
            started_at=now - timedelta(seconds=15),
        )
        playbook = Playbook(
            name="cancelled-playbook",
            description="test description",
            steps=[],
        )

        mock_get_exec.return_value = execution
        mock_update_status.return_value = True
        mock_get_playbook.return_value = playbook

        engine = PlaybookExecutionEngine()
        result = engine.cancel_execution(100)

        assert result is True
        mock_record_exec.assert_called_once_with(
            "cancelled-playbook", "cancelled"
        )
        mock_record_duration.assert_called_once()
        mock_update_pending.assert_called_once()

    @patch("Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE", False)
    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.record_playbook_execution_duration")
    @patch("Medic.Core.playbook_engine.record_playbook_execution")
    @patch("Medic.Core.playbook_engine.update_execution_status")
    def test_complete_execution_no_start_time_skips_duration(
        self,
        mock_update_status,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test _complete_execution skips duration when no start time."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import Playbook

        playbook = Playbook(
            name="no-start-playbook",
            description="test description",
            steps=[],
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
            started_at=None,  # No start time
            playbook=playbook,
        )

        engine = PlaybookExecutionEngine()
        engine._complete_execution(execution)

        mock_record_exec.assert_called_once_with(
            "no-start-playbook", "completed"
        )
        mock_record_duration.assert_not_called()

    @patch("Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE", False)
    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.record_playbook_execution_duration")
    @patch("Medic.Core.playbook_engine.record_playbook_execution")
    @patch("Medic.Core.playbook_engine.update_execution_status")
    def test_complete_execution_unknown_playbook_name(
        self,
        mock_update_status,
        mock_record_exec,
        mock_record_duration,
        mock_update_pending
    ):
        """Test _complete_execution uses 'unknown' when no playbook."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
            started_at=now,
            playbook=None,  # No playbook loaded
        )

        engine = PlaybookExecutionEngine()
        engine._complete_execution(execution)

        mock_record_exec.assert_called_once_with("unknown", "completed")

    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.update_execution_status")
    @patch("Medic.Core.playbook_engine.get_execution")
    def test_approve_execution_updates_pending_metric(
        self,
        mock_get_exec,
        mock_update_status,
        mock_update_pending
    ):
        """Test approve_execution updates pending approval metric."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )

        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.PENDING_APPROVAL,
            current_step=0,
        )

        mock_get_exec.return_value = execution
        mock_update_status.return_value = True

        engine = PlaybookExecutionEngine()

        # Mock resume_execution to prevent full execution
        with patch.object(engine, 'resume_execution'):
            result = engine.approve_execution(100)

        assert result is True
        mock_update_pending.assert_called_once()

    @patch("Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE", False)
    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.create_execution")
    @patch("Medic.Core.playbook_engine.get_playbook_by_id")
    def test_start_execution_pending_updates_metric(
        self,
        mock_get_playbook,
        mock_create_execution,
        mock_update_pending
    ):
        """Test start_execution updates pending metric for pending_approval."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import ApprovalMode, Playbook

        playbook = Playbook(
            name="approval-required-playbook",
            description="test description",
            steps=[],
            approval=ApprovalMode.REQUIRED,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.PENDING_APPROVAL,
            current_step=0,
        )

        mock_get_playbook.return_value = playbook
        mock_create_execution.return_value = execution

        engine = PlaybookExecutionEngine()
        result = engine.start_execution(playbook_id=10, service_id=42)

        assert result is not None
        mock_update_pending.assert_called_once()

    @patch("Medic.Core.playbook_engine.AUDIT_LOG_AVAILABLE", False)
    @patch("Medic.Core.playbook_engine._update_pending_approval_metric")
    @patch("Medic.Core.playbook_engine.create_execution")
    @patch("Medic.Core.playbook_engine.get_playbook_by_id")
    def test_start_execution_running_no_pending_update(
        self,
        mock_get_playbook,
        mock_create_execution,
        mock_update_pending
    ):
        """Test start_execution doesn't update pending for immediate run."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            PlaybookExecutionEngine,
        )
        from Medic.Core.playbook_parser import ApprovalMode, Playbook

        playbook = Playbook(
            name="no-approval-playbook",
            description="test description",
            steps=[],
            approval=ApprovalMode.NONE,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=42,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        mock_get_playbook.return_value = playbook
        mock_create_execution.return_value = execution

        engine = PlaybookExecutionEngine()

        # Mock _execute_steps to prevent full execution
        with patch.object(engine, '_execute_steps'):
            result = engine.start_execution(playbook_id=10, service_id=42)

        assert result is not None
        # Pending approval metric should NOT be called for running status
        mock_update_pending.assert_not_called()
