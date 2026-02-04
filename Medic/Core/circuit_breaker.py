"""Circuit breaker for playbook executions.

This module provides circuit breaker functionality to prevent runaway
playbook executions. It tracks execution counts per service within a
sliding time window and blocks new executions when the threshold is exceeded.

Default configuration:
- Window: 1 hour (3600 seconds)
- Max executions per service: 5

When the circuit breaker trips:
- New playbook executions for that service are blocked
- A warning is logged
- An alert is recorded in metrics

Usage:
    from Medic.Core.circuit_breaker import (
        check_circuit_breaker,
        record_execution,
        is_circuit_open,
    )

    # Check before starting execution
    if is_circuit_open(service_id):
        # Block execution
        return

    # Record execution when it starts
    record_execution(service_id)
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.utils.datetime_helpers import now as get_now

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


# Default configuration
DEFAULT_WINDOW_SECONDS = 3600  # 1 hour
DEFAULT_MAX_EXECUTIONS = 5  # Max 5 executions per service per window


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    window_seconds: int = DEFAULT_WINDOW_SECONDS
    max_executions: int = DEFAULT_MAX_EXECUTIONS


@dataclass
class CircuitBreakerStatus:
    """Status of the circuit breaker for a service."""

    service_id: int
    is_open: bool
    execution_count: int
    window_start: datetime
    window_end: datetime
    threshold: int
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_id": self.service_id,
            "is_open": self.is_open,
            "execution_count": self.execution_count,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "threshold": self.threshold,
            "message": self.message,
        }


# Global configuration (can be overridden)
_config: CircuitBreakerConfig = CircuitBreakerConfig()


def get_config() -> CircuitBreakerConfig:
    """Get the current circuit breaker configuration."""
    return _config


def set_config(config: CircuitBreakerConfig) -> None:
    """
    Set the circuit breaker configuration.

    Args:
        config: New configuration to apply
    """
    global _config
    _config = config
    logger.log(
        level=20,
        msg=f"Circuit breaker config updated: window={config.window_seconds}s, "
        f"max_executions={config.max_executions}",
    )


def reset_config() -> None:
    """Reset configuration to defaults."""
    global _config
    _config = CircuitBreakerConfig()


def get_execution_count_in_window(
    service_id: int, window_seconds: Optional[int] = None
) -> int:
    """
    Get the number of playbook executions for a service within the time window.

    This counts executions from the playbook_executions table that were
    started within the sliding window.

    Args:
        service_id: The service ID to check
        window_seconds: Optional custom window (uses config default if not set)

    Returns:
        Number of executions in the window
    """
    config = get_config()
    window = window_seconds or config.window_seconds

    # Calculate window start time
    now = get_now()
    window_start = now - timedelta(seconds=window)

    # Query executions within window
    result = db.query_db(
        """
        SELECT COUNT(*) as count
        FROM medic.playbook_executions
        WHERE service_id = %s
          AND created_at >= %s
        """,
        (service_id, window_start),
        show_columns=True,
    )

    if not result or result == "[]":
        return 0

    try:
        rows = json.loads(str(result))
        if rows:
            return int(rows[0].get("count", 0))
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        logger.log(
            level=30, msg=f"Error parsing execution count for service {service_id}"
        )

    return 0


def is_circuit_open(
    service_id: int, config: Optional[CircuitBreakerConfig] = None
) -> bool:
    """
    Check if the circuit breaker is open (blocking) for a service.

    The circuit is open when the number of executions within the window
    exceeds the configured threshold.

    Args:
        service_id: The service ID to check
        config: Optional custom config (uses global config if not set)

    Returns:
        True if circuit is open (blocking), False otherwise
    """
    cfg = config or get_config()

    count = get_execution_count_in_window(service_id, cfg.window_seconds)

    is_open = count >= cfg.max_executions

    if is_open:
        logger.log(
            level=30,
            msg=f"Circuit breaker OPEN for service {service_id}: "
            f"{count} executions in last {cfg.window_seconds}s "
            f"(threshold: {cfg.max_executions})",
        )

    return is_open


def check_circuit_breaker(
    service_id: int, config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreakerStatus:
    """
    Check the full circuit breaker status for a service.

    Returns detailed status including execution count, window times,
    and whether the circuit is open.

    Args:
        service_id: The service ID to check
        config: Optional custom config (uses global config if not set)

    Returns:
        CircuitBreakerStatus with full details
    """
    cfg = config or get_config()

    now = get_now()
    window_start = now - timedelta(seconds=cfg.window_seconds)
    window_end = now

    count = get_execution_count_in_window(service_id, cfg.window_seconds)
    is_open = count >= cfg.max_executions

    if is_open:
        message = (
            f"Circuit breaker tripped: {count} executions in window "
            f"(threshold: {cfg.max_executions}). "
            f"New executions blocked until window expires."
        )
    else:
        remaining = cfg.max_executions - count
        message = (
            f"Circuit closed: {count}/{cfg.max_executions} executions. "
            f"{remaining} more allowed."
        )

    return CircuitBreakerStatus(
        service_id=service_id,
        is_open=is_open,
        execution_count=count,
        window_start=window_start,
        window_end=window_end,
        threshold=cfg.max_executions,
        message=message,
    )


def record_circuit_breaker_trip(
    service_id: int, execution_count: int, playbook_name: Optional[str] = None
) -> None:
    """
    Record a circuit breaker trip event.

    This logs the event and records metrics for monitoring.

    Args:
        service_id: The service ID that triggered the trip
        execution_count: Number of executions that triggered the trip
        playbook_name: Optional name of the blocked playbook
    """
    # Import here to avoid circular imports
    try:
        from Medic.Core.metrics import record_circuit_breaker_trip as record_metric

        record_metric(service_id)
    except ImportError:
        pass

    if playbook_name:
        logger.log(
            level=40,
            msg=f"CIRCUIT BREAKER TRIPPED: Service {service_id} blocked from "
            f"executing playbook '{playbook_name}'. "
            f"Execution count: {execution_count}",
        )
    else:
        logger.log(
            level=40,
            msg=f"CIRCUIT BREAKER TRIPPED: Service {service_id} blocked. "
            f"Execution count: {execution_count}",
        )


def get_services_with_open_circuit() -> List[CircuitBreakerStatus]:
    """
    Get all services that currently have an open circuit breaker.

    Useful for monitoring and dashboards.

    Returns:
        List of CircuitBreakerStatus for services with open circuits
    """
    config = get_config()
    now = get_now()
    window_start = now - timedelta(seconds=config.window_seconds)

    # Query services with high execution counts in window
    result = db.query_db(
        """
        SELECT service_id, COUNT(*) as count
        FROM medic.playbook_executions
        WHERE created_at >= %s
          AND service_id IS NOT NULL
        GROUP BY service_id
        HAVING COUNT(*) >= %s
        ORDER BY count DESC
        """,
        (window_start, config.max_executions),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    try:
        rows = json.loads(str(result))
        statuses = []

        for row in rows:
            service_id = row.get("service_id")
            count = row.get("count", 0)

            if service_id is not None:
                statuses.append(
                    CircuitBreakerStatus(
                        service_id=service_id,
                        is_open=True,
                        execution_count=count,
                        window_start=window_start,
                        window_end=now,
                        threshold=config.max_executions,
                        message=f"Circuit open: {count} executions in window",
                    )
                )

        return statuses

    except (json.JSONDecodeError, TypeError, KeyError):
        logger.log(level=30, msg="Error parsing services with open circuits")
        return []


def get_execution_history_for_service(
    service_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get recent playbook execution history for a service.

    Useful for debugging circuit breaker behavior.

    Args:
        service_id: The service ID to query
        limit: Maximum number of executions to return

    Returns:
        List of execution records with id, status, and timestamps
    """
    result = db.query_db(
        """
        SELECT e.execution_id, e.playbook_id, e.status, e.created_at,
               e.started_at, e.completed_at, p.name as playbook_name
        FROM medic.playbook_executions e
        LEFT JOIN medic.playbooks p ON e.playbook_id = p.playbook_id
        WHERE e.service_id = %s
        ORDER BY e.created_at DESC
        LIMIT %s
        """,
        (service_id, limit),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    try:
        return json.loads(str(result))
    except (json.JSONDecodeError, TypeError):
        return []
