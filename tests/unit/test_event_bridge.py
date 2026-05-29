"""Unit tests for the Redis pub/sub -> WebSocket :class:`EventBridge`.

These tests verify the bridge correctly relays well-formed events to the
connection manager, ignores malformed/irrelevant payloads, and starts/stops
gracefully even when Redis is unavailable.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from rag_processor.websocket.bridge import EventBridge


@pytest.mark.unit
class TestEventBridgeRelay:
    """Tests for payload parsing and relaying to the connection manager."""

    @pytest.mark.asyncio
    async def test_relay_broadcasts_well_formed_event(self) -> None:
        """A valid event payload is broadcast to its batch's connections."""
        bridge = EventBridge()
        event = {
            "event_type": "job_completed",
            "batch_id": "11111111-1111-1111-1111-111111111111",
            "job_id": "22222222-2222-2222-2222-222222222222",
            "status": "completed",
            "data": {"filename": "doc.pdf"},
        }

        with patch(
            "rag_processor.websocket.bridge.connection_manager.broadcast",
            new=AsyncMock(return_value=1),
        ) as mock_broadcast:
            await bridge._relay(json.dumps(event))

        mock_broadcast.assert_awaited_once()
        args = mock_broadcast.await_args.args
        assert args[0] == event["batch_id"]
        assert args[1]["event_type"] == "job_completed"

    @pytest.mark.asyncio
    async def test_relay_ignores_non_string_payload(self) -> None:
        """Non-string payloads (e.g. None) are ignored without broadcasting."""
        bridge = EventBridge()
        with patch(
            "rag_processor.websocket.bridge.connection_manager.broadcast",
            new=AsyncMock(),
        ) as mock_broadcast:
            await bridge._relay(None)

        mock_broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_relay_ignores_malformed_json(self) -> None:
        """Malformed JSON is logged and ignored, never broadcast."""
        bridge = EventBridge()
        with patch(
            "rag_processor.websocket.bridge.connection_manager.broadcast",
            new=AsyncMock(),
        ) as mock_broadcast:
            await bridge._relay("{not valid json")

        mock_broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_relay_ignores_event_without_batch_id(self) -> None:
        """An event lacking a batch_id cannot be routed and is dropped."""
        bridge = EventBridge()
        with patch(
            "rag_processor.websocket.bridge.connection_manager.broadcast",
            new=AsyncMock(),
        ) as mock_broadcast:
            await bridge._relay(json.dumps({"status": "ok"}))

        mock_broadcast.assert_not_awaited()


@pytest.mark.unit
class TestEventBridgeLifecycle:
    """Tests for graceful start/stop behavior."""

    @pytest.mark.asyncio
    async def test_start_degrades_gracefully_when_redis_unavailable(self) -> None:
        """If subscribing raises, the bridge stays disabled and does not raise."""
        with patch("rag_processor.websocket.bridge.aioredis.Redis") as mock_redis_cls:
            mock_client = mock_redis_cls.return_value
            mock_client.pubsub.side_effect = OSError("redis down")
            mock_client.aclose = AsyncMock()

            bridge = EventBridge()
            await bridge.start()

        assert bridge.running is False
        # stop() on a never-started bridge must be safe.
        await bridge.stop()
