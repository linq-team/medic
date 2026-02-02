"""Slack client for Medic notifications."""
import os
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


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
        response = client.chat_postMessage(
            channel=slack_channel,
            text=message
        )
        return response["ok"]
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        return False
    except Exception as e:
        logger.error(f"Failed to send Slack message: {str(e)}")
        return False
