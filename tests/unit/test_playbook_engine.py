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

    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.get_playbook_by_id')
    @patch('Medic.Core.playbook_engine.create_execution')
    def test_start_execution_with_approval(
        self,
        mock_create,
        mock_get_playbook,
        mock_update
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
        mock_update_exec
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

    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.get_execution')
    def test_approve_execution_success(self, mock_get, mock_update):
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

    @patch('Medic.Core.playbook_engine.update_execution_status')
    @patch('Medic.Core.playbook_engine.get_execution')
    def test_cancel_execution_success(self, mock_get, mock_update):
        """Test cancelling an execution."""
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
        mock_update.return_value = True

        engine = PlaybookExecutionEngine()
        result = engine.cancel_execution(1)

        assert result is True

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
        mock_update_exec
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


class TestPlaceholderSteps:
    """Tests for placeholder step executors."""

    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_webhook_step_placeholder(self, mock_create):
        """Test webhook step placeholder returns pending."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_webhook_step_placeholder,
        )
        from Medic.Core.playbook_parser import WebhookStep

        mock_create.return_value = MagicMock(result_id=1)

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

        result = execute_webhook_step_placeholder(step, execution)

        assert result.status == StepResultStatus.PENDING
        assert "not yet implemented" in result.output

    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_script_step_placeholder(self, mock_create):
        """Test script step placeholder returns pending."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_script_step_placeholder,
        )
        from Medic.Core.playbook_parser import ScriptStep

        mock_create.return_value = MagicMock(result_id=1)

        step = ScriptStep(
            name="test-script",
            script_name="restart-service",
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_script_step_placeholder(step, execution)

        assert result.status == StepResultStatus.PENDING
        assert "not yet implemented" in result.output

    @patch('Medic.Core.playbook_engine.create_step_result')
    def test_condition_step_placeholder(self, mock_create):
        """Test condition step placeholder returns pending."""
        from Medic.Core.playbook_engine import (
            ExecutionStatus,
            PlaybookExecution,
            StepResultStatus,
            execute_condition_step_placeholder,
        )
        from Medic.Core.playbook_parser import ConditionStep, ConditionType

        mock_create.return_value = MagicMock(result_id=1)

        step = ConditionStep(
            name="test-condition",
            condition_type=ConditionType.HEARTBEAT_RECEIVED,
        )
        execution = PlaybookExecution(
            execution_id=100,
            playbook_id=10,
            service_id=None,
            status=ExecutionStatus.RUNNING,
            current_step=0,
        )

        result = execute_condition_step_placeholder(step, execution)

        assert result.status == StepResultStatus.PENDING
        assert "not yet implemented" in result.output
