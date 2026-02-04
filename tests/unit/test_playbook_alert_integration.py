"""Unit tests for Medic.Core.playbook_alert_integration module."""
import pytest
from unittest.mock import MagicMock, patch

from Medic.Core.playbook_alert_integration import (
    PlaybookTriggerResult,
    get_alert_consecutive_failures,
    should_trigger_playbook,
    trigger_playbook_for_alert,
)
from Medic.Core.playbook_engine import (
    ApprovalMode,
    ExecutionStatus,
    PlaybookExecution,
)
from Medic.Core.playbook_parser import Playbook
from Medic.Core.playbook_triggers import MatchedPlaybook


class TestPlaybookTriggerResult:
    """Tests for PlaybookTriggerResult dataclass."""

    def test_to_dict_no_execution(self):
        """Test conversion to dict when no execution."""
        result = PlaybookTriggerResult(
            triggered=False,
            status="no_match",
            message="No playbook matched"
        )

        d = result.to_dict()
        assert d["triggered"] is False
        assert d["execution_id"] is None
        assert d["playbook_id"] is None
        assert d["playbook_name"] is None
        assert d["status"] == "no_match"
        assert d["message"] == "No playbook matched"

    def test_to_dict_with_execution(self):
        """Test conversion to dict with execution and playbook."""
        mock_execution = PlaybookExecution(
            execution_id=123,
            playbook_id=456,
            service_id=789,
            status=ExecutionStatus.RUNNING,
        )
        mock_playbook = MatchedPlaybook(
            playbook_id=456,
            playbook_name="restart-service",
            trigger_id=111,
            service_pattern="worker-*",
            consecutive_failures=3,
        )

        result = PlaybookTriggerResult(
            triggered=True,
            execution=mock_execution,
            playbook=mock_playbook,
            status="running",
            message="Playbook started"
        )

        d = result.to_dict()
        assert d["triggered"] is True
        assert d["execution_id"] == 123
        assert d["playbook_id"] == 456
        assert d["playbook_name"] == "restart-service"
        assert d["status"] == "running"


class TestGetAlertConsecutiveFailures:
    """Tests for get_alert_consecutive_failures function."""

    def test_returns_cycle_count(self):
        """Test returns alert cycle as consecutive failures."""
        assert get_alert_consecutive_failures(1) == 1
        assert get_alert_consecutive_failures(3) == 3
        assert get_alert_consecutive_failures(10) == 10

    def test_returns_minimum_1(self):
        """Test returns at least 1 even for zero or negative."""
        assert get_alert_consecutive_failures(0) == 1
        assert get_alert_consecutive_failures(-1) == 1


class TestShouldTriggerPlaybook:
    """Tests for should_trigger_playbook function."""

    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_returns_matched_playbook_when_found(self, mock_find):
        """Test returns MatchedPlaybook when trigger matches."""
        mock_matched = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=3,
        )
        mock_find.return_value = mock_matched

        result = should_trigger_playbook("worker-prod-01", 3)

        assert result == mock_matched
        mock_find.assert_called_once_with("worker-prod-01", 3)

    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_returns_none_when_no_match(self, mock_find):
        """Test returns None when no trigger matches."""
        mock_find.return_value = None

        result = should_trigger_playbook("unknown-service", 1)

        assert result is None
        mock_find.assert_called_once_with("unknown-service", 1)


class TestTriggerPlaybookForAlert:
    """Tests for trigger_playbook_for_alert function."""

    @pytest.fixture(autouse=True)
    def mock_circuit_breaker(self):
        """Mock circuit breaker to allow tests to run without DB."""
        from Medic.Core.circuit_breaker import CircuitBreakerStatus
        from datetime import datetime
        import pytz

        mock_status = CircuitBreakerStatus(
            service_id=0,
            is_open=False,
            execution_count=0,
            window_start=datetime.now(pytz.UTC),
            window_end=datetime.now(pytz.UTC),
            threshold=5,
            message="Circuit closed",
        )

        with patch(
            "Medic.Core.playbook_alert_integration.check_circuit_breaker",
            return_value=mock_status
        ):
            yield

    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_no_match_returns_not_triggered(self, mock_find):
        """Test returns not triggered when no playbook matches."""
        mock_find.return_value = None

        result = trigger_playbook_for_alert(
            service_id=123,
            service_name="worker-prod-01",
            consecutive_failures=1,
        )

        assert result.triggered is False
        assert result.status == "no_match"
        assert "No playbook trigger matched" in result.message

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_playbook_load_failure(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test returns error when playbook cannot be loaded."""
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=1,
        )
        mock_get_playbook.return_value = None

        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=1,
        )

        assert result.triggered is False
        assert result.status == "error"
        assert "Failed to load playbook" in result.message
        mock_start.assert_not_called()

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_approval_none_starts_immediately(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test playbook with approval=none starts immediately."""
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=1,
        )

        mock_playbook = MagicMock(spec=Playbook)
        mock_playbook.name = "restart-service"
        mock_playbook.approval = ApprovalMode.NONE
        mock_get_playbook.return_value = mock_playbook

        mock_execution = PlaybookExecution(
            execution_id=999,
            playbook_id=123,
            service_id=100,
            status=ExecutionStatus.RUNNING,
        )
        mock_start.return_value = mock_execution

        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=1,
        )

        assert result.triggered is True
        assert result.status == "running"
        assert result.execution == mock_execution
        assert "started immediately" in result.message

        # Verify skip_approval=True was passed
        mock_start.assert_called_once()
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs["skip_approval"] is True

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_approval_required_creates_pending(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test playbook with approval=required creates pending execution."""
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=1,
        )

        mock_playbook = MagicMock(spec=Playbook)
        mock_playbook.name = "restart-service"
        mock_playbook.approval = ApprovalMode.REQUIRED
        mock_get_playbook.return_value = mock_playbook

        mock_execution = PlaybookExecution(
            execution_id=999,
            playbook_id=123,
            service_id=100,
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        mock_start.return_value = mock_execution

        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=1,
        )

        assert result.triggered is True
        assert result.status == "pending_approval"
        assert result.execution == mock_execution
        assert "awaiting approval" in result.message

        # Verify skip_approval=False was passed
        mock_start.assert_called_once()
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs["skip_approval"] is False

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_approval_timeout_creates_pending_with_timeout(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test playbook with approval=timeout creates pending with timeout."""
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=1,
        )

        mock_playbook = MagicMock(spec=Playbook)
        mock_playbook.name = "restart-service"
        mock_playbook.approval = ApprovalMode.TIMEOUT
        mock_playbook.approval_timeout_minutes = 5
        mock_get_playbook.return_value = mock_playbook

        mock_execution = PlaybookExecution(
            execution_id=999,
            playbook_id=123,
            service_id=100,
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        mock_start.return_value = mock_execution

        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=1,
        )

        assert result.triggered is True
        assert result.status == "pending_approval"
        assert "auto-approve in 5m" in result.message

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_execution_failure(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test returns error when execution fails to start."""
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=1,
        )

        mock_playbook = MagicMock(spec=Playbook)
        mock_playbook.name = "restart-service"
        mock_playbook.approval = ApprovalMode.NONE
        mock_get_playbook.return_value = mock_playbook

        mock_start.return_value = None  # Execution failed

        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=1,
        )

        assert result.triggered is False
        assert result.status == "error"
        assert "Failed to create playbook execution" in result.message

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_context_passed_to_execution(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test context variables are passed to execution."""
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=3,
        )

        mock_playbook = MagicMock(spec=Playbook)
        mock_playbook.name = "restart-service"
        mock_playbook.approval = ApprovalMode.NONE
        mock_get_playbook.return_value = mock_playbook

        mock_execution = PlaybookExecution(
            execution_id=999,
            playbook_id=123,
            service_id=100,
            status=ExecutionStatus.RUNNING,
        )
        mock_start.return_value = mock_execution

        trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=3,
            alert_context={"ALERT_ID": 555}
        )

        # Verify context was passed
        mock_start.assert_called_once()
        call_kwargs = mock_start.call_args[1]
        context = call_kwargs["context"]
        assert context["SERVICE_ID"] == 100
        assert context["SERVICE_NAME"] == "worker-prod-01"
        assert context["CONSECUTIVE_FAILURES"] == 3
        assert context["TRIGGER_ID"] == 456
        assert context["ALERT_ID"] == 555

    @patch("Medic.Core.playbook_alert_integration.start_playbook_execution")
    @patch("Medic.Core.playbook_alert_integration.get_playbook_by_id")
    @patch("Medic.Core.playbook_alert_integration.find_playbook_for_alert")
    def test_trigger_with_higher_failure_threshold(
        self, mock_find, mock_get_playbook, mock_start
    ):
        """Test trigger only fires when failure count meets threshold."""
        # First call: 2 failures, trigger requires 3 - no match
        mock_find.return_value = None
        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=2,
        )
        assert result.triggered is False

        # Second call: 3 failures - matches
        mock_find.return_value = MatchedPlaybook(
            playbook_id=123,
            playbook_name="restart-service",
            trigger_id=456,
            service_pattern="worker-*",
            consecutive_failures=3,
        )
        mock_playbook = MagicMock(spec=Playbook)
        mock_playbook.name = "restart-service"
        mock_playbook.approval = ApprovalMode.NONE
        mock_get_playbook.return_value = mock_playbook
        mock_start.return_value = PlaybookExecution(
            execution_id=999,
            playbook_id=123,
            service_id=100,
            status=ExecutionStatus.RUNNING,
        )

        result = trigger_playbook_for_alert(
            service_id=100,
            service_name="worker-prod-01",
            consecutive_failures=3,
        )
        assert result.triggered is True

    def test_circuit_breaker_blocks_execution(self):
        """Test circuit breaker blocks execution when open."""
        from Medic.Core.circuit_breaker import CircuitBreakerStatus
        from datetime import datetime
        import pytz

        # Create an open circuit status
        open_status = CircuitBreakerStatus(
            service_id=100,
            is_open=True,
            execution_count=5,
            window_start=datetime.now(pytz.UTC),
            window_end=datetime.now(pytz.UTC),
            threshold=5,
            message="Circuit breaker tripped: 5 executions in window",
        )

        with patch(
            "Medic.Core.playbook_alert_integration.check_circuit_breaker",
            return_value=open_status
        ), patch(
            "Medic.Core.playbook_alert_integration.record_circuit_breaker_trip"
        ) as mock_record, patch(
            "Medic.Core.playbook_alert_integration.find_playbook_for_alert"
        ) as mock_find:
            result = trigger_playbook_for_alert(
                service_id=100,
                service_name="worker-prod-01",
                consecutive_failures=3,
            )

            assert result.triggered is False
            assert result.status == "circuit_breaker_open"
            assert "Circuit breaker tripped" in result.message

            # Verify trip was recorded
            mock_record.assert_called_once()

            # Verify playbook matching was never attempted
            mock_find.assert_not_called()


class TestMonitorIntegration:
    """Tests for monitor.py integration with playbook triggers.

    Note: These tests use fixtures that mock the slack_client and pagerduty_client
    modules to allow importing monitor.py in the test environment.
    """

    @pytest.fixture
    def mock_monitor_deps(self, monkeypatch):
        """Mock monitor.py dependencies before import."""
        import sys
        mock_slack = MagicMock()
        mock_pagerduty = MagicMock()
        sys.modules['slack_client'] = mock_slack
        sys.modules['pagerduty_client'] = mock_pagerduty
        yield mock_slack, mock_pagerduty
        # Cleanup
        if 'slack_client' in sys.modules:
            del sys.modules['slack_client']
        if 'pagerduty_client' in sys.modules:
            del sys.modules['pagerduty_client']
        if 'Medic.Worker.monitor' in sys.modules:
            del sys.modules['Medic.Worker.monitor']

    def test_check_playbook_triggers_calls_trigger(self, mock_monitor_deps):
        """Test _check_playbook_triggers calls trigger function."""
        mock_slack, _ = mock_monitor_deps

        with patch.dict(
            'sys.modules',
            {'slack_client': mock_slack, 'pagerduty_client': MagicMock()}
        ):
            # Now import monitor after mocking dependencies
            from Medic.Worker import monitor

            with patch.object(
                monitor, 'PLAYBOOK_TRIGGERS_AVAILABLE', True
            ), patch.object(
                monitor, 'trigger_playbook_for_alert'
            ) as mock_trigger, patch.object(
                monitor, 'get_alert_consecutive_failures', return_value=3
            ) as mock_get_failures:

                mock_trigger.return_value = PlaybookTriggerResult(
                    triggered=False,
                    status="no_match",
                    message="No match"
                )

                monitor._check_playbook_triggers(
                    service_id=100,
                    service_name="worker-prod-01",
                    alert_cycle=3
                )

                mock_get_failures.assert_called_once_with(3)
                mock_trigger.assert_called_once_with(
                    service_id=100,
                    service_name="worker-prod-01",
                    consecutive_failures=3,
                    alert_context={"ALERT_CYCLE": 3}
                )

    def test_check_playbook_triggers_sends_slack_running(self, mock_monitor_deps):
        """Test sends Slack message when playbook starts running."""
        mock_slack, _ = mock_monitor_deps

        with patch.dict(
            'sys.modules',
            {'slack_client': mock_slack, 'pagerduty_client': MagicMock()}
        ):
            from Medic.Worker import monitor

            mock_execution = MagicMock()
            mock_execution.execution_id = 999
            mock_playbook = MagicMock()
            mock_playbook.playbook_name = "restart-service"

            with patch.object(
                monitor, 'PLAYBOOK_TRIGGERS_AVAILABLE', True
            ), patch.object(
                monitor, 'trigger_playbook_for_alert'
            ) as mock_trigger, patch.object(
                monitor, 'get_alert_consecutive_failures', return_value=1
            ), patch.object(
                monitor, 'slack', mock_slack
            ):

                mock_trigger.return_value = PlaybookTriggerResult(
                    triggered=True,
                    execution=mock_execution,
                    playbook=mock_playbook,
                    status="running",
                    message="Started"
                )

                monitor._check_playbook_triggers(
                    service_id=100,
                    service_name="worker-prod-01",
                    alert_cycle=1
                )

                mock_slack.send_message.assert_called_once()
                call_args = mock_slack.send_message.call_args[0][0]
                assert ":robot_face:" in call_args
                assert "restart-service" in call_args
                assert "started" in call_args

    def test_check_playbook_triggers_sends_slack_pending(self, mock_monitor_deps):
        """Test sends Slack message when playbook awaiting approval."""
        mock_slack, _ = mock_monitor_deps

        with patch.dict(
            'sys.modules',
            {'slack_client': mock_slack, 'pagerduty_client': MagicMock()}
        ):
            from Medic.Worker import monitor

            mock_execution = MagicMock()
            mock_execution.execution_id = 999
            mock_playbook = MagicMock()
            mock_playbook.playbook_name = "restart-service"

            with patch.object(
                monitor, 'PLAYBOOK_TRIGGERS_AVAILABLE', True
            ), patch.object(
                monitor, 'trigger_playbook_for_alert'
            ) as mock_trigger, patch.object(
                monitor, 'get_alert_consecutive_failures', return_value=1
            ), patch.object(
                monitor, 'slack', mock_slack
            ):

                mock_trigger.return_value = PlaybookTriggerResult(
                    triggered=True,
                    execution=mock_execution,
                    playbook=mock_playbook,
                    status="pending_approval",
                    message="Awaiting approval"
                )

                monitor._check_playbook_triggers(
                    service_id=100,
                    service_name="worker-prod-01",
                    alert_cycle=1
                )

                mock_slack.send_message.assert_called_once()
                call_args = mock_slack.send_message.call_args[0][0]
                assert ":hourglass:" in call_args
                assert "awaiting approval" in call_args

    def test_check_playbook_triggers_disabled(self, mock_monitor_deps):
        """Test does nothing when playbook triggers disabled."""
        mock_slack, _ = mock_monitor_deps

        with patch.dict(
            'sys.modules',
            {'slack_client': mock_slack, 'pagerduty_client': MagicMock()}
        ):
            from Medic.Worker import monitor

            with patch.object(
                monitor, 'PLAYBOOK_TRIGGERS_AVAILABLE', False
            ), patch.object(
                monitor, 'slack', mock_slack
            ):

                monitor._check_playbook_triggers(
                    service_id=100,
                    service_name="worker-prod-01",
                    alert_cycle=1
                )

                # No slack message should be sent
                mock_slack.send_message.assert_not_called()

    def test_check_playbook_triggers_handles_exception(self, mock_monitor_deps):
        """Test handles exceptions gracefully."""
        mock_slack, _ = mock_monitor_deps

        with patch.dict(
            'sys.modules',
            {'slack_client': mock_slack, 'pagerduty_client': MagicMock()}
        ):
            from Medic.Worker import monitor

            with patch.object(
                monitor, 'PLAYBOOK_TRIGGERS_AVAILABLE', True
            ), patch.object(
                monitor, 'trigger_playbook_for_alert'
            ) as mock_trigger, patch.object(
                monitor, 'get_alert_consecutive_failures', return_value=1
            ), patch.object(
                monitor, 'logger'
            ) as mock_logger:

                mock_trigger.side_effect = Exception("Test error")

                # Should not raise
                monitor._check_playbook_triggers(
                    service_id=100,
                    service_name="worker-prod-01",
                    alert_cycle=1
                )

                # Should log error
                mock_logger.log.assert_called()
