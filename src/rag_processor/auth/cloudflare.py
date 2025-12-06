"""Cloudflare Access JWT validation middleware.

Validates JWT tokens from Cloudflare Access and extracts user context.
Supports bypass mode for local development without Cloudflare.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from rag_processor.auth.models import CloudflareUser, TokenClaims
from rag_processor.core.config import settings
from rag_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from starlette.requests import Request
    from starlette.responses import Response

logger = get_logger(__name__)

# Header name for Cloudflare Access JWT
CF_ACCESS_JWT_HEADER = "Cf-Access-Jwt-Assertion"

# Type alias for JWKS structure
JWKSData = dict[str, Any]


class _JWKSCache:
    """Simple cache for JWKS keys."""

    def __init__(self) -> None:
        self.data: JWKSData = {}
        self.timestamp: float = 0
        self.ttl: float = 3600  # 1 hour

    def is_valid(self) -> bool:
        """Check if cache is still valid.

        Returns:
            True if cache has data and TTL hasn't expired.
        """
        return bool(self.data) and (time.time() - self.timestamp) < self.ttl

    def update(self, data: JWKSData) -> None:
        """Update cache with new data.

        Args:
            data: JWKS data to cache.
        """
        self.data = data
        self.timestamp = time.time()

    def clear(self) -> None:
        """Clear the cache."""
        self.data = {}
        self.timestamp = 0


_jwks_cache = _JWKSCache()


class CloudflareAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Cloudflare Access JWT tokens.

    Validates the JWT signature using Cloudflare's JWKS endpoint and
    extracts user information into request.state.user.

    For local development, set CLOUDFLARE_ENABLED=false to use bypass mode
    which creates a mock user without requiring Cloudflare authentication.
    """

    # Paths that don't require authentication
    PUBLIC_PATHS: ClassVar[set[str]] = {
        "/health",
        "/health/",
        "/health/live",
        "/health/ready",
        "/health/startup",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(  # noqa: PLR0911 - Multiple returns for clarity
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and validate JWT if required.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            Response from downstream handler or 401 error.
        """
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Bypass mode for local development
        if not settings.cloudflare_enabled:
            request.state.user = self._get_bypass_user()
            return await call_next(request)

        # Extract JWT from header
        token = request.headers.get(CF_ACCESS_JWT_HEADER)
        if not token:
            return self._unauthorized_response("Missing authentication token")

        # Validate token and extract user
        try:
            user = await self._validate_token(token)
            request.state.user = user
        except jwt.ExpiredSignatureError:
            return self._unauthorized_response("Token has expired")
        except jwt.InvalidAudienceError:
            return self._unauthorized_response("Invalid token audience")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", error=str(e))
            return self._unauthorized_response("Invalid authentication token")
        except Exception as e:
            logger.exception("Unexpected error during token validation")
            return self._unauthorized_response(f"Authentication error: {e}")

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public and doesn't require auth.

        Args:
            path: Request URL path.

        Returns:
            True if path is public.
        """
        # Exact match or prefix match for health endpoints
        return path in self.PUBLIC_PATHS or path.startswith("/health")

    def _get_bypass_user(self) -> CloudflareUser:
        """Create mock user for local development bypass mode.

        Returns:
            Mock CloudflareUser for development.
        """
        now = datetime.now(tz=UTC)
        return CloudflareUser(
            email="dev@localhost",
            user_id="dev-user-001",
            groups=["developers"],
            issued_at=now,
            expires_at=now,
        )

    async def _validate_token(self, token: str) -> CloudflareUser:
        """Validate JWT token and extract user.

        Args:
            token: JWT token string from header.

        Returns:
            CloudflareUser extracted from token claims.

        Raises:
            InvalidTokenError: If token is invalid or key not found.
        """
        # Get JWKS for signature validation
        jwks = await self._get_jwks()

        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            msg = "Token missing key ID"
            raise jwt.InvalidTokenError(msg)

        # Find matching key
        rsa_key = self._find_key(jwks, kid)
        if not rsa_key:
            msg = f"Key {kid} not found in JWKS"
            raise jwt.InvalidTokenError(msg)

        # Validate and decode token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.cloudflare_audience_tag,
            issuer=f"https://{settings.cloudflare_team_domain}",
        )

        # Parse claims and create user
        claims = TokenClaims(**payload)
        return claims.to_user()

    async def _get_jwks(self) -> JWKSData:
        """Fetch JWKS from Cloudflare with caching.

        Returns:
            JWKS dictionary with public keys.
        """
        # Return cached JWKS if still valid
        if _jwks_cache.is_valid():
            return _jwks_cache.data

        # Fetch fresh JWKS
        jwks_url = f"https://{settings.cloudflare_team_domain}/cdn-cgi/access/certs"
        async with httpx.AsyncClient() as client:  # nosec B113 - timeout is specified below
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks: JWKSData = response.json()

        # Update cache
        _jwks_cache.update(jwks)

        keys_list: list[Any] = jwks.get("keys", [])
        logger.debug("Refreshed JWKS cache", keys_count=len(keys_list))
        return jwks

    def _find_key(self, jwks: JWKSData, kid: str) -> RSAPublicKey | None:
        """Find RSA key by key ID in JWKS.

        Args:
            jwks: JWKS dictionary.
            kid: Key ID to find.

        Returns:
            RSA public key or None if not found.
        """
        keys_list: list[dict[str, Any]] = jwks.get("keys", [])
        for key in keys_list:
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(key)  # type: ignore[return-value]
        return None

    def _unauthorized_response(self, detail: str) -> JSONResponse:
        """Create 401 Unauthorized response.

        Args:
            detail: Error detail message.

        Returns:
            JSONResponse with 401 status.
        """
        return JSONResponse(
            status_code=401,
            content={"detail": detail},
        )


def clear_jwks_cache() -> None:
    """Clear the JWKS cache.

    Useful for testing or forcing a refresh.
    """
    _jwks_cache.clear()
