"""Unit tests for webhook delivery service."""
import json
import time
from unittest.mock import MagicMock, patch

import requests


class TestDeliveryStatus:
    """Tests for DeliveryStatus enum."""

    def test_enum_values(self):
        """Test that DeliveryStatus has correct values."""
        from Medic.Core.webhook_delivery import DeliveryStatus

        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SUCCESS.value == "success"
        assert DeliveryStatus.FAILED.value == "failed"
        assert DeliveryStatus.RETRYING.value == "retrying"

    def test_string_conversion(self):
        """Test DeliveryStatus converts to string correctly via .value."""
        from Medic.Core.webhook_delivery import DeliveryStatus

        # str(Enum) inherits from str, so direct comparison works
        assert DeliveryStatus.PENDING == "pending"
        assert DeliveryStatus.SUCCESS == "success"
        # .value also works
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SUCCESS.value == "success"


class TestWebhookConfig:
    """Tests for WebhookConfig dataclass."""

    def test_create_config(self):
        """Test creating a WebhookConfig."""
        from Medic.Core.webhook_delivery import WebhookConfig

        config = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={"X-Custom": "value"},
            enabled=True,
            service_id=42,
        )

        assert config.webhook_id == 1
        assert config.url == "https://example.com/webhook"
        assert config.headers == {"X-Custom": "value"}
        assert config.enabled is True
        assert config.service_id == 42

    def test_default_values(self):
        """Test WebhookConfig default values."""
        from Medic.Core.webhook_delivery import WebhookConfig

        config = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
        )

        assert config.enabled is True
        assert config.service_id is None


class TestDeliveryResult:
    """Tests for DeliveryResult dataclass."""

    def test_success_result(self):
        """Test creating a successful DeliveryResult."""
        from Medic.Core.webhook_delivery import DeliveryResult

        result = DeliveryResult(
            success=True,
            status_code=200,
            response_body='{"ok": true}',
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.response_body == '{"ok": true}'
        assert result.error_message is None

    def test_failure_result(self):
        """Test creating a failed DeliveryResult."""
        from Medic.Core.webhook_delivery import DeliveryResult

        result = DeliveryResult(
            success=False,
            error_message="Connection refused",
        )

        assert result.success is False
        assert result.status_code is None
        assert result.error_message == "Connection refused"


class TestWebhookDeliveryServiceSendRequest:
    """Tests for WebhookDeliveryService._send_request method."""

    def test_successful_request(self):
        """Test successful HTTP request."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"received": true}'

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={"X-Custom": "value"},
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.response_body == '{"received": true}'

        # Verify request was made correctly
        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["json"] == {"event": "test"}
        assert "Content-Type" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Custom"] == "value"

    def test_non_2xx_status_code(self):
        """Test that non-2xx status codes are treated as failures."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.status_code == 500
        assert result.response_body == "Internal Server Error"

    def test_timeout_error(self):
        """Test handling of timeout errors."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_client = MagicMock(side_effect=requests.Timeout())
        service = WebhookDeliveryService(
            http_client=mock_client, request_timeout=10
        )

        result = service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.status_code is None
        assert "timed out" in result.error_message.lower()

    def test_connection_error(self):
        """Test handling of connection errors."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_client = MagicMock(
            side_effect=requests.ConnectionError("Connection refused")
        )
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.status_code is None
        assert "Connection error" in result.error_message

    def test_request_exception(self):
        """Test handling of generic request exceptions."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        err = requests.RequestException("Unknown error")
        mock_client = MagicMock(side_effect=err)
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert "Request failed" in result.error_message

    def test_response_body_truncation(self):
        """Test that large response bodies are truncated."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            MAX_RESPONSE_BODY_SIZE,
        )

        # Create a response body larger than the limit
        large_body = "x" * (MAX_RESPONSE_BODY_SIZE + 1000)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = large_body

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is True
        assert len(result.response_body) <= MAX_RESPONSE_BODY_SIZE + 20
        assert result.response_body.endswith("...[truncated]")

    def test_custom_headers_merged(self):
        """Test that custom headers are merged with Content-Type."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        custom_headers = {
            "Authorization": "Bearer token123",
            "X-Signature": "abc123",
        }

        service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers=custom_headers,
        )

        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
        assert call_kwargs["headers"]["X-Signature"] == "abc123"

    def test_2xx_status_codes_are_success(self):
        """Test that all 2xx status codes are treated as success."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        for status_code in [200, 201, 202, 204, 299]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = "OK"

            mock_client = MagicMock(return_value=mock_response)
            service = WebhookDeliveryService(http_client=mock_client)

            result = service._send_request(
                url="https://example.com/webhook",
                payload={},
                headers={},
            )

            msg = f"Status {status_code} should be success"
            assert result.success is True, msg


class TestWebhookDeliveryServiceRetry:
    """Tests for WebhookDeliveryService retry logic."""

    def test_default_retry_delays(self):
        """Test that default retry delays are 1s, 5s, 30s."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            RETRY_DELAYS,
            MAX_ATTEMPTS,
        )

        service = WebhookDeliveryService()

        assert service.retry_delays == RETRY_DELAYS
        assert service.retry_delays == [1, 5, 30]
        assert service.max_attempts == MAX_ATTEMPTS
        assert service.max_attempts == 3

    def test_custom_retry_configuration(self):
        """Test custom retry configuration."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        service = WebhookDeliveryService(
            retry_delays=[2, 4, 8],
            max_attempts=5,
        )

        assert service.retry_delays == [2, 4, 8]
        assert service.max_attempts == 5

    def test_success_on_first_attempt_no_retry(self):
        """Test that successful first attempt doesn't retry."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        webhook = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
        )

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                result = service.deliver(webhook, {"event": "test"})

        assert result.success is True
        assert mock_client.call_count == 1

    def test_retry_on_failure(self):
        """Test that failures trigger retries."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Error"

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = "OK"

        # Fail twice, then succeed
        responses = [
            mock_response_fail, mock_response_fail, mock_response_success
        ]
        mock_client = MagicMock(side_effect=responses)

        # Use minimal delays for test speed
        service = WebhookDeliveryService(
            http_client=mock_client,
            retry_delays=[0.01, 0.01, 0.01],
        )

        webhook = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
        )

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                result = service.deliver(webhook, {"event": "test"})

        assert result.success is True
        assert mock_client.call_count == 3

    def test_max_attempts_reached(self):
        """Test that delivery fails after max attempts."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
            DeliveryStatus,
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        mock_client = MagicMock(return_value=mock_response)

        service = WebhookDeliveryService(
            http_client=mock_client,
            retry_delays=[0.01, 0.01, 0.01],
            max_attempts=3,
        )

        webhook = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
        )

        update_calls = []

        def track_update(delivery_id, status, attempts, code, body):
            update_calls.append((status, attempts))
            return True

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", side_effect=track_update
            ):
                result = service.deliver(webhook, {"event": "test"})

        assert result.success is False
        assert result.status_code == 500
        assert mock_client.call_count == 3

        # Should have updated to FAILED after all attempts
        final_update = update_calls[-1]
        assert final_update[0] == DeliveryStatus.FAILED
        assert final_update[1] == 3

    def test_disabled_webhook_not_delivered(self):
        """Test that disabled webhooks are not delivered."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        mock_client = MagicMock()
        service = WebhookDeliveryService(http_client=mock_client)

        webhook = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
            enabled=False,
        )

        result = service.deliver(webhook, {"event": "test"})

        assert result.success is False
        assert "disabled" in result.error_message.lower()
        mock_client.assert_not_called()


class TestWebhookDeliveryServiceDatabase:
    """Tests for database operations in WebhookDeliveryService."""

    def test_create_delivery_record(self, mock_env_vars):
        """Test creating a delivery record."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        service = WebhookDeliveryService()

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps([{"delivery_id": 42}])

            delivery_id = service._create_delivery_record(
                webhook_id=1,
                payload={"event": "test"},
            )

            assert delivery_id == 42
            mock_query.assert_called_once()

            # Verify query contains expected values
            call_args = mock_query.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "INSERT INTO medic.webhook_deliveries" in query
            assert params[0] == 1  # webhook_id
            assert "event" in params[1]  # payload as JSON string
            assert params[2] == "pending"  # status

    def test_create_delivery_record_failure(self, mock_env_vars):
        """Test handling of create delivery record failure."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        service = WebhookDeliveryService()

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = None

            delivery_id = service._create_delivery_record(
                webhook_id=1,
                payload={"event": "test"},
            )

            assert delivery_id is None

    def test_update_delivery_record(self, mock_env_vars):
        """Test updating a delivery record."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            DeliveryStatus,
        )

        service = WebhookDeliveryService()

        with patch("Medic.Core.webhook_delivery.insert_db") as mock_insert:
            mock_insert.return_value = True

            success = service._update_delivery_record(
                delivery_id=42,
                status=DeliveryStatus.SUCCESS,
                attempts=1,
                response_code=200,
                response_body="OK",
            )

            assert success is True
            mock_insert.assert_called_once()

            call_args = mock_insert.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "UPDATE medic.webhook_deliveries" in query
            assert params[0] == "success"  # status
            assert params[1] == 1  # attempts
            assert params[2] == 200  # response_code
            assert params[3] == "OK"  # response_body
            assert params[4] == 42  # delivery_id


class TestWebhookDeliveryServiceAsync:
    """Tests for async delivery in WebhookDeliveryService."""

    def test_async_retry_returns_immediately(self):
        """Test that async_retry=True returns immediately."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        # Create a slow mock that would block if not async
        def slow_request(*args, **kwargs):
            time.sleep(0.5)
            response = MagicMock()
            response.status_code = 200
            response.text = "OK"
            return response

        mock_client = MagicMock(side_effect=slow_request)
        service = WebhookDeliveryService(http_client=mock_client)

        webhook = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
        )

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                start = time.time()
                result = service.deliver(
                    webhook, {"event": "test"}, async_retry=True
                )
                elapsed = time.time() - start

        # Should return almost immediately (before the 0.5s sleep)
        assert elapsed < 0.1
        assert "asynchronously" in result.error_message.lower()

        # Wait for async delivery to complete
        time.sleep(0.7)


class TestDeliverToAll:
    """Tests for deliver_to_all method."""

    def test_deliver_to_multiple_webhooks(self):
        """Test delivering to multiple webhooks."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        webhooks = [
            WebhookConfig(
                webhook_id=1, url="https://example1.com/hook", headers={}
            ),
            WebhookConfig(
                webhook_id=2, url="https://example2.com/hook", headers={}
            ),
            WebhookConfig(
                webhook_id=3, url="https://example3.com/hook", headers={}
            ),
        ]

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                results = service.deliver_to_all(
                    webhooks, {"event": "test"}, async_delivery=False
                )

        assert len(results) == 3
        assert all(r.success for r in results.values())
        assert mock_client.call_count == 3

    def test_deliver_to_all_skips_disabled(self):
        """Test that disabled webhooks are skipped."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        webhooks = [
            WebhookConfig(
                webhook_id=1,
                url="https://example1.com/hook",
                headers={},
                enabled=True,
            ),
            WebhookConfig(
                webhook_id=2,
                url="https://example2.com/hook",
                headers={},
                enabled=False,
            ),
        ]

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                results = service.deliver_to_all(
                    webhooks, {"event": "test"}, async_delivery=False
                )

        assert len(results) == 2
        assert results[1].success is True
        assert results[2].success is False
        assert "disabled" in results[2].error_message.lower()

    def test_deliver_to_all_parallel(self):
        """Test parallel delivery to multiple webhooks."""
        from Medic.Core.webhook_delivery import (
            WebhookDeliveryService,
            WebhookConfig,
        )

        # Track call times to verify parallelism
        call_times = []

        def track_time(*args, **kwargs):
            call_times.append(time.time())
            time.sleep(0.1)  # Simulate network latency
            response = MagicMock()
            response.status_code = 200
            response.text = "OK"
            return response

        mock_client = MagicMock(side_effect=track_time)
        service = WebhookDeliveryService(http_client=mock_client)

        webhooks = [
            WebhookConfig(
                webhook_id=i, url=f"https://ex{i}.com/hook", headers={}
            )
            for i in range(1, 4)
        ]

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                start = time.time()
                results = service.deliver_to_all(
                    webhooks, {"event": "test"}, async_delivery=True
                )
                elapsed = time.time() - start

        assert len(results) == 3
        # Parallel: ~0.1s (one latency), not ~0.3s (sequential)
        # Allow extra overhead for CI environments
        assert elapsed < 0.5


class TestGlobalService:
    """Tests for global service functions."""

    def test_get_webhook_delivery_service_singleton(self):
        """Test get_webhook_delivery_service returns the same instance."""
        from Medic.Core.webhook_delivery import (
            get_webhook_delivery_service,
            set_webhook_delivery_service,
        )

        # Reset to ensure clean state
        set_webhook_delivery_service(None)

        service1 = get_webhook_delivery_service()
        service2 = get_webhook_delivery_service()

        assert service1 is service2

    def test_set_webhook_delivery_service(self):
        """Test set_webhook_delivery_service replaces the global instance."""
        from Medic.Core.webhook_delivery import (
            get_webhook_delivery_service,
            set_webhook_delivery_service,
            WebhookDeliveryService,
        )

        original = get_webhook_delivery_service()
        new_service = WebhookDeliveryService()
        set_webhook_delivery_service(new_service)

        assert get_webhook_delivery_service() is new_service
        assert get_webhook_delivery_service() is not original

        # Clean up
        set_webhook_delivery_service(None)

    def test_deliver_webhook_convenience_function(self):
        """Test deliver_webhook convenience function."""
        from Medic.Core.webhook_delivery import (
            deliver_webhook,
            set_webhook_delivery_service,
            WebhookDeliveryService,
            WebhookConfig,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)
        set_webhook_delivery_service(service)

        webhook = WebhookConfig(
            webhook_id=1,
            url="https://example.com/webhook",
            headers={},
        )

        with patch.object(service, "_create_delivery_record", return_value=1):
            with patch.object(
                service, "_update_delivery_record", return_value=True
            ):
                result = deliver_webhook(webhook, {"event": "test"})

        assert result.success is True

        # Clean up
        set_webhook_delivery_service(None)


class TestGetWebhooksForService:
    """Tests for get_webhooks_for_service function."""

    def test_get_webhooks_with_service_id(self, mock_env_vars):
        """Test getting webhooks for a specific service."""
        from Medic.Core.webhook_delivery import get_webhooks_for_service

        mock_data = [
            {
                "webhook_id": 1,
                "service_id": 42,
                "url": "https://example.com/webhook1",
                "headers": {"X-Custom": "value"},
                "enabled": True,
            },
            {
                "webhook_id": 2,
                "service_id": None,
                "url": "https://example.com/webhook2",
                "headers": {},
                "enabled": True,
            },
        ]

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps(mock_data)

            webhooks = get_webhooks_for_service(service_id=42)

            assert len(webhooks) == 2
            assert webhooks[0].webhook_id == 1
            assert webhooks[0].url == "https://example.com/webhook1"
            assert webhooks[0].headers == {"X-Custom": "value"}
            assert webhooks[1].webhook_id == 2

    def test_get_global_webhooks(self, mock_env_vars):
        """Test getting global webhooks (no service_id)."""
        from Medic.Core.webhook_delivery import get_webhooks_for_service

        mock_data = [
            {
                "webhook_id": 1,
                "service_id": None,
                "url": "https://example.com/global",
                "headers": {},
                "enabled": True,
            },
        ]

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps(mock_data)

            webhooks = get_webhooks_for_service(service_id=None)

            assert len(webhooks) == 1
            assert webhooks[0].service_id is None

    def test_get_webhooks_empty_result(self, mock_env_vars):
        """Test handling empty webhook list."""
        from Medic.Core.webhook_delivery import get_webhooks_for_service

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = None

            webhooks = get_webhooks_for_service(service_id=42)

            assert webhooks == []

    def test_get_webhooks_handles_json_string_headers(self, mock_env_vars):
        """Test handling headers as JSON string from database."""
        from Medic.Core.webhook_delivery import get_webhooks_for_service

        mock_data = [
            {
                "webhook_id": 1,
                "service_id": 42,
                "url": "https://example.com/webhook",
                "headers": '{"Authorization": "Bearer token"}',
                "enabled": True,
            },
        ]

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps(mock_data)

            webhooks = get_webhooks_for_service(service_id=42)

            auth_header = {"Authorization": "Bearer token"}
            assert webhooks[0].headers == auth_header


class TestGetDeliveryById:
    """Tests for get_delivery_by_id function."""

    def test_get_existing_delivery(self, mock_env_vars):
        """Test getting an existing delivery record."""
        from Medic.Core.webhook_delivery import (
            get_delivery_by_id, DeliveryStatus
        )

        mock_data = [
            {
                "delivery_id": 42,
                "webhook_id": 1,
                "payload": {"event": "test"},
                "status": "success",
                "attempts": 1,
                "last_attempt_at": "2024-01-01T00:00:00Z",
                "response_code": 200,
                "response_body": "OK",
            },
        ]

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps(mock_data)

            record = get_delivery_by_id(42)

            assert record is not None
            assert record.delivery_id == 42
            assert record.webhook_id == 1
            assert record.payload == {"event": "test"}
            assert record.status == DeliveryStatus.SUCCESS
            assert record.attempts == 1
            assert record.response_code == 200

    def test_get_nonexistent_delivery(self, mock_env_vars):
        """Test getting a non-existent delivery record."""
        from Medic.Core.webhook_delivery import get_delivery_by_id

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps([])

            record = get_delivery_by_id(999)

            assert record is None

    def test_get_delivery_handles_json_string_payload(self, mock_env_vars):
        """Test handling payload as JSON string from database."""
        from Medic.Core.webhook_delivery import get_delivery_by_id

        mock_data = [
            {
                "delivery_id": 42,
                "webhook_id": 1,
                "payload": '{"event": "test", "data": {"key": "value"}}',
                "status": "pending",
                "attempts": 0,
            },
        ]

        with patch("Medic.Core.webhook_delivery.query_db") as mock_query:
            mock_query.return_value = json.dumps(mock_data)

            record = get_delivery_by_id(42)

            assert record is not None
            expected = {"event": "test", "data": {"key": "value"}}
            assert record.payload == expected


class TestConstants:
    """Tests for module constants."""

    def test_retry_delays_constant(self):
        """Test that RETRY_DELAYS is correct."""
        from Medic.Core.webhook_delivery import RETRY_DELAYS

        assert RETRY_DELAYS == [1, 5, 30]

    def test_max_attempts_constant(self):
        """Test that MAX_ATTEMPTS is correct."""
        from Medic.Core.webhook_delivery import MAX_ATTEMPTS

        assert MAX_ATTEMPTS == 3

    def test_request_timeout_constant(self):
        """Test that REQUEST_TIMEOUT is correct."""
        from Medic.Core.webhook_delivery import REQUEST_TIMEOUT

        assert REQUEST_TIMEOUT == 30

    def test_max_response_body_size_constant(self):
        """Test that MAX_RESPONSE_BODY_SIZE is correct."""
        from Medic.Core.webhook_delivery import MAX_RESPONSE_BODY_SIZE

        assert MAX_RESPONSE_BODY_SIZE == 4096


class TestWebhookDeliveryServiceSSRFPrevention:
    """Tests for SSRF prevention in WebhookDeliveryService."""

    @patch('Medic.Core.webhook_delivery.validate_url')
    def test_send_request_validates_url(self, mock_validate_url):
        """Test that _send_request validates URL before making request."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_validate_url.return_value = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        service._send_request(
            url="https://example.com/webhook",
            payload={"event": "test"},
            headers={},
        )

        # Verify validate_url was called
        mock_validate_url.assert_called_once_with("https://example.com/webhook")

    @patch('Medic.Core.webhook_delivery.validate_url')
    def test_send_request_rejects_private_ip(self, mock_validate_url):
        """Test that _send_request rejects private IPs."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService
        from Medic.Core.url_validator import InvalidURLError

        mock_validate_url.side_effect = InvalidURLError("Invalid webhook URL")

        mock_client = MagicMock()
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="http://10.0.0.5/internal",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.error_message == "Invalid webhook URL"
        # HTTP client should NOT be called
        mock_client.assert_not_called()

    @patch('Medic.Core.webhook_delivery.validate_url')
    def test_send_request_rejects_localhost(self, mock_validate_url):
        """Test that _send_request rejects localhost URLs."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService
        from Medic.Core.url_validator import InvalidURLError

        mock_validate_url.side_effect = InvalidURLError("Invalid webhook URL")

        mock_client = MagicMock()
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="http://127.0.0.1:8080/api",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.error_message == "Invalid webhook URL"
        mock_client.assert_not_called()

    @patch('Medic.Core.webhook_delivery.validate_url')
    def test_send_request_rejects_metadata_endpoint(self, mock_validate_url):
        """Test that _send_request rejects cloud metadata endpoints."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService
        from Medic.Core.url_validator import InvalidURLError

        mock_validate_url.side_effect = InvalidURLError("Invalid webhook URL")

        mock_client = MagicMock()
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="http://169.254.169.254/latest/meta-data/",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.error_message == "Invalid webhook URL"
        mock_client.assert_not_called()

    @patch('Medic.Core.webhook_delivery.validate_url')
    def test_send_request_rejects_file_scheme(self, mock_validate_url):
        """Test that _send_request rejects file:// URLs."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService
        from Medic.Core.url_validator import InvalidURLError

        mock_validate_url.side_effect = InvalidURLError("Invalid webhook URL")

        mock_client = MagicMock()
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="file:///etc/passwd",
            payload={"event": "test"},
            headers={},
        )

        assert result.success is False
        assert result.error_message == "Invalid webhook URL"
        mock_client.assert_not_called()

    @patch('Medic.Core.webhook_delivery.validate_url')
    def test_send_request_allows_valid_https_url(self, mock_validate_url):
        """Test that _send_request allows valid HTTPS URLs."""
        from Medic.Core.webhook_delivery import WebhookDeliveryService

        mock_validate_url.return_value = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"received": true}'

        mock_client = MagicMock(return_value=mock_response)
        service = WebhookDeliveryService(http_client=mock_client)

        result = service._send_request(
            url="https://api.slack.com/webhooks/123",
            payload={"text": "Hello"},
            headers={},
        )

        assert result.success is True
        assert result.status_code == 200
        mock_client.assert_called_once()
