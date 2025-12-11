"""Unit tests for Redis connectivity and cache operations.

Tests use fakeredis to provide an in-memory Redis implementation.
"""

import pytest
import pytest_asyncio
from fakeredis import aioredis as fakeredis_aio


@pytest_asyncio.fixture
async def fake_redis():
    """Create a fakeredis instance for testing.

    Yields:
        FakeRedis instance that mimics Redis behavior.
    """
    redis = fakeredis_aio.FakeRedis(decode_responses=True)
    yield redis
    await redis.aclose()


@pytest.mark.unit
class TestRedisConnectivity:
    """Unit tests for basic Redis operations."""

    @pytest.mark.asyncio
    async def test_ping_returns_pong(self, fake_redis) -> None:
        """Test that Redis PING returns PONG."""
        result = await fake_redis.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_set_and_get_value(self, fake_redis) -> None:
        """Test basic set and get operations."""
        await fake_redis.set("test_key", "test_value")
        value = await fake_redis.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_expiry(self, fake_redis) -> None:
        """Test setting a key with TTL."""
        await fake_redis.setex("expiring_key", 60, "temp_value")
        value = await fake_redis.get("expiring_key")
        ttl = await fake_redis.ttl("expiring_key")

        assert value == "temp_value"
        assert ttl > 0
        assert ttl <= 60

    @pytest.mark.asyncio
    async def test_delete_key(self, fake_redis) -> None:
        """Test deleting a key."""
        await fake_redis.set("to_delete", "value")
        deleted = await fake_redis.delete("to_delete")
        value = await fake_redis.get("to_delete")

        assert deleted == 1
        assert value is None

    @pytest.mark.asyncio
    async def test_key_exists(self, fake_redis) -> None:
        """Test checking if key exists."""
        await fake_redis.set("existing_key", "value")

        assert await fake_redis.exists("existing_key") == 1
        assert await fake_redis.exists("non_existing_key") == 0


@pytest.mark.unit
class TestRQQueueOperations:
    """Unit tests for RQ-style queue operations using Redis lists."""

    @pytest.mark.asyncio
    async def test_enqueue_job_to_priority_queue(self, fake_redis) -> None:
        """Test enqueueing a job to a priority queue."""
        # Simulate RQ-style queue (uses LPUSH/RPOP pattern)
        job_data = '{"job_id": "123", "task": "process_file"}'

        # Enqueue to high priority queue
        await fake_redis.lpush("rq:queue:high", job_data)

        # Check queue length
        length = await fake_redis.llen("rq:queue:high")
        assert length == 1

        # Dequeue job
        job = await fake_redis.rpop("rq:queue:high")
        assert job == job_data

    @pytest.mark.asyncio
    async def test_multiple_priority_queues(self, fake_redis) -> None:
        """Test multiple priority queues."""
        # Add jobs to different queues
        await fake_redis.lpush("rq:queue:high", "urgent_job")
        await fake_redis.lpush("rq:queue:default", "normal_job")
        await fake_redis.lpush("rq:queue:low", "background_job")

        # Verify each queue has its job
        high_len = await fake_redis.llen("rq:queue:high")
        default_len = await fake_redis.llen("rq:queue:default")
        low_len = await fake_redis.llen("rq:queue:low")

        assert high_len == 1
        assert default_len == 1
        assert low_len == 1

    @pytest.mark.asyncio
    async def test_job_persistence_simulation(self, fake_redis) -> None:
        """Test that job data persists (simulates AOF behavior)."""
        # Store job metadata
        job_id = "job:12345"
        await fake_redis.hset(
            job_id,
            mapping={
                "status": "queued",
                "filename": "document.pdf",
                "priority": "high",
            },
        )

        # Retrieve job metadata
        status = await fake_redis.hget(job_id, "status")
        filename = await fake_redis.hget(job_id, "filename")

        assert status == "queued"
        assert filename == "document.pdf"

        # Update status
        await fake_redis.hset(job_id, "status", "processing")
        new_status = await fake_redis.hget(job_id, "status")
        assert new_status == "processing"


@pytest.mark.unit
class TestRedisListOperations:
    """Unit tests for Redis list operations used in event log."""

    @pytest.mark.asyncio
    async def test_event_log_append(self, fake_redis) -> None:
        """Test appending events to a log (for WebSocket replay)."""
        batch_id = "batch:abc123:events"

        # Append events
        await fake_redis.rpush(batch_id, '{"event_id": 1, "type": "job_started"}')
        await fake_redis.rpush(batch_id, '{"event_id": 2, "type": "job_progress"}')
        await fake_redis.rpush(batch_id, '{"event_id": 3, "type": "job_completed"}')

        # Get all events
        events = await fake_redis.lrange(batch_id, 0, -1)
        assert len(events) == 3

        # Get events after a certain point (for reconnect replay)
        events_after_1 = await fake_redis.lrange(batch_id, 1, -1)
        assert len(events_after_1) == 2

    @pytest.mark.asyncio
    async def test_event_log_with_ttl(self, fake_redis) -> None:
        """Test event log with TTL (7 day retention)."""
        batch_id = "batch:xyz789:events"

        await fake_redis.rpush(batch_id, '{"event": "test"}')
        await fake_redis.expire(batch_id, 604800)  # 7 days in seconds

        ttl = await fake_redis.ttl(batch_id)
        assert ttl > 0
        assert ttl <= 604800
