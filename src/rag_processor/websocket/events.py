"""Event types and publishing for WebSocket updates.

Defines event structure and functions for publishing events to Redis.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

UTC = timezone.utc
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import redis
from pydantic import BaseModel, Field

from rag_processor.core.config import settings
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)

# Redis channel prefix for batch events
BATCH_EVENTS_CHANNEL = "batch:{batch_id}:events"
BATCH_EVENTS_LIST = "batch:{batch_id}:event_history"


class EventType(str, Enum):
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
        event_id: Unique event identifier.
        event_type: Type of event.
        batch_id: Batch identifier.
        job_id: Job identifier (for job events).
        status: Current status.
        message: Human-readable message.
        data: Additional event data.
        timestamp: Event timestamp.
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
            Dictionary with string UUIDs and ISO timestamp.
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

    Returns:
        Redis client instance.
    """
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        db=settings.redis_db,
        decode_responses=True,
    )


def publish_event(event: BatchEvent, redis_client: redis.Redis | None = None) -> None:
    """Publish an event to Redis for WebSocket broadcasting.

    Publishes to a channel for real-time broadcast and stores
    in a list for event replay on reconnect.

    Args:
        event: Event to publish.
        redis_client: Optional Redis client (for testing).
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
        batch_id: Batch identifier.
        redis_client: Optional Redis client (for testing).
        limit: Maximum events to return.

    Returns:
        List of events (oldest first).
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
        event_type: Type of event.
        batch_id: Batch identifier.
        job_id: Job identifier.
        status: Current status.
        message: Human-readable message.
        **data: Additional event data.

    Returns:
        BatchEvent instance.
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
        event_type: Type of event.
        batch_id: Batch identifier.
        status: Current status.
        message: Human-readable message.
        **data: Additional event data.

    Returns:
        BatchEvent instance.
    """
    return BatchEvent(
        event_type=event_type,
        batch_id=batch_id,
        status=status,
        message=message,
        data=data,
    )
