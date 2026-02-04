"""Unit tests for Medic.Core.logging_config module."""
import json
import logging
import os
from datetime import datetime
from unittest.mock import patch

from flask import Flask, g

from Medic.Core.logging_config import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_SERVICE_NAME,
    DEFAULT_VERSION,
    JSONFormatter,
    LOG_LEVELS,
    OTEL_SEVERITY_NUMBER,
    OTEL_SEVERITY_TEXT,
    TextFormatter,
    configure_logging,
    get_log_config,
    get_logger,
    get_request_context,
    get_trace_context,
    is_logging_configured,
    reset_logging_config,
)


class TestOtelSeverityMapping:
    """Tests for OTEL severity level mappings."""

    def test_severity_text_mapping(self):
        """Test that OTEL severity text mapping is correct."""
        assert OTEL_SEVERITY_TEXT[logging.DEBUG] == "DEBUG"
        assert OTEL_SEVERITY_TEXT[logging.INFO] == "INFO"
        assert OTEL_SEVERITY_TEXT[logging.WARNING] == "WARN"
        assert OTEL_SEVERITY_TEXT[logging.ERROR] == "ERROR"
        assert OTEL_SEVERITY_TEXT[logging.CRITICAL] == "FATAL"

    def test_severity_number_mapping(self):
        """Test that OTEL severity number mapping is correct."""
        assert OTEL_SEVERITY_NUMBER[logging.DEBUG] == 5
        assert OTEL_SEVERITY_NUMBER[logging.INFO] == 9
        assert OTEL_SEVERITY_NUMBER[logging.WARNING] == 13
        assert OTEL_SEVERITY_NUMBER[logging.ERROR] == 17
        assert OTEL_SEVERITY_NUMBER[logging.CRITICAL] == 21


class TestLogLevels:
    """Tests for log level mapping."""

    def test_standard_levels(self):
        """Test standard log level names."""
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL

    def test_alias_levels(self):
        """Test log level aliases."""
        assert LOG_LEVELS["WARN"] == logging.WARNING
        assert LOG_LEVELS["FATAL"] == logging.CRITICAL


class TestGetLogConfig:
    """Tests for get_log_config function."""

    def test_default_values(self):
        """Test that default values are returned when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_log_config()
            assert config["format"] == DEFAULT_LOG_FORMAT
            assert config["level"] == DEFAULT_LOG_LEVEL
            assert config["service_name"] == DEFAULT_SERVICE_NAME
            assert config["environment"] == DEFAULT_ENVIRONMENT
            assert config["version"] == DEFAULT_VERSION

    def test_env_var_override_format(self):
        """Test MEDIC_LOG_FORMAT env var."""
        with patch.dict(os.environ, {"MEDIC_LOG_FORMAT": "TEXT"}):
            config = get_log_config()
            assert config["format"] == "text"

    def test_env_var_override_level(self):
        """Test MEDIC_LOG_LEVEL env var."""
        with patch.dict(os.environ, {"MEDIC_LOG_LEVEL": "debug"}):
            config = get_log_config()
            assert config["level"] == "DEBUG"

    def test_env_var_override_service_name(self):
        """Test OTEL_SERVICE_NAME env var."""
        with patch.dict(os.environ, {"OTEL_SERVICE_NAME": "my-service"}):
            config = get_log_config()
            assert config["service_name"] == "my-service"

    def test_env_var_override_environment(self):
        """Test MEDIC_ENVIRONMENT env var."""
        with patch.dict(os.environ, {"MEDIC_ENVIRONMENT": "production"}):
            config = get_log_config()
            assert config["environment"] == "production"

    def test_env_var_override_version(self):
        """Test MEDIC_VERSION env var."""
        with patch.dict(os.environ, {"MEDIC_VERSION": "1.2.3"}):
            config = get_log_config()
            assert config["version"] == "1.2.3"


class TestGetTraceContext:
    """Tests for get_trace_context function."""

    def test_no_request_context(self):
        """Test trace context when not in request context."""
        context = get_trace_context()
        assert context["trace_id"] is None
        assert context["span_id"] is None

    def test_with_request_context_no_trace(self):
        """Test trace context when in request but no trace set."""
        app = Flask(__name__)
        with app.test_request_context():
            context = get_trace_context()
            assert context["trace_id"] is None
            assert context["span_id"] is None

    def test_with_trace_context(self):
        """Test trace context when trace IDs are set in g."""
        app = Flask(__name__)
        with app.test_request_context():
            g.trace_id = "00112233445566778899aabbccddeeff"
            g.span_id = "0011223344556677"
            context = get_trace_context()
            assert context["trace_id"] == "00112233445566778899aabbccddeeff"
            assert context["span_id"] == "0011223344556677"


class TestGetRequestContext:
    """Tests for get_request_context function."""

    def test_no_request_context(self):
        """Test request context when not in request."""
        context = get_request_context()
        assert context == {}

    def test_with_request_context(self):
        """Test request context extraction."""
        app = Flask(__name__)
        with app.test_request_context("/api/health", method="GET"):
            context = get_request_context()
            assert context["http.method"] == "GET"
            assert context["http.route"] == "/api/health"
            assert "http.url" in context


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_basic_format(self):
        """Test basic log formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["Body"] == "Test message"
        assert parsed["SeverityText"] == "INFO"
        assert parsed["SeverityNumber"] == 9
        assert parsed["Resource"]["service.name"] == DEFAULT_SERVICE_NAME
        assert parsed["Resource"]["service.version"] == DEFAULT_VERSION
        assert parsed["Resource"]["deployment.environment"] == DEFAULT_ENVIRONMENT
        assert parsed["InstrumentationScope"]["Name"] == "test.logger"

    def test_custom_service_info(self):
        """Test formatter with custom service info."""
        formatter = JSONFormatter(
            service_name="custom-service",
            environment="production",
            version="2.0.0",
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["Resource"]["service.name"] == "custom-service"
        assert parsed["Resource"]["service.version"] == "2.0.0"
        assert parsed["Resource"]["deployment.environment"] == "production"

    def test_all_severity_levels(self):
        """Test all log severity levels."""
        formatter = JSONFormatter()

        test_cases = [
            (logging.DEBUG, "DEBUG", 5),
            (logging.INFO, "INFO", 9),
            (logging.WARNING, "WARN", 13),
            (logging.ERROR, "ERROR", 17),
            (logging.CRITICAL, "FATAL", 21),
        ]

        for level, expected_text, expected_number in test_cases:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="/path/to/file.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["SeverityText"] == expected_text
            assert parsed["SeverityNumber"] == expected_number

    def test_timestamp_format(self):
        """Test that timestamp is ISO 8601 format."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        # Should be parseable as ISO format
        timestamp = datetime.fromisoformat(parsed["Timestamp"])
        assert timestamp.tzinfo is not None

    def test_trace_context_included(self):
        """Test that trace context is included when available."""
        formatter = JSONFormatter()
        app = Flask(__name__)

        with app.test_request_context():
            g.trace_id = "00112233445566778899aabbccddeeff"
            g.span_id = "0011223344556677"

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/file.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            parsed = json.loads(output)

            assert parsed["TraceId"] == "00112233445566778899aabbccddeeff"
            assert parsed["SpanId"] == "0011223344556677"

    def test_no_trace_context_fields_when_not_available(self):
        """Test that trace fields are omitted when not available."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "TraceId" not in parsed
        assert "SpanId" not in parsed

    def test_request_context_included(self):
        """Test that request context is included."""
        formatter = JSONFormatter()
        app = Flask(__name__)

        with app.test_request_context("/api/test", method="POST"):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/file.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            parsed = json.loads(output)

            assert parsed["Attributes"]["http.method"] == "POST"
            assert parsed["Attributes"]["http.route"] == "/api/test"

    def test_code_location_attributes(self):
        """Test that code location attributes are included."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["Attributes"]["code.filepath"] == "/path/to/file.py"
        assert parsed["Attributes"]["code.lineno"] == 42
        assert parsed["Attributes"]["code.function"] == "test_function"

    def test_exception_info(self):
        """Test that exception info is included."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["Attributes"]["exception.type"] == "ValueError"
        assert parsed["Attributes"]["exception.message"] == "Test error"
        assert "exception.stacktrace" in parsed["Attributes"]

    def test_extra_fields_in_attributes(self):
        """Test that extra fields are included in Attributes."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.user_id = "user123"
        record.request_id = "req456"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["Attributes"]["user_id"] == "user123"
        assert parsed["Attributes"]["request_id"] == "req456"

    def test_message_formatting_with_args(self):
        """Test that message is properly formatted with args."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=1,
            msg="User %s logged in from %s",
            args=("john", "127.0.0.1"),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["Body"] == "User john logged in from 127.0.0.1"


class TestTextFormatter:
    """Tests for TextFormatter class."""

    def test_basic_format(self):
        """Test basic text formatting."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "test.logger" in output
        assert "INFO" in output
        assert "Test message" in output

    def test_trace_context_in_text(self):
        """Test that trace context is included in text format."""
        formatter = TextFormatter()
        app = Flask(__name__)

        with app.test_request_context():
            g.trace_id = "00112233445566778899aabbccddeeff"

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/file.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)

            assert "trace_id=00112233445566778899aabbccddeeff" in output
            assert "Test message" in output

    def test_no_trace_context_in_text(self):
        """Test text format without trace context."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "trace_id=" not in output
        assert "Test message" in output


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def setup_method(self):
        """Reset logging config before each test."""
        reset_logging_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging_config()
        # Reset root logger
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_configure_with_defaults(self):
        """Test configuring with default values."""
        with patch.dict(os.environ, {}, clear=True):
            configure_logging()
            assert is_logging_configured()

    def test_configure_json_format(self):
        """Test configuring JSON format."""
        configure_logging(log_format="json")
        root = logging.getLogger()
        assert len(root.handlers) > 0
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_configure_text_format(self):
        """Test configuring text format."""
        configure_logging(log_format="text")
        root = logging.getLogger()
        assert len(root.handlers) > 0
        assert isinstance(root.handlers[0].formatter, TextFormatter)

    def test_configure_log_level(self):
        """Test configuring log level."""
        configure_logging(log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_from_env(self):
        """Test configuring from environment variables."""
        with patch.dict(os.environ, {
            "MEDIC_LOG_FORMAT": "text",
            "MEDIC_LOG_LEVEL": "WARNING",
        }):
            configure_logging()
            root = logging.getLogger()
            assert root.level == logging.WARNING
            assert isinstance(root.handlers[0].formatter, TextFormatter)

    def test_explicit_params_override_env(self):
        """Test that explicit parameters override env vars."""
        with patch.dict(os.environ, {"MEDIC_LOG_LEVEL": "DEBUG"}):
            configure_logging(log_level="ERROR")
            root = logging.getLogger()
            assert root.level == logging.ERROR

    def test_removes_existing_handlers(self):
        """Test that existing handlers are removed."""
        root = logging.getLogger()
        old_handler = logging.StreamHandler()
        root.addHandler(old_handler)

        configure_logging()

        assert old_handler not in root.handlers


class TestGetLogger:
    """Tests for get_logger function."""

    def setup_method(self):
        """Reset logging config before each test."""
        reset_logging_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging_config()
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_auto_configures_if_not_configured(self):
        """Test that get_logger auto-configures logging."""
        assert not is_logging_configured()
        get_logger("test")
        assert is_logging_configured()

    def test_does_not_reconfigure_if_already_configured(self):
        """Test that get_logger doesn't reconfigure if already done."""
        configure_logging(log_level="DEBUG")
        root = logging.getLogger()
        original_level = root.level

        with patch.dict(os.environ, {"MEDIC_LOG_LEVEL": "ERROR"}):
            get_logger("test")
            assert root.level == original_level


class TestLoggingIntegration:
    """Integration tests for the logging system."""

    def setup_method(self):
        """Reset logging config before each test."""
        reset_logging_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_logging_config()
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_json_logging_with_flask_app(self):
        """Test JSON logging within Flask request context."""
        app = Flask(__name__)
        configure_logging(log_format="json")

        with app.test_request_context("/api/test", method="GET"):
            g.trace_id = "test-trace-id"
            g.span_id = "test-span-id"

            logger = get_logger("test.integration")

            # Capture log output
            import io
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setFormatter(JSONFormatter())
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

            logger.info("Test log message")

            output = stream.getvalue()
            parsed = json.loads(output)

            assert parsed["Body"] == "Test log message"
            assert parsed["TraceId"] == "test-trace-id"
            assert parsed["SpanId"] == "test-span-id"
            assert parsed["Attributes"]["http.method"] == "GET"
            assert parsed["Attributes"]["http.route"] == "/api/test"

    def test_logging_outside_request_context(self):
        """Test JSON logging outside of Flask request context."""
        configure_logging(log_format="json")
        logger = get_logger("test.outside")

        # Capture log output
        import io
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("Background task log")

        output = stream.getvalue()
        parsed = json.loads(output)

        assert parsed["Body"] == "Background task log"
        assert "TraceId" not in parsed
        assert "http.method" not in parsed["Attributes"]
