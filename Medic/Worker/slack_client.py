"""Slack client for Medic notifications."""

import os
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Import metrics (optional - graceful degradation)
try:
    from Medic.Core.metrics import record_slack_request

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    record_slack_request = None  # type: ignore[misc, assignment]


def get_client() -> WebClient:
    """Get a configured Slack WebClient."""
    token = os.environ.get("SLACK_API_TOKEN")
    if not token:
        logger.warning("SLACK_API_TOKEN not set")
    return WebClient(token=token)


def send_message(message: str) -> bool:
    """
    Send a message to the configured Slack channel.

    Args:
        message: The message text to send

    Returns:
        True on success, False on failure
    """
    slack_channel = os.environ.get("SLACK_CHANNEL_ID")
    if not slack_channel:
        logger.warning("SLACK_CHANNEL_ID not set, skipping Slack notification")
        return False

    try:
        client = get_client()
        response = client.chat_postMessage(channel=slack_channel, text=message)
        success = response["ok"]
        if METRICS_AVAILABLE and record_slack_request is not None:
            record_slack_request(success=success)
        return success
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        if METRICS_AVAILABLE and record_slack_request is not None:
            record_slack_request(success=False)
        return False
    except Exception as e:
        logger.error(f"Failed to send Slack message: {str(e)}")
        if METRICS_AVAILABLE and record_slack_request is not None:
            record_slack_request(success=False)
        return False
