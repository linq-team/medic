import os
import requests
import logging
from typing import Optional

# Log Setup
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Default base URL, configurable via environment variable
DEFAULT_BASE_URL = "https://medic.example.com"


def get_base_url() -> str:
    """Get the Medic API base URL from environment or use default."""
    return os.environ.get("MEDIC_BASE_URL", DEFAULT_BASE_URL)


def SendHeartbeat(
    heartbeat_name: str, service_name: str, status: str, base_url: Optional[str] = None
) -> bool:
    """
    Send a heartbeat to the Medic service.

    Args:
        heartbeat_name: The name of the registered heartbeat
        service_name: The name of the associated service
        status: Current status (UP/DOWN/DEGRADED/etc)
        base_url: Optional base URL override. If not provided, uses MEDIC_BASE_URL env var

    Returns:
        True on success, False on failure
    """
    try:
        url = f"{base_url or get_base_url()}/heartbeat"
        payload = {
            "heartbeat_name": heartbeat_name,
            "service_name": service_name,
            "status": status,
        }
        headers = {
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code >= 300:
            logger.warning("Unable to post heartbeat: %s", response.text)
            return False

        return True
    except requests.RequestException as e:
        logger.error("Failed to Send Heartbeat. Upstream Error: %s", str(e))
        return False
