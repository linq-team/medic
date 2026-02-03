"""Team-based alert routing for Medic.

This module provides functionality to route alerts to the appropriate
Slack channel based on the service's team configuration. If a service
has a team with a Slack channel, alerts are sent there. Otherwise,
alerts fall back to the default channel.

It also supports flexible alert routing with multiple notification targets
per service, with two routing modes:
- notify_all: Send to all enabled targets
- notify_until_success: Send to targets in priority order until one succeeds
"""
import os
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from Medic.Core.database import query_db

logger = logging.getLogger(__name__)


def get_team_for_service(service_id: int) -> Optional[dict]:
    """
    Get the team associated with a service.

    Args:
        service_id: The service ID to look up

    Returns:
        Team dict with team_id, name, slack_channel_id or None if no team
    """
    query = """
        SELECT t.team_id, t.name, t.slack_channel_id
        FROM medic.teams t
        INNER JOIN services s ON s.team_id = t.team_id
        WHERE s.service_id = %s
    """
    result = query_db(query, (service_id,), show_columns=True)

    if not result:
        return None

    # query_db returns JSON string when show_columns=True
    data = json.loads(str(result))
    if not data:
        return None

    return data[0]


def get_slack_channel_for_service(service_id: int) -> str:
    """
    Get the Slack channel to use for alerts for a given service.

    Routing priority:
    1. If service has a team with a Slack channel, use that
    2. Otherwise, fall back to the default SLACK_CHANNEL_ID

    Args:
        service_id: The service ID to get the channel for

    Returns:
        Slack channel ID to use for alerts
    """
    default_channel = os.environ.get("SLACK_CHANNEL_ID", "")

    team = get_team_for_service(service_id)
    if team and team.get("slack_channel_id"):
        channel = team["slack_channel_id"]
        logger.debug(
            f"Using team '{team['name']}' Slack channel {channel} "
            f"for service {service_id}"
        )
        return channel

    if team:
        logger.debug(
            f"Team '{team['name']}' has no Slack channel, "
            f"using default for service {service_id}"
        )
    else:
        logger.debug(
            f"No team for service {service_id}, using default channel"
        )

    return default_channel


def get_slack_channel_for_team(team_id: int) -> str:
    """
    Get the Slack channel for a team.

    Args:
        team_id: The team ID to look up

    Returns:
        Team's Slack channel ID or default channel if not set
    """
    default_channel = os.environ.get("SLACK_CHANNEL_ID", "")

    query = """
        SELECT team_id, name, slack_channel_id
        FROM medic.teams
        WHERE team_id = %s
    """
    result = query_db(query, (team_id,), show_columns=True)

    if not result:
        logger.debug(f"Team {team_id} not found, using default channel")
        return default_channel

    data = json.loads(str(result))
    if not data:
        return default_channel

    team = data[0]
    if team.get("slack_channel_id"):
        return team["slack_channel_id"]

    logger.debug(
        f"Team '{team['name']}' has no Slack channel, using default"
    )
    return default_channel


class NotificationMode(str, Enum):
    """Alert routing mode for multiple notification targets."""

    NOTIFY_ALL = "notify_all"
    NOTIFY_UNTIL_SUCCESS = "notify_until_success"


class NotificationType(str, Enum):
    """Types of notification targets."""

    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


@dataclass
class NotificationTarget:
    """A notification target configuration."""

    target_id: int
    service_id: int
    target_type: NotificationType
    config: Dict[str, Any]
    priority: int
    enabled: bool


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt."""

    target_id: int
    target_type: NotificationType
    success: bool
    error_message: Optional[str] = None


def get_notification_targets_for_service(
    service_id: int,
    enabled_only: bool = True,
) -> List[NotificationTarget]:
    """
    Get notification targets for a service, ordered by priority.

    Args:
        service_id: The service ID to get targets for
        enabled_only: If True, only return enabled targets (default: True)

    Returns:
        List of NotificationTarget objects ordered by priority (lower first)
    """
    if enabled_only:
        query = """
            SELECT target_id, service_id, type, config, priority, enabled
            FROM medic.notification_targets
            WHERE service_id = %s AND enabled = TRUE
            ORDER BY priority ASC, target_id ASC
        """
    else:
        query = """
            SELECT target_id, service_id, type, config, priority, enabled
            FROM medic.notification_targets
            WHERE service_id = %s
            ORDER BY priority ASC, target_id ASC
        """

    result = query_db(query, (service_id,), show_columns=True)

    if not result:
        return []

    try:
        data = json.loads(str(result))
        targets = []
        for row in data:
            config = row.get("config", {})
            if isinstance(config, str):
                config = json.loads(config)

            targets.append(
                NotificationTarget(
                    target_id=row["target_id"],
                    service_id=row["service_id"],
                    target_type=NotificationType(row["type"]),
                    config=config,
                    priority=row["priority"],
                    enabled=row.get("enabled", True),
                )
            )
        return targets
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse notification targets: {e}")
        return []


def route_alert(
    service_id: int,
    payload: Dict[str, Any],
    mode: NotificationMode = NotificationMode.NOTIFY_ALL,
    sender: Optional[Callable[[NotificationTarget, Dict[str, Any]], bool]] = None
) -> List[NotificationResult]:
    """
    Route an alert to notification targets for a service.

    Args:
        service_id: The service ID to route alerts for
        payload: The alert payload to send
        mode: Routing mode - NOTIFY_ALL or NOTIFY_UNTIL_SUCCESS
        sender: Optional callback to send notification. If None, uses
               default_notification_sender. Signature: (target, payload) -> bool

    Returns:
        List of NotificationResult objects for each target attempted
    """
    targets = get_notification_targets_for_service(service_id)

    if not targets:
        logger.debug(
            f"No notification targets found for service {service_id}"
        )
        return []

    if sender is None:
        sender = default_notification_sender

    results: List[NotificationResult] = []

    if mode == NotificationMode.NOTIFY_ALL:
        results = _route_notify_all(targets, payload, sender)
    elif mode == NotificationMode.NOTIFY_UNTIL_SUCCESS:
        results = _route_notify_until_success(targets, payload, sender)
    else:
        logger.warning(f"Unknown routing mode: {mode}, defaulting to notify_all")
        results = _route_notify_all(targets, payload, sender)

    return results


def _route_notify_all(
    targets: List[NotificationTarget],
    payload: Dict[str, Any],
    sender: Callable[[NotificationTarget, Dict[str, Any]], bool],
) -> List[NotificationResult]:
    """
    Send notification to all enabled targets.

    Args:
        targets: List of notification targets
        payload: The alert payload to send
        sender: Callback to send notification

    Returns:
        List of NotificationResult for each target
    """
    results: List[NotificationResult] = []

    for target in targets:
        if not target.enabled:
            results.append(
                NotificationResult(
                    target_id=target.target_id,
                    target_type=target.target_type,
                    success=False,
                    error_message="Target is disabled",
                )
            )
            continue

        try:
            success = sender(target, payload)
            results.append(
                NotificationResult(
                    target_id=target.target_id,
                    target_type=target.target_type,
                    success=success,
                    error_message=None if success else "Delivery failed",
                )
            )
            if success:
                logger.info(
                    f"Successfully sent alert to target {target.target_id} "
                    f"({target.target_type.value})"
                )
            else:
                logger.warning(
                    f"Failed to send alert to target {target.target_id} "
                    f"({target.target_type.value})"
                )
        except Exception as e:
            logger.error(
                f"Error sending alert to target {target.target_id}: {e}"
            )
            results.append(
                NotificationResult(
                    target_id=target.target_id,
                    target_type=target.target_type,
                    success=False,
                    error_message=str(e),
                )
            )

    return results


def _route_notify_until_success(
    targets: List[NotificationTarget],
    payload: Dict[str, Any],
    sender: Callable[[NotificationTarget, Dict[str, Any]], bool],
) -> List[NotificationResult]:
    """
    Send notification to targets in priority order until one succeeds.

    Args:
        targets: List of notification targets (should be pre-sorted by priority)
        payload: The alert payload to send
        sender: Callback to send notification

    Returns:
        List of NotificationResult for targets attempted (stops after success)
    """
    results: List[NotificationResult] = []

    for target in targets:
        if not target.enabled:
            results.append(
                NotificationResult(
                    target_id=target.target_id,
                    target_type=target.target_type,
                    success=False,
                    error_message="Target is disabled",
                )
            )
            continue

        try:
            success = sender(target, payload)
            results.append(
                NotificationResult(
                    target_id=target.target_id,
                    target_type=target.target_type,
                    success=success,
                    error_message=None if success else "Delivery failed",
                )
            )

            if success:
                logger.info(
                    f"Successfully sent alert to target {target.target_id} "
                    f"({target.target_type.value}), stopping routing"
                )
                # Stop after first success
                break
            else:
                logger.warning(
                    f"Failed to send alert to target {target.target_id} "
                    f"({target.target_type.value}), trying next target"
                )

        except Exception as e:
            logger.error(
                f"Error sending alert to target {target.target_id}: {e}"
            )
            results.append(
                NotificationResult(
                    target_id=target.target_id,
                    target_type=target.target_type,
                    success=False,
                    error_message=str(e),
                )
            )
            # Continue to next target on error

    return results


def default_notification_sender(
    target: NotificationTarget,
    payload: Dict[str, Any],
) -> bool:
    """
    Default notification sender that dispatches based on target type.

    This is a placeholder implementation. Real implementations should
    integrate with actual Slack, PagerDuty, and webhook delivery services.

    Args:
        target: The notification target to send to
        payload: The alert payload to send

    Returns:
        True if notification was sent successfully, False otherwise
    """
    target_type = target.target_type

    if target_type == NotificationType.SLACK:
        return _send_slack_notification(target, payload)
    elif target_type == NotificationType.PAGERDUTY:
        return _send_pagerduty_notification(target, payload)
    elif target_type == NotificationType.WEBHOOK:
        return _send_webhook_notification(target, payload)
    else:
        logger.warning(f"Unknown notification type: {target_type}")
        return False


def _send_slack_notification(
    target: NotificationTarget,
    payload: Dict[str, Any],
) -> bool:
    """
    Send a Slack notification.

    Args:
        target: The Slack notification target
        payload: The alert payload

    Returns:
        True if sent successfully, False otherwise
    """
    channel_id = target.config.get("channel_id")
    if not channel_id:
        logger.error(f"Slack target {target.target_id} missing channel_id")
        return False

    logger.debug(
        f"Sending Slack notification to channel {channel_id} "
        f"for target {target.target_id}"
    )
    # Placeholder - actual Slack sending would be implemented here
    # or delegated to existing Slack notification module
    return True


def _send_pagerduty_notification(
    target: NotificationTarget,
    payload: Dict[str, Any],
) -> bool:
    """
    Send a PagerDuty notification.

    Args:
        target: The PagerDuty notification target
        payload: The alert payload

    Returns:
        True if sent successfully, False otherwise
    """
    service_key = target.config.get("service_key")
    if not service_key:
        logger.error(f"PagerDuty target {target.target_id} missing service_key")
        return False

    logger.debug(
        f"Sending PagerDuty notification with service_key "
        f"for target {target.target_id}"
    )
    # Placeholder - actual PagerDuty sending would be implemented here
    # or delegated to existing PagerDuty notification module
    return True


def _send_webhook_notification(
    target: NotificationTarget,
    payload: Dict[str, Any],
) -> bool:
    """
    Send a webhook notification.

    Args:
        target: The webhook notification target
        payload: The alert payload

    Returns:
        True if sent successfully, False otherwise
    """
    url = target.config.get("url")
    if not url:
        logger.error(f"Webhook target {target.target_id} missing url")
        return False

    logger.debug(
        f"Sending webhook notification to {url} "
        f"for target {target.target_id}"
    )
    # Placeholder - actual webhook sending would be implemented here
    # or delegated to webhook_delivery service
    return True


def has_notification_targets(service_id: int) -> bool:
    """
    Check if a service has any enabled notification targets.

    Args:
        service_id: The service ID to check

    Returns:
        True if service has at least one enabled target, False otherwise
    """
    targets = get_notification_targets_for_service(service_id)
    return len(targets) > 0


def get_successful_results(
    results: List[NotificationResult]
) -> List[NotificationResult]:
    """
    Filter notification results to only successful ones.

    Args:
        results: List of NotificationResult objects

    Returns:
        List of successful NotificationResult objects
    """
    return [r for r in results if r.success]


def get_failed_results(
    results: List[NotificationResult]
) -> List[NotificationResult]:
    """
    Filter notification results to only failed ones.

    Args:
        results: List of NotificationResult objects

    Returns:
        List of failed NotificationResult objects
    """
    return [r for r in results if not r.success]


def all_notifications_succeeded(results: List[NotificationResult]) -> bool:
    """
    Check if all notification attempts succeeded.

    Args:
        results: List of NotificationResult objects

    Returns:
        True if all results are successful, False otherwise
    """
    if not results:
        return False
    return all(r.success for r in results)


def any_notification_succeeded(results: List[NotificationResult]) -> bool:
    """
    Check if any notification attempt succeeded.

    Args:
        results: List of NotificationResult objects

    Returns:
        True if at least one result is successful, False otherwise
    """
    return any(r.success for r in results)
