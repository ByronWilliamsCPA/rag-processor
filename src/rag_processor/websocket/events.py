"""Event types and publishing for WebSocket updates.

Defines event structure and functions for publishing events to Redis.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from rag_processor.core.redis import get_redis_client as _get_shared_redis_client
from rag_processor.utils.logging import get_logger

if TYPE_CHECKING:
    import redis

UTC = timezone.utc  # noqa: UP017

logger = get_logger(__name__)

# Redis channel prefix for batch events
BATCH_EVENTS_CHANNEL = "batch:{batch_id}:events"
BATCH_EVENTS_LIST = "batch:{batch_id}:event_history"


class EventType(StrEnum):
    """Types of batch events.

    Attributes:
        JOB_QUEUED: Job added to queue.
        JOB_PROCESSING: Job started processing.
        JOB_COMPLETED: Job completed successfully.
        JOB_FAILED: Job failed.
        BATCH_CREATED: Batch created.
        BATCH_COMPLETED: All jobs in batch completed.
        BATCH_FAILED: All jobs in batch failed.
    """

    JOB_QUEUED = "job_queued"
    JOB_PROCESSING = "job_processing"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    BATCH_CREATED = "batch_created"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"


class BatchEvent(BaseModel):
    """Event for batch/job status updates.

    Attributes:
        event_id (UUID): Unique event identifier.
        event_type (EventType): Type of event.
        batch_id (UUID): Batch identifier.
        job_id (UUID | None): Job identifier (for job events).
        status (str): Current status.
        message (str): Human-readable message.
        data (dict[str, Any]): Additional event data.
        timestamp (datetime): Event timestamp.
    """

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    batch_id: UUID
    job_id: UUID | None = None
    status: str
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    def to_json_dict(self) -> dict[str, Any]:
        """Convert event to JSON-serializable dict.

        Returns:
            dict[str, Any]: Dictionary with string UUIDs and ISO timestamp.
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "batch_id": str(self.batch_id),
            "job_id": str(self.job_id) if self.job_id else None,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


def get_redis_client() -> redis.Redis:
    """Get a Redis client for event publishing.

    Returns a decoded (str) client backed by the shared connection pool in
    ``core/redis.py`` so event publishing reuses the same Redis connections as
    the rest of the application.

    Returns:
        redis.Redis: Redis client instance.
    """
    return _get_shared_redis_client(decode_responses=True)


def publish_event(event: BatchEvent, redis_client: redis.Redis | None = None) -> None:
    """Publish an event to Redis for WebSocket broadcasting.

    Publishes to a channel for real-time broadcast and stores
    in a list for event replay on reconnect.

    Args:
        event (BatchEvent): Event to publish.
        redis_client (redis.Redis | None): Optional Redis client (for testing).
    """
    client = redis_client or get_redis_client()

    batch_id = str(event.batch_id)
    channel = BATCH_EVENTS_CHANNEL.format(batch_id=batch_id)
    history_key = BATCH_EVENTS_LIST.format(batch_id=batch_id)

    event_json = event.model_dump_json()

    # Publish to channel for real-time subscribers
    client.publish(channel, event_json)

    # Store in list for replay (keep last 100 events)
    client.lpush(history_key, event_json)
    client.ltrim(history_key, 0, 99)

    logger.debug(
        "Event published",
        event_type=event.event_type.value,
        batch_id=batch_id,
        job_id=str(event.job_id) if event.job_id else None,
    )


def get_event_history(
    batch_id: UUID | str,
    redis_client: redis.Redis | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get event history for a batch.

    Used for replay on WebSocket reconnect.

    Args:
        batch_id (UUID | str): Batch identifier.
        redis_client (redis.Redis | None): Optional Redis client (for testing).
        limit (int): Maximum events to return.

    Returns:
        list[dict[str, Any]]: List of events (oldest first).
    """
    client = redis_client or get_redis_client()
    history_key = BATCH_EVENTS_LIST.format(batch_id=str(batch_id))

    # Get events from list (stored newest first)
    events_json = client.lrange(history_key, 0, limit - 1)

    # Parse and reverse to get oldest first
    events = []
    for event_str in reversed(events_json):  # type: ignore[arg-type]
        try:
            events.append(json.loads(event_str))
        except json.JSONDecodeError:
            logger.warning("Failed to parse event from history", raw_event=event_str)

    return events


async def get_event_history_async(
    batch_id: UUID | str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Async, non-blocking wrapper around :func:`get_event_history`.

    Offloads the synchronous Redis reads to a worker thread so async WebSocket
    handlers do not block the event loop, mirroring the ``*_async`` wrappers in
    ``rag_processor.queue.jobs``.

    Args:
        batch_id (UUID | str): Batch identifier.
        limit (int): Maximum events to return.

    Returns:
        list[dict[str, Any]]: List of events (oldest first).
    """
    return await asyncio.to_thread(get_event_history, batch_id, limit=limit)


def create_job_event(
    event_type: EventType,
    batch_id: UUID,
    job_id: UUID,
    status: str,
    message: str = "",
    **data: Any,
) -> BatchEvent:
    """Create a job-related event.

    Args:
        event_type (EventType): Type of event.
        batch_id (UUID): Batch identifier.
        job_id (UUID): Job identifier.
        status (str): Current status.
        message (str): Human-readable message.
        **data (Any): Additional event data.

    Returns:
        BatchEvent: BatchEvent instance.
    """
    return BatchEvent(
        event_type=event_type,
        batch_id=batch_id,
        job_id=job_id,
        status=status,
        message=message,
        data=data,
    )


def create_batch_event(
    event_type: EventType,
    batch_id: UUID,
    status: str,
    message: str = "",
    **data: Any,
) -> BatchEvent:
    """Create a batch-level event.

    Args:
        event_type (EventType): Type of event.
        batch_id (UUID): Batch identifier.
        status (str): Current status.
        message (str): Human-readable message.
        **data (Any): Additional event data.

    Returns:
        BatchEvent: BatchEvent instance.
    """
    return BatchEvent(
        event_type=event_type,
        batch_id=batch_id,
        status=status,
        message=message,
        data=data,
    )
