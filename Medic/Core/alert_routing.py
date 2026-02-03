"""Team-based alert routing for Medic.

This module provides functionality to route alerts to the appropriate
Slack channel based on the service's team configuration. If a service
has a team with a Slack channel, alerts are sent there. Otherwise,
alerts fall back to the default channel.
"""
import os
import json
import logging
from typing import Optional

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
