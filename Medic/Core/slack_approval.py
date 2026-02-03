"""Slack approval module for playbook executions.

This module provides functionality to send Slack messages with interactive
approval buttons and handle the webhook callbacks when users click them.

Key functions:
- send_approval_request: Send Slack message with approve/reject buttons
- handle_slack_interaction: Process button click callbacks
- create_approval_request_record: Create approval request in database
- approve_request: Mark request as approved and resume execution
- reject_request: Mark request as rejected and cancel execution

Usage:
    from Medic.Core.slack_approval import (
        send_approval_request,
        handle_slack_interaction,
    )

    # When playbook execution needs approval
    result = send_approval_request(
        execution_id=123,
        playbook_name="restart-service",
        service_name="worker-prod-01",
        expires_at=datetime.now() + timedelta(minutes=30)
    )

    # In Slack interaction webhook handler
    response = handle_slack_interaction(payload)
"""
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import pytz
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import Medic.Core.database as db
import Medic.Helpers.logSettings as logLevel
from Medic.Core.playbook_engine import (
    ExecutionStatus,
    approve_playbook_execution,
    cancel_playbook_execution,
    get_execution,
    update_execution_status,
)

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Represents an approval request record."""

    request_id: Optional[int]
    execution_id: int
    requested_at: datetime
    expires_at: Optional[datetime]
    status: ApprovalStatus
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Slack message tracking
    slack_message_ts: Optional[str] = None
    slack_channel_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "requested_at": (
                self.requested_at.isoformat() if self.requested_at else None
            ),
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at else None
            ),
            "status": self.status.value,
            "decided_by": self.decided_by,
            "decided_at": (
                self.decided_at.isoformat() if self.decided_at else None
            ),
        }


@dataclass
class ApprovalResult:
    """Result of an approval action."""

    success: bool
    message: str
    request: Optional[ApprovalRequest] = None
    execution_id: Optional[int] = None


def _now() -> datetime:
    """Get current time in Chicago timezone."""
    return datetime.now(pytz.timezone('America/Chicago'))


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse a datetime string in various formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def get_slack_client() -> WebClient:
    """Get a configured Slack WebClient."""
    token = os.environ.get("SLACK_API_TOKEN")
    if not token:
        logger.warning("SLACK_API_TOKEN not set")
    return WebClient(token=token)


def get_slack_channel() -> Optional[str]:
    """Get the default Slack channel ID."""
    return os.environ.get("SLACK_CHANNEL_ID")


def get_slack_signing_secret() -> Optional[str]:
    """Get the Slack signing secret for request verification."""
    return os.environ.get("SLACK_SIGNING_SECRET")


# ============================================================================
# Database Operations
# ============================================================================

def create_approval_request_record(
    execution_id: int,
    expires_at: Optional[datetime] = None,
    slack_message_ts: Optional[str] = None,
    slack_channel_id: Optional[str] = None
) -> Optional[ApprovalRequest]:
    """
    Create an approval request record in the database.

    Args:
        execution_id: ID of the playbook execution
        expires_at: Optional expiration time for the request
        slack_message_ts: Optional Slack message timestamp for updating
        slack_channel_id: Optional Slack channel ID for updating

    Returns:
        ApprovalRequest object on success, None on failure
    """
    now = _now()

    result = db.query_db(
        """
        INSERT INTO medic.approval_requests
        (execution_id, requested_at, expires_at, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING request_id
        """,
        (execution_id, now, expires_at, ApprovalStatus.PENDING.value, now, now),
        show_columns=True
    )

    if not result or result == '[]':
        logger.log(
            level=40,
            msg=f"Failed to create approval request for execution {execution_id}"
        )
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    request_id = rows[0].get('request_id')

    logger.log(
        level=20,
        msg=f"Created approval request {request_id} for execution {execution_id}"
    )

    return ApprovalRequest(
        request_id=request_id,
        execution_id=execution_id,
        requested_at=now,
        expires_at=expires_at,
        status=ApprovalStatus.PENDING,
        decided_by=None,
        decided_at=None,
        created_at=now,
        updated_at=now,
        slack_message_ts=slack_message_ts,
        slack_channel_id=slack_channel_id,
    )


def get_approval_request_by_execution(
    execution_id: int
) -> Optional[ApprovalRequest]:
    """
    Get an approval request by execution ID.

    Args:
        execution_id: The execution ID

    Returns:
        ApprovalRequest object if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT request_id, execution_id, requested_at, expires_at, status,
               decided_by, decided_at, created_at, updated_at
        FROM medic.approval_requests
        WHERE execution_id = %s
        """,
        (execution_id,),
        show_columns=True
    )

    if not result or result == '[]':
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return _parse_approval_request(rows[0])


def get_approval_request(request_id: int) -> Optional[ApprovalRequest]:
    """
    Get an approval request by ID.

    Args:
        request_id: The request ID

    Returns:
        ApprovalRequest object if found, None otherwise
    """
    result = db.query_db(
        """
        SELECT request_id, execution_id, requested_at, expires_at, status,
               decided_by, decided_at, created_at, updated_at
        FROM medic.approval_requests
        WHERE request_id = %s
        """,
        (request_id,),
        show_columns=True
    )

    if not result or result == '[]':
        return None

    rows = json.loads(str(result))
    if not rows:
        return None

    return _parse_approval_request(rows[0])


def get_pending_approval_requests() -> List[ApprovalRequest]:
    """
    Get all pending approval requests.

    Returns:
        List of pending ApprovalRequest objects
    """
    result = db.query_db(
        """
        SELECT request_id, execution_id, requested_at, expires_at, status,
               decided_by, decided_at, created_at, updated_at
        FROM medic.approval_requests
        WHERE status = 'pending'
        ORDER BY requested_at ASC
        """,
        show_columns=True
    )

    if not result or result == '[]':
        return []

    rows = json.loads(str(result))
    return [
        req for req in (_parse_approval_request(r) for r in rows if r)
        if req is not None
    ]


def update_approval_request_status(
    request_id: int,
    status: ApprovalStatus,
    decided_by: Optional[str] = None,
    decided_at: Optional[datetime] = None
) -> bool:
    """
    Update an approval request status.

    Args:
        request_id: The request ID
        status: New status
        decided_by: User who made the decision
        decided_at: Time of decision

    Returns:
        True if updated, False otherwise
    """
    now = _now()

    # For approved/rejected, require decided_by and decided_at
    if status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        if not decided_by:
            logger.log(
                level=30,
                msg=f"Cannot update request {request_id} to {status.value} "
                    "without decided_by"
            )
            return False
        if not decided_at:
            decided_at = now

    # For expired, set decided_at but not decided_by
    if status == ApprovalStatus.EXPIRED:
        decided_at = now
        decided_by = None

    result = db.insert_db(
        """
        UPDATE medic.approval_requests
        SET status = %s, decided_by = %s, decided_at = %s, updated_at = %s
        WHERE request_id = %s
        """,
        (status.value, decided_by, decided_at, now, request_id)
    )

    if result:
        logger.log(
            level=20,
            msg=f"Updated approval request {request_id} to {status.value}"
        )

    return bool(result)


def _parse_approval_request(data: Dict[str, Any]) -> Optional[ApprovalRequest]:
    """Parse a database row into an ApprovalRequest object."""
    try:
        requested_at = data.get('requested_at')
        expires_at = data.get('expires_at')
        decided_at = data.get('decided_at')
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')

        if isinstance(requested_at, str):
            requested_at = _parse_datetime(requested_at)
        if isinstance(expires_at, str):
            expires_at = _parse_datetime(expires_at)
        if isinstance(decided_at, str):
            decided_at = _parse_datetime(decided_at)
        if isinstance(created_at, str):
            created_at = _parse_datetime(created_at)
        if isinstance(updated_at, str):
            updated_at = _parse_datetime(updated_at)

        # requested_at should always be set; if parsing failed, use current time
        if requested_at is None:
            requested_at = _now()

        return ApprovalRequest(
            request_id=data['request_id'],
            execution_id=data['execution_id'],
            requested_at=requested_at,
            expires_at=expires_at,
            status=ApprovalStatus(data['status']),
            decided_by=data.get('decided_by'),
            decided_at=decided_at,
            created_at=created_at,
            updated_at=updated_at,
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.log(level=30, msg=f"Failed to parse approval request data: {e}")
        return None


# ============================================================================
# Slack Interactive Message Functions
# ============================================================================

def build_approval_blocks(
    execution_id: int,
    playbook_name: str,
    service_name: str,
    expires_at: Optional[datetime] = None,
    description: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Build Slack Block Kit blocks for approval message.

    Args:
        execution_id: Playbook execution ID
        playbook_name: Name of the playbook
        service_name: Name of the service
        expires_at: Optional expiration time
        description: Optional description of what the playbook does

    Returns:
        List of Block Kit block dicts
    """
    blocks: List[Dict[str, Any]] = []

    # Header section
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":hourglass: Playbook Approval Required",
            "emoji": True
        }
    })

    # Main info section
    main_text = (
        f"*Playbook:* `{playbook_name}`\n"
        f"*Service:* `{service_name}`\n"
        f"*Execution ID:* `{execution_id}`"
    )
    if description:
        main_text += f"\n*Description:* {description}"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": main_text
        }
    })

    # Expiration warning if applicable
    if expires_at:
        # Format expiration time
        expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S %Z")
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":clock3: _This request expires at {expires_str}_"
                }
            ]
        })

    # Divider before buttons
    blocks.append({"type": "divider"})

    # Action buttons
    blocks.append({
        "type": "actions",
        "block_id": f"approval_actions_{execution_id}",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Approve",
                    "emoji": True
                },
                "style": "primary",
                "action_id": "approve_playbook",
                "value": str(execution_id)
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Decline",
                    "emoji": True
                },
                "style": "danger",
                "action_id": "reject_playbook",
                "value": str(execution_id)
            }
        ]
    })

    return blocks


def build_approval_result_blocks(
    execution_id: int,
    playbook_name: str,
    service_name: str,
    approved: bool,
    decided_by: str,
    decided_at: datetime
) -> List[Dict[str, Any]]:
    """
    Build Slack Block Kit blocks for approval result message (replaces buttons).

    Args:
        execution_id: Playbook execution ID
        playbook_name: Name of the playbook
        service_name: Name of the service
        approved: Whether the playbook was approved
        decided_by: User who made the decision
        decided_at: Time of decision

    Returns:
        List of Block Kit block dicts
    """
    status_emoji = ":white_check_mark:" if approved else ":x:"
    status_text = "Approved" if approved else "Declined"
    header_text = f"{status_emoji} Playbook {status_text}"

    blocks: List[Dict[str, Any]] = []

    # Header section
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header_text,
            "emoji": True
        }
    })

    # Main info section
    decided_str = decided_at.strftime("%Y-%m-%d %H:%M:%S %Z")
    main_text = (
        f"*Playbook:* `{playbook_name}`\n"
        f"*Service:* `{service_name}`\n"
        f"*Execution ID:* `{execution_id}`\n"
        f"*Decision:* {status_text} by <@{decided_by}> at {decided_str}"
    )

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": main_text
        }
    })

    return blocks


def send_approval_request(
    execution_id: int,
    playbook_name: str,
    service_name: str,
    expires_at: Optional[datetime] = None,
    description: Optional[str] = None,
    channel_id: Optional[str] = None,
    slack_client: Optional[WebClient] = None
) -> ApprovalResult:
    """
    Send a Slack message with approval buttons for a playbook execution.

    This function:
    1. Creates an approval_request record in the database
    2. Sends a Slack message with interactive buttons
    3. Returns the result

    Args:
        execution_id: Playbook execution ID
        playbook_name: Name of the playbook
        service_name: Name of the service
        expires_at: Optional expiration time for auto-reject
        description: Optional description of what the playbook does
        channel_id: Optional Slack channel ID (defaults to env var)
        slack_client: Optional Slack client (for testing)

    Returns:
        ApprovalResult with success status and details
    """
    # Get channel ID
    channel = channel_id or get_slack_channel()
    if not channel:
        logger.log(
            level=40,
            msg="SLACK_CHANNEL_ID not configured, cannot send approval request"
        )
        return ApprovalResult(
            success=False,
            message="Slack channel not configured",
            execution_id=execution_id
        )

    # Build message blocks
    blocks = build_approval_blocks(
        execution_id=execution_id,
        playbook_name=playbook_name,
        service_name=service_name,
        expires_at=expires_at,
        description=description
    )

    # Fallback text for notifications
    fallback_text = (
        f"Playbook approval required: {playbook_name} for {service_name} "
        f"(execution: {execution_id})"
    )

    # Get Slack client
    client = slack_client or get_slack_client()

    try:
        # Send the message
        response = client.chat_postMessage(
            channel=channel,
            text=fallback_text,
            blocks=blocks
        )

        if not response.get("ok"):
            error_msg = response.get("error", "Unknown error")
            logger.log(
                level=40,
                msg=f"Failed to send approval request: {error_msg}"
            )
            return ApprovalResult(
                success=False,
                message=f"Failed to send Slack message: {error_msg}",
                execution_id=execution_id
            )

        # Get message timestamp for later updates
        message_ts = response.get("ts")

        # Create approval request record
        request = create_approval_request_record(
            execution_id=execution_id,
            expires_at=expires_at,
            slack_message_ts=message_ts,
            slack_channel_id=channel
        )

        if not request:
            logger.log(
                level=40,
                msg=f"Failed to create approval request record for execution "
                    f"{execution_id}"
            )
            return ApprovalResult(
                success=False,
                message="Failed to create approval request record",
                execution_id=execution_id
            )

        logger.log(
            level=20,
            msg=f"Sent approval request for execution {execution_id} "
                f"(message_ts: {message_ts})"
        )

        return ApprovalResult(
            success=True,
            message="Approval request sent",
            request=request,
            execution_id=execution_id
        )

    except SlackApiError as e:
        error_msg = e.response.get("error", str(e))
        logger.log(
            level=40,
            msg=f"Slack API error sending approval request: {error_msg}"
        )
        return ApprovalResult(
            success=False,
            message=f"Slack API error: {error_msg}",
            execution_id=execution_id
        )
    except Exception as e:
        logger.log(
            level=40,
            msg=f"Error sending approval request: {str(e)}"
        )
        return ApprovalResult(
            success=False,
            message=f"Error: {str(e)}",
            execution_id=execution_id
        )


def update_approval_message(
    channel_id: str,
    message_ts: str,
    execution_id: int,
    playbook_name: str,
    service_name: str,
    approved: bool,
    decided_by: str,
    decided_at: datetime,
    slack_client: Optional[WebClient] = None
) -> bool:
    """
    Update the Slack approval message to show the decision result.

    Replaces the interactive buttons with a static result message.

    Args:
        channel_id: Slack channel ID
        message_ts: Message timestamp
        execution_id: Playbook execution ID
        playbook_name: Name of the playbook
        service_name: Name of the service
        approved: Whether the playbook was approved
        decided_by: User who made the decision
        decided_at: Time of decision
        slack_client: Optional Slack client (for testing)

    Returns:
        True if message was updated, False otherwise
    """
    # Build result blocks
    blocks = build_approval_result_blocks(
        execution_id=execution_id,
        playbook_name=playbook_name,
        service_name=service_name,
        approved=approved,
        decided_by=decided_by,
        decided_at=decided_at
    )

    status_text = "approved" if approved else "declined"
    fallback_text = f"Playbook {status_text}: {playbook_name} for {service_name}"

    # Get Slack client
    client = slack_client or get_slack_client()

    try:
        response = client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text=fallback_text,
            blocks=blocks
        )

        if response.get("ok"):
            logger.log(
                level=20,
                msg=f"Updated approval message for execution {execution_id}"
            )
            return True
        else:
            error_msg = response.get("error", "Unknown error")
            logger.log(
                level=30,
                msg=f"Failed to update approval message: {error_msg}"
            )
            return False

    except SlackApiError as e:
        logger.log(
            level=30,
            msg=f"Slack API error updating approval message: "
                f"{e.response.get('error', str(e))}"
        )
        return False
    except Exception as e:
        logger.log(
            level=30,
            msg=f"Error updating approval message: {str(e)}"
        )
        return False


# ============================================================================
# Approval Action Handlers
# ============================================================================

def approve_request(
    execution_id: int,
    decided_by: str,
    slack_client: Optional[WebClient] = None
) -> ApprovalResult:
    """
    Approve a playbook execution request.

    This function:
    1. Validates the request is pending
    2. Updates the approval_request status to approved
    3. Updates the playbook execution status to running
    4. Resumes the playbook execution
    5. Updates the Slack message

    Args:
        execution_id: Playbook execution ID
        decided_by: Slack user ID who approved
        slack_client: Optional Slack client (for testing)

    Returns:
        ApprovalResult with success status and details
    """
    now = _now()

    # Get the approval request
    request = get_approval_request_by_execution(execution_id)
    if not request:
        return ApprovalResult(
            success=False,
            message=f"No approval request found for execution {execution_id}",
            execution_id=execution_id
        )

    # Validate status is pending
    if request.status != ApprovalStatus.PENDING:
        return ApprovalResult(
            success=False,
            message=f"Request already {request.status.value}",
            request=request,
            execution_id=execution_id
        )

    # Check if expired
    if request.expires_at and now > request.expires_at:
        # Mark as expired
        update_approval_request_status(
            request.request_id or 0,
            ApprovalStatus.EXPIRED
        )
        return ApprovalResult(
            success=False,
            message="Approval request has expired",
            request=request,
            execution_id=execution_id
        )

    # Update approval request status
    if not update_approval_request_status(
        request.request_id or 0,
        ApprovalStatus.APPROVED,
        decided_by=decided_by,
        decided_at=now
    ):
        return ApprovalResult(
            success=False,
            message="Failed to update approval request status",
            request=request,
            execution_id=execution_id
        )

    # Approve and resume playbook execution
    if not approve_playbook_execution(execution_id):
        logger.log(
            level=30,
            msg=f"Failed to resume playbook execution {execution_id} "
                "(may already be running)"
        )
        # Don't fail - the approval was recorded

    logger.log(
        level=20,
        msg=f"Playbook execution {execution_id} approved by {decided_by}"
    )

    # Update the request object
    request.status = ApprovalStatus.APPROVED
    request.decided_by = decided_by
    request.decided_at = now

    return ApprovalResult(
        success=True,
        message=f"Playbook execution {execution_id} approved",
        request=request,
        execution_id=execution_id
    )


def reject_request(
    execution_id: int,
    decided_by: str,
    slack_client: Optional[WebClient] = None
) -> ApprovalResult:
    """
    Reject a playbook execution request.

    This function:
    1. Validates the request is pending
    2. Updates the approval_request status to rejected
    3. Cancels the playbook execution
    4. Updates the Slack message

    Args:
        execution_id: Playbook execution ID
        decided_by: Slack user ID who rejected
        slack_client: Optional Slack client (for testing)

    Returns:
        ApprovalResult with success status and details
    """
    now = _now()

    # Get the approval request
    request = get_approval_request_by_execution(execution_id)
    if not request:
        return ApprovalResult(
            success=False,
            message=f"No approval request found for execution {execution_id}",
            execution_id=execution_id
        )

    # Validate status is pending
    if request.status != ApprovalStatus.PENDING:
        return ApprovalResult(
            success=False,
            message=f"Request already {request.status.value}",
            request=request,
            execution_id=execution_id
        )

    # Check if expired
    if request.expires_at and now > request.expires_at:
        # Mark as expired
        update_approval_request_status(
            request.request_id or 0,
            ApprovalStatus.EXPIRED
        )
        return ApprovalResult(
            success=False,
            message="Approval request has expired",
            request=request,
            execution_id=execution_id
        )

    # Update approval request status
    if not update_approval_request_status(
        request.request_id or 0,
        ApprovalStatus.REJECTED,
        decided_by=decided_by,
        decided_at=now
    ):
        return ApprovalResult(
            success=False,
            message="Failed to update approval request status",
            request=request,
            execution_id=execution_id
        )

    # Cancel playbook execution
    if not cancel_playbook_execution(execution_id):
        logger.log(
            level=30,
            msg=f"Failed to cancel playbook execution {execution_id} "
                "(may already be terminal)"
        )
        # Don't fail - the rejection was recorded

    logger.log(
        level=20,
        msg=f"Playbook execution {execution_id} rejected by {decided_by}"
    )

    # Update the request object
    request.status = ApprovalStatus.REJECTED
    request.decided_by = decided_by
    request.decided_at = now

    return ApprovalResult(
        success=True,
        message=f"Playbook execution {execution_id} rejected",
        request=request,
        execution_id=execution_id
    )


# ============================================================================
# Slack Interaction Webhook Handler
# ============================================================================

def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str
) -> bool:
    """
    Verify the Slack request signature.

    Args:
        signing_secret: Slack app signing secret
        timestamp: X-Slack-Request-Timestamp header
        body: Raw request body
        signature: X-Slack-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    # Check timestamp is not too old (5 minutes)
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            logger.log(level=30, msg="Slack request timestamp too old")
            return False
    except ValueError:
        logger.log(level=30, msg="Invalid Slack request timestamp")
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body}"
    expected_sig = (
        "v0=" +
        hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
    )

    # Compare signatures
    if hmac.compare_digest(expected_sig, signature):
        return True

    logger.log(level=30, msg="Slack signature verification failed")
    return False


@dataclass
class SlackInteractionResult:
    """Result of handling a Slack interaction."""

    success: bool
    message: str
    response_action: Optional[str] = None  # "update", "errors", etc.
    response_blocks: Optional[List[Dict[str, Any]]] = None


def handle_slack_interaction(
    payload: Dict[str, Any],
    slack_client: Optional[WebClient] = None
) -> SlackInteractionResult:
    """
    Handle a Slack interaction webhook callback.

    This is called when a user clicks an interactive button in a Slack message.

    Args:
        payload: The parsed Slack interaction payload
        slack_client: Optional Slack client (for testing)

    Returns:
        SlackInteractionResult with response details
    """
    # Extract interaction details
    interaction_type = payload.get("type")
    if interaction_type != "block_actions":
        return SlackInteractionResult(
            success=False,
            message=f"Unsupported interaction type: {interaction_type}"
        )

    actions = payload.get("actions", [])
    if not actions:
        return SlackInteractionResult(
            success=False,
            message="No actions in payload"
        )

    action = actions[0]
    action_id = action.get("action_id")
    execution_id_str = action.get("value")

    # Validate action
    if action_id not in ("approve_playbook", "reject_playbook"):
        return SlackInteractionResult(
            success=False,
            message=f"Unknown action: {action_id}"
        )

    # Parse execution ID
    try:
        execution_id = int(execution_id_str)
    except (ValueError, TypeError):
        return SlackInteractionResult(
            success=False,
            message=f"Invalid execution ID: {execution_id_str}"
        )

    # Get user info
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")

    # Get message info for updating
    message = payload.get("message", {})
    message_ts = message.get("ts")
    channel = payload.get("channel", {})
    channel_id = channel.get("id")

    # Get playbook and service info from execution
    execution = get_execution(execution_id)
    playbook_name = "Unknown"
    service_name = "Unknown"

    if execution:
        # Try to get playbook name
        playbook_result = db.query_db(
            "SELECT name FROM medic.playbooks WHERE playbook_id = %s",
            (execution.playbook_id,),
            show_columns=True
        )
        if playbook_result and playbook_result != '[]':
            rows = json.loads(str(playbook_result))
            if rows:
                playbook_name = rows[0].get('name', 'Unknown')

        # Try to get service name
        if execution.service_id:
            service_result = db.query_db(
                "SELECT name FROM services WHERE service_id = %s",
                (execution.service_id,),
                show_columns=True
            )
            if service_result and service_result != '[]':
                rows = json.loads(str(service_result))
                if rows:
                    service_name = rows[0].get('name', 'Unknown')

    # Process the action
    if action_id == "approve_playbook":
        result = approve_request(execution_id, user_id, slack_client)
        approved = True
    else:
        result = reject_request(execution_id, user_id, slack_client)
        approved = False

    if not result.success:
        logger.log(
            level=30,
            msg=f"Failed to process {action_id} for execution {execution_id}: "
                f"{result.message}"
        )
        return SlackInteractionResult(
            success=False,
            message=result.message
        )

    # Update the Slack message to show result
    if message_ts and channel_id:
        decided_at = (
            result.request.decided_at if result.request and result.request.decided_at
            else _now()
        )
        update_approval_message(
            channel_id=channel_id,
            message_ts=message_ts,
            execution_id=execution_id,
            playbook_name=playbook_name,
            service_name=service_name,
            approved=approved,
            decided_by=user_id,
            decided_at=decided_at,
            slack_client=slack_client
        )

    return SlackInteractionResult(
        success=True,
        message=result.message,
        response_action="update"
    )


def expire_pending_requests() -> int:
    """
    Check for and expire pending approval requests that have passed their
    expiration time.

    This should be called periodically (e.g., by a cron job or the monitor).

    Returns:
        Number of requests expired
    """
    now = _now()

    # Find expired requests
    result = db.query_db(
        """
        SELECT request_id, execution_id
        FROM medic.approval_requests
        WHERE status = 'pending'
          AND expires_at IS NOT NULL
          AND expires_at < %s
        """,
        (now,),
        show_columns=True
    )

    if not result or result == '[]':
        return 0

    rows = json.loads(str(result))
    expired_count = 0

    for row in rows:
        request_id = row.get('request_id')
        execution_id = row.get('execution_id')

        # Update request status to expired
        if update_approval_request_status(request_id, ApprovalStatus.EXPIRED):
            # Cancel the execution
            cancel_playbook_execution(execution_id)
            expired_count += 1

            logger.log(
                level=20,
                msg=f"Expired approval request {request_id} "
                    f"(execution: {execution_id})"
            )

    return expired_count
