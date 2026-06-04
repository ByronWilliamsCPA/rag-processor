"""FastAPI application entry point for RAG Processor Gateway.

This module exposes an application factory, :func:`create_app`, which builds and
configures a fully wired FastAPI application with:

- Health check endpoints for Kubernetes probes
- CORS middleware for frontend integration (single source of truth)
- Security middleware (headers, rate limiting, SSRF prevention)
- Correlation ID middleware for distributed tracing
- Cloudflare Access authentication middleware
- A Redis pub/sub -> WebSocket bridge for real-time batch events
- The centralized exception hierarchy mapped to HTTP responses

A module-level ``app`` instance is created from the factory for uvicorn
(``uvicorn rag_processor.main:app``). Tests can call :func:`create_app` directly
to build isolated instances with overridden dependencies.
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
from rag_processor.websocket.bridge import EventBridge
from rag_processor.websocket.router import router as websocket_router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Configure structured logging once at import time so that any module-level
# logging during application construction is formatted consistently.
setup_logging(
    level=settings.log_level,
    json_logs=settings.json_logs,
    include_timestamp=settings.include_timestamp,
)

logger = get_logger(__name__)

# Statuses at or above this value are server-class errors whose ``details``
# must be withheld from clients to avoid leaking internal infrastructure.
_SERVER_ERROR_THRESHOLD = 500

# Versioned API mount point shared by the user, ingest, and batch routers.
_API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events.

    On startup it launches the Redis pub/sub -> WebSocket :class:`EventBridge`
    so that events published by background workers are relayed to connected
    clients. On shutdown the bridge is stopped and the shared Redis pools are
    released cleanly.

    Args:
        app: The FastAPI application instance.

    Yields:
        None after startup; cleanup runs after yield on shutdown.
    """
    logger.info(
        "Starting RAG Processor Gateway",
        version=__version__,
        log_level=settings.log_level,
        cloudflare_enabled=settings.cloudflare_enabled,
    )

    # Start the event bridge. It degrades gracefully if Redis is unavailable,
    # so a missing broker never blocks application startup.
    bridge = EventBridge()
    await bridge.start()
    app.state.event_bridge = bridge

    yield

    # Shutdown
    await bridge.stop()
    logger.info("Shutting down RAG Processor Gateway")
    close_redis_pools()


def _resolve_cors_origins() -> list[str]:
    """Resolve and validate the configured CORS origins.

    Wildcard ``"*"`` is forbidden because the gateway sends credentials; reject
    it loudly rather than silently producing an insecure configuration.

    Returns:
        The explicit list of allowed CORS origins.

    Raises:
        RuntimeError: If the wildcard origin is configured.
    """
    cors_origins = list(settings.cors_allowed_origins)
    if "*" in cors_origins:
        msg = (
            "CORS allow_origins=['*'] is not permitted with allow_credentials=True. "
            "Set RAG_PROCESSOR_CORS_ALLOWED_ORIGINS to an explicit list of origins."
        )
        raise RuntimeError(msg)
    return cors_origins


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


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    This is the single place where middleware ordering, CORS, routers, and the
    exception hierarchy are assembled. Building the app inside a factory (rather
    than at import time) keeps construction explicit and lets tests create
    isolated instances with overridden dependencies.

    Returns:
        A fully configured FastAPI application.
    """
    app = FastAPI(
        title="RAG Processor Gateway",
        description="API Gateway for RAG file ingestion pipeline",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware (single source of truth, added before other middleware).
    # Origins come from settings so production deployments override via
    # RAG_PROCESSOR_CORS_ALLOWED_ORIGINS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_cors_origins(),
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

    # Correlation ID middleware for distributed tracing.
    app.add_middleware(CorrelationMiddleware)

    # Cloudflare Access authentication middleware.
    app.add_middleware(CloudflareAuthMiddleware)

    # Security middleware (headers, rate limiting, SSRF prevention). CORS is
    # intentionally NOT delegated here to avoid a second, conflicting layer;
    # see middleware.security.add_security_middleware.
    security_config = SecurityConfig(
        enable_rate_limiting=settings.rate_limiting_enabled,
        rate_limit_rpm=settings.rate_limit_rpm,
        trust_proxy_headers=settings.rate_limit_trust_proxy,
        client_ip_header=settings.rate_limit_client_ip_header,
    )
    add_security_middleware(app, security_config)

    # Routers
    app.include_router(health_router)
    app.include_router(user_router, prefix=_API_V1_PREFIX)
    app.include_router(ingest_router, prefix=_API_V1_PREFIX)
    app.include_router(batch_router, prefix=_API_V1_PREFIX)
    app.include_router(websocket_router)

    # Wire the centralized exception hierarchy into the app so any
    # ``ProjectBaseError`` is rendered with the mapped HTTP status.
    app.add_exception_handler(ProjectBaseError, handle_project_error)  # type: ignore[arg-type]

    app.add_api_route(
        "/",
        root,
        methods=["GET"],
        tags=["root"],
        summary="API information",
        description=(
            "Returns basic API metadata including the service name, version, "
            "and the path to the interactive OpenAPI docs. Requires Cloudflare "
            "Access authentication when `CLOUDFLARE_ENABLED=true`."
        ),
    )
    return app


# Application instance for uvicorn (uvicorn rag_processor.main:app).
app = create_app()

# Export app for uvicorn
__all__ = ["app", "create_app"]
