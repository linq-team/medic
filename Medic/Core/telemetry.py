"""
OpenTelemetry instrumentation for Medic.

Provides distributed tracing capabilities with OpenTelemetry, supporting
Grafana/Loki/Tempo correlation via W3C trace context propagation.

Features:
- TracerProvider configuration with OTLP exporter
- Flask auto-instrumentation for request tracing
- W3C trace context header propagation
- Trace ID storage in Flask g context for log correlation

Environment variables:
- OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://alloy:4317)
- OTEL_SERVICE_NAME: Service name for traces (default: medic)
- OTEL_RESOURCE_ATTRIBUTES: Additional resource attributes (comma-separated)
- MEDIC_ENVIRONMENT: Deployment environment (default: development)
- MEDIC_VERSION: Application version (default: unknown)

Usage:
    from Medic.Core.telemetry import init_telemetry, get_current_trace_id

    # In app initialization
    app = Flask(__name__)
    init_telemetry(app)

    # Get trace ID for logging
    trace_id = get_current_trace_id()
"""

import logging
import os
from typing import Optional

from flask import Flask, g
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Module-level flag to track initialization
_initialized: bool = False
_tracer_provider: Optional[TracerProvider] = None


# Default configuration values
DEFAULT_OTLP_ENDPOINT: str = "http://alloy:4317"
DEFAULT_SERVICE_NAME: str = "medic"
DEFAULT_ENVIRONMENT: str = "development"
DEFAULT_VERSION: str = "unknown"


def get_otel_config() -> dict:
    """
    Get OpenTelemetry configuration from environment variables.

    Returns:
        Dictionary with OTEL configuration values
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    service_name = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    environment = os.environ.get("MEDIC_ENVIRONMENT", DEFAULT_ENVIRONMENT)
    version = os.environ.get("MEDIC_VERSION", DEFAULT_VERSION)

    # Parse additional resource attributes from OTEL_RESOURCE_ATTRIBUTES
    resource_attributes = {}
    raw_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    if raw_attrs:
        for attr in raw_attrs.split(","):
            if "=" in attr:
                key, value = attr.split("=", 1)
                resource_attributes[key.strip()] = value.strip()

    return {
        "endpoint": endpoint,
        "service_name": service_name,
        "environment": environment,
        "version": version,
        "resource_attributes": resource_attributes,
    }


def create_resource(config: dict) -> Resource:
    """
    Create an OpenTelemetry Resource with service metadata.

    Args:
        config: Configuration dictionary from get_otel_config()

    Returns:
        Resource object with service attributes
    """
    attributes = {
        "service.name": config["service_name"],
        "service.version": config["version"],
        "deployment.environment": config["environment"],
    }

    # Merge any additional resource attributes
    attributes.update(config.get("resource_attributes", {}))

    return Resource.create(attributes)


def create_tracer_provider(resource: Resource, endpoint: str) -> TracerProvider:
    """
    Create and configure a TracerProvider with OTLP exporter.

    Args:
        resource: Resource object with service metadata
        endpoint: OTLP collector endpoint URL

    Returns:
        Configured TracerProvider
    """
    provider = TracerProvider(resource=resource)

    # Create OTLP exporter
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,  # Use insecure for internal cluster communication
    )

    # Use batch processor for efficient span export
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    return provider


def setup_propagators() -> None:
    """
    Configure W3C trace context propagation for distributed tracing.
    """
    propagator = CompositePropagator([TraceContextTextMapPropagator()])
    set_global_textmap(propagator)


def store_trace_context() -> None:
    """
    Store current trace context in Flask g for log correlation.

    This should be called at the start of each request to make
    trace_id and span_id available for logging.
    """
    span = trace.get_current_span()
    if span is not None:
        span_context = span.get_span_context()
        if span_context.is_valid:
            # Format trace_id and span_id as hex strings
            g.trace_id = format(span_context.trace_id, "032x")
            g.span_id = format(span_context.span_id, "016x")
        else:
            g.trace_id = None
            g.span_id = None
    else:
        g.trace_id = None
        g.span_id = None


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID from Flask g context.

    Returns:
        Trace ID as hex string, or None if not in a traced request
    """
    return getattr(g, "trace_id", None)


def get_current_span_id() -> Optional[str]:
    """
    Get the current span ID from Flask g context.

    Returns:
        Span ID as hex string, or None if not in a traced request
    """
    return getattr(g, "span_id", None)


def init_telemetry(app: Flask, enable: bool = True) -> bool:
    """
    Initialize OpenTelemetry instrumentation for the Flask application.

    This function:
    1. Creates a TracerProvider with OTLP exporter
    2. Instruments the Flask application
    3. Sets up W3C trace context propagation
    4. Registers a before_request hook to store trace context

    Args:
        app: Flask application instance to instrument
        enable: Whether to enable telemetry (default: True)

    Returns:
        True if initialization succeeded, False otherwise
    """
    global _initialized, _tracer_provider

    if _initialized:
        logger.log(level=10, msg="Telemetry already initialized, skipping")
        return True

    if not enable:
        logger.log(level=20, msg="Telemetry disabled via enable=False")
        _initialized = True
        return True

    try:
        # Get configuration
        config = get_otel_config()

        logger.log(
            level=20,
            msg=f"Initializing OpenTelemetry: service={config['service_name']}"
            f", endpoint={config['endpoint']}"
            f", environment={config['environment']}",
        )

        # Create resource and tracer provider
        resource = create_resource(config)
        _tracer_provider = create_tracer_provider(resource, config["endpoint"])

        # Set as global tracer provider
        trace.set_tracer_provider(_tracer_provider)

        # Setup W3C trace context propagation
        setup_propagators()

        # Instrument Flask application
        FlaskInstrumentor().instrument_app(app)

        # Register before_request hook to store trace context
        @app.before_request
        def before_request_trace_context():
            store_trace_context()

        _initialized = True

        logger.log(level=20, msg="OpenTelemetry initialization complete")

        return True

    except Exception as e:
        logger.log(level=40, msg=f"Failed to initialize OpenTelemetry: {e}")
        return False


def init_worker_telemetry(
    service_name: str = "medic-worker", enable: bool = True
) -> bool:
    """
    Initialize OpenTelemetry instrumentation for background workers.

    This function initializes telemetry without Flask dependencies,
    suitable for background processes like the monitoring worker.

    Args:
        service_name: Service name for traces (default: medic-worker)
        enable: Whether to enable telemetry (default: True)

    Returns:
        True if initialization succeeded, False otherwise
    """
    global _initialized, _tracer_provider

    if _initialized:
        logger.log(level=10, msg="Telemetry already initialized, skipping")
        return True

    if not enable:
        logger.log(level=20, msg="Worker telemetry disabled via enable=False")
        _initialized = True
        return True

    try:
        # Get configuration and override service name
        config = get_otel_config()
        config["service_name"] = service_name

        logger.log(
            level=20,
            msg=f"Initializing worker OpenTelemetry: service={config['service_name']}"
            f", endpoint={config['endpoint']}"
            f", environment={config['environment']}",
        )

        # Create resource and tracer provider
        resource = create_resource(config)
        _tracer_provider = create_tracer_provider(resource, config["endpoint"])

        # Set as global tracer provider
        trace.set_tracer_provider(_tracer_provider)

        # Setup W3C trace context propagation
        setup_propagators()

        _initialized = True

        logger.log(level=20, msg="Worker OpenTelemetry initialization complete")

        return True

    except Exception as e:
        logger.log(level=40, msg=f"Failed to initialize worker OpenTelemetry: {e}")
        return False


def shutdown_telemetry() -> None:
    """
    Gracefully shutdown the telemetry system.

    Flushes any pending spans and releases resources.
    """
    global _initialized, _tracer_provider

    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
            logger.log(level=20, msg="OpenTelemetry shutdown complete")
        except Exception as e:
            logger.log(level=30, msg=f"Error during OpenTelemetry shutdown: {e}")

    _initialized = False
    _tracer_provider = None


def is_telemetry_enabled() -> bool:
    """
    Check if telemetry has been initialized.

    Returns:
        True if init_telemetry() has been called successfully
    """
    return _initialized


def get_tracer(name: str = __name__) -> trace.Tracer:
    """
    Get a tracer instance for creating custom spans.

    Args:
        name: Name for the tracer (typically __name__)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)
