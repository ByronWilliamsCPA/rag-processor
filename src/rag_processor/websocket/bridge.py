"""Redis pub/sub -> WebSocket bridge.

Background workers publish batch/job events to Redis pub/sub channels
(``batch:{batch_id}:events``) via :mod:`rag_processor.websocket.events`. The API
process, however, is what holds the live WebSocket connections in its in-process
:data:`~rag_processor.websocket.connection_manager.connection_manager`.

This module provides the missing link: an :class:`EventBridge` that subscribes
to the event channels and relays every message to the locally connected clients
for the relevant batch. Without it, events would be published but never reach
the browser.

The bridge degrades gracefully: if Redis is unavailable at startup the bridge
logs a warning and stays disabled rather than crashing the application.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING, Any

from redis import asyncio as aioredis
from redis.exceptions import RedisError

from rag_processor.core.config import settings
from rag_processor.utils.logging import get_logger
from rag_processor.websocket.connection_manager import connection_manager

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub

logger = get_logger(__name__)

# Glob pattern matching every per-batch event channel.
EVENT_CHANNEL_PATTERN = "batch:*:events"


class EventBridge:
    """Relays Redis pub/sub batch events to local WebSocket connections.

    Example:
        bridge = EventBridge()
        await bridge.start()
        ...
        await bridge.stop()
    """

    def __init__(self) -> None:
        """Initialize the bridge in a stopped state."""
        self._redis: aioredis.Redis | None = None
        self._pubsub: PubSub | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def running(self) -> bool:
        """Whether the bridge is actively listening for events."""
        return self._running

    async def start(self) -> None:
        """Subscribe to event channels and begin relaying messages.

        Safe to call when Redis is unavailable: failures are logged and the
        bridge remains disabled instead of propagating the error.
        """
        try:
            self._redis = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                db=settings.redis_db,
                decode_responses=True,
            )
            self._pubsub = self._redis.pubsub()
            await self._pubsub.psubscribe(EVENT_CHANNEL_PATTERN)
        except (RedisError, OSError) as e:
            logger.warning(
                "Event bridge disabled: could not subscribe to Redis events",
                error=str(e),
            )
            await self._cleanup()
            return

        self._running = True
        self._task = asyncio.create_task(self._listen())
        logger.info("Event bridge started", pattern=EVENT_CHANNEL_PATTERN)

    async def stop(self) -> None:
        """Stop relaying and release Redis resources."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        await self._cleanup()
        logger.info("Event bridge stopped")

    async def _cleanup(self) -> None:
        """Close the pub/sub subscription and Redis connection."""
        if self._pubsub is not None:
            with contextlib.suppress(RedisError, OSError):
                await self._pubsub.punsubscribe(EVENT_CHANNEL_PATTERN)
                await self._pubsub.aclose()
            self._pubsub = None

        if self._redis is not None:
            with contextlib.suppress(RedisError, OSError):
                await self._redis.aclose()
            self._redis = None

    async def _listen(self) -> None:
        """Consume pub/sub messages and broadcast them to WebSocket clients."""
        if self._pubsub is None:
            return

        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                await self._relay(message.get("data"))
        except asyncio.CancelledError:
            raise
        except (RedisError, OSError) as e:
            logger.warning("Event bridge listener stopped on error", error=str(e))
            self._running = False

    async def _relay(self, raw: Any) -> None:
        """Parse a raw pub/sub payload and broadcast it to the batch's clients.

        Args:
            raw: The raw ``data`` field from a pub/sub message (JSON string).
        """
        if not isinstance(raw, str):
            return

        try:
            event: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Event bridge received malformed event payload")
            return

        batch_id = event.get("batch_id")
        if not batch_id:
            return

        await connection_manager.broadcast(str(batch_id), event)
