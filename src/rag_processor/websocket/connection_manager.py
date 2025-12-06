"""WebSocket connection manager.

Manages active WebSocket connections per batch for broadcasting events.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from rag_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from fastapi import WebSocket

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by batch.

    Tracks active connections per batch_id and provides
    methods to broadcast messages to all connected clients.

    Example:
        manager = ConnectionManager()
        await manager.connect(websocket, batch_id)
        await manager.broadcast(batch_id, {"status": "processing"})
        manager.disconnect(websocket, batch_id)
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        # Map batch_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, batch_id: UUID | str) -> None:
        """Accept a WebSocket connection and track it for the batch.

        Args:
            websocket: WebSocket connection to track.
            batch_id: Batch identifier.
        """
        await websocket.accept()
        batch_key = str(batch_id)
        self._connections[batch_key].add(websocket)

        logger.info(
            "WebSocket connected",
            batch_id=batch_key,
            total_connections=len(self._connections[batch_key]),
        )

    def disconnect(self, websocket: WebSocket, batch_id: UUID | str) -> None:
        """Remove a WebSocket connection from tracking.

        Args:
            websocket: WebSocket connection to remove.
            batch_id: Batch identifier.
        """
        batch_key = str(batch_id)
        self._connections[batch_key].discard(websocket)

        # Clean up empty batch entries
        if not self._connections[batch_key]:
            del self._connections[batch_key]

        logger.info(
            "WebSocket disconnected",
            batch_id=batch_key,
            remaining_connections=len(self._connections.get(batch_key, set())),
        )

    async def broadcast(
        self,
        batch_id: UUID | str,
        message: dict[str, str | int | float | bool | None],
    ) -> int:
        """Broadcast a message to all connections for a batch.

        Args:
            batch_id: Batch identifier.
            message: JSON-serializable message to send.

        Returns:
            Number of clients that received the message.
        """
        batch_key = str(batch_id)
        connections = self._connections.get(batch_key, set())

        if not connections:
            return 0

        sent_count = 0
        disconnected: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except (RuntimeError, ConnectionError, OSError) as e:
                logger.warning(
                    "Failed to send WebSocket message",
                    batch_id=batch_key,
                    error=str(e),
                )
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self._connections[batch_key].discard(ws)

        logger.debug(
            "Broadcast sent",
            batch_id=batch_key,
            sent_count=sent_count,
            failed_count=len(disconnected),
        )

        return sent_count

    async def send_personal(
        self,
        websocket: WebSocket,
        message: dict[str, str | int | float | bool | None],
    ) -> bool:
        """Send a message to a specific WebSocket connection.

        Args:
            websocket: Target WebSocket connection.
            message: JSON-serializable message to send.

        Returns:
            True if message sent successfully, False otherwise.
        """
        try:
            await websocket.send_json(message)
        except (RuntimeError, ConnectionError, OSError) as e:
            logger.warning("Failed to send personal message", error=str(e))
            return False
        else:
            return True

    def get_connection_count(self, batch_id: UUID | str) -> int:
        """Get the number of connections for a batch.

        Args:
            batch_id: Batch identifier.

        Returns:
            Number of active connections.
        """
        batch_key = str(batch_id)
        return len(self._connections.get(batch_key, set()))

    def get_all_batch_ids(self) -> list[str]:
        """Get all batch IDs with active connections.

        Returns:
            List of batch IDs.
        """
        return list(self._connections.keys())

    def clear_all(self) -> None:
        """Clear all tracked connections."""
        self._connections.clear()
        logger.warning("All WebSocket connections cleared")


# Global connection manager instance
connection_manager = ConnectionManager()
