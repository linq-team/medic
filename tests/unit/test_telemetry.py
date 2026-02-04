"""Unit tests for OpenTelemetry instrumentation module."""
import os
from unittest.mock import MagicMock, patch

from flask import Flask


class TestGetOtelConfig:
    """Tests for get_otel_config function."""

    def test_returns_default_values_when_no_env_vars(self):
        """Should return default configuration when no env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()

            assert config["endpoint"] == "http://alloy:4317"
            assert config["service_name"] == "medic"
            assert config["environment"] == "development"
            assert config["version"] == "unknown"
            assert config["resource_attributes"] == {}

    def test_returns_custom_endpoint_from_env(self):
        """Should use OTEL_EXPORTER_OTLP_ENDPOINT from environment."""
        with patch.dict(
            os.environ,
            {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://custom:4317"},
        ):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert config["endpoint"] == "http://custom:4317"

    def test_returns_custom_service_name_from_env(self):
        """Should use OTEL_SERVICE_NAME from environment."""
        with patch.dict(os.environ, {"OTEL_SERVICE_NAME": "custom-service"}):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert config["service_name"] == "custom-service"

    def test_returns_custom_environment_from_env(self):
        """Should use MEDIC_ENVIRONMENT from environment."""
        with patch.dict(os.environ, {"MEDIC_ENVIRONMENT": "production"}):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert config["environment"] == "production"

    def test_returns_custom_version_from_env(self):
        """Should use MEDIC_VERSION from environment."""
        with patch.dict(os.environ, {"MEDIC_VERSION": "1.2.3"}):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert config["version"] == "1.2.3"

    def test_parses_resource_attributes_from_env(self):
        """Should parse OTEL_RESOURCE_ATTRIBUTES as comma-separated key=value."""
        with patch.dict(
            os.environ,
            {"OTEL_RESOURCE_ATTRIBUTES": "key1=value1,key2=value2"},
        ):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert config["resource_attributes"]["key1"] == "value1"
            assert config["resource_attributes"]["key2"] == "value2"

    def test_handles_empty_resource_attributes(self):
        """Should handle empty OTEL_RESOURCE_ATTRIBUTES gracefully."""
        with patch.dict(os.environ, {"OTEL_RESOURCE_ATTRIBUTES": ""}):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert config["resource_attributes"] == {}

    def test_handles_malformed_resource_attributes(self):
        """Should skip malformed entries in OTEL_RESOURCE_ATTRIBUTES."""
        with patch.dict(
            os.environ,
            {"OTEL_RESOURCE_ATTRIBUTES": "key1=value1,malformed,key2=value2"},
        ):
            from Medic.Core.telemetry import get_otel_config

            config = get_otel_config()
            assert "key1" in config["resource_attributes"]
            assert "key2" in config["resource_attributes"]
            assert "malformed" not in config["resource_attributes"]


class TestCreateResource:
    """Tests for create_resource function."""

    def test_creates_resource_with_service_attributes(self):
        """Should create resource with service name, version, and environment."""
        from Medic.Core.telemetry import create_resource

        config = {
            "service_name": "test-service",
            "version": "1.0.0",
            "environment": "test",
            "resource_attributes": {},
        }

        resource = create_resource(config)

        # Resource attributes are accessible via _attributes
        attrs = dict(resource.attributes)
        assert attrs["service.name"] == "test-service"
        assert attrs["service.version"] == "1.0.0"
        assert attrs["deployment.environment"] == "test"

    def test_merges_additional_resource_attributes(self):
        """Should merge additional resource attributes from config."""
        from Medic.Core.telemetry import create_resource

        config = {
            "service_name": "test-service",
            "version": "1.0.0",
            "environment": "test",
            "resource_attributes": {"custom.attr": "custom-value"},
        }

        resource = create_resource(config)
        attrs = dict(resource.attributes)

        assert attrs["custom.attr"] == "custom-value"


class TestCreateTracerProvider:
    """Tests for create_tracer_provider function."""

    @patch(
        "Medic.Core.telemetry.OTLPSpanExporter"
    )
    @patch("Medic.Core.telemetry.BatchSpanProcessor")
    def test_creates_tracer_provider_with_exporter(
        self, mock_processor_class, mock_exporter_class
    ):
        """Should create TracerProvider with OTLP exporter."""
        from Medic.Core.telemetry import create_resource, create_tracer_provider

        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        config = {
            "service_name": "test",
            "version": "1.0.0",
            "environment": "test",
            "resource_attributes": {},
        }
        resource = create_resource(config)

        provider = create_tracer_provider(resource, "http://test:4317")

        mock_exporter_class.assert_called_once_with(
            endpoint="http://test:4317",
            insecure=True,
        )
        mock_processor_class.assert_called_once_with(mock_exporter)
        assert provider is not None


class TestStoreTraceContext:
    """Tests for store_trace_context function."""

    def test_stores_trace_id_and_span_id_in_flask_g(self):
        """Should store trace_id and span_id in Flask g context."""
        from Medic.Core.telemetry import store_trace_context

        app = Flask(__name__)

        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x12345678901234567890123456789012
        mock_span_context.span_id = 0x1234567890123456

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with app.app_context():
            with app.test_request_context():
                with patch(
                    "Medic.Core.telemetry.trace.get_current_span",
                    return_value=mock_span,
                ):
                    from flask import g

                    store_trace_context()

                    assert g.trace_id == "12345678901234567890123456789012"
                    assert g.span_id == "1234567890123456"

    def test_stores_none_when_no_current_span(self):
        """Should store None when there is no current span."""
        from Medic.Core.telemetry import store_trace_context

        app = Flask(__name__)

        with app.app_context():
            with app.test_request_context():
                with patch(
                    "Medic.Core.telemetry.trace.get_current_span",
                    return_value=None,
                ):
                    from flask import g

                    store_trace_context()

                    assert g.trace_id is None
                    assert g.span_id is None

    def test_stores_none_when_span_context_invalid(self):
        """Should store None when span context is invalid."""
        from Medic.Core.telemetry import store_trace_context

        app = Flask(__name__)

        mock_span_context = MagicMock()
        mock_span_context.is_valid = False

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with app.app_context():
            with app.test_request_context():
                with patch(
                    "Medic.Core.telemetry.trace.get_current_span",
                    return_value=mock_span,
                ):
                    from flask import g

                    store_trace_context()

                    assert g.trace_id is None
                    assert g.span_id is None


class TestGetCurrentTraceId:
    """Tests for get_current_trace_id function."""

    def test_returns_trace_id_from_flask_g(self):
        """Should return trace_id stored in Flask g context."""
        from Medic.Core.telemetry import get_current_trace_id

        app = Flask(__name__)

        with app.app_context():
            with app.test_request_context():
                from flask import g

                g.trace_id = "abc123"

                result = get_current_trace_id()
                assert result == "abc123"

    def test_returns_none_when_no_trace_id(self):
        """Should return None when trace_id is not in g context."""
        from Medic.Core.telemetry import get_current_trace_id

        app = Flask(__name__)

        with app.app_context():
            with app.test_request_context():
                result = get_current_trace_id()
                assert result is None


class TestGetCurrentSpanId:
    """Tests for get_current_span_id function."""

    def test_returns_span_id_from_flask_g(self):
        """Should return span_id stored in Flask g context."""
        from Medic.Core.telemetry import get_current_span_id

        app = Flask(__name__)

        with app.app_context():
            with app.test_request_context():
                from flask import g

                g.span_id = "span123"

                result = get_current_span_id()
                assert result == "span123"

    def test_returns_none_when_no_span_id(self):
        """Should return None when span_id is not in g context."""
        from Medic.Core.telemetry import get_current_span_id

        app = Flask(__name__)

        with app.app_context():
            with app.test_request_context():
                result = get_current_span_id()
                assert result is None


class TestInitTelemetry:
    """Tests for init_telemetry function."""

    def setup_method(self):
        """Reset module state before each test."""
        import Medic.Core.telemetry as telemetry_module

        telemetry_module._initialized = False
        telemetry_module._tracer_provider = None

    def teardown_method(self):
        """Reset module state after each test."""
        import Medic.Core.telemetry as telemetry_module

        telemetry_module._initialized = False
        telemetry_module._tracer_provider = None

    @patch("Medic.Core.telemetry.FlaskInstrumentor")
    @patch("Medic.Core.telemetry.trace.set_tracer_provider")
    @patch("Medic.Core.telemetry.create_tracer_provider")
    @patch("Medic.Core.telemetry.create_resource")
    @patch("Medic.Core.telemetry.setup_propagators")
    def test_initializes_telemetry_successfully(
        self,
        mock_propagators,
        mock_create_resource,
        mock_create_provider,
        mock_set_provider,
        mock_flask_instrumentor,
    ):
        """Should initialize telemetry and return True."""
        from Medic.Core.telemetry import init_telemetry

        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        mock_instrumentor_instance = MagicMock()
        mock_flask_instrumentor.return_value = mock_instrumentor_instance

        app = Flask(__name__)

        result = init_telemetry(app)

        assert result is True
        mock_create_resource.assert_called_once()
        mock_create_provider.assert_called_once()
        mock_set_provider.assert_called_once_with(mock_provider)
        mock_propagators.assert_called_once()
        mock_instrumentor_instance.instrument_app.assert_called_once_with(app)

    @patch("Medic.Core.telemetry.FlaskInstrumentor")
    @patch("Medic.Core.telemetry.trace.set_tracer_provider")
    @patch("Medic.Core.telemetry.create_tracer_provider")
    @patch("Medic.Core.telemetry.create_resource")
    def test_skips_if_already_initialized(
        self,
        mock_create_resource,
        mock_create_provider,
        mock_set_provider,
        mock_flask_instrumentor,
    ):
        """Should skip initialization if already initialized."""
        import Medic.Core.telemetry as telemetry_module
        from Medic.Core.telemetry import init_telemetry

        telemetry_module._initialized = True

        app = Flask(__name__)
        result = init_telemetry(app)

        assert result is True
        mock_create_resource.assert_not_called()

    def test_returns_true_when_disabled(self):
        """Should return True without initializing when enable=False."""
        from Medic.Core.telemetry import init_telemetry, is_telemetry_enabled

        app = Flask(__name__)
        result = init_telemetry(app, enable=False)

        assert result is True
        assert is_telemetry_enabled() is True

    @patch("Medic.Core.telemetry.create_resource")
    def test_returns_false_on_exception(self, mock_create_resource):
        """Should return False if initialization fails."""
        from Medic.Core.telemetry import init_telemetry

        mock_create_resource.side_effect = Exception("Test error")

        app = Flask(__name__)
        result = init_telemetry(app)

        assert result is False


class TestShutdownTelemetry:
    """Tests for shutdown_telemetry function."""

    def setup_method(self):
        """Reset module state before each test."""
        import Medic.Core.telemetry as telemetry_module

        telemetry_module._initialized = False
        telemetry_module._tracer_provider = None

    def teardown_method(self):
        """Reset module state after each test."""
        import Medic.Core.telemetry as telemetry_module

        telemetry_module._initialized = False
        telemetry_module._tracer_provider = None

    def test_shuts_down_tracer_provider(self):
        """Should call shutdown on tracer provider."""
        import Medic.Core.telemetry as telemetry_module
        from Medic.Core.telemetry import shutdown_telemetry

        mock_provider = MagicMock()
        telemetry_module._tracer_provider = mock_provider
        telemetry_module._initialized = True

        shutdown_telemetry()

        mock_provider.shutdown.assert_called_once()
        assert telemetry_module._initialized is False
        assert telemetry_module._tracer_provider is None

    def test_handles_shutdown_exception(self):
        """Should handle exceptions during shutdown gracefully."""
        import Medic.Core.telemetry as telemetry_module
        from Medic.Core.telemetry import shutdown_telemetry

        mock_provider = MagicMock()
        mock_provider.shutdown.side_effect = Exception("Shutdown error")
        telemetry_module._tracer_provider = mock_provider
        telemetry_module._initialized = True

        # Should not raise
        shutdown_telemetry()

        assert telemetry_module._initialized is False
        assert telemetry_module._tracer_provider is None


class TestIsTelemetryEnabled:
    """Tests for is_telemetry_enabled function."""

    def setup_method(self):
        """Reset module state before each test."""
        import Medic.Core.telemetry as telemetry_module

        telemetry_module._initialized = False
        telemetry_module._tracer_provider = None

    def teardown_method(self):
        """Reset module state after each test."""
        import Medic.Core.telemetry as telemetry_module

        telemetry_module._initialized = False
        telemetry_module._tracer_provider = None

    def test_returns_false_when_not_initialized(self):
        """Should return False when telemetry is not initialized."""
        from Medic.Core.telemetry import is_telemetry_enabled

        assert is_telemetry_enabled() is False

    def test_returns_true_when_initialized(self):
        """Should return True when telemetry is initialized."""
        import Medic.Core.telemetry as telemetry_module
        from Medic.Core.telemetry import is_telemetry_enabled

        telemetry_module._initialized = True

        assert is_telemetry_enabled() is True


class TestGetTracer:
    """Tests for get_tracer function."""

    @patch("Medic.Core.telemetry.trace.get_tracer")
    def test_returns_tracer_with_name(self, mock_get_tracer):
        """Should call trace.get_tracer with provided name."""
        from Medic.Core.telemetry import get_tracer

        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer

        result = get_tracer("custom.name")

        mock_get_tracer.assert_called_once_with("custom.name")
        assert result == mock_tracer

    @patch("Medic.Core.telemetry.trace.get_tracer")
    def test_uses_module_name_as_default(self, mock_get_tracer):
        """Should use __name__ as default tracer name."""
        from Medic.Core.telemetry import get_tracer

        get_tracer()

        # Default is __name__ of telemetry module
        mock_get_tracer.assert_called_once()
