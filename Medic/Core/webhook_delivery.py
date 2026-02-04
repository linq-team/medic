"""Webhook delivery service for Medic.

Sends webhook notifications with retry logic and delivery tracking.
"""
import json
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import requests

import Medic.Helpers.logSettings as logLevel
from Medic.Core.database import insert_db, query_db

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


# Exponential backoff delays in seconds: 1s, 5s, 30s
RETRY_DELAYS = [1, 5, 30]
MAX_ATTEMPTS = 3

# HTTP timeout for webhook requests (seconds)
REQUEST_TIMEOUT = 30

# Maximum response body size to store (bytes)
MAX_RESPONSE_BODY_SIZE = 4096


@dataclass
class WebhookConfig:
    """Configuration for a webhook."""

    webhook_id: int
    url: str
    headers: Dict[str, str]
    enabled: bool = True
    service_id: Optional[int] = None


@dataclass
class DeliveryResult:
    """Result of a webhook delivery attempt."""

    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DeliveryRecord:
    """Record of a webhook delivery in the database."""

    delivery_id: int
    webhook_id: int
    payload: Dict[str, Any]
    status: DeliveryStatus
    attempts: int
    last_attempt_at: Optional[str] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None


class WebhookDeliveryService:
    """Service for delivering webhooks with retry logic.

    Supports:
    - Sending POST requests with JSON payloads
    - Custom headers from webhook configuration
    - Exponential backoff retry: 1s, 5s, 30s (max 3 attempts)
    - Delivery status tracking in webhook_deliveries table
    """

    def __init__(
        self,
        retry_delays: Optional[List[int]] = None,
        max_attempts: int = MAX_ATTEMPTS,
        request_timeout: int = REQUEST_TIMEOUT,
        http_client: Optional[Callable[..., requests.Response]] = None,
    ):
        """
        Initialize the webhook delivery service.

        Args:
            retry_delays: List of delays in seconds between retries.
                         Default: [1, 5, 30]
            max_attempts: Maximum number of delivery attempts. Default: 3
            request_timeout: HTTP request timeout in seconds. Default: 30
            http_client: Optional custom HTTP client for testing.
                        Default: requests.post
        """
        if retry_delays is not None:
            self.retry_delays = retry_delays
        else:
            self.retry_delays = RETRY_DELAYS
        self.max_attempts = max_attempts
        self.request_timeout = request_timeout
        self._http_client = http_client or requests.post
        self._lock = threading.Lock()

    def _send_request(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> DeliveryResult:
        """
        Send HTTP POST request to webhook URL.

        Args:
            url: Webhook endpoint URL
            payload: JSON payload to send
            headers: HTTP headers to include

        Returns:
            DeliveryResult with status and response details
        """
        # Prepare headers - always include Content-Type
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers)

        try:
            response = self._http_client(
                url,
                json=payload,
                headers=request_headers,
                timeout=self.request_timeout,
            )

            # Truncate response body if too large
            response_body = response.text
            if len(response_body) > MAX_RESPONSE_BODY_SIZE:
                truncated = response_body[:MAX_RESPONSE_BODY_SIZE]
                response_body = truncated + "...[truncated]"

            # Success if status code is 2xx
            success = 200 <= response.status_code < 300

            return DeliveryResult(
                success=success,
                status_code=response.status_code,
                response_body=response_body,
            )

        except requests.Timeout:
            logger.warning(f"Webhook request timed out: {url}")
            timeout_msg = f"Request timed out after {self.request_timeout}s"
            return DeliveryResult(
                success=False,
                error_message=timeout_msg,
            )

        except requests.ConnectionError as e:
            logger.warning(f"Webhook connection error: {url} - {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"Connection error: {str(e)}",
            )

        except requests.RequestException as e:
            logger.warning(f"Webhook request failed: {url} - {str(e)}")
            return DeliveryResult(
                success=False,
                error_message=f"Request failed: {str(e)}",
            )

    def _create_delivery_record(
        self,
        webhook_id: int,
        payload: Dict[str, Any],
    ) -> Optional[int]:
        """
        Create a new delivery record in the database.

        Args:
            webhook_id: ID of the webhook configuration
            payload: JSON payload being sent

        Returns:
            Delivery ID if created successfully, None otherwise
        """
        query = """
            INSERT INTO medic.webhook_deliveries
                (webhook_id, payload, status, attempts)
            VALUES (%s, %s, %s, %s)
            RETURNING delivery_id
        """
        status_val = DeliveryStatus.PENDING.value
        params = (webhook_id, json.dumps(payload), status_val, 0)

        result = query_db(query, params, show_columns=True)
        if result:
            try:
                data = json.loads(str(result))
                if data and len(data) > 0:
                    return data[0].get("delivery_id")
            except (json.JSONDecodeError, TypeError):
                logger.error("Failed to parse delivery ID from insert result")
        return None

    def _update_delivery_record(
        self,
        delivery_id: int,
        status: DeliveryStatus,
        attempts: int,
        response_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> bool:
        """
        Update a delivery record in the database.

        Args:
            delivery_id: ID of the delivery record
            status: New delivery status
            attempts: Number of attempts made
            response_code: HTTP response code from last attempt
            response_body: Response body from last attempt

        Returns:
            True if updated successfully, False otherwise
        """
        query = """
            UPDATE medic.webhook_deliveries
            SET status = %s,
                attempts = %s,
                last_attempt_at = NOW(),
                response_code = %s,
                response_body = %s
            WHERE delivery_id = %s
        """
        params = (
            status.value, attempts, response_code, response_body, delivery_id
        )

        return insert_db(query, params)

    def deliver(
        self,
        webhook: WebhookConfig,
        payload: Dict[str, Any],
        async_retry: bool = False,
    ) -> DeliveryResult:
        """
        Deliver a webhook with retry logic.

        Attempts delivery up to max_attempts times with exponential backoff.
        Tracks delivery status in the webhook_deliveries table.

        Args:
            webhook: Webhook configuration
            payload: JSON payload to send
            async_retry: If True, retries happen in background thread.
                        If False (default), retries block the caller.

        Returns:
            DeliveryResult from the final attempt
        """
        if not webhook.enabled:
            wh_id = webhook.webhook_id
            logger.debug(f"Webhook {wh_id} is disabled, skipping delivery")
            return DeliveryResult(
                success=False,
                error_message="Webhook is disabled",
            )

        # Create delivery record
        delivery_id = self._create_delivery_record(webhook.webhook_id, payload)
        if delivery_id is None:
            wh_id = webhook.webhook_id
            err = f"Failed to create delivery record for webhook {wh_id}"
            logger.error(err)
            # Continue without tracking if database fails
            delivery_id = -1

        logger.info(
            f"Starting webhook delivery {delivery_id} to {webhook.url} "
            f"for webhook {webhook.webhook_id}"
        )

        if async_retry:
            # Start delivery in background thread
            thread = threading.Thread(
                target=self._deliver_with_retry,
                args=(webhook, payload, delivery_id),
                daemon=True,
            )
            thread.start()
            return DeliveryResult(
                success=True,
                error_message="Delivery started asynchronously",
            )

        return self._deliver_with_retry(webhook, payload, delivery_id)

    def _deliver_with_retry(
        self,
        webhook: WebhookConfig,
        payload: Dict[str, Any],
        delivery_id: int,
    ) -> DeliveryResult:
        """
        Internal method to deliver with retry logic.

        Args:
            webhook: Webhook configuration
            payload: JSON payload to send
            delivery_id: ID of the delivery record

        Returns:
            DeliveryResult from the final attempt
        """
        last_result: Optional[DeliveryResult] = None

        for attempt in range(self.max_attempts):
            attempt_num = attempt + 1

            logger.debug(
                f"Webhook delivery attempt {attempt_num}/{self.max_attempts} "
                f"for delivery {delivery_id}"
            )

            # Update status to retrying if this is a retry
            if attempt > 0:
                self._update_delivery_record(
                    delivery_id,
                    DeliveryStatus.RETRYING,
                    attempt_num,
                    last_result.status_code if last_result else None,
                    last_result.response_body or last_result.error_message
                    if last_result
                    else None,
                )

            # Attempt delivery
            result = self._send_request(webhook.url, payload, webhook.headers)
            last_result = result

            if result.success:
                msg = f"Webhook delivery {delivery_id} succeeded on "
                logger.info(msg + f"attempt {attempt_num}")
                self._update_delivery_record(
                    delivery_id,
                    DeliveryStatus.SUCCESS,
                    attempt_num,
                    result.status_code,
                    result.response_body,
                )
                return result

            logger.warning(
                f"Webhook delivery {delivery_id} failed on "
                f"attempt {attempt_num}: status={result.status_code}, "
                f"error={result.error_message}"
            )

            # Check if we should retry
            if attempt_num < self.max_attempts:
                delay_idx = min(attempt, len(self.retry_delays) - 1)
                delay = self.retry_delays[delay_idx]
                msg = f"Webhook delivery {delivery_id} waiting {delay}s"
                logger.debug(msg + " before retry")
                time.sleep(delay)

        # All attempts failed
        max_att = self.max_attempts
        err_msg = f"Webhook delivery {delivery_id} failed after {max_att} "
        err_msg += "attempts"
        logger.error(err_msg)
        self._update_delivery_record(
            delivery_id,
            DeliveryStatus.FAILED,
            self.max_attempts,
            last_result.status_code if last_result else None,
            last_result.response_body or last_result.error_message
            if last_result
            else None,
        )

        return last_result if last_result else DeliveryResult(
            success=False,
            error_message="Delivery failed",
        )

    def deliver_to_all(
        self,
        webhooks: List[WebhookConfig],
        payload: Dict[str, Any],
        async_delivery: bool = True,
    ) -> Dict[int, DeliveryResult]:
        """
        Deliver payload to multiple webhooks.

        Args:
            webhooks: List of webhook configurations
            payload: JSON payload to send to all webhooks
            async_delivery: If True, deliveries happen in parallel.
                           If False, deliveries happen sequentially.

        Returns:
            Dictionary mapping webhook_id to DeliveryResult
        """
        results: Dict[int, DeliveryResult] = {}

        if async_delivery:
            threads: List[threading.Thread] = []

            def deliver_and_store(webhook: WebhookConfig) -> None:
                result = self.deliver(webhook, payload, async_retry=False)
                with self._lock:
                    results[webhook.webhook_id] = result

            for webhook in webhooks:
                if webhook.enabled:
                    thread = threading.Thread(
                        target=deliver_and_store,
                        args=(webhook,),
                    )
                    threads.append(thread)
                    thread.start()
                else:
                    results[webhook.webhook_id] = DeliveryResult(
                        success=False,
                        error_message="Webhook is disabled",
                    )

            for thread in threads:
                thread.join()

        else:
            for webhook in webhooks:
                results[webhook.webhook_id] = self.deliver(
                    webhook, payload, async_retry=False
                )

        return results


# Global default delivery service instance
_default_service: Optional[WebhookDeliveryService] = None
_default_service_lock = threading.Lock()


def get_webhook_delivery_service() -> WebhookDeliveryService:
    """
    Get the global webhook delivery service instance.

    Returns:
        The global WebhookDeliveryService instance
    """
    global _default_service
    with _default_service_lock:
        if _default_service is None:
            _default_service = WebhookDeliveryService()
        return _default_service


def set_webhook_delivery_service(
    service: Optional[WebhookDeliveryService],
) -> None:
    """
    Set the global webhook delivery service instance.

    Args:
        service: WebhookDeliveryService instance to use globally
                 (or None to reset)
    """
    global _default_service
    with _default_service_lock:
        _default_service = service


def deliver_webhook(
    webhook: WebhookConfig,
    payload: Dict[str, Any],
    async_retry: bool = False,
) -> DeliveryResult:
    """
    Convenience function to deliver a webhook using the global service.

    Args:
        webhook: Webhook configuration
        payload: JSON payload to send
        async_retry: If True, retries happen in background thread

    Returns:
        DeliveryResult from the delivery attempt
    """
    service = get_webhook_delivery_service()
    return service.deliver(webhook, payload, async_retry)


def get_webhooks_for_service(
    service_id: Optional[int] = None
) -> List[WebhookConfig]:
    """
    Get webhook configurations for a service.

    Args:
        service_id: Service ID to get webhooks for.
                    If None, returns global webhooks.

    Returns:
        List of WebhookConfig objects
    """
    if service_id is not None:
        # Get webhooks for specific service OR global webhooks
        query = """
            SELECT webhook_id, service_id, url, headers, enabled
            FROM medic.webhooks
            WHERE (service_id = %s OR service_id IS NULL)
              AND enabled = TRUE
            ORDER BY webhook_id
        """
        params = (service_id,)
    else:
        # Get only global webhooks
        query = """
            SELECT webhook_id, service_id, url, headers, enabled
            FROM medic.webhooks
            WHERE service_id IS NULL
              AND enabled = TRUE
            ORDER BY webhook_id
        """
        params = None

    result = query_db(query, params, show_columns=True)
    if not result:
        return []

    try:
        data = json.loads(str(result))
        webhooks = []
        for row in data:
            headers = row.get("headers", {})
            if isinstance(headers, str):
                headers = json.loads(headers)
            webhooks.append(
                WebhookConfig(
                    webhook_id=row["webhook_id"],
                    url=row["url"],
                    headers=headers,
                    enabled=row.get("enabled", True),
                    service_id=row.get("service_id"),
                )
            )
        return webhooks
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.error(f"Failed to parse webhooks from database: {e}")
        return []


def get_delivery_by_id(delivery_id: int) -> Optional[DeliveryRecord]:
    """
    Get a delivery record by ID.

    Args:
        delivery_id: ID of the delivery record

    Returns:
        DeliveryRecord if found, None otherwise
    """
    query = """
        SELECT delivery_id, webhook_id, payload, status, attempts,
               last_attempt_at, response_code, response_body
        FROM medic.webhook_deliveries
        WHERE delivery_id = %s
    """
    result = query_db(query, (delivery_id,), show_columns=True)
    if not result:
        return None

    try:
        data = json.loads(str(result))
        if not data or len(data) == 0:
            return None
        row = data[0]
        payload = row.get("payload", {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        return DeliveryRecord(
            delivery_id=row["delivery_id"],
            webhook_id=row["webhook_id"],
            payload=payload,
            status=DeliveryStatus(row["status"]),
            attempts=row["attempts"],
            last_attempt_at=row.get("last_attempt_at"),
            response_code=row.get("response_code"),
            response_body=row.get("response_body"),
        )
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse delivery record: {e}")
        return None
