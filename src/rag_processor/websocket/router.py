"""WebSocket router for real-time status updates.

Provides WebSocket endpoints for batch status streaming.
"""

from __future__ import annotations

import asyncio
from uuid import UUID  # noqa: TC003 - Used at runtime by FastAPI

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from rag_processor.auth.cloudflare import verify_cloudflare_token
from rag_processor.auth.dependencies import batch_is_owned_by
from rag_processor.core.config import settings
from rag_processor.queue.jobs import get_batch_status_async
from rag_processor.utils.logging import get_logger
from rag_processor.websocket.connection_manager import connection_manager
from rag_processor.websocket.events import get_event_history

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


async def verify_ws_token(token: str | None) -> dict[str, str] | None:
    """Verify WebSocket authentication token.

    Args:
        token: CF Access token from query parameter.

    Returns:
        User info dict if valid, None otherwise.
    """
    if not settings.cloudflare_enabled:
        # Bypass mode. The returned identity MUST match
        # CloudflareAuthMiddleware._get_bypass_user() so that a batch created
        # over HTTP in dev mode can be subscribed to over WebSocket. (Previously
        # this returned "anonymous@local" / "local" which broke ownership
        # checks after batch_is_owned_by was introduced.) Mirror the middleware's
        # CRITICAL log so production misconfiguration is loud on every WS upgrade.
        logger.critical(
            "Cloudflare auth is DISABLED - WebSocket upgrade authenticated "
            "as bypass user. This must only be used for local development.",
        )
        return {"email": "dev@localhost", "user_id": "dev-user-001"}

    if not token:
        return None

    try:
        # Verify token with Cloudflare.
        return await verify_cloudflare_token(token)
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError) as e:
        logger.warning("WebSocket token verification failed", error=str(e))
        return None
    except Exception as e:  # noqa: BLE001
        # JWKS fetch failures (httpx.ConnectError, TimeoutException,
        # HTTPStatusError) and json.JSONDecodeError aren't JWT exceptions and
        # would otherwise propagate, closing the WS with 1011 (internal error)
        # instead of 1008 (policy violation). Mirror the HTTP middleware which
        # already handles this with a broad except.
        logger.warning("WebSocket token verification error", error=str(e))
        return None


async def _replay_events(
    websocket: WebSocket,
    batch_id: UUID,
    last_event_id: str,
) -> None:
    """Replay missed events to a reconnecting client.

    Args:
        websocket: WebSocket connection.
        batch_id: Batch identifier.
        last_event_id: Last event ID received by client.
    """
    # Offload the synchronous Redis read off the event loop.
    history = await asyncio.to_thread(get_event_history, batch_id)
    found_last = False

    for event in history:
        if found_last:
            await connection_manager.send_personal(websocket, event)
        elif event.get("event_id") == last_event_id:
            found_last = True


async def _handle_client_message(
    websocket: WebSocket,
    data: dict[str, str | int | float | bool | None],
) -> None:
    """Handle incoming message from client.

    Args:
        websocket: WebSocket connection.
        data: Message data from client.
    """
    # Handle ping
    if data.get("type") == "ping":
        await connection_manager.send_personal(
            websocket,
            {"type": "pong", "timestamp": data.get("timestamp")},
        )


async def _websocket_message_loop(websocket: WebSocket) -> None:
    """Main message loop for WebSocket connection.

    Args:
        websocket: WebSocket connection.
    """
    while True:
        try:
            # Wait for messages (client can send ping or other commands)
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=30.0,
            )
            await _handle_client_message(websocket, data)

        except TimeoutError:
            # Send keepalive ping
            try:
                await connection_manager.send_personal(
                    websocket,
                    {"type": "ping"},
                )
            except (RuntimeError, ConnectionError, OSError):
                break


@router.websocket("/ws/batch/{batch_id}")
async def websocket_batch_status(
    websocket: WebSocket,
    batch_id: UUID,
    cf_access_token: str | None = Query(default=None, alias="token"),
    last_event_id: str | None = Query(default=None),
) -> None:
    """WebSocket endpoint for real-time batch status updates.

    Connect to receive job status updates for a specific batch.
    Authentication via query parameter `token` (Cloudflare Access JWT).

    Args:
        websocket: WebSocket connection.
        batch_id: Batch to subscribe to.
        cf_access_token: Cloudflare Access token for authentication.
        last_event_id: Last received event ID for replay.
    """
    # Verify authentication
    user = await verify_ws_token(cf_access_token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify batch exists and the caller owns it. Treat "not found" and
    # "not authorized" identically to avoid leaking batch IDs.
    batch, _ = await get_batch_status_async(batch_id)
    if batch is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Shared ownership helper. user_id-takes-precedence semantics: a matching
    # email with a mismatched user_id is NOT enough to grant access.
    requester_user_id = user.get("user_id") or None
    requester_email = user.get("email") or None
    if not batch_is_owned_by(
        batch,
        requester_user_id=requester_user_id,
        requester_email=requester_email,
    ):
        # Minimal log context: opaque IDs only. Don't leak owner identity.
        logger.warning(
            "Unauthorized WebSocket batch access attempt",
            batch_id=str(batch_id),
            requester_user_id=requester_user_id,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept connection
    await connection_manager.connect(websocket, batch_id)

    logger.info(
        "WebSocket connection established",
        batch_id=str(batch_id),
        requester_user_id=requester_user_id,
    )

    try:
        # Send initial status
        await connection_manager.send_personal(
            websocket,
            {
                "type": "connected",
                "batch_id": str(batch_id),
                "message": "Connected to batch status stream",
            },
        )

        # Replay missed events if last_event_id provided
        if last_event_id:
            await _replay_events(websocket, batch_id, last_event_id)

        # Run message loop
        await _websocket_message_loop(websocket)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", batch_id=str(batch_id))
    except (RuntimeError, ConnectionError, OSError) as e:
        logger.exception("WebSocket error", batch_id=str(batch_id), error=str(e))
    finally:
        connection_manager.disconnect(websocket, batch_id)
