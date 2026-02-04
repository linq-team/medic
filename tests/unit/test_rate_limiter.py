"""Unit tests for rate limiting infrastructure."""
import time
import threading
import pytest


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self):
        """Test that RateLimitConfig has correct default values."""
        from Medic.Core.rate_limiter import (
            RateLimitConfig,
            DEFAULT_HEARTBEAT_LIMIT,
            DEFAULT_MANAGEMENT_LIMIT,
        )

        config = RateLimitConfig()

        assert config.heartbeat_limit == DEFAULT_HEARTBEAT_LIMIT
        assert config.heartbeat_limit == 100
        assert config.management_limit == DEFAULT_MANAGEMENT_LIMIT
        assert config.management_limit == 20
        assert config.window_seconds == 60

    def test_custom_values(self):
        """Test that RateLimitConfig accepts custom values."""
        from Medic.Core.rate_limiter import RateLimitConfig

        config = RateLimitConfig(
            heartbeat_limit=500,
            management_limit=50,
            window_seconds=120,
        )

        assert config.heartbeat_limit == 500
        assert config.management_limit == 50
        assert config.window_seconds == 120


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_allowed_result(self):
        """Test creating an allowed result."""
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at=time.time() + 60,
        )

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 99
        assert result.retry_after is None

    def test_denied_result(self):
        """Test creating a denied result."""
        from Medic.Core.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=30,
        )

        assert result.allowed is False
        assert result.limit == 100
        assert result.remaining == 0
        assert result.retry_after == 30


class TestSlidingWindowEntry:
    """Tests for SlidingWindowEntry class."""

    def test_add_request_increments_count(self):
        """Test that adding a request increments the count."""
        from Medic.Core.rate_limiter import SlidingWindowEntry

        entry = SlidingWindowEntry(window_seconds=60)
        now = time.time()

        count1 = entry.add_request(now)
        count2 = entry.add_request(now)
        count3 = entry.add_request(now)

        assert count1 == 1
        assert count2 == 2
        assert count3 == 3

    def test_old_requests_expire(self):
        """Test that requests outside the window are removed."""
        from Medic.Core.rate_limiter import SlidingWindowEntry

        entry = SlidingWindowEntry(window_seconds=60)

        # Add request in the past (61 seconds ago)
        old_time = time.time() - 61
        entry.add_request(old_time)

        # Current request should only count itself
        now = time.time()
        count = entry.add_request(now)

        assert count == 1

    def test_get_count_returns_correct_value(self):
        """Test that get_count returns the correct value."""
        from Medic.Core.rate_limiter import SlidingWindowEntry

        entry = SlidingWindowEntry(window_seconds=60)
        now = time.time()

        entry.add_request(now)
        entry.add_request(now)
        entry.add_request(now)

        assert entry.get_count(now) == 3

    def test_get_oldest_timestamp(self):
        """Test that get_oldest_timestamp returns the oldest timestamp."""
        from Medic.Core.rate_limiter import SlidingWindowEntry

        entry = SlidingWindowEntry(window_seconds=60)
        now = time.time()

        entry.add_request(now - 30)
        entry.add_request(now - 20)
        entry.add_request(now - 10)

        oldest = entry.get_oldest_timestamp()
        assert oldest is not None
        assert abs(oldest - (now - 30)) < 0.1

    def test_get_oldest_timestamp_empty(self):
        """Test that get_oldest_timestamp returns None for empty entry."""
        from Medic.Core.rate_limiter import SlidingWindowEntry

        entry = SlidingWindowEntry(window_seconds=60)

        assert entry.get_oldest_timestamp() is None

    def test_clear_removes_all_timestamps(self):
        """Test that clear removes all timestamps."""
        from Medic.Core.rate_limiter import SlidingWindowEntry

        entry = SlidingWindowEntry(window_seconds=60)
        now = time.time()

        entry.add_request(now)
        entry.add_request(now)
        entry.clear()

        assert entry.get_count(now) == 0


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter class."""

    def test_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=10)
        )

        for i in range(10):
            result = limiter.check_rate_limit("test_key", "management")
            assert result.allowed is True, f"Request {i+1} allowed"
            assert result.remaining == 10 - (i + 1)

    def test_blocks_requests_over_limit(self):
        """Test that requests over the limit are blocked."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=5)
        )

        # Use up the limit
        for _ in range(5):
            result = limiter.check_rate_limit("test_key", "management")
            assert result.allowed is True

        # Next request should be blocked
        result = limiter.check_rate_limit("test_key", "management")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None
        assert result.retry_after > 0

    def test_different_endpoint_types_separate_buckets(self):
        """Test that heartbeat and management have separate limits."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(
                heartbeat_limit=10, management_limit=5
            )
        )

        # Use up management limit
        for _ in range(5):
            result = limiter.check_rate_limit("test_key", "management")
            assert result.allowed is True

        # Management should be blocked
        result = limiter.check_rate_limit("test_key", "management")
        assert result.allowed is False

        # Heartbeat should still be allowed
        result = limiter.check_rate_limit("test_key", "heartbeat")
        assert result.allowed is True

    def test_different_keys_separate_buckets(self):
        """Test that different API keys have separate limits."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=5)
        )

        # Use up limit for key1
        for _ in range(5):
            result = limiter.check_rate_limit("key1", "management")
            assert result.allowed is True

        # key1 should be blocked
        result = limiter.check_rate_limit("key1", "management")
        assert result.allowed is False

        # key2 should still be allowed
        result = limiter.check_rate_limit("key2", "management")
        assert result.allowed is True

    def test_custom_key_config(self):
        """Test that custom per-key configuration works."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=5)
        )

        # Set higher limit for premium key
        premium_config = RateLimitConfig(management_limit=100)
        limiter.set_key_config("premium_key", premium_config)

        # Default key limited to 5
        for _ in range(5):
            result = limiter.check_rate_limit("regular_key", "management")
            assert result.allowed is True
        result = limiter.check_rate_limit("regular_key", "management")
        assert result.allowed is False

        # Premium key can do many more
        for _ in range(50):
            result = limiter.check_rate_limit("premium_key", "management")
            assert result.allowed is True

    def test_get_current_usage(self):
        """Test that get_current_usage returns correct count."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=100)
        )

        # Initial usage is 0
        assert limiter.get_current_usage("test_key", "management") == 0

        # Make some requests
        limiter.check_rate_limit("test_key", "management")
        limiter.check_rate_limit("test_key", "management")
        limiter.check_rate_limit("test_key", "management")

        assert limiter.get_current_usage("test_key", "management") == 3

    def test_reset_single_endpoint(self):
        """Test that reset clears counters for a specific endpoint."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(
                management_limit=5, heartbeat_limit=5
            )
        )

        # Make requests to both endpoints
        for _ in range(3):
            limiter.check_rate_limit("test_key", "management")
            limiter.check_rate_limit("test_key", "heartbeat")

        assert limiter.get_current_usage("test_key", "management") == 3
        assert limiter.get_current_usage("test_key", "heartbeat") == 3

        # Reset only management
        limiter.reset("test_key", "management")

        assert limiter.get_current_usage("test_key", "management") == 0
        assert limiter.get_current_usage("test_key", "heartbeat") == 3

    def test_reset_all_endpoints(self):
        """Test that reset without endpoint clears all counters for key."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(
                management_limit=5, heartbeat_limit=5
            )
        )

        # Make requests to both endpoints
        for _ in range(3):
            limiter.check_rate_limit("test_key", "management")
            limiter.check_rate_limit("test_key", "heartbeat")

        # Reset all for this key
        limiter.reset("test_key")

        assert limiter.get_current_usage("test_key", "management") == 0
        assert limiter.get_current_usage("test_key", "heartbeat") == 0

    def test_cleanup_expired_removes_empty_buckets(self):
        """Test that cleanup_expired removes empty buckets."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(
                management_limit=100, window_seconds=1
            )
        )

        # Add some requests
        limiter.check_rate_limit("key1", "management")
        limiter.check_rate_limit("key2", "management")

        # Wait for window to expire
        time.sleep(1.1)

        # Cleanup should remove expired buckets
        removed = limiter.cleanup_expired()
        assert removed == 2

    def test_result_metadata_correct(self):
        """Test that result metadata is correct."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(
                management_limit=10, window_seconds=60
            )
        )

        result = limiter.check_rate_limit("test_key", "management")

        assert result.limit == 10
        assert result.remaining == 9
        assert result.reset_at > time.time()
        assert result.reset_at <= time.time() + 60

    def test_thread_safety(self):
        """Test that concurrent requests are handled safely."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=1000)
        )

        errors = []
        success_count = [0]

        def make_requests():
            try:
                for _ in range(100):
                    result = limiter.check_rate_limit(
                        "concurrent_key", "management"
                    )
                    if result.allowed:
                        success_count[0] += 1
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_requests) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        # Should have allowed close to 1000 requests (the limit)
        assert success_count[0] <= 1000
        # Should have allowed most requests (at least 900)
        assert success_count[0] >= 900

    def test_config_parameter_override(self):
        """Test that config parameter overrides key config."""
        from Medic.Core.rate_limiter import (
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=100)
        )
        key_config = RateLimitConfig(management_limit=50)
        limiter.set_key_config("test_key", key_config)

        # Use custom config with limit of 2
        custom_config = RateLimitConfig(management_limit=2)

        result1 = limiter.check_rate_limit(
            "test_key", "management", config=custom_config
        )
        result2 = limiter.check_rate_limit(
            "test_key", "management", config=custom_config
        )
        result3 = limiter.check_rate_limit(
            "test_key", "management", config=custom_config
        )

        assert result1.allowed is True
        assert result2.allowed is True
        # Third request blocked by custom limit
        assert result3.allowed is False

    def test_heartbeat_default_limit(self):
        """Test heartbeat endpoints have correct default limit (100/min)."""
        from Medic.Core.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        # Should allow 100 heartbeat requests
        for i in range(100):
            result = limiter.check_rate_limit("test_key", "heartbeat")
            assert result.allowed is True, f"Request {i+1} allowed"

        # 101st should be blocked
        result = limiter.check_rate_limit("test_key", "heartbeat")
        assert result.allowed is False

    def test_management_default_limit(self):
        """Test management endpoints have correct default limit (20/min)."""
        from Medic.Core.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        # Should allow 20 management requests
        for i in range(20):
            result = limiter.check_rate_limit("test_key", "management")
            assert result.allowed is True, f"Request {i+1} allowed"

        # 21st should be blocked
        result = limiter.check_rate_limit("test_key", "management")
        assert result.allowed is False


class TestGlobalRateLimiter:
    """Tests for global rate limiter functions."""

    def test_get_rate_limiter_returns_singleton(self):
        """Test that get_rate_limiter returns the same instance."""
        from Medic.Core.rate_limiter import (
            get_rate_limiter,
            set_rate_limiter,
        )

        # Reset to ensure clean state
        set_rate_limiter(None)

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_set_rate_limiter(self):
        """Test that set_rate_limiter replaces the global instance."""
        from Medic.Core.rate_limiter import (
            get_rate_limiter,
            set_rate_limiter,
            InMemoryRateLimiter,
        )

        original = get_rate_limiter()
        new_limiter = InMemoryRateLimiter()
        set_rate_limiter(new_limiter)

        assert get_rate_limiter() is new_limiter
        assert get_rate_limiter() is not original

        # Clean up
        set_rate_limiter(None)

    def test_check_rate_limit_convenience_function(self):
        """Test that the convenience function works correctly."""
        from Medic.Core.rate_limiter import (
            check_rate_limit,
            set_rate_limiter,
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        # Set up a fresh limiter
        limiter = InMemoryRateLimiter(
            default_config=RateLimitConfig(management_limit=5)
        )
        set_rate_limiter(limiter)

        # Use convenience function
        result = check_rate_limit("test_key", "management")

        assert result.allowed is True
        assert result.limit == 5

        # Clean up
        set_rate_limiter(None)

    def test_set_key_rate_limit_convenience_function(self):
        """Test that set_key_rate_limit convenience function works."""
        from Medic.Core.rate_limiter import (
            check_rate_limit,
            set_key_rate_limit,
            set_rate_limiter,
            InMemoryRateLimiter,
            RateLimitConfig,
        )

        # Set up a fresh limiter
        limiter = InMemoryRateLimiter()
        set_rate_limiter(limiter)

        # Set custom limit for a key
        custom = RateLimitConfig(management_limit=200)
        set_key_rate_limit("premium_key", custom)

        result = check_rate_limit("premium_key", "management")

        assert result.limit == 200

        # Clean up
        set_rate_limiter(None)


class TestRedisRateLimiter:
    """Tests for RedisRateLimiter class."""

    def test_raises_not_implemented(self):
        """Test that RedisRateLimiter raises NotImplementedError."""
        from Medic.Core.rate_limiter import RedisRateLimiter

        with pytest.raises(NotImplementedError):
            RedisRateLimiter(redis_client=None)
