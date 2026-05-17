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
from rag_processor.api.batch import router as batch_router
from rag_processor.api.ingest import router as ingest_router
from rag_processor.api.user import router as user_router
from rag_processor.auth.cloudflare import CloudflareAuthMiddleware
from rag_processor.core.config import settings
from rag_processor.middleware import (
    CorrelationMiddleware,
    SecurityConfig,
    add_security_middleware,
)
from rag_processor.utils.logging import get_logger, setup_logging
from rag_processor.websocket.router import router as websocket_router

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

# Add CORS middleware (must be added before other middleware).
# Origins come from settings so production deployments can override via
# RAG_PROCESSOR_CORS_ALLOWED_ORIGINS. Wildcard "*" is forbidden because we send
# credentials; reject it loudly rather than silently producing an insecure config.
_cors_origins = list(settings.cors_allowed_origins)
if "*" in _cors_origins:
    msg = (
        "CORS allow_origins=['*'] is not permitted with allow_credentials=True. "
        "Set RAG_PROCESSOR_CORS_ALLOWED_ORIGINS to an explicit list of origins."
    )
    raise RuntimeError(msg)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Correlation-ID",
        "X-Request-ID",
        "Cf-Access-Jwt-Assertion",
    ],
    expose_headers=["X-Correlation-ID", "X-Request-ID"],
)

# Add correlation ID middleware for distributed tracing
app.add_middleware(CorrelationMiddleware)

# Add Cloudflare Access authentication middleware
app.add_middleware(CloudflareAuthMiddleware)

# Add security middleware (headers, rate limiting, SSRF prevention)
security_config = SecurityConfig(
    enable_rate_limiting=settings.rate_limiting_enabled,
    rate_limit_rpm=settings.rate_limit_rpm,
)
add_security_middleware(app, security_config)

# Include routers
app.include_router(health_router)
app.include_router(user_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(batch_router, prefix="/api/v1")
app.include_router(websocket_router)


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
