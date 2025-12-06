"""FastAPI application entry point for RAG Processor Gateway.

This module creates and configures the FastAPI application with:
- Health check endpoints for Kubernetes probes
- CORS middleware for frontend integration
- Security middleware (headers, rate limiting, SSRF prevention)
- Correlation ID middleware for distributed tracing
- Cloudflare Access authentication middleware
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_processor import __version__
from rag_processor.api import health_router
from rag_processor.api.ingest import router as ingest_router
from rag_processor.api.user import router as user_router
from rag_processor.auth.cloudflare import CloudflareAuthMiddleware
from rag_processor.core.config import settings
from rag_processor.middleware import CorrelationMiddleware, add_security_middleware
from rag_processor.utils.logging import get_logger, setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Configure structured logging
setup_logging(
    level=settings.log_level,
    json_logs=settings.json_logs,
    include_timestamp=settings.include_timestamp,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application lifespan handler for startup and shutdown events.

    Args:
        app: The FastAPI application instance.

    Yields:
        None after startup, cleanup runs after yield on shutdown.
    """
    # Startup
    logger.info(
        "Starting RAG Processor Gateway",
        version=__version__,
        log_level=settings.log_level,
        cloudflare_enabled=settings.cloudflare_enabled,
    )

    yield

    # Shutdown
    logger.info("Shutting down RAG Processor Gateway")


# Create FastAPI application
app = FastAPI(
    title="RAG Processor Gateway",
    description="API Gateway for RAG file ingestion pipeline",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware (must be added before other middleware)
# #ASSUME: cors: Frontend runs on localhost:3000 in development
# #VERIFY: Update allowed origins for production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://frontend:3000",  # Docker service name
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Request-ID"],
)

# Add correlation ID middleware for distributed tracing
app.add_middleware(CorrelationMiddleware)

# Add Cloudflare Access authentication middleware
app.add_middleware(CloudflareAuthMiddleware)

# Add security middleware (headers, rate limiting, SSRF prevention)
add_security_middleware(app)

# Include routers
app.include_router(health_router)
app.include_router(user_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint returning API information.

    Returns:
        Dictionary with API name and version.
    """
    return {
        "name": "RAG Processor Gateway",
        "version": __version__,
        "docs": "/docs",
    }


# Export app for uvicorn
__all__ = ["app"]
