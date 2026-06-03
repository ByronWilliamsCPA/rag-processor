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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_processor import __version__
from rag_processor.api import health_router
from rag_processor.api.batch import router as batch_router
from rag_processor.api.ingest import router as ingest_router
from rag_processor.api.user import router as user_router
from rag_processor.auth.cloudflare import CloudflareAuthMiddleware
from rag_processor.core.config import settings
from rag_processor.core.exceptions import ProjectBaseError, http_status_for
from rag_processor.core.redis import close_redis_pools
from rag_processor.middleware import (
    CorrelationMiddleware,
    SecurityConfig,
    add_security_middleware,
    get_correlation_id,
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

# Statuses at or above this value are server-class errors whose ``details``
# must be withheld from clients to avoid leaking internal infrastructure.
_SERVER_ERROR_THRESHOLD = 500


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
    close_redis_pools()


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


@app.exception_handler(ProjectBaseError)
async def handle_project_error(
    request: Request,  # noqa: ARG001 - required by FastAPI handler signature
    exc: ProjectBaseError,
) -> JSONResponse:
    """Translate domain exceptions into consistent JSON error responses.

    Wires the centralized exception hierarchy into the app so any
    ``ProjectBaseError`` raised by a handler or dependency is rendered with the
    appropriate HTTP status and a structured body, instead of surfacing as a
    generic 500.

    Args:
        request: The incoming request (unused).
        exc: The raised project exception.

    Returns:
        A JSON response with the mapped status code and the exception payload.
    """
    status = http_status_for(exc)
    correlation_id = get_correlation_id()

    # Server-class failures (5xx) must never leak internal infrastructure
    # context (e.g. service_name, status_code, database operation/table held in
    # ``details``) to clients. Return only the safe error/message/code fields
    # and keep the full context in server-side logs for troubleshooting.
    if status >= _SERVER_ERROR_THRESHOLD:
        logger.error(
            "Request failed with server error",
            correlation_id=correlation_id,
            status=status,
            error=exc.__class__.__name__,
            error_code=exc.error_code,
            details=exc.details,
        )
        payload: dict[str, object] = {
            "error": exc.__class__.__name__,
            "message": exc.message,
        }
        if exc.error_code:
            payload["code"] = exc.error_code
        return JSONResponse(status_code=status, content=payload)

    logger.warning(
        "Request failed with client error",
        correlation_id=correlation_id,
        status=status,
        error=exc.__class__.__name__,
        error_code=exc.error_code,
    )
    return JSONResponse(status_code=status, content=exc.to_dict())


@app.get(
    "/",
    tags=["root"],
    summary="API information",
    description=(
        "Returns basic API metadata including the service name, version, "
        "and the path to the interactive OpenAPI docs. Requires Cloudflare "
        "Access authentication when `CLOUDFLARE_ENABLED=true`."
    ),
)
async def root() -> dict[str, str]:
    """API information.

    Returns metadata about the running gateway: service name, version,
    and the URL of the interactive OpenAPI documentation.

    Authentication: Requires a valid Cloudflare Access JWT in the
    `Cf-Access-Jwt-Assertion` header when Cloudflare auth is enabled.

    Returns:
        Dictionary with `name`, `version`, and `docs` URL.
    """
    return {
        "name": "RAG Processor Gateway",
        "version": __version__,
        "docs": "/docs",
    }


# Export app for uvicorn
__all__ = ["app"]
