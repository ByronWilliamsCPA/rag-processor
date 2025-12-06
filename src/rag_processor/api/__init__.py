"""API package for RAG Processor.

This package contains FastAPI routers and API-related functionality.
"""

from __future__ import annotations

from rag_processor.api.health import router as health_router
from rag_processor.api.ingest import router as ingest_router

__all__ = ["health_router", "ingest_router"]
