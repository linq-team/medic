"""Health check endpoints for Medic."""

import os
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def check_database_health() -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        from Medic.Core.database import connect_db

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {
            "status": "healthy",
            "latency_ms": 0,  # Would measure actual latency in production
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def check_pagerduty_health() -> Dict[str, Any]:
    """Check PagerDuty configuration."""
    routing_key = os.environ.get("PAGERDUTY_ROUTING_KEY")
    if routing_key:
        return {"status": "configured", "routing_key_set": True}
    return {"status": "not_configured", "routing_key_set": False}


def check_slack_health() -> Dict[str, Any]:
    """Check Slack configuration."""
    token = os.environ.get("SLACK_API_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL_ID")

    if token and channel:
        return {"status": "configured", "token_set": True, "channel_set": True}
    return {
        "status": "partially_configured" if token or channel else "not_configured",
        "token_set": bool(token),
        "channel_set": bool(channel),
    }


def get_full_health_status() -> Dict[str, Any]:
    """Get comprehensive health status."""
    from Medic.Core import metrics

    db_health = check_database_health()
    pd_health = check_pagerduty_health()
    slack_health = check_slack_health()

    # Update metrics
    metrics.update_health_status("database", db_health["status"] == "healthy")
    metrics.update_health_status("pagerduty", pd_health["status"] == "configured")
    metrics.update_health_status("slack", slack_health["status"] == "configured")

    overall_healthy = (
        db_health["status"] == "healthy"
        and pd_health["status"] == "configured"
        and slack_health["status"] == "configured"
    )

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "2.0.0",
        "components": {
            "database": db_health,
            "pagerduty": pd_health,
            "slack": slack_health,
        },
    }


def get_liveness_status() -> Dict[str, Any]:
    """Simple liveness check - is the service running?"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat() + "Z"}


def get_readiness_status() -> Dict[str, Any]:
    """Readiness check - can the service accept traffic?"""
    db_health = check_database_health()

    ready = db_health["status"] == "healthy"

    return {
        "status": "ready" if ready else "not_ready",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": db_health["status"],
    }
