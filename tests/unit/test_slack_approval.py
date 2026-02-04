"""Unit tests for slack_approval module."""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytz


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_approval_status_values(self):
        """Test ApprovalStatus enum has expected values."""
        from Medic.Core.slack_approval import ApprovalStatus

        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EXPIRED.value == "expired"


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""

    def test_approval_request_creation(self):
        """Test creating an ApprovalRequest object."""
        from Medic.Core.slack_approval import ApprovalRequest, ApprovalStatus

        now = datetime.now(pytz.timezone('America/Chicago'))
        request = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now,
            expires_at=now + timedelta(minutes=30),
            status=ApprovalStatus.PENDING,
            decided_by=None,
            decided_at=None,
        )

        assert request.request_id == 1
        assert request.execution_id == 100
        assert request.status == ApprovalStatus.PENDING
        assert request.decided_by is None
        assert request.decided_at is None

    def test_approval_request_to_dict(self):
        """Test ApprovalRequest.to_dict() method."""
        from Medic.Core.slack_approval import ApprovalRequest, ApprovalStatus

        now = datetime.now(pytz.timezone('America/Chicago'))
        expires = now + timedelta(minutes=30)
        request = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now,
            expires_at=expires,
            status=ApprovalStatus.PENDING,
            decided_by=None,
            decided_at=None,
        )

        result = request.to_dict()

        assert result["request_id"] == 1
        assert result["execution_id"] == 100
        assert result["status"] == "pending"
        assert result["decided_by"] is None
        assert result["decided_at"] is None
        assert now.isoformat() in result["requested_at"]


class TestApprovalResult:
    """Tests for ApprovalResult dataclass."""

    def test_approval_result_success(self):
        """Test creating a successful ApprovalResult."""
        from Medic.Core.slack_approval import ApprovalResult

        result = ApprovalResult(
            success=True,
            message="Approval sent",
            execution_id=100
        )

        assert result.success is True
        assert result.message == "Approval sent"
        assert result.execution_id == 100

    def test_approval_result_failure(self):
        """Test creating a failed ApprovalResult."""
        from Medic.Core.slack_approval import ApprovalResult

        result = ApprovalResult(
            success=False,
            message="Channel not configured",
            execution_id=100
        )

        assert result.success is False
        assert "Channel not configured" in result.message


class TestBuildApprovalBlocks:
    """Tests for build_approval_blocks function."""

    def test_build_approval_blocks_basic(self):
        """Test building basic approval blocks."""
        from Medic.Core.slack_approval import build_approval_blocks

        blocks = build_approval_blocks(
            execution_id=123,
            playbook_name="restart-service",
            service_name="worker-prod-01"
        )

        # Should have header, section, divider, actions
        assert len(blocks) >= 4

        # Check header
        assert blocks[0]["type"] == "header"
        assert "Approval Required" in blocks[0]["text"]["text"]

        # Check section has playbook and service info
        section = blocks[1]
        assert section["type"] == "section"
        assert "restart-service" in section["text"]["text"]
        assert "worker-prod-01" in section["text"]["text"]
        assert "123" in section["text"]["text"]

        # Check actions block has buttons
        actions = [b for b in blocks if b["type"] == "actions"][0]
        assert len(actions["elements"]) == 2

        # Check approve button
        approve_btn = actions["elements"][0]
        assert approve_btn["action_id"] == "approve_playbook"
        assert approve_btn["style"] == "primary"
        assert approve_btn["value"] == "123"

        # Check decline button
        decline_btn = actions["elements"][1]
        assert decline_btn["action_id"] == "reject_playbook"
        assert decline_btn["style"] == "danger"
        assert decline_btn["value"] == "123"

    def test_build_approval_blocks_with_expiration(self):
        """Test building approval blocks with expiration time."""
        from Medic.Core.slack_approval import build_approval_blocks

        expires_at = datetime.now(pytz.timezone('America/Chicago')) + \
            timedelta(minutes=30)

        blocks = build_approval_blocks(
            execution_id=123,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            expires_at=expires_at
        )

        # Should have context block with expiration
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 1
        assert "expires" in context_blocks[0]["elements"][0]["text"].lower()

    def test_build_approval_blocks_with_description(self):
        """Test building approval blocks with description."""
        from Medic.Core.slack_approval import build_approval_blocks

        blocks = build_approval_blocks(
            execution_id=123,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            description="This will restart the worker service"
        )

        # Check description is in section
        section = blocks[1]
        assert "This will restart the worker service" in section["text"]["text"]


class TestBuildApprovalResultBlocks:
    """Tests for build_approval_result_blocks function."""

    def test_build_approval_result_blocks_approved(self):
        """Test building result blocks for approved playbook."""
        from Medic.Core.slack_approval import build_approval_result_blocks

        now = datetime.now(pytz.timezone('America/Chicago'))
        blocks = build_approval_result_blocks(
            execution_id=123,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            approved=True,
            decided_by="U12345",
            decided_at=now
        )

        # Check header shows approved
        assert blocks[0]["type"] == "header"
        assert "Approved" in blocks[0]["text"]["text"]
        assert ":white_check_mark:" in blocks[0]["text"]["text"]

        # Check section has decision info
        section = blocks[1]
        assert "Approved" in section["text"]["text"]
        assert "<@U12345>" in section["text"]["text"]

    def test_build_approval_result_blocks_declined(self):
        """Test building result blocks for declined playbook."""
        from Medic.Core.slack_approval import build_approval_result_blocks

        now = datetime.now(pytz.timezone('America/Chicago'))
        blocks = build_approval_result_blocks(
            execution_id=123,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            approved=False,
            decided_by="U12345",
            decided_at=now
        )

        # Check header shows declined
        assert blocks[0]["type"] == "header"
        assert "Declined" in blocks[0]["text"]["text"]
        assert ":x:" in blocks[0]["text"]["text"]

        # Check section has decision info
        section = blocks[1]
        assert "Declined" in section["text"]["text"]
        assert "<@U12345>" in section["text"]["text"]


class TestVerifySlackSignature:
    """Tests for verify_slack_signature function."""

    def test_verify_slack_signature_valid(self):
        """Test signature verification with valid signature."""
        from Medic.Core.slack_approval import verify_slack_signature

        signing_secret = "test_secret_123"
        timestamp = str(int(time.time()))
        body = "payload=test_data"

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_sig = "v0=" + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        result = verify_slack_signature(
            signing_secret, timestamp, body, expected_sig
        )
        assert result is True

    def test_verify_slack_signature_invalid(self):
        """Test signature verification with invalid signature."""
        from Medic.Core.slack_approval import verify_slack_signature

        signing_secret = "test_secret_123"
        timestamp = str(int(time.time()))
        body = "payload=test_data"

        result = verify_slack_signature(
            signing_secret, timestamp, body, "v0=invalid_signature"
        )
        assert result is False

    def test_verify_slack_signature_old_timestamp(self):
        """Test signature verification rejects old timestamps."""
        from Medic.Core.slack_approval import verify_slack_signature

        signing_secret = "test_secret_123"
        # 10 minutes ago - too old
        timestamp = str(int(time.time()) - 600)
        body = "payload=test_data"

        # Compute valid signature but with old timestamp
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = "v0=" + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        result = verify_slack_signature(
            signing_secret, timestamp, body, signature
        )
        assert result is False

    def test_verify_slack_signature_invalid_timestamp(self):
        """Test signature verification with invalid timestamp."""
        from Medic.Core.slack_approval import verify_slack_signature

        result = verify_slack_signature(
            "secret", "not_a_number", "body", "v0=sig"
        )
        assert result is False


class TestCreateApprovalRequestRecord:
    """Tests for create_approval_request_record function."""

    @patch('Medic.Core.slack_approval.db')
    def test_create_approval_request_success(self, mock_db):
        """Test successful creation of approval request."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            create_approval_request_record,
        )

        # Mock successful insert
        mock_db.query_db.return_value = json.dumps([{"request_id": 1}])

        result = create_approval_request_record(execution_id=100)

        assert result is not None
        assert result.request_id == 1
        assert result.execution_id == 100
        assert result.status == ApprovalStatus.PENDING

        # Verify query was called
        mock_db.query_db.assert_called_once()

    @patch('Medic.Core.slack_approval.db')
    def test_create_approval_request_failure(self, mock_db):
        """Test failed creation of approval request."""
        from Medic.Core.slack_approval import create_approval_request_record

        # Mock failed insert
        mock_db.query_db.return_value = '[]'

        result = create_approval_request_record(execution_id=100)

        assert result is None

    @patch('Medic.Core.slack_approval.db')
    def test_create_approval_request_with_expiration(self, mock_db):
        """Test creating approval request with expiration."""
        from Medic.Core.slack_approval import create_approval_request_record

        mock_db.query_db.return_value = json.dumps([{"request_id": 1}])

        expires_at = datetime.now(pytz.timezone('America/Chicago')) + \
            timedelta(minutes=30)

        result = create_approval_request_record(
            execution_id=100,
            expires_at=expires_at
        )

        assert result is not None
        assert result.expires_at == expires_at


class TestGetApprovalRequest:
    """Tests for get_approval_request functions."""

    @patch('Medic.Core.slack_approval.db')
    def test_get_approval_request_by_execution_found(self, mock_db):
        """Test finding approval request by execution ID."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            get_approval_request_by_execution,
        )

        mock_db.query_db.return_value = json.dumps([{
            "request_id": 1,
            "execution_id": 100,
            "requested_at": "2026-02-03T10:00:00",
            "expires_at": None,
            "status": "pending",
            "decided_by": None,
            "decided_at": None,
            "created_at": "2026-02-03T10:00:00",
            "updated_at": "2026-02-03T10:00:00",
        }])

        result = get_approval_request_by_execution(100)

        assert result is not None
        assert result.request_id == 1
        assert result.execution_id == 100
        assert result.status == ApprovalStatus.PENDING

    @patch('Medic.Core.slack_approval.db')
    def test_get_approval_request_by_execution_not_found(self, mock_db):
        """Test approval request not found by execution ID."""
        from Medic.Core.slack_approval import get_approval_request_by_execution

        mock_db.query_db.return_value = '[]'

        result = get_approval_request_by_execution(100)

        assert result is None

    @patch('Medic.Core.slack_approval.db')
    def test_get_approval_request_by_id(self, mock_db):
        """Test finding approval request by request ID."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            get_approval_request,
        )

        mock_db.query_db.return_value = json.dumps([{
            "request_id": 1,
            "execution_id": 100,
            "requested_at": "2026-02-03T10:00:00",
            "expires_at": None,
            "status": "approved",
            "decided_by": "U12345",
            "decided_at": "2026-02-03T10:05:00",
            "created_at": "2026-02-03T10:00:00",
            "updated_at": "2026-02-03T10:05:00",
        }])

        result = get_approval_request(1)

        assert result is not None
        assert result.request_id == 1
        assert result.status == ApprovalStatus.APPROVED
        assert result.decided_by == "U12345"


class TestUpdateApprovalRequestStatus:
    """Tests for update_approval_request_status function."""

    @patch('Medic.Core.slack_approval.db')
    def test_update_status_to_approved(self, mock_db):
        """Test updating status to approved."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            update_approval_request_status,
        )

        mock_db.insert_db.return_value = True

        result = update_approval_request_status(
            request_id=1,
            status=ApprovalStatus.APPROVED,
            decided_by="U12345"
        )

        assert result is True
        mock_db.insert_db.assert_called_once()

    @patch('Medic.Core.slack_approval.db')
    def test_update_status_to_rejected(self, mock_db):
        """Test updating status to rejected."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            update_approval_request_status,
        )

        mock_db.insert_db.return_value = True

        result = update_approval_request_status(
            request_id=1,
            status=ApprovalStatus.REJECTED,
            decided_by="U12345"
        )

        assert result is True

    @patch('Medic.Core.slack_approval.db')
    def test_update_status_to_approved_without_decided_by(self, mock_db):
        """Test that approved status requires decided_by."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            update_approval_request_status,
        )

        result = update_approval_request_status(
            request_id=1,
            status=ApprovalStatus.APPROVED,
            decided_by=None  # Missing required field
        )

        assert result is False
        mock_db.insert_db.assert_not_called()

    @patch('Medic.Core.slack_approval.db')
    def test_update_status_to_expired(self, mock_db):
        """Test updating status to expired."""
        from Medic.Core.slack_approval import (
            ApprovalStatus,
            update_approval_request_status,
        )

        mock_db.insert_db.return_value = True

        result = update_approval_request_status(
            request_id=1,
            status=ApprovalStatus.EXPIRED
        )

        assert result is True


class TestSendApprovalRequest:
    """Tests for send_approval_request function."""

    @patch('Medic.Core.slack_approval.create_approval_request_record')
    @patch('Medic.Core.slack_approval.get_slack_channel')
    def test_send_approval_request_success(
        self, mock_get_channel, mock_create_record
    ):
        """Test successfully sending approval request."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalStatus,
            send_approval_request,
        )

        mock_get_channel.return_value = "C12345"

        # Mock Slack client
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.123456"
        }

        # Mock record creation
        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_create_record.return_value = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now,
            expires_at=None,
            status=ApprovalStatus.PENDING,
            decided_by=None,
            decided_at=None,
            slack_message_ts="1234567890.123456",
            slack_channel_id="C12345"
        )

        result = send_approval_request(
            execution_id=100,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            slack_client=mock_client
        )

        assert result.success is True
        assert result.execution_id == 100
        assert result.request is not None
        mock_client.chat_postMessage.assert_called_once()

    @patch('Medic.Core.slack_approval.get_slack_channel')
    def test_send_approval_request_no_channel(self, mock_get_channel):
        """Test sending approval request with no channel configured."""
        from Medic.Core.slack_approval import send_approval_request

        mock_get_channel.return_value = None

        result = send_approval_request(
            execution_id=100,
            playbook_name="restart-service",
            service_name="worker-prod-01"
        )

        assert result.success is False
        assert "channel not configured" in result.message.lower()

    @patch('Medic.Core.slack_approval.get_slack_channel')
    def test_send_approval_request_slack_error(self, mock_get_channel):
        """Test handling Slack API error."""
        from slack_sdk.errors import SlackApiError

        from Medic.Core.slack_approval import send_approval_request

        mock_get_channel.return_value = "C12345"

        # Mock Slack client that raises error
        mock_client = MagicMock()
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="Error",
            response={"error": "channel_not_found"}
        )

        result = send_approval_request(
            execution_id=100,
            playbook_name="restart-service",
            service_name="worker-prod-01",
            slack_client=mock_client
        )

        assert result.success is False
        assert "slack api error" in result.message.lower()


class TestApproveRequest:
    """Tests for approve_request function."""

    @patch('Medic.Core.slack_approval.approve_playbook_execution')
    @patch('Medic.Core.slack_approval.update_approval_request_status')
    @patch('Medic.Core.slack_approval.get_approval_request_by_execution')
    def test_approve_request_success(
        self, mock_get_request, mock_update_status, mock_approve_execution
    ):
        """Test successfully approving a request."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalStatus,
            approve_request,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_get_request.return_value = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now,
            expires_at=None,
            status=ApprovalStatus.PENDING,
            decided_by=None,
            decided_at=None,
        )
        mock_update_status.return_value = True
        mock_approve_execution.return_value = True

        result = approve_request(
            execution_id=100,
            decided_by="U12345"
        )

        assert result.success is True
        assert result.request.status == ApprovalStatus.APPROVED
        assert result.request.decided_by == "U12345"
        mock_approve_execution.assert_called_once_with(100)

    @patch('Medic.Core.slack_approval.get_approval_request_by_execution')
    def test_approve_request_not_found(self, mock_get_request):
        """Test approving a non-existent request."""
        from Medic.Core.slack_approval import approve_request

        mock_get_request.return_value = None

        result = approve_request(
            execution_id=100,
            decided_by="U12345"
        )

        assert result.success is False
        assert "no approval request found" in result.message.lower()

    @patch('Medic.Core.slack_approval.get_approval_request_by_execution')
    def test_approve_request_already_approved(self, mock_get_request):
        """Test approving an already approved request."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalStatus,
            approve_request,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_get_request.return_value = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now,
            expires_at=None,
            status=ApprovalStatus.APPROVED,  # Already approved
            decided_by="U99999",
            decided_at=now,
        )

        result = approve_request(
            execution_id=100,
            decided_by="U12345"
        )

        assert result.success is False
        assert "already approved" in result.message.lower()

    @patch('Medic.Core.slack_approval.update_approval_request_status')
    @patch('Medic.Core.slack_approval.get_approval_request_by_execution')
    def test_approve_request_expired(
        self, mock_get_request, mock_update_status
    ):
        """Test approving an expired request."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalStatus,
            approve_request,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        # Expired 5 minutes ago
        expired_at = now - timedelta(minutes=5)
        mock_get_request.return_value = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now - timedelta(minutes=35),
            expires_at=expired_at,
            status=ApprovalStatus.PENDING,
            decided_by=None,
            decided_at=None,
        )
        mock_update_status.return_value = True

        result = approve_request(
            execution_id=100,
            decided_by="U12345"
        )

        assert result.success is False
        assert "expired" in result.message.lower()


class TestRejectRequest:
    """Tests for reject_request function."""

    @patch('Medic.Core.slack_approval.cancel_playbook_execution')
    @patch('Medic.Core.slack_approval.update_approval_request_status')
    @patch('Medic.Core.slack_approval.get_approval_request_by_execution')
    def test_reject_request_success(
        self, mock_get_request, mock_update_status, mock_cancel_execution
    ):
        """Test successfully rejecting a request."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalStatus,
            reject_request,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))
        mock_get_request.return_value = ApprovalRequest(
            request_id=1,
            execution_id=100,
            requested_at=now,
            expires_at=None,
            status=ApprovalStatus.PENDING,
            decided_by=None,
            decided_at=None,
        )
        mock_update_status.return_value = True
        mock_cancel_execution.return_value = True

        result = reject_request(
            execution_id=100,
            decided_by="U12345"
        )

        assert result.success is True
        assert result.request.status == ApprovalStatus.REJECTED
        assert result.request.decided_by == "U12345"
        mock_cancel_execution.assert_called_once_with(100)

    @patch('Medic.Core.slack_approval.get_approval_request_by_execution')
    def test_reject_request_not_found(self, mock_get_request):
        """Test rejecting a non-existent request."""
        from Medic.Core.slack_approval import reject_request

        mock_get_request.return_value = None

        result = reject_request(
            execution_id=100,
            decided_by="U12345"
        )

        assert result.success is False
        assert "no approval request found" in result.message.lower()


class TestHandleSlackInteraction:
    """Tests for handle_slack_interaction function."""

    @patch('Medic.Core.slack_approval.update_approval_message')
    @patch('Medic.Core.slack_approval.approve_request')
    @patch('Medic.Core.slack_approval.get_execution')
    @patch('Medic.Core.slack_approval.db')
    def test_handle_approve_action(
        self, mock_db, mock_get_execution, mock_approve, mock_update_msg
    ):
        """Test handling approve button click."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalResult,
            ApprovalStatus,
            handle_slack_interaction,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))

        # Mock execution lookup
        mock_execution = MagicMock()
        mock_execution.playbook_id = 1
        mock_execution.service_id = 10
        mock_get_execution.return_value = mock_execution

        # Mock DB queries for playbook/service names
        mock_db.query_db.return_value = json.dumps([{"name": "test-playbook"}])

        # Mock approve_request
        mock_approve.return_value = ApprovalResult(
            success=True,
            message="Approved",
            request=ApprovalRequest(
                request_id=1,
                execution_id=100,
                requested_at=now,
                expires_at=None,
                status=ApprovalStatus.APPROVED,
                decided_by="U12345",
                decided_at=now,
            ),
            execution_id=100
        )

        mock_update_msg.return_value = True

        payload = {
            "type": "block_actions",
            "actions": [{
                "action_id": "approve_playbook",
                "value": "100"
            }],
            "user": {"id": "U12345"},
            "message": {"ts": "1234567890.123456"},
            "channel": {"id": "C12345"}
        }

        result = handle_slack_interaction(payload)

        assert result.success is True
        mock_approve.assert_called_once_with(100, "U12345", None)

    @patch('Medic.Core.slack_approval.update_approval_message')
    @patch('Medic.Core.slack_approval.reject_request')
    @patch('Medic.Core.slack_approval.get_execution')
    @patch('Medic.Core.slack_approval.db')
    def test_handle_reject_action(
        self, mock_db, mock_get_execution, mock_reject, mock_update_msg
    ):
        """Test handling reject button click."""
        from Medic.Core.slack_approval import (
            ApprovalRequest,
            ApprovalResult,
            ApprovalStatus,
            handle_slack_interaction,
        )

        now = datetime.now(pytz.timezone('America/Chicago'))

        # Mock execution lookup
        mock_execution = MagicMock()
        mock_execution.playbook_id = 1
        mock_execution.service_id = 10
        mock_get_execution.return_value = mock_execution

        # Mock DB queries for playbook/service names
        mock_db.query_db.return_value = json.dumps([{"name": "test-playbook"}])

        # Mock reject_request
        mock_reject.return_value = ApprovalResult(
            success=True,
            message="Rejected",
            request=ApprovalRequest(
                request_id=1,
                execution_id=100,
                requested_at=now,
                expires_at=None,
                status=ApprovalStatus.REJECTED,
                decided_by="U12345",
                decided_at=now,
            ),
            execution_id=100
        )

        mock_update_msg.return_value = True

        payload = {
            "type": "block_actions",
            "actions": [{
                "action_id": "reject_playbook",
                "value": "100"
            }],
            "user": {"id": "U12345"},
            "message": {"ts": "1234567890.123456"},
            "channel": {"id": "C12345"}
        }

        result = handle_slack_interaction(payload)

        assert result.success is True
        mock_reject.assert_called_once_with(100, "U12345", None)

    def test_handle_invalid_interaction_type(self):
        """Test handling invalid interaction type."""
        from Medic.Core.slack_approval import handle_slack_interaction

        payload = {
            "type": "message_action",  # Wrong type
            "actions": []
        }

        result = handle_slack_interaction(payload)

        assert result.success is False
        assert "unsupported" in result.message.lower()

    def test_handle_unknown_action(self):
        """Test handling unknown action ID."""
        from Medic.Core.slack_approval import handle_slack_interaction

        payload = {
            "type": "block_actions",
            "actions": [{
                "action_id": "unknown_action",
                "value": "100"
            }]
        }

        result = handle_slack_interaction(payload)

        assert result.success is False
        assert "unknown action" in result.message.lower()

    def test_handle_invalid_execution_id(self):
        """Test handling invalid execution ID."""
        from Medic.Core.slack_approval import handle_slack_interaction

        payload = {
            "type": "block_actions",
            "actions": [{
                "action_id": "approve_playbook",
                "value": "not_a_number"
            }]
        }

        result = handle_slack_interaction(payload)

        assert result.success is False
        assert "invalid execution id" in result.message.lower()


class TestExpirePendingRequests:
    """Tests for expire_pending_requests function."""

    @patch('Medic.Core.slack_approval.cancel_playbook_execution')
    @patch('Medic.Core.slack_approval.update_approval_request_status')
    @patch('Medic.Core.slack_approval.db')
    def test_expire_pending_requests(
        self, mock_db, mock_update_status, mock_cancel
    ):
        """Test expiring pending requests."""
        from Medic.Core.slack_approval import expire_pending_requests

        # Mock finding expired requests
        mock_db.query_db.return_value = json.dumps([
            {"request_id": 1, "execution_id": 100},
            {"request_id": 2, "execution_id": 200},
        ])
        mock_update_status.return_value = True
        mock_cancel.return_value = True

        count = expire_pending_requests()

        assert count == 2
        assert mock_update_status.call_count == 2
        assert mock_cancel.call_count == 2

    @patch('Medic.Core.slack_approval.db')
    def test_expire_pending_requests_none_expired(self, mock_db):
        """Test when no requests are expired."""
        from Medic.Core.slack_approval import expire_pending_requests

        mock_db.query_db.return_value = '[]'

        count = expire_pending_requests()

        assert count == 0


class TestUpdateApprovalMessage:
    """Tests for update_approval_message function."""

    def test_update_approval_message_success(self):
        """Test successfully updating approval message."""
        from Medic.Core.slack_approval import update_approval_message

        mock_client = MagicMock()
        mock_client.chat_update.return_value = {"ok": True}

        now = datetime.now(pytz.timezone('America/Chicago'))
        result = update_approval_message(
            channel_id="C12345",
            message_ts="1234567890.123456",
            execution_id=100,
            playbook_name="test-playbook",
            service_name="test-service",
            approved=True,
            decided_by="U12345",
            decided_at=now,
            slack_client=mock_client
        )

        assert result is True
        mock_client.chat_update.assert_called_once()

    def test_update_approval_message_failure(self):
        """Test failed message update."""
        from Medic.Core.slack_approval import update_approval_message

        mock_client = MagicMock()
        mock_client.chat_update.return_value = {
            "ok": False,
            "error": "message_not_found"
        }

        now = datetime.now(pytz.timezone('America/Chicago'))
        result = update_approval_message(
            channel_id="C12345",
            message_ts="1234567890.123456",
            execution_id=100,
            playbook_name="test-playbook",
            service_name="test-service",
            approved=True,
            decided_by="U12345",
            decided_at=now,
            slack_client=mock_client
        )

        assert result is False
