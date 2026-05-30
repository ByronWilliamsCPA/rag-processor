"""API package for RAG Processor.

This package contains FastAPI routers and API-related functionality.
"""

from __future__ import annotations

from rag_processor.api.batch import router as batch_router
from rag_processor.api.health import router as health_router
from rag_processor.api.ingest import router as ingest_router
from rag_processor.api.user import router as user_router

__all__ = [
    "batch_router",
    "health_router",
    "ingest_router",
    "user_router",
]
