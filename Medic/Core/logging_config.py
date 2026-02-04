"""
Structured JSON logging with OpenTelemetry semantic conventions for Medic.

Provides JSON-formatted logs compatible with Grafana/Loki that include
trace context (trace_id, span_id) for correlation with Tempo traces.

Features:
- JSONFormatter with OTEL semantic conventions
- Automatic trace context injection from Flask g context
- Configurable log format (json/text) and level
- Request context fields (http.method, http.route, http.status_code)
- Resource attributes (service.name, service.version, deployment.environment)

Environment variables:
- MEDIC_LOG_FORMAT: 'json' (default) or 'text'
- MEDIC_LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
- OTEL_SERVICE_NAME: Service name for logs (default: medic)
- MEDIC_ENVIRONMENT: Deployment environment (default: development)
- MEDIC_VERSION: Application version (default: unknown)

Usage:
    from Medic.Core.logging_config import configure_logging, get_logger

    # In app initialization
    configure_logging()

    # Get a logger
    logger = get_logger(__name__)
    logger.info("Request processed", extra={"user_id": "123"})
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import g, has_request_context, request

# OTEL severity level mapping (following OTEL semantic conventions)
# https://opentelemetry.io/docs/specs/otel/logs/data-model/#severity-fields
OTEL_SEVERITY_TEXT: Dict[int, str] = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "FATAL",
}

OTEL_SEVERITY_NUMBER: Dict[int, int] = {
    logging.DEBUG: 5,      # DEBUG
    logging.INFO: 9,       # INFO
    logging.WARNING: 13,   # WARN
    logging.ERROR: 17,     # ERROR
    logging.CRITICAL: 21,  # FATAL
}

# Log level mapping
LOG_LEVELS: Dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.CRITICAL,
}

# Default configuration
DEFAULT_LOG_FORMAT: str = "json"
DEFAULT_LOG_LEVEL: str = "INFO"
DEFAULT_SERVICE_NAME: str = "medic"
DEFAULT_ENVIRONMENT: str = "development"
DEFAULT_VERSION: str = "unknown"

# Module-level flag to track configuration
_configured: bool = False


def get_log_config() -> Dict[str, Any]:
    """
    Get logging configuration from environment variables.

    Returns:
        Dictionary with logging configuration values
    """
    return {
        "format": os.environ.get("MEDIC_LOG_FORMAT", DEFAULT_LOG_FORMAT).lower(),
        "level": os.environ.get("MEDIC_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
        "service_name": os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
        "environment": os.environ.get("MEDIC_ENVIRONMENT", DEFAULT_ENVIRONMENT),
        "version": os.environ.get("MEDIC_VERSION", DEFAULT_VERSION),
    }


def get_trace_context() -> Dict[str, Optional[str]]:
    """
    Get current trace context from Flask g context.

    Returns:
        Dictionary with trace_id and span_id (or None if not available)
    """
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    if has_request_context():
        trace_id = getattr(g, "trace_id", None)
        span_id = getattr(g, "span_id", None)

    return {
        "trace_id": trace_id,
        "span_id": span_id,
    }


def get_request_context() -> Dict[str, Optional[str]]:
    """
    Get current HTTP request context from Flask request.

    Returns:
        Dictionary with HTTP request fields (or empty if not in request context)
    """
    context: Dict[str, Optional[str]] = {}

    if has_request_context():
        context["http.method"] = request.method
        context["http.route"] = request.path
        context["http.url"] = request.url
        # Note: http.status_code is typically added in after_request handlers

    return context


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter with OpenTelemetry semantic conventions.

    Produces structured JSON logs compatible with Grafana/Loki, including:
    - OTEL severity fields (SeverityText, SeverityNumber)
    - Trace context (TraceId, SpanId) for log-to-trace correlation
    - Resource attributes (service.name, service.version, deployment.environment)
    - Request context (http.method, http.route)
    - Custom attributes from log extra fields
    """

    def __init__(
        self,
        service_name: str = DEFAULT_SERVICE_NAME,
        environment: str = DEFAULT_ENVIRONMENT,
        version: str = DEFAULT_VERSION,
    ):
        """
        Initialize the JSON formatter.

        Args:
            service_name: Service name for resource attributes
            environment: Deployment environment
            version: Application version
        """
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON with OTEL semantic conventions.

        Args:
            record: LogRecord to format

        Returns:
            JSON-formatted log string
        """
        # Build the log entry following OTEL log data model
        log_entry: Dict[str, Any] = {
            # Timestamp in ISO 8601 format with timezone
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            # OTEL severity fields
            "SeverityText": OTEL_SEVERITY_TEXT.get(record.levelno, "INFO"),
            "SeverityNumber": OTEL_SEVERITY_NUMBER.get(record.levelno, 9),
            # Body is the log message
            "Body": record.getMessage(),
            # Resource attributes
            "Resource": {
                "service.name": self.service_name,
                "service.version": self.version,
                "deployment.environment": self.environment,
            },
            # Instrumentation scope
            "InstrumentationScope": {
                "Name": record.name,
            },
            # Attributes for additional context
            "Attributes": {},
        }

        # Add trace context
        trace_context = get_trace_context()
        if trace_context["trace_id"]:
            log_entry["TraceId"] = trace_context["trace_id"]
        if trace_context["span_id"]:
            log_entry["SpanId"] = trace_context["span_id"]

        # Add request context
        request_context = get_request_context()
        for key, value in request_context.items():
            if value is not None:
                log_entry["Attributes"][key] = value

        # Add log record attributes
        log_entry["Attributes"]["code.filepath"] = record.pathname
        log_entry["Attributes"]["code.lineno"] = record.lineno
        log_entry["Attributes"]["code.function"] = record.funcName

        # Add exception info if present
        if record.exc_info:
            log_entry["Attributes"]["exception.type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else None
            )
            log_entry["Attributes"]["exception.message"] = str(record.exc_info[1])
            log_entry["Attributes"]["exception.stacktrace"] = (
                self.formatException(record.exc_info)
            )

        # Add any extra fields from the log call
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "asctime",
            ):
                # Add custom extra fields to Attributes
                log_entry["Attributes"][key] = value

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter with trace context.

    Produces traditional text logs with optional trace_id for debugging.
    """

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
    ):
        """
        Initialize the text formatter.

        Args:
            fmt: Log format string (default includes trace_id)
            datefmt: Date format string
        """
        if fmt is None:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as text with optional trace context.

        Args:
            record: LogRecord to format

        Returns:
            Text-formatted log string
        """
        # Add trace context to the record for formatting
        trace_context = get_trace_context()
        if trace_context["trace_id"]:
            record.trace_id = trace_context["trace_id"]
            # Prepend trace_id to message if not already in format
            original_msg = record.getMessage()
            record.msg = f"[trace_id={trace_context['trace_id']}] {original_msg}"
            record.args = ()

        return super().format(record)


def configure_logging(
    log_format: Optional[str] = None,
    log_level: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
    version: Optional[str] = None,
) -> None:
    """
    Configure the logging system with OTEL-compatible formatters.

    This function sets up the root logger with either JSON or text formatting,
    depending on the MEDIC_LOG_FORMAT environment variable or explicit parameter.

    Args:
        log_format: 'json' or 'text' (default: from env or 'json')
        log_level: Log level name (default: from env or 'INFO')
        service_name: Service name for logs (default: from env or 'medic')
        environment: Deployment environment (default: from env or 'development')
        version: Application version (default: from env or 'unknown')
    """
    global _configured

    # Get config from env if not explicitly provided
    config = get_log_config()

    log_format = log_format or config["format"]
    log_level = log_level or config["level"]
    service_name = service_name or config["service_name"]
    environment = environment or config["environment"]
    version = version or config["version"]

    # Convert level name to logging constant
    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)

    # Get or create the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create stdout handler (logs go to stdout for container collection)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create appropriate formatter
    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter(
            service_name=service_name,
            environment=environment,
            version=version,
        )
    else:
        formatter = TextFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the configured settings.

    If logging hasn't been configured yet, this will configure it
    with default settings.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    if not _configured:
        configure_logging()

    return logging.getLogger(name)


def is_logging_configured() -> bool:
    """
    Check if logging has been configured.

    Returns:
        True if configure_logging() has been called
    """
    return _configured


def reset_logging_config() -> None:
    """
    Reset the logging configuration state.

    This is primarily for testing purposes.
    """
    global _configured
    _configured = False
