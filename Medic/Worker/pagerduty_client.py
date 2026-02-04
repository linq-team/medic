"""PagerDuty integration client for Medic alerts."""

import os
import logging
import requests
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Import metrics (optional - graceful degradation)
try:
    from Medic.Core.metrics import record_pagerduty_request

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    record_pagerduty_request = None  # type: ignore[misc, assignment]

# PagerDuty Events API v2 endpoint
PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

# Priority to PagerDuty severity mapping
PRIORITY_SEVERITY_MAP = {
    "p1": "critical",
    "p2": "error",
    "p3": "warning",
    "p4": "info",
    "p5": "info",
}


def get_routing_key() -> str:
    """Get the PagerDuty routing key from environment."""
    key = os.environ.get("PAGERDUTY_ROUTING_KEY")
    if not key:
        logger.warning("PAGERDUTY_ROUTING_KEY not set")
    return key or ""


def get_severity(priority: str) -> str:
    """Map Medic priority to PagerDuty severity."""
    return PRIORITY_SEVERITY_MAP.get(priority.lower(), "warning")


def create_alert(
    alert_message: str,
    service_name: str,
    heartbeat_name: str,
    team: str,
    priority: str = "p3",
    runbook: Optional[str] = None,
) -> Optional[str]:
    """
    Create a PagerDuty alert for a heartbeat failure.

    Args:
        alert_message: The alert message/title
        service_name: Name of the service that failed
        heartbeat_name: Name of the heartbeat that failed
        team: Team responsible for the service
        priority: Alert priority (p1-p5)
        runbook: Optional URL to runbook documentation

    Returns:
        The dedup_key (incident key) on success, None on failure
    """
    routing_key = get_routing_key()
    if not routing_key:
        logger.error(
            "Cannot create PagerDuty alert: PAGERDUTY_ROUTING_KEY not configured"
        )
        return None

    # Use heartbeat_name as dedup_key for idempotent alerts
    dedup_key = f"medic-{heartbeat_name}"

    payload: dict[str, Any] = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": dedup_key,
        "payload": {
            "summary": alert_message,
            "source": "medic",
            "severity": get_severity(priority),
            "component": heartbeat_name,
            "group": team,
            "class": "heartbeat_failure",
            "custom_details": {
                "service_name": service_name,
                "heartbeat_name": heartbeat_name,
                "team": team,
                "priority": priority,
            },
        },
        "client": "Medic Heartbeat Monitor",
        "client_url": os.environ.get("MEDIC_BASE_URL", ""),
    }

    # Add runbook link if provided
    if runbook:
        payload["links"] = [{"href": runbook, "text": "Runbook"}]

    try:
        response = requests.post(
            PAGERDUTY_EVENTS_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 202:
            result = response.json()
            logger.info(
                "PagerDuty alert created: dedup_key=%s, status=%s",
                dedup_key,
                result.get("status"),
            )
            if METRICS_AVAILABLE and record_pagerduty_request is not None:
                record_pagerduty_request(action="trigger", success=True)
            return dedup_key
        else:
            logger.error(
                "Failed to create PagerDuty alert: status=%d, response=%s",
                response.status_code,
                response.text,
            )
            if METRICS_AVAILABLE and record_pagerduty_request is not None:
                record_pagerduty_request(action="trigger", success=False)
            return None

    except requests.RequestException as e:
        logger.error("Failed to create PagerDuty alert: %s", str(e))
        if METRICS_AVAILABLE and record_pagerduty_request is not None:
            record_pagerduty_request(action="trigger", success=False)
        return None


def close_alert(dedup_key: str) -> bool:
    """
    Resolve a PagerDuty alert.

    Args:
        dedup_key: The dedup_key returned when the alert was created

    Returns:
        True on success, False on failure
    """
    routing_key = get_routing_key()
    if not routing_key:
        logger.error(
            "Cannot close PagerDuty alert: PAGERDUTY_ROUTING_KEY not configured"
        )
        return False

    if not dedup_key or dedup_key == "NULL":
        logger.warning("Cannot close PagerDuty alert: no dedup_key provided")
        return False

    payload = {
        "routing_key": routing_key,
        "event_action": "resolve",
        "dedup_key": dedup_key,
    }

    try:
        response = requests.post(
            PAGERDUTY_EVENTS_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 202:
            logger.info("PagerDuty alert resolved: dedup_key=%s", dedup_key)
            if METRICS_AVAILABLE and record_pagerduty_request is not None:
                record_pagerduty_request(action="resolve", success=True)
            return True
        else:
            logger.error(
                "Failed to resolve PagerDuty alert: status=%d, response=%s",
                response.status_code,
                response.text,
            )
            if METRICS_AVAILABLE and record_pagerduty_request is not None:
                record_pagerduty_request(action="resolve", success=False)
            return False

    except requests.RequestException as e:
        logger.error("Failed to resolve PagerDuty alert: %s", str(e))
        if METRICS_AVAILABLE and record_pagerduty_request is not None:
            record_pagerduty_request(action="resolve", success=False)
        return False


def acknowledge_alert(dedup_key: str) -> bool:
    """
    Acknowledge a PagerDuty alert.

    Args:
        dedup_key: The dedup_key returned when the alert was created

    Returns:
        True on success, False on failure
    """
    routing_key = get_routing_key()
    if not routing_key:
        logger.error(
            "Cannot acknowledge PagerDuty alert: PAGERDUTY_ROUTING_KEY not configured"
        )
        return False

    if not dedup_key or dedup_key == "NULL":
        logger.warning("Cannot acknowledge PagerDuty alert: no dedup_key provided")
        return False

    payload = {
        "routing_key": routing_key,
        "event_action": "acknowledge",
        "dedup_key": dedup_key,
    }

    try:
        response = requests.post(
            PAGERDUTY_EVENTS_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 202:
            logger.info("PagerDuty alert acknowledged: dedup_key=%s", dedup_key)
            if METRICS_AVAILABLE and record_pagerduty_request is not None:
                record_pagerduty_request(action="acknowledge", success=True)
            return True
        else:
            logger.error(
                "Failed to acknowledge PagerDuty alert: status=%d, response=%s",
                response.status_code,
                response.text,
            )
            if METRICS_AVAILABLE and record_pagerduty_request is not None:
                record_pagerduty_request(action="acknowledge", success=False)
            return False

    except requests.RequestException as e:
        logger.error("Failed to acknowledge PagerDuty alert: %s", str(e))
        if METRICS_AVAILABLE and record_pagerduty_request is not None:
            record_pagerduty_request(action="acknowledge", success=False)
        return False
