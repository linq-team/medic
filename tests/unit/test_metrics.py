"""Unit tests for metrics module with OTEL semantic conventions."""
import os
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask


class TestGetConfig:
    """Tests for _get_config function."""

    def test_returns_default_values_when_no_env_vars(self):
        """Should return default configuration when no env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            from Medic.Core.metrics import _get_config

            config = _get_config()

            assert config["service_name"] == "medic"
            assert config["environment"] == "development"
            assert config["version"] == "unknown"

    def test_returns_custom_service_name_from_env(self):
        """Should use OTEL_SERVICE_NAME from environment."""
        with patch.dict(os.environ, {"OTEL_SERVICE_NAME": "custom-service"}):
            from Medic.Core.metrics import _get_config

            config = _get_config()
            assert config["service_name"] == "custom-service"

    def test_returns_custom_environment_from_env(self):
        """Should use MEDIC_ENVIRONMENT from environment."""
        with patch.dict(os.environ, {"MEDIC_ENVIRONMENT": "production"}):
            from Medic.Core.metrics import _get_config

            config = _get_config()
            assert config["environment"] == "production"

    def test_returns_custom_version_from_env(self):
        """Should use MEDIC_VERSION from environment."""
        with patch.dict(os.environ, {"MEDIC_VERSION": "1.2.3"}):
            from Medic.Core.metrics import _get_config

            config = _get_config()
            assert config["version"] == "1.2.3"


class TestBuildExemplar:
    """Tests for _build_exemplar function."""

    def test_returns_exemplar_dict_with_trace_id(self):
        """Should return dict with trace_id when provided."""
        from Medic.Core.metrics import _build_exemplar

        result = _build_exemplar("abc123def456")

        assert result == {"trace_id": "abc123def456"}

    def test_returns_none_when_trace_id_is_none(self):
        """Should return None when trace_id is None."""
        from Medic.Core.metrics import _build_exemplar

        result = _build_exemplar(None)

        assert result is None

    def test_returns_none_when_trace_id_is_empty_string(self):
        """Should return None when trace_id is empty string."""
        from Medic.Core.metrics import _build_exemplar

        result = _build_exemplar("")

        assert result is None


class TestRecordRequestDurationWithExemplar:
    """Tests for record_request_duration_with_exemplar function."""

    @patch("Medic.Core.metrics.REQUEST_LATENCY")
    def test_records_duration_with_exemplar(self, mock_histogram):
        """Should record duration with trace_id exemplar."""
        from Medic.Core.metrics import record_request_duration_with_exemplar

        mock_labels = MagicMock()
        mock_histogram.labels.return_value = mock_labels

        record_request_duration_with_exemplar(
            method="GET",
            endpoint="/api/v1/health",
            duration=0.123,
            trace_id="trace123"
        )

        mock_histogram.labels.assert_called_once()
        mock_labels.observe.assert_called_once_with(
            0.123, exemplar={"trace_id": "trace123"}
        )

    @patch("Medic.Core.metrics.REQUEST_LATENCY")
    def test_records_duration_without_exemplar(self, mock_histogram):
        """Should record duration with None exemplar when no trace_id."""
        from Medic.Core.metrics import record_request_duration_with_exemplar

        mock_labels = MagicMock()
        mock_histogram.labels.return_value = mock_labels

        record_request_duration_with_exemplar(
            method="POST",
            endpoint="/api/v1/services",
            duration=0.456,
            trace_id=None
        )

        mock_labels.observe.assert_called_once_with(0.456, exemplar=None)


class TestRecordPlaybookExecutionDurationWithExemplar:
    """Tests for record_playbook_execution_duration_with_exemplar."""

    @patch("Medic.Core.metrics.PLAYBOOK_EXECUTION_DURATION")
    def test_records_duration_with_exemplar(self, mock_histogram):
        """Should record playbook duration with trace_id exemplar."""
        from Medic.Core.metrics import (
            record_playbook_execution_duration_with_exemplar,
        )

        mock_labels = MagicMock()
        mock_histogram.labels.return_value = mock_labels

        record_playbook_execution_duration_with_exemplar(
            playbook_name="restart-service",
            duration_seconds=45.5,
            trace_id="playbook-trace-123"
        )

        mock_histogram.labels.assert_called_once()
        mock_labels.observe.assert_called_once_with(
            45.5, exemplar={"trace_id": "playbook-trace-123"}
        )

    @patch("Medic.Core.metrics.PLAYBOOK_EXECUTION_DURATION")
    def test_records_duration_without_exemplar(self, mock_histogram):
        """Should record duration with None exemplar when no trace_id."""
        from Medic.Core.metrics import (
            record_playbook_execution_duration_with_exemplar,
        )

        mock_labels = MagicMock()
        mock_histogram.labels.return_value = mock_labels

        record_playbook_execution_duration_with_exemplar(
            playbook_name="scale-up",
            duration_seconds=120.0,
            trace_id=None
        )

        mock_labels.observe.assert_called_once_with(120.0, exemplar=None)


class TestRecordDbQueryDurationWithExemplar:
    """Tests for record_db_query_duration_with_exemplar."""

    @patch("Medic.Core.metrics.DB_QUERY_DURATION")
    def test_records_duration_with_exemplar(self, mock_histogram):
        """Should record query duration with trace_id exemplar."""
        from Medic.Core.metrics import record_db_query_duration_with_exemplar

        mock_labels = MagicMock()
        mock_histogram.labels.return_value = mock_labels

        record_db_query_duration_with_exemplar(
            operation="select",
            duration=0.025,
            trace_id="db-trace-456"
        )

        mock_histogram.labels.assert_called_once()
        mock_labels.observe.assert_called_once_with(
            0.025, exemplar={"trace_id": "db-trace-456"}
        )


class TestTrackRequestMetrics:
    """Tests for track_request_metrics decorator."""

    def test_increments_counter_on_success(self):
        """Should increment request counter on successful response."""
        from Medic.Core.metrics import track_request_metrics, REQUEST_COUNT

        app = Flask(__name__)

        @track_request_metrics
        def test_endpoint():
            return {"success": True}, 200

        with app.test_request_context("/test", method="GET"):
            with patch.object(
                REQUEST_COUNT, "labels", return_value=MagicMock()
            ) as mock_labels:
                app.preprocess_request()
                result = test_endpoint()

                assert result == ({"success": True}, 200)
                mock_labels.assert_called()

    def test_increments_counter_on_exception(self):
        """Should increment counter with 500 status on exception."""
        from Medic.Core.metrics import track_request_metrics, REQUEST_COUNT

        app = Flask(__name__)

        @track_request_metrics
        def test_endpoint():
            raise ValueError("Test error")

        with app.test_request_context("/test", method="POST"):
            with patch.object(
                REQUEST_COUNT, "labels", return_value=MagicMock()
            ) as mock_labels:
                app.preprocess_request()
                with pytest.raises(ValueError):
                    test_endpoint()

                # Should be called with 500 status
                call_args = mock_labels.call_args
                assert call_args is not None

    def test_records_latency_with_trace_id_from_flask_g(self):
        """Should record latency with trace_id from Flask g context."""
        from Medic.Core.metrics import track_request_metrics

        app = Flask(__name__)

        @track_request_metrics
        def test_endpoint():
            return {"success": True}, 200

        with app.test_request_context("/test", method="GET"):
            with patch(
                "Medic.Core.metrics.record_request_duration_with_exemplar"
            ) as mock_record:
                from flask import g
                g.trace_id = "test-trace-abc"

                app.preprocess_request()
                test_endpoint()

                mock_record.assert_called_once()
                call_kwargs = mock_record.call_args[1]
                assert call_kwargs["trace_id"] == "test-trace-abc"


class TestTrackDbQuery:
    """Tests for track_db_query decorator."""

    def test_records_query_duration(self):
        """Should record database query duration."""
        from Medic.Core.metrics import track_db_query

        app = Flask(__name__)

        @track_db_query("select")
        def query_function():
            return [{"id": 1}]

        with app.test_request_context("/test"):
            with patch(
                "Medic.Core.metrics.record_db_query_duration_with_exemplar"
            ) as mock_record:
                result = query_function()

                assert result == [{"id": 1}]
                mock_record.assert_called_once()
                call_kwargs = mock_record.call_args[1]
                assert call_kwargs["operation"] == "select"

    def test_records_trace_id_from_flask_g(self):
        """Should include trace_id from Flask g in exemplar."""
        from Medic.Core.metrics import track_db_query

        app = Flask(__name__)

        @track_db_query("insert")
        def insert_function():
            return 1

        with app.test_request_context("/test"):
            with patch(
                "Medic.Core.metrics.record_db_query_duration_with_exemplar"
            ) as mock_record:
                from flask import g
                g.trace_id = "db-query-trace"

                insert_function()

                call_kwargs = mock_record.call_args[1]
                assert call_kwargs["trace_id"] == "db-query-trace"

    def test_handles_no_request_context(self):
        """Should handle being called outside request context."""
        from Medic.Core.metrics import track_db_query

        @track_db_query("delete")
        def delete_function():
            return True

        with patch(
            "Medic.Core.metrics.record_db_query_duration_with_exemplar"
        ) as mock_record:
            result = delete_function()

            assert result is True
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["trace_id"] is None


class TestGetMetrics:
    """Tests for get_metrics function."""

    def test_returns_openmetrics_by_default(self):
        """Should return OpenMetrics format by default."""
        with patch(
            "Medic.Core.metrics.generate_openmetrics_latest"
        ) as mock_openmetrics:
            mock_openmetrics.return_value = b"# TYPE test gauge\ntest 1\n# EOF"
            from Medic.Core.metrics import get_metrics

            result = get_metrics()

            mock_openmetrics.assert_called_once()
            assert isinstance(result, bytes)

    def test_returns_prometheus_format_when_specified(self):
        """Should return Prometheus format when openmetrics=False."""
        with patch("Medic.Core.metrics.generate_latest") as mock_prometheus:
            mock_prometheus.return_value = b"# TYPE test gauge\ntest 1\n"
            from Medic.Core.metrics import get_metrics

            result = get_metrics(openmetrics=False)

            mock_prometheus.assert_called_once()
            assert isinstance(result, bytes)


class TestGetMetricsContentType:
    """Tests for get_metrics_content_type function."""

    def test_returns_openmetrics_content_type_by_default(self):
        """Should return OpenMetrics content type by default."""
        from Medic.Core.metrics import (
            get_metrics_content_type,
            OPENMETRICS_CONTENT_TYPE,
        )

        result = get_metrics_content_type()

        assert result == OPENMETRICS_CONTENT_TYPE

    def test_returns_prometheus_content_type_when_specified(self):
        """Should return Prometheus content type when openmetrics=False."""
        from Medic.Core.metrics import (
            get_metrics_content_type,
            CONTENT_TYPE_LATEST,
        )

        result = get_metrics_content_type(openmetrics=False)

        assert result == CONTENT_TYPE_LATEST


class TestRefreshConfig:
    """Tests for refresh_config function."""

    @patch("Medic.Core.metrics.MEDIC_BUILD_INFO")
    @patch("Medic.Core.metrics._get_python_version")
    def test_updates_config_from_env(self, mock_python_version, mock_info_gauge):
        """Should update config from environment variables."""
        mock_python_version.return_value = "3.14.3"
        mock_labels = MagicMock()
        mock_info_gauge.labels.return_value = mock_labels

        with patch.dict(os.environ, {
            "OTEL_SERVICE_NAME": "new-service",
            "MEDIC_ENVIRONMENT": "staging",
            "MEDIC_VERSION": "2.0.0",
        }):
            from Medic.Core.metrics import refresh_config

            refresh_config()

            mock_info_gauge.labels.assert_called_with(
                service_name="new-service",
                service_version="2.0.0",
                deployment_environment="staging",
                python_version="3.14.3"
            )
            mock_labels.set.assert_called_with(1)


class TestMedicBuildInfoGauge:
    """Tests for medic_build_info gauge with resource attributes."""

    def test_medic_build_info_exists(self):
        """Should have medic_build_info gauge defined."""
        from Medic.Core.metrics import MEDIC_BUILD_INFO

        assert MEDIC_BUILD_INFO is not None

    def test_medic_build_info_has_expected_labels(self):
        """Should have expected OTEL resource attribute labels."""
        from Medic.Core.metrics import MEDIC_BUILD_INFO

        # Access the label names via the metric's internal structure
        label_names = MEDIC_BUILD_INFO._labelnames
        assert "service_name" in label_names
        assert "service_version" in label_names
        assert "deployment_environment" in label_names
        assert "python_version" in label_names


class TestOtelMetricNaming:
    """Tests for OTEL semantic metric naming conventions."""

    def test_request_count_uses_otel_naming(self):
        """REQUEST_COUNT should use OTEL http.server naming."""
        from Medic.Core.metrics import REQUEST_COUNT

        # The metric name should follow OTEL conventions
        # Counter _name doesn't include _total suffix (added at export)
        assert REQUEST_COUNT._name == "medic_http_server_request"

    def test_request_latency_uses_otel_naming(self):
        """REQUEST_LATENCY should use OTEL http.server naming."""
        from Medic.Core.metrics import REQUEST_LATENCY

        expected = "medic_http_server_request_duration_seconds"
        assert REQUEST_LATENCY._name == expected

    def test_db_query_duration_uses_otel_naming(self):
        """DB_QUERY_DURATION should use OTEL db.client naming."""
        from Medic.Core.metrics import DB_QUERY_DURATION

        expected = "medic_db_client_operation_duration_seconds"
        assert DB_QUERY_DURATION._name == expected


class TestRecordHeartbeat:
    """Tests for record_heartbeat function."""

    @patch("Medic.Core.metrics.HEARTBEAT_COUNT")
    def test_records_heartbeat_with_labels(self, mock_counter):
        """Should record heartbeat with correct labels."""
        from Medic.Core.metrics import record_heartbeat

        mock_labels = MagicMock()
        mock_counter.labels.return_value = mock_labels

        record_heartbeat("my-service", "ok")

        mock_counter.labels.assert_called_once_with(
            heartbeat_name="my-service",
            status="ok"
        )
        mock_labels.inc.assert_called_once()


class TestRecordAlertCreated:
    """Tests for record_alert_created function."""

    @patch("Medic.Core.metrics.ALERT_ACTIVE")
    @patch("Medic.Core.metrics.ALERT_COUNT")
    def test_increments_counter_and_gauge(self, mock_counter, mock_gauge):
        """Should increment both counter and active gauge."""
        from Medic.Core.metrics import record_alert_created

        mock_counter_labels = MagicMock()
        mock_counter.labels.return_value = mock_counter_labels

        record_alert_created("P1", "platform")

        mock_counter.labels.assert_called_once_with(
            priority="P1", team="platform"
        )
        mock_counter_labels.inc.assert_called_once()
        mock_gauge.inc.assert_called_once()


class TestRecordAlertResolved:
    """Tests for record_alert_resolved function."""

    @patch("Medic.Core.metrics.ALERT_ACTIVE")
    @patch("Medic.Core.metrics.ALERT_RESOLVED")
    def test_increments_resolved_and_decrements_active(
        self, mock_resolved, mock_active
    ):
        """Should increment resolved counter and decrement active gauge."""
        from Medic.Core.metrics import record_alert_resolved

        record_alert_resolved()

        mock_resolved.inc.assert_called_once()
        mock_active.dec.assert_called_once()


class TestRecordPlaybookExecution:
    """Tests for record_playbook_execution function."""

    @patch("Medic.Core.metrics.PLAYBOOK_EXECUTIONS")
    def test_records_execution_with_labels(self, mock_counter):
        """Should record playbook execution with correct labels."""
        from Medic.Core.metrics import record_playbook_execution

        mock_labels = MagicMock()
        mock_counter.labels.return_value = mock_labels

        record_playbook_execution("restart-service", "completed")

        mock_counter.labels.assert_called_once()
        call_kwargs = mock_counter.labels.call_args[1]
        assert call_kwargs["playbook"] == "restart-service"
        assert call_kwargs["status"] == "completed"
        mock_labels.inc.assert_called_once()


class TestRecordPlaybookExecutionDuration:
    """Tests for record_playbook_execution_duration function."""

    @patch(
        "Medic.Core.metrics.record_playbook_execution_duration_with_exemplar"
    )
    def test_calls_exemplar_function_without_trace_id(self, mock_record):
        """Should call exemplar function with None trace_id."""
        from Medic.Core.metrics import record_playbook_execution_duration

        record_playbook_execution_duration("scale-up", 60.0)

        mock_record.assert_called_once_with(
            playbook_name="scale-up",
            duration_seconds=60.0,
            trace_id=None
        )


class TestRecordAuthFailure:
    """Tests for record_auth_failure function."""

    @patch("Medic.Core.metrics.AUTH_FAILURES")
    def test_records_auth_failure_with_reason(self, mock_counter):
        """Should record auth failure with reason label."""
        from Medic.Core.metrics import record_auth_failure

        mock_labels = MagicMock()
        mock_counter.labels.return_value = mock_labels

        record_auth_failure("invalid_key")

        mock_counter.labels.assert_called_once_with(reason="invalid_key")
        mock_labels.inc.assert_called_once()


class TestUpdateHealthStatus:
    """Tests for update_health_status function."""

    @patch("Medic.Core.metrics.HEALTH_STATUS")
    def test_sets_healthy_status(self, mock_gauge):
        """Should set gauge to 1 for healthy component."""
        from Medic.Core.metrics import update_health_status

        mock_labels = MagicMock()
        mock_gauge.labels.return_value = mock_labels

        update_health_status("database", True)

        mock_gauge.labels.assert_called_once_with(component="database")
        mock_labels.set.assert_called_once_with(1)

    @patch("Medic.Core.metrics.HEALTH_STATUS")
    def test_sets_unhealthy_status(self, mock_gauge):
        """Should set gauge to 0 for unhealthy component."""
        from Medic.Core.metrics import update_health_status

        mock_labels = MagicMock()
        mock_gauge.labels.return_value = mock_labels

        update_health_status("redis", False)

        mock_gauge.labels.assert_called_once_with(component="redis")
        mock_labels.set.assert_called_once_with(0)


class TestRecordCircuitBreakerTrip:
    """Tests for record_circuit_breaker_trip function."""

    @patch("Medic.Core.metrics.CIRCUIT_BREAKER_TRIPS")
    def test_records_trip_with_service_id(self, mock_counter):
        """Should record circuit breaker trip with service_id label."""
        from Medic.Core.metrics import record_circuit_breaker_trip

        mock_labels = MagicMock()
        mock_counter.labels.return_value = mock_labels

        record_circuit_breaker_trip(123)

        mock_counter.labels.assert_called_once_with(service_id="123")
        mock_labels.inc.assert_called_once()


class TestBackwardsCompatibility:
    """Tests for backwards compatibility aliases."""

    def test_old_request_count_alias_exists(self):
        """Should have alias for old metric name."""
        from Medic.Core.metrics import (
            medic_http_requests_total,
            REQUEST_COUNT,
        )

        assert medic_http_requests_total is REQUEST_COUNT

    def test_old_request_latency_alias_exists(self):
        """Should have alias for old metric name."""
        from Medic.Core.metrics import (
            medic_http_request_duration_seconds,
            REQUEST_LATENCY,
        )

        assert medic_http_request_duration_seconds is REQUEST_LATENCY
