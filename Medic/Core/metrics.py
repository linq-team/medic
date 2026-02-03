"""Prometheus metrics for Medic."""
import time
import logging
from functools import wraps
from typing import Callable, Any

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Application info
APP_INFO = Info('medic', 'Medic application information')
APP_INFO.info({
    'version': '2.0.0',
    'description': 'Heartbeat monitoring service'
})

# Request metrics
REQUEST_COUNT = Counter(
    'medic_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'medic_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Heartbeat metrics
HEARTBEAT_COUNT = Counter(
    'medic_heartbeats_total',
    'Total heartbeats received',
    ['heartbeat_name', 'status']
)

HEARTBEAT_REGISTERED = Gauge(
    'medic_registered_services',
    'Number of registered heartbeat services'
)

HEARTBEAT_ACTIVE = Gauge(
    'medic_active_services',
    'Number of active heartbeat services'
)

# Alert metrics
ALERT_COUNT = Counter(
    'medic_alerts_total',
    'Total alerts triggered',
    ['priority', 'team']
)

ALERT_ACTIVE = Gauge(
    'medic_alerts_active',
    'Number of currently active alerts'
)

ALERT_RESOLVED = Counter(
    'medic_alerts_resolved_total',
    'Total alerts resolved'
)

# Worker metrics
WORKER_CYCLE_DURATION = Histogram(
    'medic_worker_cycle_duration_seconds',
    'Duration of worker monitoring cycle',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

WORKER_SERVICES_CHECKED = Counter(
    'medic_worker_services_checked_total',
    'Total services checked by worker'
)

# Database metrics
DB_QUERY_DURATION = Histogram(
    'medic_db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

DB_CONNECTION_ERRORS = Counter(
    'medic_db_connection_errors_total',
    'Total database connection errors'
)

# Authentication metrics
AUTH_FAILURES = Counter(
    'medic_auth_failures_total',
    'Total authentication failures',
    ['reason']
)

# External service metrics
PAGERDUTY_REQUESTS = Counter(
    'medic_pagerduty_requests_total',
    'Total PagerDuty API requests',
    ['action', 'status']
)

SLACK_REQUESTS = Counter(
    'medic_slack_requests_total',
    'Total Slack API requests',
    ['status']
)

# Health status
HEALTH_STATUS = Gauge(
    'medic_health_status',
    'Health status of Medic components',
    ['component']
)

# Duration threshold alerts
DURATION_ALERTS = Counter(
    'medic_duration_alerts_total',
    'Total duration threshold alerts triggered',
    ['alert_type']  # exceeded, stale
)

STALE_JOBS = Gauge(
    'medic_stale_jobs_current',
    'Number of currently stale jobs exceeding max duration'
)

# Circuit breaker metrics
CIRCUIT_BREAKER_TRIPS = Counter(
    'medic_circuit_breaker_trips_total',
    'Total circuit breaker trips (blocked playbook executions)',
    ['service_id']
)

CIRCUIT_BREAKER_OPEN = Gauge(
    'medic_circuit_breaker_open',
    'Number of services with open circuit breakers'
)


def track_request_metrics(func: Callable) -> Callable:
    """Decorator to track request metrics."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        from flask import request
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            status = result[1] if isinstance(result, tuple) else 200
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.endpoint or 'unknown',
                status=str(status)
            ).inc()
            return result
        except Exception as e:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.endpoint or 'unknown',
                status='500'
            ).inc()
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.endpoint or 'unknown'
            ).observe(duration)

    return wrapper


def track_db_query(operation: str):
    """Decorator to track database query metrics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(operation=operation).observe(duration)
        return wrapper
    return decorator


def record_heartbeat(heartbeat_name: str, status: str):
    """Record a heartbeat metric."""
    HEARTBEAT_COUNT.labels(heartbeat_name=heartbeat_name, status=status).inc()


def record_alert_created(priority: str, team: str):
    """Record alert creation metric."""
    ALERT_COUNT.labels(priority=priority, team=team).inc()
    ALERT_ACTIVE.inc()


def record_alert_resolved():
    """Record alert resolution metric."""
    ALERT_RESOLVED.inc()
    ALERT_ACTIVE.dec()


def record_pagerduty_request(action: str, success: bool):
    """Record PagerDuty request metric."""
    PAGERDUTY_REQUESTS.labels(
        action=action,
        status='success' if success else 'failure'
    ).inc()


def record_slack_request(success: bool):
    """Record Slack request metric."""
    SLACK_REQUESTS.labels(status='success' if success else 'failure').inc()


def record_auth_failure(reason: str):
    """
    Record an authentication failure metric.

    Args:
        reason: The reason for the failure. Should be one of:
                - 'invalid_key': API key not found or doesn't match
                - 'expired_key': API key has expired
                - 'insufficient_scope': API key lacks required scopes
    """
    AUTH_FAILURES.labels(reason=reason).inc()


def update_service_counts(registered: int, active: int):
    """Update service count gauges."""
    HEARTBEAT_REGISTERED.set(registered)
    HEARTBEAT_ACTIVE.set(active)


def update_health_status(component: str, healthy: bool):
    """Update health status gauge."""
    HEALTH_STATUS.labels(component=component).set(1 if healthy else 0)


def record_duration_alert(alert_type: str):
    """
    Record a duration threshold alert metric.

    Args:
        alert_type: The type of alert. Should be one of:
                   - 'exceeded': Job completed but exceeded max_duration
                   - 'stale': Job started but hasn't completed within max_duration
    """
    DURATION_ALERTS.labels(alert_type=alert_type).inc()


def update_stale_jobs_count(count: int):
    """Update the current count of stale jobs."""
    STALE_JOBS.set(count)


def record_circuit_breaker_trip(service_id: int):
    """
    Record a circuit breaker trip metric.

    Args:
        service_id: The service ID that was blocked
    """
    CIRCUIT_BREAKER_TRIPS.labels(service_id=str(service_id)).inc()


def update_circuit_breaker_open_count(count: int):
    """
    Update the count of services with open circuit breakers.

    Args:
        count: Number of services with open circuits
    """
    CIRCUIT_BREAKER_OPEN.set(count)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST
