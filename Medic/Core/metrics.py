"""
Prometheus metrics for Medic with OpenTelemetry semantic conventions.

Provides application metrics with OTEL naming conventions and exemplar support
for Grafana trace correlation. Metrics are exposed in OpenMetrics format to
support exemplars that enable Grafana to jump from metric spikes to example
traces.

Features:
- OTEL semantic metric naming conventions
- Exemplar support for histograms (trace_id correlation)
- Service info gauge with resource attributes
- OpenMetrics format for exemplar exposure

Environment variables:
- OTEL_SERVICE_NAME: Service name for metrics (default: medic)
- MEDIC_ENVIRONMENT: Deployment environment (default: development)
- MEDIC_VERSION: Application version (default: unknown)

Usage:
    from Medic.Core.metrics import (
        record_request_duration_with_exemplar,
        record_playbook_execution_duration_with_exemplar,
        get_metrics,
    )

    # Record request duration with trace exemplar
    record_request_duration_with_exemplar(
        method="GET",
        endpoint="/api/v1/services",
        duration=0.123,
        trace_id="abc123def456"
    )
"""

import logging
import os
import sys
import time
from functools import wraps
from collections.abc import Callable
from typing import Any, Optional

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)
from prometheus_client.openmetrics.exposition import (
    generate_latest as generate_openmetrics_latest,
    CONTENT_TYPE_LATEST as OPENMETRICS_CONTENT_TYPE,
)

import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())

# Default configuration values
DEFAULT_SERVICE_NAME: str = "medic"
DEFAULT_ENVIRONMENT: str = "development"
DEFAULT_VERSION: str = "unknown"


def _get_python_version() -> str:
    """
    Get the Python version string.

    Returns:
        Python version in format 'major.minor.micro' (e.g., '3.14.3')
    """
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _get_config() -> dict[str, str]:
    """
    Get metrics configuration from environment variables.

    Returns:
        Dictionary with configuration values
    """
    service_name = os.environ.get("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
    environment = os.environ.get("MEDIC_ENVIRONMENT", DEFAULT_ENVIRONMENT)
    version = os.environ.get("MEDIC_VERSION", DEFAULT_VERSION)
    python_version = _get_python_version()
    return {
        "service_name": service_name,
        "environment": environment,
        "version": version,
        "python_version": python_version,
    }


# Module-level config (initialized once at import time)
_config = _get_config()


# Application info - OTEL semantic: service.* attributes
# Using Info metric for static service metadata
APP_INFO = Info("medic_app", "Medic application information")
APP_INFO.info({"version": "2.0.0", "description": "Heartbeat monitoring service"})

# Service info gauge with OTEL resource attributes
# This provides dynamic resource labels for Grafana
# Named 'medic_build_info' to follow Prometheus conventions
MEDIC_BUILD_INFO = Gauge(
    "medic_build_info",
    "Medic service information with OTEL resource attributes",
    ["service_name", "service_version", "deployment_environment", "python_version"],
)
# Set the gauge to 1 with resource attribute labels
MEDIC_BUILD_INFO.labels(
    service_name=_config["service_name"],
    service_version=_config["version"],
    deployment_environment=_config["environment"],
    python_version=_config["python_version"],
).set(1)

# Request metrics - OTEL semantic: http.server.* namespace
REQUEST_COUNT = Counter(
    "medic_http_server_request_total",
    "Total HTTP requests (OTEL: http.server.request.total)",
    ["method", "route", "status_code", "service_name"],
)

REQUEST_LATENCY = Histogram(
    "medic_http_server_request_duration_seconds",
    "HTTP request latency in seconds (OTEL: http.server.request.duration)",
    ["method", "route", "service_name"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Heartbeat metrics - application specific
HEARTBEAT_COUNT = Counter(
    "medic_heartbeats_total", "Total heartbeats received", ["heartbeat_name", "status"]
)

HEARTBEAT_REGISTERED = Gauge(
    "medic_registered_services", "Number of registered heartbeat services"
)

HEARTBEAT_ACTIVE = Gauge("medic_active_services", "Number of active heartbeat services")

# Alert metrics
ALERT_COUNT = Counter(
    "medic_alerts_total", "Total alerts triggered", ["priority", "team"]
)

ALERT_ACTIVE = Gauge("medic_alerts_active", "Number of currently active alerts")

ALERT_RESOLVED = Counter("medic_alerts_resolved_total", "Total alerts resolved")

# Worker metrics
WORKER_CYCLE_DURATION = Histogram(
    "medic_worker_cycle_duration_seconds",
    "Duration of worker monitoring cycle",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

WORKER_SERVICES_CHECKED = Counter(
    "medic_worker_services_checked_total", "Total services checked by worker"
)

# Database metrics - OTEL semantic: db.client.* namespace
DB_QUERY_DURATION = Histogram(
    "medic_db_client_operation_duration_seconds",
    "Database query duration (OTEL: db.client.operation.duration)",
    ["operation", "service_name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

DB_CONNECTION_ERRORS = Counter(
    "medic_db_connection_errors_total", "Total database connection errors"
)

# Authentication metrics
AUTH_FAILURES = Counter(
    "medic_auth_failures_total", "Total authentication failures", ["reason"]
)

# External service metrics
PAGERDUTY_REQUESTS = Counter(
    "medic_pagerduty_requests_total",
    "Total PagerDuty API requests",
    ["action", "status"],
)

SLACK_REQUESTS = Counter(
    "medic_slack_requests_total", "Total Slack API requests", ["status"]
)

# Health status
HEALTH_STATUS = Gauge(
    "medic_health_status", "Health status of Medic components", ["component"]
)

# Duration threshold alerts
DURATION_ALERTS = Counter(
    "medic_duration_alerts_total",
    "Total duration threshold alerts triggered",
    ["alert_type"],  # exceeded, stale
)

STALE_JOBS = Gauge(
    "medic_stale_jobs_current", "Number of currently stale jobs exceeding max duration"
)

# Circuit breaker metrics
CIRCUIT_BREAKER_TRIPS = Counter(
    "medic_circuit_breaker_trips_total",
    "Total circuit breaker trips (blocked playbook executions)",
    ["service_id"],
)

CIRCUIT_BREAKER_OPEN = Gauge(
    "medic_circuit_breaker_open", "Number of services with open circuit breakers"
)

# Playbook execution metrics
PLAYBOOK_EXECUTIONS = Counter(
    "medic_playbook_executions_total",
    "Total playbook executions",
    ["playbook", "status", "service_name"],
)

PLAYBOOK_EXECUTION_DURATION = Histogram(
    "medic_playbook_execution_duration_seconds",
    "Playbook execution duration in seconds",
    ["playbook", "service_name"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0],
)

PLAYBOOK_EXECUTIONS_PENDING_APPROVAL = Gauge(
    "medic_playbook_executions_pending_approval",
    "Number of playbook executions pending approval",
)


# Backwards compatibility aliases for old metric names
# These ensure existing dashboards continue to work
medic_http_requests_total = REQUEST_COUNT
medic_http_request_duration_seconds = REQUEST_LATENCY


def _build_exemplar(trace_id: Optional[str]) -> Optional[dict[str, str]]:
    """
    Build an exemplar dictionary for a metric observation.

    Args:
        trace_id: The trace ID to include in the exemplar, or None

    Returns:
        Exemplar dictionary with trace_id, or None if no trace_id
    """
    if trace_id:
        return {"trace_id": trace_id}
    return None


def record_request_duration_with_exemplar(
    method: str, endpoint: str, duration: float, trace_id: Optional[str] = None
) -> None:
    """
    Record request duration with an optional trace exemplar.

    Exemplars enable Grafana to jump from a metric spike directly to an
    example trace that contributed to that spike.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Request endpoint/route
        duration: Request duration in seconds
        trace_id: Optional trace ID for exemplar correlation
    """
    exemplar = _build_exemplar(trace_id)
    REQUEST_LATENCY.labels(
        method=method, route=endpoint, service_name=_config["service_name"]
    ).observe(duration, exemplar=exemplar)


def record_playbook_execution_duration_with_exemplar(
    playbook_name: str, duration_seconds: float, trace_id: Optional[str] = None
) -> None:
    """
    Record playbook execution duration with an optional trace exemplar.

    Args:
        playbook_name: Name of the playbook that was executed
        duration_seconds: Duration of the execution in seconds
        trace_id: Optional trace ID for exemplar correlation
    """
    exemplar = _build_exemplar(trace_id)
    PLAYBOOK_EXECUTION_DURATION.labels(
        playbook=playbook_name, service_name=_config["service_name"]
    ).observe(duration_seconds, exemplar=exemplar)


def record_db_query_duration_with_exemplar(
    operation: str, duration: float, trace_id: Optional[str] = None
) -> None:
    """
    Record database query duration with an optional trace exemplar.

    Args:
        operation: Database operation type (select, insert, update, etc.)
        duration: Query duration in seconds
        trace_id: Optional trace ID for exemplar correlation
    """
    exemplar = _build_exemplar(trace_id)
    DB_QUERY_DURATION.labels(
        operation=operation, service_name=_config["service_name"]
    ).observe(duration, exemplar=exemplar)


def track_request_metrics(func: Callable) -> Callable:
    """
    Decorator to track request metrics with automatic trace correlation.

    Automatically extracts trace_id from Flask g context for exemplar.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from flask import request, g

        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            status = result[1] if isinstance(result, tuple) else 200
            REQUEST_COUNT.labels(
                method=request.method,
                route=request.endpoint or "unknown",
                status_code=str(status),
                service_name=_config["service_name"],
            ).inc()
            return result
        except Exception:
            REQUEST_COUNT.labels(
                method=request.method,
                route=request.endpoint or "unknown",
                status_code="500",
                service_name=_config["service_name"],
            ).inc()
            raise
        finally:
            duration = time.time() - start_time
            # Get trace_id from Flask g context if available
            trace_id = getattr(g, "trace_id", None)
            record_request_duration_with_exemplar(
                method=request.method,
                endpoint=request.endpoint or "unknown",
                duration=duration,
                trace_id=trace_id,
            )

    return wrapper


def track_db_query(operation: str) -> Callable:
    """
    Decorator to track database query metrics with automatic trace correlation.

    Args:
        operation: Database operation type (select, insert, update, etc.)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from flask import g, has_request_context

            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                # Get trace_id from Flask g context if in request
                trace_id = None
                if has_request_context():
                    trace_id = getattr(g, "trace_id", None)
                record_db_query_duration_with_exemplar(
                    operation=operation, duration=duration, trace_id=trace_id
                )

        return wrapper

    return decorator


def record_heartbeat(heartbeat_name: str, status: str) -> None:
    """Record a heartbeat metric."""
    HEARTBEAT_COUNT.labels(heartbeat_name=heartbeat_name, status=status).inc()


def record_alert_created(priority: str, team: str) -> None:
    """Record alert creation metric."""
    ALERT_COUNT.labels(priority=priority, team=team).inc()
    ALERT_ACTIVE.inc()


def record_alert_resolved() -> None:
    """Record alert resolution metric."""
    ALERT_RESOLVED.inc()
    ALERT_ACTIVE.dec()


def record_pagerduty_request(action: str, success: bool) -> None:
    """Record PagerDuty request metric."""
    PAGERDUTY_REQUESTS.labels(
        action=action, status="success" if success else "failure"
    ).inc()


def record_slack_request(success: bool) -> None:
    """Record Slack request metric."""
    SLACK_REQUESTS.labels(status="success" if success else "failure").inc()


def record_auth_failure(reason: str) -> None:
    """
    Record an authentication failure metric.

    Args:
        reason: The reason for the failure. Should be one of:
                - 'invalid_key': API key not found or doesn't match
                - 'expired_key': API key has expired
                - 'insufficient_scope': API key lacks required scopes
    """
    AUTH_FAILURES.labels(reason=reason).inc()


def update_service_counts(registered: int, active: int) -> None:
    """Update service count gauges."""
    HEARTBEAT_REGISTERED.set(registered)
    HEARTBEAT_ACTIVE.set(active)


def update_health_status(component: str, healthy: bool) -> None:
    """Update health status gauge."""
    HEALTH_STATUS.labels(component=component).set(1 if healthy else 0)


def record_duration_alert(alert_type: str) -> None:
    """
    Record a duration threshold alert metric.

    Args:
        alert_type: The type of alert. Should be one of:
                   - 'exceeded': Job completed but exceeded max_duration
                   - 'stale': Job hasn't completed within max_duration
    """
    DURATION_ALERTS.labels(alert_type=alert_type).inc()


def update_stale_jobs_count(count: int) -> None:
    """Update the current count of stale jobs."""
    STALE_JOBS.set(count)


def record_circuit_breaker_trip(service_id: int) -> None:
    """
    Record a circuit breaker trip metric.

    Args:
        service_id: The service ID that was blocked
    """
    CIRCUIT_BREAKER_TRIPS.labels(service_id=str(service_id)).inc()


def update_circuit_breaker_open_count(count: int) -> None:
    """
    Update the count of services with open circuit breakers.

    Args:
        count: Number of services with open circuits
    """
    CIRCUIT_BREAKER_OPEN.set(count)


def record_playbook_execution(playbook_name: str, status: str) -> None:
    """
    Record a playbook execution metric.

    Args:
        playbook_name: Name of the playbook that was executed
        status: Final status of the execution (completed, failed, cancelled)
    """
    PLAYBOOK_EXECUTIONS.labels(
        playbook=playbook_name, status=status, service_name=_config["service_name"]
    ).inc()


def record_playbook_execution_duration(
    playbook_name: str, duration_seconds: float
) -> None:
    """
    Record the duration of a playbook execution.

    This is a convenience function that calls
    record_playbook_execution_duration_with_exemplar without a trace_id.
    For trace correlation, use record_playbook_execution_duration_with_exemplar
    directly.

    Args:
        playbook_name: Name of the playbook that was executed
        duration_seconds: Duration of the execution in seconds
    """
    record_playbook_execution_duration_with_exemplar(
        playbook_name=playbook_name, duration_seconds=duration_seconds, trace_id=None
    )


def update_pending_approval_count(count: int) -> None:
    """
    Update the count of playbook executions pending approval.

    Args:
        count: Number of executions currently pending approval
    """
    PLAYBOOK_EXECUTIONS_PENDING_APPROVAL.set(count)


def get_metrics(openmetrics: bool = True) -> bytes:
    """
    Generate Prometheus/OpenMetrics output.

    Args:
        openmetrics: If True (default), use OpenMetrics format which supports
                     exemplars. If False, use standard Prometheus format.

    Returns:
        Metrics output as bytes
    """
    if openmetrics:
        return generate_openmetrics_latest(REGISTRY)
    return generate_latest()


def get_metrics_content_type(openmetrics: bool = True) -> str:
    """
    Get the content type for metrics output.

    Args:
        openmetrics: If True (default), return OpenMetrics content type.
                     If False, return standard Prometheus content type.

    Returns:
        Content type string
    """
    if openmetrics:
        return OPENMETRICS_CONTENT_TYPE
    return CONTENT_TYPE_LATEST


def refresh_config() -> None:
    """
    Refresh the metrics configuration from environment variables.

    Call this if environment variables change after module import.
    Updates the medic_build_info gauge with new values.
    """
    global _config
    _config = _get_config()

    # Update the build info gauge with new values
    MEDIC_BUILD_INFO.labels(
        service_name=_config["service_name"],
        service_version=_config["version"],
        deployment_environment=_config["environment"],
        python_version=_config["python_version"],
    ).set(1)
