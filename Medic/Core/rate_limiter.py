"""Rate limiting infrastructure for Medic API.

Supports in-memory and Redis backends with sliding window algorithm.
"""
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

import Medic.Helpers.logSettings as logLevel

# Log Setup
logger = logging.getLogger(__name__)
logger.setLevel(logLevel.logSetup())


# Default rate limits (requests per minute)
DEFAULT_HEARTBEAT_LIMIT = 100  # 100 req/min for heartbeat endpoints
DEFAULT_MANAGEMENT_LIMIT = 20  # 20 req/min for management endpoints


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting an API key."""

    heartbeat_limit: int = DEFAULT_HEARTBEAT_LIMIT
    management_limit: int = DEFAULT_MANAGEMENT_LIMIT
    window_seconds: int = 60  # 1 minute window


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: float  # Unix timestamp when the window resets
    # Seconds to wait before retrying (if rate limited)
    retry_after: Optional[int] = None


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    @abstractmethod
    def check_rate_limit(
        self,
        key: str,
        endpoint_type: str = "management",
        config: Optional[RateLimitConfig] = None,
    ) -> RateLimitResult:
        """
        Check if a request is allowed under rate limits.

        Args:
            key: Identifier for the rate limit bucket (typically API key ID)
            endpoint_type: Type of endpoint - "heartbeat" or "management"
            config: Optional custom rate limit configuration

        Returns:
            RateLimitResult with allow/deny decision and metadata
        """
        pass

    @abstractmethod
    def get_current_usage(
        self,
        key: str,
        endpoint_type: str = "management",
    ) -> int:
        """
        Get current request count for a key within the window.

        Args:
            key: Identifier for the rate limit bucket
            endpoint_type: Type of endpoint - "heartbeat" or "management"

        Returns:
            Current request count in the window
        """
        pass

    @abstractmethod
    def reset(self, key: str, endpoint_type: Optional[str] = None) -> None:
        """
        Reset rate limit counters for a key.

        Args:
            key: Identifier for the rate limit bucket
            endpoint_type: Optional endpoint type to reset. If None, reset all.
        """
        pass


class SlidingWindowEntry:
    """A single entry in the sliding window for a rate limit bucket."""

    def __init__(self, window_seconds: int):
        self.window_seconds = window_seconds
        self.timestamps: list[float] = []
        self.lock = threading.Lock()

    def add_request(self, now: float) -> int:
        """
        Add a request timestamp and return current count.

        Args:
            now: Current timestamp

        Returns:
            Number of requests in the current window
        """
        with self.lock:
            # Remove timestamps outside the window
            cutoff = now - self.window_seconds
            self.timestamps = [ts for ts in self.timestamps if ts > cutoff]
            # Add new timestamp
            self.timestamps.append(now)
            return len(self.timestamps)

    def get_count(self, now: float) -> int:
        """
        Get current request count within window.

        Args:
            now: Current timestamp

        Returns:
            Number of requests in the current window
        """
        with self.lock:
            cutoff = now - self.window_seconds
            self.timestamps = [ts for ts in self.timestamps if ts > cutoff]
            return len(self.timestamps)

    def get_oldest_timestamp(self) -> Optional[float]:
        """Get the oldest timestamp in the window."""
        with self.lock:
            return self.timestamps[0] if self.timestamps else None

    def clear(self) -> None:
        """Clear all timestamps."""
        with self.lock:
            self.timestamps.clear()


class InMemoryRateLimiter(RateLimiter):
    """
    In-memory rate limiter using sliding window algorithm.

    Thread-safe implementation suitable for single-instance deployments.
    For multi-instance deployments, use RedisRateLimiter.
    """

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        """
        Initialize the in-memory rate limiter.

        Args:
            default_config: Default rate limit configuration to use
        """
        self.default_config = default_config or RateLimitConfig()
        # Buckets keyed by "{key}:{endpoint_type}"
        self._buckets: Dict[str, SlidingWindowEntry] = {}
        self._buckets_lock = threading.Lock()
        # Per-key custom configurations
        self._key_configs: Dict[str, RateLimitConfig] = {}
        self._configs_lock = threading.Lock()

    def set_key_config(self, key: str, config: RateLimitConfig) -> None:
        """
        Set custom rate limit configuration for a specific key.

        Args:
            key: Identifier for the rate limit bucket (typically API key ID)
            config: Custom rate limit configuration
        """
        with self._configs_lock:
            self._key_configs[key] = config
        logger.debug(f"Set custom rate limit config for key {key}: {config}")

    def get_key_config(self, key: str) -> RateLimitConfig:
        """
        Get rate limit configuration for a key.

        Args:
            key: Identifier for the rate limit bucket

        Returns:
            Rate limit configuration (custom or default)
        """
        with self._configs_lock:
            return self._key_configs.get(key, self.default_config)

    def _get_bucket(
        self, key: str, endpoint_type: str, window_seconds: int
    ) -> SlidingWindowEntry:
        """
        Get or create a bucket for the given key and endpoint type.

        Args:
            key: Identifier for the rate limit bucket
            endpoint_type: Type of endpoint
            window_seconds: Window duration in seconds

        Returns:
            SlidingWindowEntry for the bucket
        """
        bucket_key = f"{key}:{endpoint_type}"
        with self._buckets_lock:
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = SlidingWindowEntry(window_seconds)
            return self._buckets[bucket_key]

    def _get_limit_for_endpoint(
        self, config: RateLimitConfig, endpoint_type: str
    ) -> int:
        """
        Get the rate limit for the given endpoint type.

        Args:
            config: Rate limit configuration
            endpoint_type: Type of endpoint

        Returns:
            Rate limit for the endpoint type
        """
        if endpoint_type == "heartbeat":
            return config.heartbeat_limit
        return config.management_limit

    def check_rate_limit(
        self,
        key: str,
        endpoint_type: str = "management",
        config: Optional[RateLimitConfig] = None,
    ) -> RateLimitResult:
        """
        Check if a request is allowed and record it.

        Uses sliding window algorithm: counts requests in the last
        window_seconds.

        Args:
            key: Identifier for the rate limit bucket (typically API key ID)
            endpoint_type: Type of endpoint - "heartbeat" or "management"
            config: Optional custom config (overrides key config)

        Returns:
            RateLimitResult with allow/deny decision and metadata
        """
        # Get configuration (priority: parameter > key config > default)
        if config is None:
            config = self.get_key_config(key)

        limit = self._get_limit_for_endpoint(config, endpoint_type)
        bucket = self._get_bucket(key, endpoint_type, config.window_seconds)
        now = time.time()

        # Get current count before adding
        current_count = bucket.get_count(now)

        if current_count >= limit:
            # Rate limited
            oldest = bucket.get_oldest_timestamp()
            if oldest is not None:
                reset_at = oldest + config.window_seconds
                retry_after = max(1, int(reset_at - now))
            else:
                reset_at = now + config.window_seconds
                retry_after = config.window_seconds

            logger.debug(
                f"Rate limit exceeded for {key}:{endpoint_type}. "
                f"Count: {current_count}, Limit: {limit}"
            )

            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        # Add the request
        new_count = bucket.add_request(now)
        remaining = max(0, limit - new_count)

        # Calculate reset time (when oldest request falls out of window)
        oldest = bucket.get_oldest_timestamp()
        if oldest:
            reset_at = oldest + config.window_seconds
        else:
            reset_at = now + config.window_seconds

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    def get_current_usage(
        self,
        key: str,
        endpoint_type: str = "management",
    ) -> int:
        """
        Get current request count for a key within the window.

        Args:
            key: Identifier for the rate limit bucket
            endpoint_type: Type of endpoint - "heartbeat" or "management"

        Returns:
            Current request count in the window
        """
        config = self.get_key_config(key)
        bucket = self._get_bucket(key, endpoint_type, config.window_seconds)
        return bucket.get_count(time.time())

    def reset(self, key: str, endpoint_type: Optional[str] = None) -> None:
        """
        Reset rate limit counters for a key.

        Args:
            key: Identifier for the rate limit bucket
            endpoint_type: Optional endpoint type to reset. If None, reset all.
        """
        if endpoint_type:
            bucket_key = f"{key}:{endpoint_type}"
            with self._buckets_lock:
                if bucket_key in self._buckets:
                    self._buckets[bucket_key].clear()
            logger.debug(f"Reset rate limit for {bucket_key}")
        else:
            # Reset all endpoint types for this key
            with self._buckets_lock:
                prefix = f"{key}:"
                keys_to_clear = [
                    k for k in self._buckets if k.startswith(prefix)
                ]
                for bucket_key in keys_to_clear:
                    self._buckets[bucket_key].clear()
            logger.debug(f"Reset all rate limits for key {key}")

    def cleanup_expired(self) -> int:
        """
        Remove empty buckets to prevent memory growth.

        Returns:
            Number of buckets removed
        """
        now = time.time()
        removed = 0
        with self._buckets_lock:
            keys_to_remove = []
            for bucket_key, bucket in self._buckets.items():
                if bucket.get_count(now) == 0:
                    keys_to_remove.append(bucket_key)
            for bucket_key in keys_to_remove:
                del self._buckets[bucket_key]
                removed += 1
        if removed > 0:
            logger.debug(f"Cleaned up {removed} empty rate limit buckets")
        return removed


class RedisRateLimiter(RateLimiter):
    """
    Redis-backed rate limiter for distributed deployments.

    Placeholder implementation - to be completed when Redis support is needed.
    """

    def __init__(
        self,
        redis_client: Any,
        default_config: Optional[RateLimitConfig] = None,
        key_prefix: str = "medic:ratelimit:",
    ):
        """
        Initialize the Redis rate limiter.

        Args:
            redis_client: Redis client instance
            default_config: Default rate limit configuration
            key_prefix: Prefix for Redis keys
        """
        self.redis = redis_client
        self.default_config = default_config or RateLimitConfig()
        self.key_prefix = key_prefix
        raise NotImplementedError(
            "RedisRateLimiter is not yet implemented. "
            "Use InMemoryRateLimiter for now."
        )

    def check_rate_limit(
        self,
        key: str,
        endpoint_type: str = "management",
        config: Optional[RateLimitConfig] = None,
    ) -> RateLimitResult:
        """Check rate limit using Redis."""
        raise NotImplementedError(
            "RedisRateLimiter.check_rate_limit not implemented"
        )

    def get_current_usage(
        self,
        key: str,
        endpoint_type: str = "management",
    ) -> int:
        """Get current usage from Redis."""
        raise NotImplementedError(
            "RedisRateLimiter.get_current_usage not implemented"
        )

    def reset(self, key: str, endpoint_type: Optional[str] = None) -> None:
        """Reset rate limit in Redis."""
        raise NotImplementedError("RedisRateLimiter.reset not implemented")


# Global default rate limiter instance
_default_limiter: Optional[RateLimiter] = None
_default_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        The global RateLimiter instance (InMemoryRateLimiter by default)
    """
    global _default_limiter
    with _default_limiter_lock:
        if _default_limiter is None:
            _default_limiter = InMemoryRateLimiter()
        return _default_limiter


def set_rate_limiter(limiter: Optional[RateLimiter]) -> None:
    """
    Set the global rate limiter instance.

    Args:
        limiter: Rate limiter instance to use globally (or None to reset)
    """
    global _default_limiter
    with _default_limiter_lock:
        _default_limiter = limiter


def check_rate_limit(
    key: str,
    endpoint_type: str = "management",
    config: Optional[RateLimitConfig] = None,
) -> RateLimitResult:
    """
    Convenience function to check rate limit using the global limiter.

    Args:
        key: Identifier for the rate limit bucket (typically API key ID)
        endpoint_type: Type of endpoint - "heartbeat" or "management"
        config: Optional custom rate limit configuration

    Returns:
        RateLimitResult with allow/deny decision and metadata
    """
    return get_rate_limiter().check_rate_limit(key, endpoint_type, config)


def set_key_rate_limit(key: str, config: RateLimitConfig) -> None:
    """
    Set custom rate limit configuration for a specific API key.

    Args:
        key: API key identifier
        config: Custom rate limit configuration
    """
    limiter = get_rate_limiter()
    if isinstance(limiter, InMemoryRateLimiter):
        limiter.set_key_config(key, config)
    else:
        logger.warning(
            "set_key_rate_limit only supported for InMemoryRateLimiter"
        )
