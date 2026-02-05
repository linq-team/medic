"""Playbook trigger matching for Medic.

This module provides functionality to match alerts to playbook triggers
based on service name patterns and consecutive failure thresholds.

Triggers are matched using:
- Service pattern: Glob pattern (e.g., "worker-*", "api-prod-*", "*")
- Consecutive failures: Number of consecutive failures before triggering

Usage:
    # Find matching trigger for a service with 3 consecutive failures
    trigger = find_matching_trigger("worker-prod-01", 3)
    if trigger:
        playbook = get_playbook_for_trigger(trigger)
"""

import fnmatch
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


@dataclass
class PlaybookTrigger:
    """Represents a playbook trigger from the database."""

    trigger_id: int
    playbook_id: int
    service_pattern: str
    consecutive_failures: int
    enabled: bool

    def matches_service(self, service_name: str) -> bool:
        """
        Check if this trigger matches a service name.

        Uses glob-style pattern matching with fnmatch.
        Patterns support:
        - * matches any sequence of characters
        - ? matches any single character
        - [seq] matches any character in seq
        - [!seq] matches any character not in seq

        Args:
            service_name: Name of the service to match

        Returns:
            True if the pattern matches the service name
        """
        if not service_name:
            return False
        return fnmatch.fnmatch(service_name.lower(), self.service_pattern.lower())

    def meets_failure_threshold(self, failure_count: int) -> bool:
        """
        Check if the failure count meets this trigger's threshold.

        Args:
            failure_count: Number of consecutive failures

        Returns:
            True if failure_count >= consecutive_failures threshold
        """
        return failure_count >= self.consecutive_failures

    def matches(self, service_name: str, failure_count: int) -> bool:
        """
        Check if this trigger matches both service and failure threshold.

        Args:
            service_name: Name of the service to match
            failure_count: Number of consecutive failures

        Returns:
            True if both conditions are met
        """
        return (
            self.enabled
            and self.matches_service(service_name)
            and self.meets_failure_threshold(failure_count)
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "trigger_id": self.trigger_id,
            "playbook_id": self.playbook_id,
            "service_pattern": self.service_pattern,
            "consecutive_failures": self.consecutive_failures,
            "enabled": self.enabled,
        }


@dataclass
class MatchedPlaybook:
    """Result of a successful trigger match."""

    playbook_id: int
    playbook_name: str
    trigger_id: int
    service_pattern: str
    consecutive_failures: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "playbook_id": self.playbook_id,
            "playbook_name": self.playbook_name,
            "trigger_id": self.trigger_id,
            "service_pattern": self.service_pattern,
            "consecutive_failures": self.consecutive_failures,
        }


def get_enabled_triggers() -> list[PlaybookTrigger]:
    """
    Get all enabled triggers from the database.

    Returns:
        List of enabled PlaybookTrigger objects ordered by
        consecutive_failures DESC (most specific first)
    """
    result = db.query_db(
        """
        SELECT trigger_id, playbook_id, service_pattern,
               consecutive_failures, enabled
        FROM medic.playbook_triggers
        WHERE enabled = TRUE
        ORDER BY consecutive_failures DESC, trigger_id ASC
        """,
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [_parse_trigger(row) for row in rows if row]


def get_triggers_for_playbook(playbook_id: int) -> list[PlaybookTrigger]:
    """
    Get all triggers associated with a specific playbook.

    Args:
        playbook_id: The playbook ID

    Returns:
        List of PlaybookTrigger objects for the playbook
    """
    result = db.query_db(
        """
        SELECT trigger_id, playbook_id, service_pattern,
               consecutive_failures, enabled
        FROM medic.playbook_triggers
        WHERE playbook_id = %s
        ORDER BY consecutive_failures DESC, trigger_id ASC
        """,
        (playbook_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return []

    rows = json.loads(str(result))
    return [_parse_trigger(row) for row in rows if row]


def find_matching_trigger(
    service_name: str, consecutive_failures: int
) -> Optional[PlaybookTrigger]:
    """
    Find a trigger that matches a service and failure count.

    Triggers are evaluated in order of specificity:
    1. Higher consecutive_failures threshold first (more specific)
    2. Then by trigger_id (deterministic ordering)

    This ensures more specific triggers (requiring more failures)
    are matched before less specific ones.

    Args:
        service_name: Name of the service to match
        consecutive_failures: Number of consecutive failures

    Returns:
        First matching PlaybookTrigger, or None if no match
    """
    triggers = get_enabled_triggers()

    for trigger in triggers:
        if trigger.matches(service_name, consecutive_failures):
            logger.log(
                level=20,
                msg=f"Trigger {trigger.trigger_id} matched service "
                f"'{service_name}' (pattern: '{trigger.service_pattern}', "
                f"failures: {consecutive_failures}/{trigger.consecutive_failures})",
            )
            return trigger

    logger.log(
        level=10,
        msg=f"No trigger matched service '{service_name}' with "
        f"{consecutive_failures} consecutive failures",
    )
    return None


def find_playbook_for_alert(
    service_name: str, consecutive_failures: int
) -> Optional[MatchedPlaybook]:
    """
    Find a playbook that should be triggered for an alert.

    This is the main function to call when an alert fires. It finds
    the most appropriate playbook based on service name and failure count.

    Args:
        service_name: Name of the service that alerted
        consecutive_failures: Number of consecutive failures

    Returns:
        MatchedPlaybook with playbook details, or None if no match
    """
    trigger = find_matching_trigger(service_name, consecutive_failures)
    if not trigger:
        return None

    # Get playbook details
    result = db.query_db(
        """
        SELECT playbook_id, name
        FROM medic.playbooks
        WHERE playbook_id = %s
        """,
        (trigger.playbook_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        logger.log(
            level=30,
            msg=f"Trigger {trigger.trigger_id} references non-existent "
            f"playbook {trigger.playbook_id}",
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    playbook_data = rows[0]

    matched = MatchedPlaybook(
        playbook_id=playbook_data["playbook_id"],
        playbook_name=playbook_data["name"],
        trigger_id=trigger.trigger_id,
        service_pattern=trigger.service_pattern,
        consecutive_failures=trigger.consecutive_failures,
    )

    logger.log(
        level=20,
        msg=f"Playbook '{matched.playbook_name}' (id: {matched.playbook_id}) "
        f"matched for service '{service_name}' with "
        f"{consecutive_failures} consecutive failures",
    )

    return matched


def get_consecutive_failures_for_service(service_id: int) -> int:
    """
    Get the current consecutive failure count for a service.

    This queries the services table for the consecutive failures counter
    that tracks how many times in a row the service has failed.

    Args:
        service_id: The service ID

    Returns:
        Number of consecutive failures (0 if none or not found)
    """
    result = db.query_db(
        """
        SELECT consecutive_failures
        FROM services
        WHERE service_id = %s
        """,
        (service_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return 0

    try:
        rows = json.loads(str(result))
        if rows:
            return int(rows[0].get("consecutive_failures", 0) or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return 0


def get_service_name_by_id(service_id: int) -> Optional[str]:
    """
    Get the name of a service by its ID.

    Args:
        service_id: The service ID

    Returns:
        Service name, or None if not found
    """
    result = db.query_db(
        """
        SELECT name
        FROM services
        WHERE service_id = %s
        """,
        (service_id,),
        show_columns=True,
    )

    if not result or result == "[]":
        return None

    try:
        rows = json.loads(str(result))
        if rows:
            return rows[0].get("name")
    except (json.JSONDecodeError, TypeError):
        pass

    return None


def find_playbook_for_service_alert(service_id: int) -> Optional[MatchedPlaybook]:
    """
    Find a playbook for an alerting service using its ID.

    This is a convenience function that looks up the service name
    and consecutive failures, then finds a matching playbook.

    Args:
        service_id: The service ID that is alerting

    Returns:
        MatchedPlaybook if found, None otherwise
    """
    # Get service name
    service_name = get_service_name_by_id(service_id)
    if not service_name:
        logger.log(
            level=30,
            msg=f"Cannot find playbook for service {service_id}: " "service not found",
        )
        return None

    # Get consecutive failures
    consecutive_failures = get_consecutive_failures_for_service(service_id)

    return find_playbook_for_alert(service_name, consecutive_failures)


def matches_glob_pattern(pattern: str, value: str) -> bool:
    """
    Check if a value matches a glob pattern.

    Case-insensitive matching using fnmatch.

    Args:
        pattern: Glob pattern (e.g., "worker-*", "*-prod-*")
        value: Value to match against

    Returns:
        True if the value matches the pattern
    """
    if not pattern or not value:
        return False
    return fnmatch.fnmatch(value.lower(), pattern.lower())


def _parse_trigger(data: dict[str, Any]) -> PlaybookTrigger:
    """Parse a database row into a PlaybookTrigger object."""
    return PlaybookTrigger(
        trigger_id=data["trigger_id"],
        playbook_id=data["playbook_id"],
        service_pattern=data["service_pattern"],
        consecutive_failures=data.get("consecutive_failures", 1),
        enabled=data.get("enabled", True),
    )
