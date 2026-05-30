"""Tests for WebSocket router endpoints.

Tests WebSocket connection handling and message processing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_ws_logger():
    """Mock the WebSocket router logger to handle structlog-style kwargs."""
    with patch("rag_processor.websocket.router.logger", MagicMock()) as mock_logger:
        yield mock_logger


class TestVerifyWsToken:
    """Tests for WebSocket token verification."""

    @pytest.mark.asyncio
    async def test_verify_ws_token_auth_disabled(self) -> None:
        """Bypass identity must match CloudflareAuthMiddleware._get_bypass_user.

        Regression for PR #26 review: a mismatch (anonymous@local vs
        dev@localhost) broke ownership checks for batches created over HTTP
        in dev mode.
        """
        mock_settings = MagicMock()
        mock_settings.cloudflare_enabled = False

        with patch("rag_processor.websocket.router.settings", mock_settings):
            from rag_processor.websocket.router import verify_ws_token

            result = await verify_ws_token(None)

        assert result is not None
        assert result["email"] == "dev@localhost"
        assert result["user_id"] == "dev-user-001"

    @pytest.mark.asyncio
    async def test_verify_ws_token_swallows_network_errors(self) -> None:
        """Non-JWT errors from verify_cloudflare_token must close cleanly.

        Regression for PR #26 review: httpx.ConnectError / TimeoutException /
        HTTPStatusError and json.JSONDecodeError aren't jwt.* subclasses and
        previously propagated, closing the socket with 1011 (internal error)
        instead of 1008 (policy violation). Mirror the HTTP middleware's
        broad except.
        """
        import httpx

        mock_settings = MagicMock()
        mock_settings.cloudflare_enabled = True

        mock_verify = AsyncMock(side_effect=httpx.ConnectError("JWKS unreachable"))

        with (
            patch("rag_processor.websocket.router.settings", mock_settings),
            patch(
                "rag_processor.websocket.router.verify_cloudflare_token", mock_verify
            ),
        ):
            from rag_processor.websocket.router import verify_ws_token

            result = await verify_ws_token("opaque-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_ws_token_no_token_with_auth_enabled(self) -> None:
        """Test token verification fails with no token when auth enabled."""
        mock_settings = MagicMock()
        mock_settings.cloudflare_enabled = True

        with patch("rag_processor.websocket.router.settings", mock_settings):
            from rag_processor.websocket.router import verify_ws_token

            result = await verify_ws_token(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_ws_token_valid_token(self) -> None:
        """Test token verification with valid token."""
        mock_settings = MagicMock()
        mock_settings.cloudflare_enabled = True

        mock_verify = AsyncMock(
            return_value={"email": "user@example.com", "user_id": "user-123"}
        )

        with (
            patch("rag_processor.websocket.router.settings", mock_settings),
            patch(
                "rag_processor.websocket.router.verify_cloudflare_token", mock_verify
            ),
        ):
            from rag_processor.websocket.router import verify_ws_token

            result = await verify_ws_token("valid-token")

        assert result is not None
        assert result["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_verify_ws_token_invalid_token(self) -> None:
        """Test token verification with invalid token."""
        import jwt

        mock_settings = MagicMock()
        mock_settings.cloudflare_enabled = True

        mock_verify = AsyncMock(side_effect=jwt.InvalidTokenError("Invalid"))

        with (
            patch("rag_processor.websocket.router.settings", mock_settings),
            patch(
                "rag_processor.websocket.router.verify_cloudflare_token", mock_verify
            ),
        ):
            from rag_processor.websocket.router import verify_ws_token

            result = await verify_ws_token("invalid-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_ws_token_expired_token(self) -> None:
        """Test token verification with expired token."""
        import jwt

        mock_settings = MagicMock()
        mock_settings.cloudflare_enabled = True

        mock_verify = AsyncMock(side_effect=jwt.ExpiredSignatureError("Expired"))

        with (
            patch("rag_processor.websocket.router.settings", mock_settings),
            patch(
                "rag_processor.websocket.router.verify_cloudflare_token", mock_verify
            ),
        ):
            from rag_processor.websocket.router import verify_ws_token

            result = await verify_ws_token("expired-token")

        assert result is None


class TestReplayEvents:
    """Tests for event replay functionality."""

    @pytest.mark.asyncio
    async def test_replay_events_from_last_event(self) -> None:
        """Test replaying events after a specific event ID."""
        batch_id = uuid4()
        mock_websocket = AsyncMock()

        events = [
            {"event_id": "event-1", "type": "job_queued"},
            {"event_id": "event-2", "type": "job_processing"},
            {"event_id": "event-3", "type": "job_completed"},
        ]

        mock_history = MagicMock(return_value=events)
        mock_cm = MagicMock()
        mock_cm.send_personal = AsyncMock()

        with (
            patch("rag_processor.websocket.router.get_event_history", mock_history),
            patch("rag_processor.websocket.router.connection_manager", mock_cm),
        ):
            from rag_processor.websocket.router import _replay_events

            await _replay_events(mock_websocket, batch_id, "event-1")

        # Should send event-2 and event-3 (events after event-1)
        assert mock_cm.send_personal.call_count == 2

    @pytest.mark.asyncio
    async def test_replay_events_no_match(self) -> None:
        """Test replay when last_event_id not found in history."""
        batch_id = uuid4()
        mock_websocket = AsyncMock()

        events = [
            {"event_id": "event-1", "type": "job_queued"},
            {"event_id": "event-2", "type": "job_processing"},
        ]

        mock_history = MagicMock(return_value=events)
        mock_cm = MagicMock()
        mock_cm.send_personal = AsyncMock()

        with (
            patch("rag_processor.websocket.router.get_event_history", mock_history),
            patch("rag_processor.websocket.router.connection_manager", mock_cm),
        ):
            from rag_processor.websocket.router import _replay_events

            await _replay_events(mock_websocket, batch_id, "nonexistent-event")

        # Should not send any events since last_event_id wasn't found
        mock_cm.send_personal.assert_not_called()


class TestHandleClientMessage:
    """Tests for client message handling."""

    @pytest.mark.asyncio
    async def test_handle_ping_message(self) -> None:
        """Test handling ping message from client."""
        mock_websocket = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.send_personal = AsyncMock()

        with patch("rag_processor.websocket.router.connection_manager", mock_cm):
            from rag_processor.websocket.router import _handle_client_message

            await _handle_client_message(
                mock_websocket, {"type": "ping", "timestamp": 1234567890}
            )

        mock_cm.send_personal.assert_called_once()
        call_args = mock_cm.send_personal.call_args
        assert call_args[0][1]["type"] == "pong"
        assert call_args[0][1]["timestamp"] == 1234567890

    @pytest.mark.asyncio
    async def test_handle_unknown_message(self) -> None:
        """Test handling unknown message type."""
        mock_websocket = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.send_personal = AsyncMock()

        with patch("rag_processor.websocket.router.connection_manager", mock_cm):
            from rag_processor.websocket.router import _handle_client_message

            await _handle_client_message(
                mock_websocket, {"type": "unknown", "data": "test"}
            )

        # Unknown messages are silently ignored
        mock_cm.send_personal.assert_not_called()


class TestWebSocketEndpoint:
    """Tests for the WebSocket batch status endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_rejects_unauthenticated(self) -> None:
        """Test WebSocket rejects connection without valid auth."""
        from fastapi import WebSocket, status

        batch_id = uuid4()
        mock_websocket = AsyncMock(spec=WebSocket)

        mock_verify = AsyncMock(return_value=None)

        with patch("rag_processor.websocket.router.verify_ws_token", mock_verify):
            from rag_processor.websocket.router import websocket_batch_status

            await websocket_batch_status(
                mock_websocket, batch_id, cf_access_token=None, last_event_id=None
            )

        mock_websocket.close.assert_called_once_with(
            code=status.WS_1008_POLICY_VIOLATION
        )

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_batch(self) -> None:
        """Test WebSocket rejects connection for non-existent batch."""
        from fastapi import WebSocket, status

        batch_id = uuid4()
        mock_websocket = AsyncMock(spec=WebSocket)

        mock_verify = AsyncMock(
            return_value={"email": "user@example.com", "user_id": "user-123"}
        )
        mock_batch_status = AsyncMock(return_value=(None, []))

        with (
            patch("rag_processor.websocket.router.verify_ws_token", mock_verify),
            patch(
                "rag_processor.websocket.router.get_batch_status_async",
                mock_batch_status,
            ),
        ):
            from rag_processor.websocket.router import websocket_batch_status

            await websocket_batch_status(
                mock_websocket, batch_id, cf_access_token="valid-token"
            )

        mock_websocket.close.assert_called_once_with(
            code=status.WS_1008_POLICY_VIOLATION
        )

    @pytest.mark.asyncio
    async def test_websocket_rejects_non_owner(self, mock_ws_logger: MagicMock) -> None:
        """Caller authenticated as user A cannot subscribe to user B's batch."""
        from fastapi import WebSocket, status

        batch_id = uuid4()
        mock_websocket = AsyncMock(spec=WebSocket)

        mock_verify = AsyncMock(
            return_value={"email": "intruder@example.com", "user_id": "u-intruder"}
        )

        # Batch belongs to a different user.
        mock_batch = MagicMock()
        mock_batch.created_by_user_id = "u-owner"
        mock_batch.created_by_email = "owner@example.com"
        mock_batch_status = AsyncMock(return_value=(mock_batch, []))

        mock_cm = MagicMock()
        mock_cm.connect = AsyncMock()
        mock_cm.send_personal = AsyncMock()
        mock_cm.disconnect = MagicMock()

        with (
            patch("rag_processor.websocket.router.verify_ws_token", mock_verify),
            patch(
                "rag_processor.websocket.router.get_batch_status_async",
                mock_batch_status,
            ),
            patch("rag_processor.websocket.router.connection_manager", mock_cm),
        ):
            from rag_processor.websocket.router import websocket_batch_status

            await websocket_batch_status(
                mock_websocket, batch_id, cf_access_token="valid-token"
            )

        # Closes with the same code as "not found" so existence is not leaked.
        mock_websocket.close.assert_called_once_with(
            code=status.WS_1008_POLICY_VIOLATION
        )
        # Never accepted the connection.
        mock_cm.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_rejects_matching_email_with_different_user_id(
        self, mock_ws_logger: MagicMock
    ) -> None:
        """Regression: matching email + different user_id must NOT grant access.

        The previous WebSocket ownership check OR'd id-match and email-match,
        so a token whose email happened to match the batch owner's email
        would bypass the user_id check. user_id must take precedence when
        both sides have it. (CodeRabbit PR #26 review.)
        """
        from fastapi import WebSocket, status

        batch_id = uuid4()
        mock_websocket = AsyncMock(spec=WebSocket)

        # Same email as the batch owner, different user_id.
        mock_verify = AsyncMock(
            return_value={"email": "owner@example.com", "user_id": "u-intruder"}
        )

        mock_batch = MagicMock()
        mock_batch.created_by_user_id = "u-owner"
        mock_batch.created_by_email = "owner@example.com"
        mock_batch_status = AsyncMock(return_value=(mock_batch, []))

        mock_cm = MagicMock()
        mock_cm.connect = AsyncMock()
        mock_cm.send_personal = AsyncMock()
        mock_cm.disconnect = MagicMock()

        with (
            patch("rag_processor.websocket.router.verify_ws_token", mock_verify),
            patch(
                "rag_processor.websocket.router.get_batch_status_async",
                mock_batch_status,
            ),
            patch("rag_processor.websocket.router.connection_manager", mock_cm),
        ):
            from rag_processor.websocket.router import websocket_batch_status

            await websocket_batch_status(
                mock_websocket, batch_id, cf_access_token="valid-token"
            )

        mock_websocket.close.assert_called_once_with(
            code=status.WS_1008_POLICY_VIOLATION
        )
        mock_cm.connect.assert_not_called()

    @pytest.mark.skip(
        reason="Module-level Redis import fires before fakeredis patches; "
        "tracked in https://github.com/ByronWilliamsCPA/rag-processor/issues/44"
    )
    @pytest.mark.asyncio
    async def test_websocket_accepts_valid_connection(
        self, mock_ws_logger: MagicMock
    ) -> None:
        """Test WebSocket accepts valid authenticated connection.

        This test verifies the websocket_batch_status function properly:
        1. Connects via connection_manager
        2. Sends initial connected message
        3. Disconnects on WebSocketDisconnect
        4. Logs connection info

        Note: This test is skipped because the websocket router module imports
        get_batch_status from queue.jobs at module level, which triggers a
        Redis connection during import before any patches can be applied.
        The individual functions are tested elsewhere.
        """

    @pytest.mark.asyncio
    async def test_websocket_replays_events_on_reconnect(
        self, mock_ws_logger: MagicMock
    ) -> None:
        """Test WebSocket replays missed events on reconnect."""
        from fastapi import WebSocket, WebSocketDisconnect

        batch_id = uuid4()
        mock_websocket = AsyncMock(spec=WebSocket)

        mock_verify = AsyncMock(
            return_value={"email": "user@example.com", "user_id": "user-123"}
        )

        # Batch must be owned by the authenticated user; otherwise the WS
        # endpoint closes the connection without replaying events.
        mock_batch = MagicMock()
        mock_batch.created_by_user_id = "user-123"
        mock_batch.created_by_email = "user@example.com"
        mock_batch_status = AsyncMock(return_value=(mock_batch, []))

        mock_cm = MagicMock()
        mock_cm.connect = AsyncMock()
        mock_cm.send_personal = AsyncMock()
        mock_cm.disconnect = MagicMock()

        mock_replay = AsyncMock()

        async def mock_message_loop(ws):
            raise WebSocketDisconnect

        with (
            patch("rag_processor.websocket.router.verify_ws_token", mock_verify),
            patch(
                "rag_processor.websocket.router.get_batch_status_async",
                mock_batch_status,
            ),
            patch("rag_processor.websocket.router.connection_manager", mock_cm),
            patch(
                "rag_processor.websocket.router._websocket_message_loop",
                mock_message_loop,
            ),
            patch("rag_processor.websocket.router._replay_events", mock_replay),
        ):
            from rag_processor.websocket.router import websocket_batch_status

            await websocket_batch_status(
                mock_websocket,
                batch_id,
                cf_access_token="valid-token",
                last_event_id="event-123",
            )

        # Should have called replay with the last_event_id
        mock_replay.assert_called_once_with(mock_websocket, batch_id, "event-123")


class TestWebSocketMessageLoop:
    """Tests for WebSocket message loop."""

    @pytest.mark.asyncio
    async def test_message_loop_handles_connection_error(self) -> None:
        """Test message loop exits on connection error during ping."""
        mock_websocket = AsyncMock()

        # Use a side effect that raises TimeoutError then ConnectionError
        call_count = 0

        async def mock_wait_for(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError
            # Use await to satisfy async requirement
            await AsyncMock()()
            raise ConnectionError("Closed")

        mock_cm = MagicMock()
        mock_cm.send_personal = AsyncMock(side_effect=ConnectionError("Closed"))

        with (
            patch("rag_processor.websocket.router.connection_manager", mock_cm),
            patch("asyncio.wait_for", mock_wait_for),
        ):
            from rag_processor.websocket.router import _websocket_message_loop

            # Should exit gracefully on connection error
            await _websocket_message_loop(mock_websocket)

        # Loop should have exited after connection error
        assert mock_cm.send_personal.call_count == 1
