"""Unit tests for the Redis pub/sub -> WebSocket :class:`EventBridge`.

These tests verify the bridge correctly relays well-formed events to the
connection manager, ignores malformed/irrelevant payloads, and starts/stops
gracefully even when Redis is unavailable.
"""

from __future__ import annotations

import asyncio
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

    @pytest.mark.asyncio
    async def test_start_listen_relay_stop_end_to_end(self) -> None:
        """A published event is consumed by the listener and broadcast, then stop() cleans up."""
        from fakeredis import FakeServer
        from fakeredis.aioredis import FakeRedis

        server = FakeServer()

        def _fake_redis(*_args: object, **_kwargs: object) -> FakeRedis:
            return FakeRedis(server=server, decode_responses=True)

        with (
            patch(
                "rag_processor.websocket.bridge.aioredis.Redis",
                side_effect=_fake_redis,
            ),
            patch(
                "rag_processor.websocket.bridge.connection_manager.broadcast",
                new=AsyncMock(return_value=1),
            ) as mock_broadcast,
        ):
            bridge = EventBridge()
            await bridge.start()
            assert bridge.running is True

            publisher = FakeRedis(server=server, decode_responses=True)
            await publisher.publish(
                "batch:xyz:events",
                json.dumps({"batch_id": "xyz", "event_type": "job_completed"}),
            )

            # Give the listener task time to receive and relay the message.
            for _ in range(50):
                if mock_broadcast.await_count:
                    break
                await asyncio.sleep(0.02)

            await publisher.aclose()
            await bridge.stop()

        mock_broadcast.assert_awaited()
        assert mock_broadcast.await_args.args[0] == "xyz"
        assert bridge.running is False

    @pytest.mark.asyncio
    async def test_listen_reconnects_after_transient_error(self) -> None:
        """A transient listener error triggers re-subscribe and resumed relaying."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        bridge = EventBridge(initial_backoff=0, max_backoff=0)
        bridge._running = True

        class _FlakyPubSub:
            """First listen() drops the connection; the second relays one event."""

            def __init__(self) -> None:
                self.attempt = 0

            async def listen(self):
                self.attempt += 1
                if self.attempt == 1:
                    raise RedisConnectionError("connection dropped")
                yield {
                    "type": "pmessage",
                    "data": json.dumps(
                        {"batch_id": "b1", "event_type": "job_completed"}
                    ),
                }
                # Stop the loop after the first successful relay.
                bridge._running = False

        fake = _FlakyPubSub()

        with (
            patch.object(bridge, "_subscribe", new=AsyncMock(return_value=fake)),
            patch.object(bridge, "_cleanup", new=AsyncMock()),
            patch(
                "rag_processor.websocket.bridge.connection_manager.broadcast",
                new=AsyncMock(return_value=1),
            ) as mock_broadcast,
        ):
            await bridge._listen()

        # Despite the first-attempt failure, the event was relayed after retry.
        mock_broadcast.assert_awaited_once()
        assert mock_broadcast.await_args.args[0] == "b1"
        assert fake.attempt == 2


@pytest.mark.integration
class TestAppLifespanStartsBridge:
    """The application lifespan starts and stops the event bridge."""

    def test_lifespan_runs_bridge_start_and_stop(self) -> None:
        """Entering/exiting the app context triggers bridge startup and shutdown."""
        from fastapi.testclient import TestClient

        from rag_processor.main import app

        # Using TestClient as a context manager runs the lifespan handler.
        with TestClient(app) as client:
            assert client.get("/health/live").status_code == 200
            assert isinstance(app.state.event_bridge, EventBridge)
