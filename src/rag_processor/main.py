"""FastAPI application factory for RAG Processor.

Creates and configures the FastAPI application with middleware,
routers, and exception handlers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_processor.api.health import router as health_router
from rag_processor.api.ingest import router as ingest_router
from rag_processor.api.user import router as user_router
from rag_processor.auth.cloudflare import CloudflareAuthMiddleware
from rag_processor.core.config import settings
from rag_processor.middleware.correlation import CorrelationMiddleware
from rag_processor.utils.logging import get_logger, setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler.

    Handles startup and shutdown events.

    Args:
        _app: FastAPI application instance (unused but required by lifespan protocol).

    Yields:
        None during application lifetime.
    """
    # Startup
    setup_logging(
        level=settings.log_level,
        json_logs=settings.json_logs,
        include_timestamp=settings.include_timestamp,
    )
    logger.info(
        "Application starting",
        cloudflare_enabled=settings.cloudflare_enabled,
    )
    yield
    # Shutdown
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="RAG Processor",
        description="React-based frontend for RAG pipeline with FastAPI backend integration",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add middleware (order matters - first added is outermost)
    # Correlation ID for request tracing
    app.add_middleware(CorrelationMiddleware)

    # Cloudflare Access authentication
    app.add_middleware(CloudflareAuthMiddleware)

    # CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",  # Vite dev server
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(user_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")

    return app


# Application instance for uvicorn
app = create_app()
