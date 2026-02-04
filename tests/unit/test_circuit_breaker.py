"""Unit tests for circuit breaker module."""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytz

from Medic.Core.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerStatus,
    check_circuit_breaker,
    get_config,
    get_execution_count_in_window,
    get_execution_history_for_service,
    get_services_with_open_circuit,
    is_circuit_open,
    record_circuit_breaker_trip,
    reset_config,
    set_config,
    DEFAULT_MAX_EXECUTIONS,
    DEFAULT_WINDOW_SECONDS,
)


@pytest.fixture
def mock_now():
    """Create a fixed datetime for testing."""
    return datetime(2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago'))


@pytest.fixture(autouse=True)
def reset_circuit_breaker_config():
    """Reset config before and after each test."""
    reset_config()
    yield
    reset_config()


class TestCircuitBreakerConfig:
    """Tests for circuit breaker configuration."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = get_config()
        assert config.window_seconds == DEFAULT_WINDOW_SECONDS
        assert config.max_executions == DEFAULT_MAX_EXECUTIONS

    def test_set_custom_config(self):
        """Test setting custom configuration."""
        custom_config = CircuitBreakerConfig(
            window_seconds=1800,
            max_executions=10
        )
        set_config(custom_config)

        config = get_config()
        assert config.window_seconds == 1800
        assert config.max_executions == 10

    def test_reset_config(self):
        """Test resetting configuration to defaults."""
        set_config(CircuitBreakerConfig(window_seconds=100, max_executions=2))
        reset_config()

        config = get_config()
        assert config.window_seconds == DEFAULT_WINDOW_SECONDS
        assert config.max_executions == DEFAULT_MAX_EXECUTIONS


class TestGetExecutionCountInWindow:
    """Tests for get_execution_count_in_window function."""

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_returns_zero_when_no_executions(self, mock_now_fn, mock_query):
        """Test returns 0 when no executions exist."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = json.dumps([{"count": 0}])

        count = get_execution_count_in_window(123)
        assert count == 0

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_returns_correct_count(self, mock_now_fn, mock_query):
        """Test returns correct execution count."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = json.dumps([{"count": 3}])

        count = get_execution_count_in_window(123)
        assert count == 3

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_handles_empty_result(self, mock_now_fn, mock_query):
        """Test handles empty database result."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = '[]'

        count = get_execution_count_in_window(123)
        assert count == 0

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_handles_none_result(self, mock_now_fn, mock_query):
        """Test handles None database result."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = None

        count = get_execution_count_in_window(123)
        assert count == 0

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_uses_custom_window(self, mock_now_fn, mock_query):
        """Test uses custom window when provided."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = json.dumps([{"count": 2}])

        count = get_execution_count_in_window(123, window_seconds=1800)
        assert count == 2

        # Verify the query was called with correct window start time
        call_args = mock_query.call_args
        assert call_args is not None
        params = call_args[0][1]
        expected_start = datetime(
            2026, 2, 3, 11, 30, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        # Params tuple: (service_id, window_start)
        assert params[0] == 123

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_handles_invalid_json(self, mock_now_fn, mock_query):
        """Test handles invalid JSON gracefully."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = "not valid json"

        count = get_execution_count_in_window(123)
        assert count == 0


class TestIsCircuitOpen:
    """Tests for is_circuit_open function."""

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_circuit_closed_when_under_threshold(self, mock_count):
        """Test circuit is closed when count is under threshold."""
        mock_count.return_value = 3
        assert is_circuit_open(123) is False

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_circuit_open_when_at_threshold(self, mock_count):
        """Test circuit is open when count equals threshold."""
        mock_count.return_value = DEFAULT_MAX_EXECUTIONS
        assert is_circuit_open(123) is True

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_circuit_open_when_over_threshold(self, mock_count):
        """Test circuit is open when count exceeds threshold."""
        mock_count.return_value = DEFAULT_MAX_EXECUTIONS + 2
        assert is_circuit_open(123) is True

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_uses_custom_config(self, mock_count):
        """Test uses custom config when provided."""
        mock_count.return_value = 3
        custom_config = CircuitBreakerConfig(
            window_seconds=1800,
            max_executions=3
        )

        # At threshold with custom config
        assert is_circuit_open(123, config=custom_config) is True

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_zero_executions_means_closed(self, mock_count):
        """Test circuit is closed with zero executions."""
        mock_count.return_value = 0
        assert is_circuit_open(123) is False


class TestCheckCircuitBreaker:
    """Tests for check_circuit_breaker function."""

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    @patch('Medic.Core.circuit_breaker._now')
    def test_returns_closed_status(self, mock_now_fn, mock_count):
        """Test returns closed status when under threshold."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_count.return_value = 2

        status = check_circuit_breaker(123)

        assert status.service_id == 123
        assert status.is_open is False
        assert status.execution_count == 2
        assert status.threshold == DEFAULT_MAX_EXECUTIONS
        assert "Circuit closed" in status.message
        assert "3 more allowed" in status.message

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    @patch('Medic.Core.circuit_breaker._now')
    def test_returns_open_status(self, mock_now_fn, mock_count):
        """Test returns open status when at/over threshold."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_count.return_value = 5

        status = check_circuit_breaker(123)

        assert status.service_id == 123
        assert status.is_open is True
        assert status.execution_count == 5
        assert "Circuit breaker tripped" in status.message
        assert "blocked until window expires" in status.message

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    @patch('Medic.Core.circuit_breaker._now')
    def test_status_to_dict(self, mock_now_fn, mock_count):
        """Test status can be converted to dict."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_count.return_value = 3

        status = check_circuit_breaker(456)
        result = status.to_dict()

        assert result['service_id'] == 456
        assert result['is_open'] is False
        assert result['execution_count'] == 3
        assert result['threshold'] == DEFAULT_MAX_EXECUTIONS
        assert 'window_start' in result
        assert 'window_end' in result
        assert 'message' in result

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    @patch('Medic.Core.circuit_breaker._now')
    def test_uses_custom_config(self, mock_now_fn, mock_count):
        """Test uses custom config when provided."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_count.return_value = 8

        custom_config = CircuitBreakerConfig(
            window_seconds=7200,
            max_executions=10
        )

        status = check_circuit_breaker(789, config=custom_config)

        assert status.is_open is False
        assert status.threshold == 10
        assert "2 more allowed" in status.message


class TestRecordCircuitBreakerTrip:
    """Tests for record_circuit_breaker_trip function."""

    @patch('Medic.Core.circuit_breaker.logger')
    def test_logs_trip_with_playbook_name(self, mock_logger):
        """Test logs trip event with playbook name."""
        record_circuit_breaker_trip(
            service_id=123,
            execution_count=5,
            playbook_name="restart-service"
        )

        mock_logger.log.assert_called()
        call_args = mock_logger.log.call_args
        assert call_args[1]['level'] == 40
        assert 'restart-service' in call_args[1]['msg']
        assert '123' in call_args[1]['msg']

    @patch('Medic.Core.circuit_breaker.logger')
    def test_logs_trip_without_playbook_name(self, mock_logger):
        """Test logs trip event without playbook name."""
        record_circuit_breaker_trip(
            service_id=456,
            execution_count=7
        )

        mock_logger.log.assert_called()
        call_args = mock_logger.log.call_args
        assert call_args[1]['level'] == 40
        assert '456' in call_args[1]['msg']

    @patch('Medic.Core.metrics.record_circuit_breaker_trip')
    @patch('Medic.Core.circuit_breaker.logger')
    def test_records_metric(self, mock_logger, mock_metric):
        """Test records metric when available."""
        record_circuit_breaker_trip(
            service_id=123,
            execution_count=5
        )

        mock_metric.assert_called_once_with(123)


class TestGetServicesWithOpenCircuit:
    """Tests for get_services_with_open_circuit function."""

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_returns_empty_when_none_open(self, mock_now_fn, mock_query):
        """Test returns empty list when no circuits are open."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = '[]'

        result = get_services_with_open_circuit()
        assert result == []

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_returns_services_with_open_circuits(self, mock_now_fn, mock_query):
        """Test returns services that have open circuits."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = json.dumps([
            {"service_id": 123, "count": 5},
            {"service_id": 456, "count": 7},
        ])

        result = get_services_with_open_circuit()

        assert len(result) == 2
        assert result[0].service_id == 123
        assert result[0].is_open is True
        assert result[0].execution_count == 5
        assert result[1].service_id == 456
        assert result[1].execution_count == 7

    @patch('Medic.Core.circuit_breaker.db.query_db')
    @patch('Medic.Core.circuit_breaker._now')
    def test_handles_none_service_id(self, mock_now_fn, mock_query):
        """Test filters out entries with None service_id."""
        mock_now_fn.return_value = datetime(
            2026, 2, 3, 12, 0, 0, tzinfo=pytz.timezone('America/Chicago')
        )
        mock_query.return_value = json.dumps([
            {"service_id": 123, "count": 5},
            {"service_id": None, "count": 3},
        ])

        result = get_services_with_open_circuit()

        assert len(result) == 1
        assert result[0].service_id == 123


class TestGetExecutionHistoryForService:
    """Tests for get_execution_history_for_service function."""

    @patch('Medic.Core.circuit_breaker.db.query_db')
    def test_returns_execution_history(self, mock_query):
        """Test returns execution history for service."""
        mock_query.return_value = json.dumps([
            {
                "execution_id": 1,
                "playbook_id": 10,
                "status": "completed",
                "created_at": "2026-02-03T11:00:00",
                "playbook_name": "restart-service"
            },
            {
                "execution_id": 2,
                "playbook_id": 10,
                "status": "failed",
                "created_at": "2026-02-03T11:30:00",
                "playbook_name": "restart-service"
            },
        ])

        result = get_execution_history_for_service(123)

        assert len(result) == 2
        assert result[0]['execution_id'] == 1
        assert result[0]['playbook_name'] == 'restart-service'
        assert result[1]['status'] == 'failed'

    @patch('Medic.Core.circuit_breaker.db.query_db')
    def test_returns_empty_when_no_history(self, mock_query):
        """Test returns empty list when no history exists."""
        mock_query.return_value = '[]'

        result = get_execution_history_for_service(123)
        assert result == []

    @patch('Medic.Core.circuit_breaker.db.query_db')
    def test_respects_limit_parameter(self, mock_query):
        """Test respects limit parameter."""
        mock_query.return_value = '[]'

        get_execution_history_for_service(123, limit=5)

        call_args = mock_query.call_args
        params = call_args[0][1]
        assert params[1] == 5


class TestIntegration:
    """Integration-style tests for circuit breaker behavior."""

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_circuit_breaker_flow_normal(self, mock_count):
        """Test normal flow with circuit staying closed."""
        # Start with 0 executions
        mock_count.return_value = 0
        assert is_circuit_open(123) is False

        # Add executions, still under threshold
        mock_count.return_value = 3
        status = check_circuit_breaker(123)
        assert status.is_open is False
        assert status.execution_count == 3

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_circuit_breaker_flow_trip(self, mock_count):
        """Test flow when circuit trips."""
        # Under threshold
        mock_count.return_value = 4
        assert is_circuit_open(123) is False

        # At threshold - circuit opens
        mock_count.return_value = 5
        assert is_circuit_open(123) is True

        # Check detailed status
        status = check_circuit_breaker(123)
        assert status.is_open is True
        assert "blocked" in status.message.lower()

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_different_services_independent(self, mock_count):
        """Test different services have independent circuit breakers."""
        # Service A has 5 executions (at threshold)
        # Service B has 2 executions (under threshold)
        def count_by_service(service_id, window_seconds=None):
            if service_id == 100:
                return 5
            elif service_id == 200:
                return 2
            return 0

        mock_count.side_effect = count_by_service

        assert is_circuit_open(100) is True
        assert is_circuit_open(200) is False

    @patch('Medic.Core.circuit_breaker.get_execution_count_in_window')
    def test_custom_thresholds(self, mock_count):
        """Test circuit breaker with custom thresholds."""
        mock_count.return_value = 3

        # Default config (5 max) - should be closed
        assert is_circuit_open(123) is False

        # Stricter config (3 max) - should be open
        strict_config = CircuitBreakerConfig(
            window_seconds=3600,
            max_executions=3
        )
        assert is_circuit_open(123, config=strict_config) is True

        # Looser config (10 max) - should be closed
        loose_config = CircuitBreakerConfig(
            window_seconds=3600,
            max_executions=10
        )
        assert is_circuit_open(123, config=loose_config) is False
