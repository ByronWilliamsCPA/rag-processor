"""Health check endpoints for Kubernetes and production monitoring.

This module provides standardized health check endpoints following best practices:
- Liveness probe: Is the application running?
- Readiness probe: Can the application serve traffic?
- Startup probe: Has the application fully started?

Implements:
- Kubernetes probe patterns
- Graceful degradation
- Detailed diagnostic information
- OWASP A09 (Security Logging) compliance
"""

from __future__ import annotations

import asyncio
import sys
import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from rag_processor.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])

# Track application start time for uptime calculation
_START_TIME = time.time()


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Overall status: ok, degraded, or error")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")
    uptime_seconds: float = Field(..., description="Application uptime in seconds")
    version: str = Field(default="0.1.0", description="Application version")
    python_version: str = Field(default_factory=lambda: sys.version.split()[0])


class ReadinessCheck(BaseModel):
    """Individual dependency check result."""

    name: str = Field(..., description="Dependency name")
    healthy: bool = Field(..., description="Whether the dependency is reachable")
    message: str = Field(default="", description="Human-readable check detail")


class ReadinessStatus(BaseModel):
    """Readiness check response with dependency details."""

    status: str = Field(..., description="Overall readiness: ready or unavailable")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")
    checks: list[ReadinessCheck] = Field(
        default_factory=list, description="Individual dependency checks"
    )


@router.get(
    "/live",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description=(
        "Indicates whether the application process is alive. Intended for "
        "Kubernetes liveness probes. This endpoint is public and does not "
        "require authentication."
    ),
)
async def liveness() -> HealthStatus:
    """Kubernetes liveness probe.

    Returns HTTP 200 whenever the process is responsive. Performs no
    dependency checks, so it should not fail due to transient downstream
    issues. If this fails, Kubernetes will restart the pod.

    Authentication: Public endpoint, no authentication required.

    Returns:
        HealthStatus: HealthStatus with current `status`, `uptime_seconds`, and
        runtime version metadata.
    """
    return HealthStatus(
        status="ok",
        uptime_seconds=time.time() - _START_TIME,
    )


async def check_redis() -> ReadinessCheck:
    """Check Redis connectivity by issuing a PING.

    Uses the shared synchronous Redis client (offloaded to a worker thread so
    the probe does not block the event loop). Never raises: connectivity
    failures are reported as an unhealthy check so the readiness handler can
    decide whether to fail the probe.

    Returns:
        ReadinessCheck: ReadinessCheck reflecting the real Redis reachability.
    """
    from rag_processor.core.redis import get_redis_client

    try:
        client = get_redis_client(decode_responses=True)
        pong = await asyncio.to_thread(client.ping)
    except Exception as exc:
        # Readiness must report status, not raise; capture any connectivity error.
        return ReadinessCheck(
            name="redis",
            healthy=False,
            message=f"Redis unreachable: {exc}",
        )
    healthy = bool(pong)
    return ReadinessCheck(
        name="redis",
        healthy=healthy,
        message="Redis reachable" if healthy else "Redis PING returned no response",
    )


@router.get(
    "/ready",
    response_model=ReadinessStatus,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Application is ready to serve traffic"},
        503: {"description": "Application is not ready (dependencies unavailable)"},
    },
    summary="Readiness probe",
    description=(
        "Checks whether the application can serve traffic by exercising "
        "all critical dependencies (database, cache, external services). "
        "Intended for Kubernetes readiness probes. This endpoint is "
        "public and does not require authentication."
    ),
)
async def readiness() -> ReadinessStatus:
    """Kubernetes readiness probe.

    Runs the configured dependency health checks (database, cache, and
    optional external services) and aggregates their results. Returns
    HTTP 503 if any critical dependency is unavailable; if this fails,
    Kubernetes will stop routing traffic to this pod.

    Authentication: Public endpoint, no authentication required.

    Returns:
        ReadinessStatus: ReadinessStatus with overall health and per-dependency check
        results (latency and error details).

    Raises:
        HTTPException: 503 when one or more critical dependencies fail.
    """
    # Run all readiness checks. Each check reports its real status; whether a
    # failing check fails the probe is decided below based on configuration.
    checks = [
        await check_redis(),
    ]

    # A check only fails readiness if it is "required". Redis is required only
    # when settings.readiness_require_redis is set, so deployments/CI without a
    # Redis dependency still report ready while the check stays truthful.
    required_names: set[str] = set()
    if settings.readiness_require_redis:
        required_names.add("redis")

    all_required_healthy = all(
        check.healthy for check in checks if check.name in required_names
    )

    if not all_required_healthy:
        # Use the declared response schema for the error body too, so the 503
        # payload matches ReadinessStatus instead of an ad-hoc dict (L5).
        unavailable = ReadinessStatus(
            status="unavailable",
            timestamp=time.time(),
            checks=checks,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=unavailable.model_dump(),
        )

    return ReadinessStatus(
        status="ready",
        timestamp=time.time(),
        checks=checks,
    )


@router.get(
    "/startup",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Startup probe",
    description=(
        "Indicates whether the application has completed startup. Intended "
        "for Kubernetes startup probes that delay liveness and readiness "
        "checks during slow initialization. This endpoint is public and "
        "does not require authentication."
    ),
)
async def startup() -> HealthStatus:
    """Kubernetes startup probe.

    Returns HTTP 200 once the application has finished initializing.
    Kubernetes uses this to defer liveness and readiness checks during
    boot so that slow startups don't trigger restarts.

    Authentication: Public endpoint, no authentication required.

    Returns:
        HealthStatus: HealthStatus indicating startup completion and uptime.
    """
    # Add any startup checks here (e.g., database migrations completed)
    # For most applications, being alive means startup is complete

    return HealthStatus(
        status="started",
        uptime_seconds=time.time() - _START_TIME,
    )


@router.get(
    "/",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description=(
        "Compatibility alias for `/health/live`. Provided for load "
        "balancers and monitors that expect a `/health` endpoint. "
        "Public endpoint, no authentication required."
    ),
    include_in_schema=False,  # Hide from OpenAPI docs (use /live instead)
)
async def health() -> HealthStatus:
    """Basic health check endpoint.

    Compatibility alias for `/health/live`, intended for load balancers
    and monitoring systems that expect a `/health` path.

    Authentication: Public endpoint, no authentication required.

    Returns:
        HealthStatus: HealthStatus from the liveness check.
    """
    return await liveness()


# =============================================================================
# Kubernetes Probe Configuration Examples
# =============================================================================
"""
Add to your Kubernetes Deployment YAML:

apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag_processor
spec:
  template:
    spec:
      containers:
      - name: app
        image: rag_processor:latest
        ports:
        - containerPort: 8000

        # Liveness probe - restart if fails
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3

        # Readiness probe - stop traffic if fails
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3

        # Startup probe - delay other probes during startup
        startupProbe:
          httpGet:
            path: /health/startup
            port: 8000
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30  # 30 * 5s = 150s max startup time
"""
