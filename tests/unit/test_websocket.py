"""Tests for WebSocket module."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.websocket.connection_manager import ConnectionManager
from rag_processor.websocket.events import (
    BatchEvent,
    EventType,
    create_batch_event,
    create_job_event,
)

UTC = timezone.utc  # noqa: UP017


class TestConnectionManager:
    """Tests for ConnectionManager."""

    @pytest.fixture
    def manager(self) -> ConnectionManager:
        """Create a fresh connection manager."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(
        self, manager: ConnectionManager, mock_websocket: MagicMock
    ) -> None:
        """Test that connect accepts the websocket."""
        batch_id = uuid4()
        await manager.connect(mock_websocket, batch_id)

        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_tracks_connection(
        self, manager: ConnectionManager, mock_websocket: MagicMock
    ) -> None:
        """Test that connect tracks the connection."""
        batch_id = uuid4()
        await manager.connect(mock_websocket, batch_id)

        assert manager.get_connection_count(batch_id) == 1

    @pytest.mark.asyncio
    async def test_multiple_connections_same_batch(
        self, manager: ConnectionManager
    ) -> None:
        """Test multiple connections to the same batch."""
        batch_id = uuid4()
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()

        await manager.connect(ws1, batch_id)
        await manager.connect(ws2, batch_id)

        assert manager.get_connection_count(batch_id) == 2

    def test_disconnect_removes_connection(
        self, manager: ConnectionManager, mock_websocket: MagicMock
    ) -> None:
        """Test that disconnect removes the connection."""
        batch_id = uuid4()
        batch_key = str(batch_id)

        # Manually add connection (bypass connect to avoid accept call)
        manager._connections[batch_key].add(mock_websocket)
        assert manager.get_connection_count(batch_id) == 1

        manager.disconnect(mock_websocket, batch_id)
        assert manager.get_connection_count(batch_id) == 0

    def test_disconnect_cleans_empty_batch(
        self, manager: ConnectionManager, mock_websocket: MagicMock
    ) -> None:
        """Test that disconnect removes empty batch entries."""
        batch_id = uuid4()
        batch_key = str(batch_id)

        manager._connections[batch_key].add(mock_websocket)
        manager.disconnect(mock_websocket, batch_id)

        assert batch_key not in manager._connections

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self, manager: ConnectionManager) -> None:
        """Test that broadcast sends to all connections."""
        batch_id = uuid4()

        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, batch_id)
        await manager.connect(ws2, batch_id)

        message = {"type": "test", "data": "hello"}
        sent_count = await manager.broadcast(batch_id, message)

        assert sent_count == 2
        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_returns_zero_for_no_connections(
        self, manager: ConnectionManager
    ) -> None:
        """Test that broadcast returns 0 for no connections."""
        batch_id = uuid4()
        sent_count = await manager.broadcast(batch_id, {"type": "test"})
        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_failed_sends(
        self, manager: ConnectionManager
    ) -> None:
        """Test that broadcast handles failed sends gracefully."""
        batch_id = uuid4()

        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock(side_effect=RuntimeError("Connection closed"))

        await manager.connect(ws1, batch_id)
        await manager.connect(ws2, batch_id)

        sent_count = await manager.broadcast(batch_id, {"type": "test"})

        # One succeeded, one failed
        assert sent_count == 1
        # Failed connection should be removed
        assert manager.get_connection_count(batch_id) == 1

    @pytest.mark.asyncio
    async def test_send_personal_success(
        self, manager: ConnectionManager, mock_websocket: MagicMock
    ) -> None:
        """Test successful personal message send."""
        result = await manager.send_personal(mock_websocket, {"type": "test"})

        assert result is True
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_personal_failure(
        self, manager: ConnectionManager, mock_websocket: MagicMock
    ) -> None:
        """Test failed personal message send."""
        mock_websocket.send_json = AsyncMock(side_effect=RuntimeError("closed"))

        result = await manager.send_personal(mock_websocket, {"type": "test"})

        assert result is False

    def test_get_all_batch_ids(self, manager: ConnectionManager) -> None:
        """Test getting all batch IDs with connections."""
        batch1 = str(uuid4())
        batch2 = str(uuid4())

        manager._connections[batch1].add(MagicMock())
        manager._connections[batch2].add(MagicMock())

        batch_ids = manager.get_all_batch_ids()

        assert set(batch_ids) == {batch1, batch2}

    def test_clear_all(self, manager: ConnectionManager) -> None:
        """Test clearing all connections."""
        batch1 = str(uuid4())
        batch2 = str(uuid4())

        manager._connections[batch1].add(MagicMock())
        manager._connections[batch2].add(MagicMock())

        manager.clear_all()

        assert len(manager._connections) == 0


class TestBatchEvent:
    """Tests for BatchEvent model."""

    def test_event_creation(self) -> None:
        """Test creating a batch event."""
        batch_id = uuid4()
        event = BatchEvent(
            event_type=EventType.JOB_QUEUED,
            batch_id=batch_id,
            status="queued",
            message="Job queued for processing",
        )

        assert event.event_type == EventType.JOB_QUEUED
        assert event.batch_id == batch_id
        assert event.status == "queued"
        assert event.event_id is not None

    def test_event_with_job_id(self) -> None:
        """Test creating event with job ID."""
        batch_id = uuid4()
        job_id = uuid4()
        event = BatchEvent(
            event_type=EventType.JOB_PROCESSING,
            batch_id=batch_id,
            job_id=job_id,
            status="processing",
        )

        assert event.job_id == job_id

    def test_to_json_dict(self) -> None:
        """Test converting event to JSON dict."""
        batch_id = uuid4()
        job_id = uuid4()
        event = BatchEvent(
            event_type=EventType.JOB_COMPLETED,
            batch_id=batch_id,
            job_id=job_id,
            status="completed",
            message="Job completed successfully",
            data={"result": "success"},
        )

        json_dict = event.to_json_dict()

        assert json_dict["event_id"] == str(event.event_id)
        assert json_dict["event_type"] == "job_completed"
        assert json_dict["batch_id"] == str(batch_id)
        assert json_dict["job_id"] == str(job_id)
        assert json_dict["status"] == "completed"
        assert "timestamp" in json_dict


class TestEventCreation:
    """Tests for event creation functions."""

    def test_create_job_event(self) -> None:
        """Test creating a job event."""
        batch_id = uuid4()
        job_id = uuid4()

        event = create_job_event(
            event_type=EventType.JOB_FAILED,
            batch_id=batch_id,
            job_id=job_id,
            status="failed",
            message="Job failed due to error",
            error="Timeout",
        )

        assert event.event_type == EventType.JOB_FAILED
        assert event.batch_id == batch_id
        assert event.job_id == job_id
        assert event.data["error"] == "Timeout"

    def test_create_batch_event(self) -> None:
        """Test creating a batch event."""
        batch_id = uuid4()

        event = create_batch_event(
            event_type=EventType.BATCH_COMPLETED,
            batch_id=batch_id,
            status="completed",
            message="All jobs completed",
            total_jobs=5,
        )

        assert event.event_type == EventType.BATCH_COMPLETED
        assert event.batch_id == batch_id
        assert event.job_id is None
        assert event.data["total_jobs"] == 5


class TestEventTypes:
    """Tests for EventType enum."""

    def test_job_event_types(self) -> None:
        """Test job-related event types."""
        assert EventType.JOB_QUEUED.value == "job_queued"
        assert EventType.JOB_PROCESSING.value == "job_processing"
        assert EventType.JOB_COMPLETED.value == "job_completed"
        assert EventType.JOB_FAILED.value == "job_failed"

    def test_batch_event_types(self) -> None:
        """Test batch-related event types."""
        assert EventType.BATCH_CREATED.value == "batch_created"
        assert EventType.BATCH_COMPLETED.value == "batch_completed"
        assert EventType.BATCH_FAILED.value == "batch_failed"


class TestPublishEvent:
    """Tests for publish_event function."""

    def test_publish_event_to_redis(self) -> None:
        """Test publishing event to Redis channel and history."""
        from rag_processor.websocket.events import publish_event

        batch_id = uuid4()
        event = BatchEvent(
            event_type=EventType.JOB_QUEUED,
            batch_id=batch_id,
            status="queued",
            message="Job queued",
        )

        mock_redis = MagicMock()

        with patch("rag_processor.websocket.events.logger"):
            publish_event(event, redis_client=mock_redis)

        # Should publish to channel
        mock_redis.publish.assert_called_once()
        # Should store in history list
        mock_redis.lpush.assert_called_once()
        # Should trim to keep last 100
        mock_redis.ltrim.assert_called_once()

    def test_publish_event_creates_client_if_not_provided(self) -> None:
        """Test that publish_event creates Redis client when not provided."""
        from rag_processor.websocket.events import publish_event

        batch_id = uuid4()
        event = BatchEvent(
            event_type=EventType.JOB_COMPLETED,
            batch_id=batch_id,
            status="completed",
        )

        mock_redis = MagicMock()

        with (
            patch(
                "rag_processor.websocket.events.get_redis_client",
                return_value=mock_redis,
            ) as mock_get_client,
            patch("rag_processor.websocket.events.logger"),
        ):
            publish_event(event)

        mock_get_client.assert_called_once()


class TestGetEventHistory:
    """Tests for get_event_history function."""

    def test_get_event_history_success(self) -> None:
        """Test getting event history from Redis."""
        import json

        from rag_processor.websocket.events import get_event_history

        batch_id = uuid4()
        event1 = {"event_id": str(uuid4()), "type": "first"}
        event2 = {"event_id": str(uuid4()), "type": "second"}

        # Redis stores newest first, we should reverse
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [
            json.dumps(event2),
            json.dumps(event1),
        ]

        with patch("rag_processor.websocket.events.logger"):
            result = get_event_history(batch_id, redis_client=mock_redis)

        # Should return oldest first
        assert len(result) == 2
        assert result[0]["type"] == "first"
        assert result[1]["type"] == "second"

    def test_get_event_history_handles_invalid_json(self) -> None:
        """Test get_event_history handles malformed JSON gracefully."""
        import json

        from rag_processor.websocket.events import get_event_history

        batch_id = uuid4()
        valid_event = {"event_id": str(uuid4()), "type": "valid"}

        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [
            "not valid json",
            json.dumps(valid_event),
        ]

        with patch("rag_processor.websocket.events.logger"):
            result = get_event_history(batch_id, redis_client=mock_redis)

        # Should only contain the valid event
        assert len(result) == 1
        assert result[0]["type"] == "valid"

    def test_get_event_history_creates_client_if_not_provided(self) -> None:
        """Test that get_event_history creates Redis client when not provided."""
        from rag_processor.websocket.events import get_event_history

        batch_id = uuid4()

        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []

        with (
            patch(
                "rag_processor.websocket.events.get_redis_client",
                return_value=mock_redis,
            ) as mock_get_client,
            patch("rag_processor.websocket.events.logger"),
        ):
            get_event_history(batch_id)

        mock_get_client.assert_called_once()

    def test_get_event_history_with_limit(self) -> None:
        """Test get_event_history respects limit parameter."""
        from rag_processor.websocket.events import get_event_history

        batch_id = uuid4()

        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []

        with patch("rag_processor.websocket.events.logger"):
            get_event_history(batch_id, redis_client=mock_redis, limit=50)

        # Should call lrange with 0 to limit-1
        mock_redis.lrange.assert_called_once()
        call_args = mock_redis.lrange.call_args[0]
        assert call_args[1] == 0
        assert call_args[2] == 49

    @pytest.mark.asyncio
    async def test_get_event_history_async_offloads_and_returns(self) -> None:
        """The async wrapper forwards to the sync reader and returns its value."""
        from rag_processor.websocket.events import get_event_history_async

        events = [{"event_id": "e1"}]
        with patch(
            "rag_processor.websocket.events.get_event_history",
            return_value=events,
        ) as mock_sync:
            result = await get_event_history_async(uuid4(), limit=25)

        assert result == events
        mock_sync.assert_called_once()
        assert mock_sync.call_args.kwargs["limit"] == 25


class TestWebSocketRouter:
    """Tests for WebSocket router."""

    @pytest.fixture(autouse=True)
    def mock_auth_settings(self) -> None:
        """Mock auth settings to disable Cloudflare auth."""
        with patch("rag_processor.websocket.router.settings") as mock:
            mock.cloudflare_enabled = False
            yield mock

    @pytest.fixture
    def mock_batch(self) -> Batch:
        """Create a mock batch."""
        return Batch(
            batch_id=uuid4(),
            created_by_email="test@example.com",
            status=BatchStatus.PROCESSING,
            total_files=1,
            created_at=datetime.now(tz=UTC),
        )

    @pytest.mark.asyncio
    async def test_verify_ws_token_bypass_mode(self) -> None:
        """Test token verification in bypass mode."""
        from rag_processor.websocket.router import verify_ws_token

        with patch("rag_processor.websocket.router.settings") as mock:
            mock.cloudflare_enabled = False
            result = await verify_ws_token(None)

        assert result is not None
        # Bypass identity must match CloudflareAuthMiddleware._get_bypass_user
        # so ownership checks work across HTTP and WebSocket. See PR #26 review.
        assert result["email"] == "dev@localhost"
        assert result["user_id"] == "dev-user-001"

    @pytest.mark.asyncio
    async def test_verify_ws_token_no_token_with_auth(self) -> None:
        """Test token verification returns None when no token provided."""
        from rag_processor.websocket.router import verify_ws_token

        with patch("rag_processor.websocket.router.settings") as mock:
            mock.cloudflare_enabled = True
            result = await verify_ws_token(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_replay_events_sends_after_last_id(self) -> None:
        """Test event replay sends events after last_event_id."""
        from rag_processor.websocket.router import _replay_events

        batch_id = uuid4()
        event1_id = str(uuid4())
        event2_id = str(uuid4())
        event3_id = str(uuid4())

        mock_history = [
            {"event_id": event1_id, "type": "first"},
            {"event_id": event2_id, "type": "second"},
            {"event_id": event3_id, "type": "third"},
        ]

        mock_websocket = MagicMock()
        mock_websocket.send_json = AsyncMock()

        with (
            patch(
                "rag_processor.websocket.events.get_event_history",
                return_value=mock_history,
            ),
            patch("rag_processor.websocket.router.connection_manager") as mock_manager,
        ):
            mock_manager.send_personal = AsyncMock()

            await _replay_events(mock_websocket, batch_id, event1_id)

            # Should have sent event2 and event3 (after event1)
            assert mock_manager.send_personal.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_client_message_ping(self) -> None:
        """Test handling ping message from client."""
        from rag_processor.websocket.router import _handle_client_message

        mock_websocket = MagicMock()

        with patch("rag_processor.websocket.router.connection_manager") as mock_manager:
            mock_manager.send_personal = AsyncMock()

            await _handle_client_message(
                mock_websocket,
                {"type": "ping", "timestamp": 12345},
            )

            mock_manager.send_personal.assert_called_once()
            call_args = mock_manager.send_personal.call_args
            assert call_args[0][1]["type"] == "pong"
            assert call_args[0][1]["timestamp"] == 12345
