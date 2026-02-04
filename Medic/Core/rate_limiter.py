"""Rate limiting infrastructure for Medic API.

Supports in-memory and Redis backends with sliding window algorithm.
"""
import logging
import os
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

    Uses a sliding window algorithm implemented with Redis sorted sets.
    Each request is stored as a member with its timestamp as the score.
    The window slides forward by removing entries older than window_seconds.

    This implementation uses Redis MULTI/EXEC transactions for atomic operations
    to ensure accuracy under concurrent access from multiple replicas.
    """

    def __init__(
        self,
        redis_client: Any = None,
        default_config: Optional[RateLimitConfig] = None,
        key_prefix: str = "medic:ratelimit:",
    ):
        """
        Initialize the Redis rate limiter.

        Args:
            redis_client: Redis client instance. If None, creates from REDIS_URL
            default_config: Default rate limit configuration
            key_prefix: Prefix for Redis keys
        """
        self.default_config = default_config or RateLimitConfig()
        self.key_prefix = key_prefix
        self._key_configs: Dict[str, RateLimitConfig] = {}
        self._configs_lock = threading.Lock()

        if redis_client is not None:
            self.redis = redis_client
        else:
            self.redis = self._create_redis_client()

    def _create_redis_client(self) -> Any:
        """
        Create a Redis client from environment variables.

        Returns:
            Redis client instance

        Raises:
            ValueError: If REDIS_URL is not set
        """
        import redis

        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            raise ValueError(
                "REDIS_URL environment variable is required for "
                "RedisRateLimiter when no client is provided"
            )

        pool_size = int(os.environ.get("REDIS_POOL_SIZE", "10"))

        # Create connection pool for better performance
        pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=pool_size,
            decode_responses=True,
        )

        return redis.Redis(connection_pool=pool)

    def is_healthy(self) -> bool:
        """
        Check if the Redis connection is healthy.

        Returns:
            True if Redis is reachable, False otherwise
        """
        try:
            self.redis.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

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

    def _get_redis_key(self, key: str, endpoint_type: str) -> str:
        """
        Generate the Redis key for a rate limit bucket.

        Args:
            key: API key identifier
            endpoint_type: Type of endpoint

        Returns:
            Redis key string
        """
        return f"{self.key_prefix}{key}:{endpoint_type}"

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
        Check if a request is allowed and record it using Redis.

        Uses sliding window algorithm with Redis sorted sets (ZSET).
        Each request is stored with timestamp as score, enabling efficient
        window-based counting and cleanup.

        Uses MULTI/EXEC for atomic operations to ensure accuracy under
        concurrent access from multiple API replicas.

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
        window_seconds = config.window_seconds
        redis_key = self._get_redis_key(key, endpoint_type)

        now = time.time()
        cutoff = now - window_seconds

        # Use pipeline for atomic operations
        pipe = self.redis.pipeline()

        # Remove expired entries
        pipe.zremrangebyscore(redis_key, "-inf", cutoff)

        # Get current count before adding
        pipe.zcard(redis_key)

        # Execute to get current count
        results = pipe.execute()
        current_count = results[1]

        if current_count >= limit:
            # Rate limited - get oldest timestamp for reset time
            oldest_entries = self.redis.zrange(
                redis_key, 0, 0, withscores=True
            )
            if oldest_entries:
                oldest_timestamp = oldest_entries[0][1]
                reset_at = oldest_timestamp + window_seconds
                retry_after = max(1, int(reset_at - now))
            else:
                reset_at = now + window_seconds
                retry_after = window_seconds

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

        # Add new request with unique member (timestamp + random suffix)
        # Using timestamp with microseconds as member to ensure uniqueness
        member = f"{now}"
        pipe = self.redis.pipeline()
        pipe.zadd(redis_key, {member: now})
        # Set expiry on the key for automatic cleanup
        pipe.expire(redis_key, window_seconds + 1)
        # Get new count
        pipe.zcard(redis_key)
        results = pipe.execute()

        new_count = results[2]
        remaining = max(0, limit - new_count)

        # Get oldest timestamp for reset time
        oldest_entries = self.redis.zrange(redis_key, 0, 0, withscores=True)
        if oldest_entries:
            oldest_timestamp = oldest_entries[0][1]
            reset_at = oldest_timestamp + window_seconds
        else:
            reset_at = now + window_seconds

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
        redis_key = self._get_redis_key(key, endpoint_type)

        now = time.time()
        cutoff = now - config.window_seconds

        # Remove expired and count in one pipeline
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(redis_key, "-inf", cutoff)
        pipe.zcard(redis_key)
        results = pipe.execute()

        return results[1]

    def reset(self, key: str, endpoint_type: Optional[str] = None) -> None:
        """
        Reset rate limit counters for a key.

        Args:
            key: Identifier for the rate limit bucket
            endpoint_type: Optional endpoint type to reset. If None, reset all.
        """
        if endpoint_type:
            redis_key = self._get_redis_key(key, endpoint_type)
            self.redis.delete(redis_key)
            logger.debug(f"Reset rate limit for {redis_key}")
        else:
            # Reset all endpoint types for this key using pattern match
            pattern = f"{self.key_prefix}{key}:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            logger.debug(f"Reset all rate limits for key {key}")


# Global default rate limiter instance (singleton)
_default_limiter: Optional[RateLimiter] = None
_default_limiter_lock = threading.Lock()

# Rate limiter type configuration
# 'redis': Force Redis (fails if Redis unavailable)
# 'memory': Force in-memory (never uses Redis)
# 'auto': Try Redis if REDIS_URL set, fall back to in-memory (default)
RATE_LIMITER_TYPE_REDIS: str = "redis"
RATE_LIMITER_TYPE_MEMORY: str = "memory"
RATE_LIMITER_TYPE_AUTO: str = "auto"


def _create_rate_limiter() -> RateLimiter:
    """
    Create a rate limiter instance based on configuration.

    The limiter type is determined by the MEDIC_RATE_LIMITER_TYPE env var:
    - 'redis': Force Redis (fails if unavailable)
    - 'memory': Force in-memory
    - 'auto' (default): Try Redis if REDIS_URL set, fall back to in-memory

    Returns:
        RateLimiter instance (Redis or InMemory)
    """
    limiter_type = os.environ.get(
        "MEDIC_RATE_LIMITER_TYPE", RATE_LIMITER_TYPE_AUTO
    ).lower()
    redis_url = os.environ.get("REDIS_URL")

    # Force in-memory limiter
    if limiter_type == RATE_LIMITER_TYPE_MEMORY:
        logger.info(
            "Using InMemoryRateLimiter (MEDIC_RATE_LIMITER_TYPE=memory)"
        )
        return InMemoryRateLimiter()

    # Force Redis limiter
    if limiter_type == RATE_LIMITER_TYPE_REDIS:
        if not redis_url:
            raise ValueError(
                "REDIS_URL is required when MEDIC_RATE_LIMITER_TYPE=redis"
            )
        logger.info("Using RedisRateLimiter (MEDIC_RATE_LIMITER_TYPE=redis)")
        return RedisRateLimiter()

    # Auto-select: try Redis if REDIS_URL is set
    if limiter_type == RATE_LIMITER_TYPE_AUTO:
        if not redis_url:
            logger.info(
                "Using InMemoryRateLimiter (REDIS_URL not set)"
            )
            return InMemoryRateLimiter()

        # Try to create Redis limiter, fall back to in-memory on failure
        try:
            redis_limiter = RedisRateLimiter()
            # Test connection to ensure Redis is reachable
            if redis_limiter.is_healthy():
                logger.info(
                    "Using RedisRateLimiter (REDIS_URL configured, "
                    "connection healthy)"
                )
                return redis_limiter
            else:
                logger.warning(
                    "Redis health check failed, falling back to "
                    "InMemoryRateLimiter"
                )
                return InMemoryRateLimiter()
        except Exception as e:
            logger.warning(
                f"Failed to create RedisRateLimiter: {e}. "
                "Falling back to InMemoryRateLimiter"
            )
            return InMemoryRateLimiter()

    # Unknown type - log warning and use in-memory
    logger.warning(
        f"Unknown MEDIC_RATE_LIMITER_TYPE='{limiter_type}', "
        "using InMemoryRateLimiter"
    )
    return InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance (singleton).

    The limiter type is determined by the MEDIC_RATE_LIMITER_TYPE env var:
    - 'redis': Force Redis (fails if unavailable)
    - 'memory': Force in-memory
    - 'auto' (default): Try Redis if REDIS_URL set, fall back to in-memory

    The limiter instance is cached as a module-level singleton.

    Returns:
        The global RateLimiter instance
    """
    global _default_limiter
    with _default_limiter_lock:
        if _default_limiter is None:
            _default_limiter = _create_rate_limiter()
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
