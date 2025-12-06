"""WebSocket module for real-time status updates.

This package contains components for WebSocket connections,
event publishing, and real-time batch status broadcasting.
"""

from __future__ import annotations

from rag_processor.websocket.connection_manager import ConnectionManager
from rag_processor.websocket.events import BatchEvent, EventType, publish_event

__all__ = [
    "BatchEvent",
    "ConnectionManager",
    "EventType",
    "publish_event",
]
