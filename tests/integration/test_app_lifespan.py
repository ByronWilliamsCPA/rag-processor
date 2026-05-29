"""Integration test for the application lifespan wiring of the event bridge.

Lives in the integration tier because it boots the full FastAPI app via
``TestClient`` (which runs the lifespan handler) rather than exercising the
:class:`EventBridge` in isolation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rag_processor.main import app
from rag_processor.websocket.bridge import EventBridge


@pytest.mark.integration
class TestAppLifespanStartsBridge:
    """The application lifespan starts and stops the event bridge."""

    def test_lifespan_runs_bridge_start_and_stop(self) -> None:
        """Entering/exiting the app context triggers bridge startup and shutdown."""
        # Using TestClient as a context manager runs the lifespan handler.
        with TestClient(app) as client:
            assert client.get("/health/live").status_code == 200
            assert isinstance(app.state.event_bridge, EventBridge)
