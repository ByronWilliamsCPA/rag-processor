"""Tests for the centralized Redis client factory (core/redis.py)."""

from __future__ import annotations

import redis

from rag_processor.core import redis as core_redis


class TestGetRedisClient:
    """Tests for get_redis_client and shared connection pools."""

    def teardown_method(self) -> None:
        """Reset shared pools so tests don't leak state."""
        core_redis.close_redis_pools()

    def test_returns_redis_client(self) -> None:
        client = core_redis.get_redis_client()
        assert isinstance(client, redis.Redis)

    def test_decoded_clients_share_one_pool(self) -> None:
        c1 = core_redis.get_redis_client(decode_responses=True)
        c2 = core_redis.get_redis_client(decode_responses=True)
        # Same process-wide pool is reused rather than re-created per client.
        assert c1.connection_pool is c2.connection_pool

    def test_decoded_and_raw_use_distinct_pools(self) -> None:
        decoded = core_redis.get_redis_client(decode_responses=True)
        raw = core_redis.get_redis_client(decode_responses=False)
        assert decoded.connection_pool is not raw.connection_pool

    def test_decode_responses_flag_propagates_to_pool(self) -> None:
        decoded = core_redis.get_redis_client(decode_responses=True)
        raw = core_redis.get_redis_client(decode_responses=False)
        assert decoded.connection_pool.connection_kwargs["decode_responses"] is True
        assert raw.connection_pool.connection_kwargs["decode_responses"] is False

    def test_close_redis_pools_resets_pools(self) -> None:
        first = core_redis.get_redis_client(decode_responses=True)
        core_redis.close_redis_pools()
        second = core_redis.get_redis_client(decode_responses=True)
        # After close a fresh pool is built on next use.
        assert first.connection_pool is not second.connection_pool

    def test_close_redis_pools_is_safe_when_unused(self) -> None:
        core_redis.close_redis_pools()
        # No pools created yet; calling again must not raise.
        core_redis.close_redis_pools()
