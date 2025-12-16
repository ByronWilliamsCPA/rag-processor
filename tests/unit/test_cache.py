"""Tests for Redis caching utilities.

Tests async cache operations using mocks.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError


# Helper to create a mock get_redis that returns an async mock
def create_mock_get_redis(mock_redis: AsyncMock):
    """Create an async function that returns the mock redis."""

    async def mock_get_redis():
        return mock_redis

    return mock_get_redis


@pytest.fixture
def mock_cache_logger():
    """Mock the cache module logger to handle structlog-style kwargs."""
    with patch("rag_processor.core.cache.logger", MagicMock()) as mock_logger:
        yield mock_logger


class TestCacheOperations:
    """Tests for cache get/set/delete operations."""

    @pytest.mark.asyncio
    async def test_get_cached_returns_value(self) -> None:
        """Test getting a cached value."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps({"key": "value"})

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import get_cached

            result = await get_cached("test_key")

        assert result == {"key": "value"}
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_cached_returns_default_when_not_found(self) -> None:
        """Test getting default when key not found."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import get_cached

            result = await get_cached("missing_key", default="default_value")

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_get_cached_returns_default_on_error(
        self, mock_cache_logger: MagicMock
    ) -> None:
        """Test returning default on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Connection failed")

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import get_cached

            result = await get_cached("test_key", default="fallback")

        assert result == "fallback"
        mock_cache_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_set_cached_success(self) -> None:
        """Test setting a cached value."""
        mock_redis = AsyncMock()

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import set_cached

            result = await set_cached("test_key", {"data": 123}, ttl=600)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_cached_failure(self, mock_cache_logger: MagicMock) -> None:
        """Test set_cached returns False on error."""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = RedisError("Write failed")

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import set_cached

            result = await set_cached("test_key", {"data": 123})

        assert result is False
        mock_cache_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_delete_cached_success(self) -> None:
        """Test deleting a cached value."""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import delete_cached

            result = await delete_cached("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_cached_not_found(self) -> None:
        """Test delete returns False when key doesn't exist."""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 0

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import delete_cached

            result = await delete_cached("missing_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_cached_failure(self, mock_cache_logger: MagicMock) -> None:
        """Test delete returns False on error."""
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = RedisError("Delete failed")

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import delete_cached

            result = await delete_cached("test_key")

        assert result is False
        mock_cache_logger.warning.assert_called()


class TestInvalidatePattern:
    """Tests for pattern-based cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_pattern_deletes_matching_keys(self) -> None:
        """Test invalidating keys by pattern."""
        mock_redis = AsyncMock()

        # Mock scan_iter as async generator
        async def mock_scan_iter(*args, **kwargs):
            for key in ["user:1", "user:2", "user:3"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 3

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import invalidate_pattern

            result = await invalidate_pattern("user:*")

        assert result == 3
        mock_redis.delete.assert_called_once_with("user:1", "user:2", "user:3")

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matches(self) -> None:
        """Test invalidating when no keys match."""
        mock_redis = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            return
            yield  # Make it an async generator that yields nothing

        mock_redis.scan_iter = mock_scan_iter

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import invalidate_pattern

            result = await invalidate_pattern("nonexistent:*")

        assert result == 0
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_pattern_error(self, mock_cache_logger: MagicMock) -> None:
        """Test invalidate returns 0 on error."""
        mock_redis = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            raise RedisError("Scan failed")
            yield

        mock_redis.scan_iter = mock_scan_iter

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import invalidate_pattern

            result = await invalidate_pattern("error:*")

        assert result == 0
        mock_cache_logger.error.assert_called()


class TestCacheWarming:
    """Tests for cache warming functionality."""

    @pytest.mark.asyncio
    async def test_warm_cache_new_key(self) -> None:
        """Test warming cache for a new key."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = False

        async def value_fn():
            return {"data": "expensive_result"}

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import warm_cache

            result = await warm_cache("new_key", value_fn, ttl=3600)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_cache_existing_key_no_force(self) -> None:
        """Test warm_cache skips existing key without force."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True

        async def value_fn():
            return {"data": "should_not_call"}

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import warm_cache

            result = await warm_cache("existing_key", value_fn)

        assert result is False
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_warm_cache_existing_key_with_force(self) -> None:
        """Test warm_cache refreshes existing key with force=True."""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True

        async def value_fn():
            return {"data": "refreshed"}

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import warm_cache

            result = await warm_cache("existing_key", value_fn, force=True)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_cache_error(self, mock_cache_logger: MagicMock) -> None:
        """Test warm_cache returns False on error."""
        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = RedisError("Connection failed")

        async def value_fn():
            return {"data": "value"}

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import warm_cache

            result = await warm_cache("error_key", value_fn)

        assert result is False
        mock_cache_logger.error.assert_called()


class TestCacheStats:
    """Tests for cache statistics."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self) -> None:
        """Test getting cache statistics."""
        mock_redis = AsyncMock()
        mock_redis.info.return_value = {
            "keyspace_hits": 100,
            "keyspace_misses": 20,
            "used_memory_human": "1.5M",
            "connected_clients": 5,
        }

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import get_cache_stats

            stats = await get_cache_stats()

        assert stats["hits"] == 100
        assert stats["misses"] == 20
        assert stats["hit_rate"] == pytest.approx(83.33, rel=0.01)
        assert stats["memory_used"] == "1.5M"
        assert stats["connected_clients"] == 5

    @pytest.mark.asyncio
    async def test_get_cache_stats_error(self, mock_cache_logger: MagicMock) -> None:
        """Test cache stats returns error dict on failure."""
        mock_redis = AsyncMock()
        mock_redis.info.side_effect = RedisError("Stats unavailable")

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import get_cache_stats

            stats = await get_cache_stats()

        assert "error" in stats
        mock_cache_logger.error.assert_called()


class TestCachedDecorator:
    """Tests for @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_cache_hit(self) -> None:
        """Test cached decorator returns cached value."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps({"result": "cached"})

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import cached

            @cached(ttl=300)
            async def expensive_function(x: int) -> dict:
                return {"result": f"computed_{x}"}

            result = await expensive_function(42)

        assert result == {"result": "cached"}
        # setex should not be called on cache hit
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_cached_decorator_cache_miss(self) -> None:
        """Test cached decorator computes and caches on miss."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Cache miss

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import cached

            @cached(ttl=300, key_prefix="test")
            async def expensive_function(x: int) -> dict:
                return {"result": f"computed_{x}"}

            result = await expensive_function(42)

        assert result == {"result": "computed_42"}
        # Should cache the result
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_decorator_graceful_degradation(
        self, mock_cache_logger: MagicMock
    ) -> None:
        """Test cached decorator falls back on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Connection lost")

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import cached

            @cached(ttl=300)
            async def expensive_function() -> dict:
                return {"result": "computed"}

            result = await expensive_function()

        # Should still return computed result despite cache error
        assert result == {"result": "computed"}
        mock_cache_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_cached_decorator_custom_key_builder(self) -> None:
        """Test cached decorator with custom key builder."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import cached

            def custom_key(user_id: str) -> str:
                return f"user:{user_id}:profile"

            @cached(ttl=300, key_builder=custom_key)
            async def get_user_profile(user_id: str) -> dict:
                return {"user_id": user_id, "name": "Test"}

            result = await get_user_profile("123")

        assert result == {"user_id": "123", "name": "Test"}
        # Verify the custom key was used
        mock_redis.get.assert_called_once_with("user:123:profile")


class TestCacheInvalidateDecorator:
    """Tests for @cache_invalidate decorator."""

    @pytest.mark.asyncio
    async def test_cache_invalidate_decorator(self) -> None:
        """Test cache_invalidate decorator invalidates after function."""
        mock_redis = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            for key in ["user:1:profile"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 1

        with patch(
            "rag_processor.core.cache.get_redis",
            create_mock_get_redis(mock_redis),
        ):
            from rag_processor.core.cache import cache_invalidate

            @cache_invalidate("user:*")
            async def update_user(user_id: str, data: dict) -> dict:
                return {"status": "updated", "user_id": user_id}

            result = await update_user("1", {"name": "New Name"})

        assert result == {"status": "updated", "user_id": "1"}
        mock_redis.delete.assert_called_once()


class TestRedisConnection:
    """Tests for Redis connection management."""

    @pytest.mark.asyncio
    async def test_get_redis_creates_pool(self) -> None:
        """Test get_redis creates connection pool on first call."""
        with patch("rag_processor.core.cache.from_url") as mock_from_url:
            mock_pool = AsyncMock()
            mock_from_url.return_value = mock_pool

            # Reset global pool
            import rag_processor.core.cache as cache_module

            cache_module._redis_pool = None

            with patch.dict("os.environ", {"REDIS_URL": "redis://test:6379/0"}):
                from rag_processor.core.cache import get_redis

                result = await get_redis()

            assert result == mock_pool
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_redis(self) -> None:
        """Test close_redis closes the pool."""
        mock_pool = AsyncMock()

        import rag_processor.core.cache as cache_module

        cache_module._redis_pool = mock_pool

        from rag_processor.core.cache import close_redis

        await close_redis()

        mock_pool.close.assert_called_once()
        assert cache_module._redis_pool is None
