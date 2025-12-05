"""API package for RAG Processor.

This package contains FastAPI routers and API-related functionality.
"""

from __future__ import annotations

from rag_processor.api.health import router as health_router

__all__ = ["health_router"]
