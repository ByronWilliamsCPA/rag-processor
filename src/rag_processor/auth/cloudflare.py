"""Cloudflare Access JWT validation middleware.

Validates JWT tokens from Cloudflare Access and extracts user context.
Supports bypass mode for local development without Cloudflare.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey  # noqa: TC002
from jwt.algorithms import RSAAlgorithm
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from rag_processor.auth.models import CloudflareUser, TokenClaims
from rag_processor.core.config import settings
from rag_processor.utils.logging import get_logger

UTC = timezone.utc  # noqa: UP017

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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

# Serializes concurrent JWKS refreshes so a cache miss under load triggers a
# single upstream fetch instead of a stampede against Cloudflare's endpoint.
#
# Created at import time. On Python 3.10+ this binds to the running loop lazily
# on first await, and the app runs a single event loop, so this is safe in
# production. The only latent risk is tests that spin up multiple event loops
# and share this module-level lock across them; if that ever arises, construct
# the lock inside the loop (e.g. a lazily-initialised per-loop lock) instead.
_jwks_lock = asyncio.Lock()

# Leeway (seconds) applied to JWT exp/iat/nbf to tolerate minor clock skew.
# Shared by the HTTP middleware and the WebSocket verification path so both
# accept exactly the same tokens.
_JWT_LEEWAY_SECONDS = 5


async def _load_jwks(*, force_refresh: bool = False) -> JWKSData:
    """Return JWKS, fetching from Cloudflare on cache miss under a lock.

    Uses double-checked locking: the common case (valid cache) returns without
    acquiring the lock; on a miss, the lock is taken and the cache re-checked so
    only one coroutine performs the upstream fetch.

    Args:
        force_refresh: If True, bypass the cached value and refetch.

    Returns:
        The JWKS dictionary with public keys.
    """
    if not force_refresh and _jwks_cache.is_valid():
        return _jwks_cache.data

    async with _jwks_lock:
        # Another coroutine may have refreshed while we waited for the lock.
        if not force_refresh and _jwks_cache.is_valid():
            return _jwks_cache.data

        jwks_url = f"https://{settings.cloudflare_team_domain}/cdn-cgi/access/certs"
        async with httpx.AsyncClient() as client:  # nosec B113 - timeout below
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            raw_payload: object = response.json()
            jwks, keys_count = _parse_jwks_payload(raw_payload)

        _jwks_cache.update(jwks)
        logger.debug("Refreshed JWKS cache", keys_count=keys_count)
        return jwks


def _parse_jwks_payload(payload: object) -> tuple[JWKSData, int]:
    """Validate a raw JWKS payload at the trust boundary before caching.

    Cloudflare's certs endpoint is trusted, but the response is still untyped
    JSON entering the auth path. Reject anything that is not an object with a
    ``keys`` list of objects each carrying a string ``kid`` so malformed data
    fails fast here instead of surfacing later during key resolution.

    Args:
        payload: The decoded JSON body from the JWKS endpoint.

    Returns:
        A tuple of the validated JWKS document and its key count.

    Raises:
        jwt.InvalidTokenError: If the payload shape is invalid.
    """
    if not isinstance(payload, dict):
        msg = "JWKS payload is not a JSON object"
        raise jwt.InvalidTokenError(msg)
    raw_keys: object = payload.get("keys")
    if not isinstance(raw_keys, list):
        msg = "JWKS payload missing 'keys' list"
        raise jwt.InvalidTokenError(msg)
    keys: list[dict[str, object]] = []
    for key in raw_keys:
        if not isinstance(key, dict) or not isinstance(key.get("kid"), str):
            msg = "JWKS key entry missing string 'kid'"
            raise jwt.InvalidTokenError(msg)
        keys.append(key)
    return {"keys": keys}, len(keys)


async def _resolve_signing_key(jwks: JWKSData, token: str) -> RSAPublicKey:
    """Resolve a token's signing key, refreshing JWKS once on a key miss.

    Cloudflare rotates Access signing keys within the cache TTL. On a missing
    ``kid`` we force-refresh the JWKS and retry once so a valid token signed
    with a freshly rotated key is not rejected until the cache expires.

    # #CRITICAL: Security: auth flow — a stale JWKS cache must not reject
    # tokens signed by a freshly rotated Cloudflare key (user-facing outage).
    # #VERIFY: force-refresh and retry key resolution exactly once on a miss.

    Args:
        jwks: The currently cached JWKS document.
        token: The JWT whose signing key is being resolved.

    Returns:
        The matching RSA public key.

    Raises:
        jwt.InvalidTokenError: If the key is missing even after a refresh.
    """
    try:
        return _resolve_key_or_raise(jwks, token)
    except jwt.InvalidTokenError as exc:
        if "not found in JWKS" not in str(exc):
            raise
        refreshed = await _load_jwks(force_refresh=True)
        return _resolve_key_or_raise(refreshed, token)


def _select_rsa_key(jwks: JWKSData, kid: str) -> RSAPublicKey | None:
    """Find the RSA public key matching ``kid`` in a JWKS document.

    Args:
        jwks: JWKS dictionary.
        kid: Key ID to find.

    Returns:
        The RSA public key, or None if no key matches.
    """
    keys_list: list[dict[str, Any]] = jwks.get("keys", [])
    for key in keys_list:
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)  # type: ignore[return-value]
    return None


def _decode_cf_jwt(token: str, rsa_key: RSAPublicKey) -> dict[str, Any]:
    """Validate and decode a Cloudflare Access JWT.

    Single source of truth for signature/audience/issuer validation and clock
    skew handling, shared by the HTTP middleware and the WebSocket path.

    Args:
        token: The JWT string.
        rsa_key: The RSA public key to verify the signature against.

    Returns:
        The decoded token payload (claims).

    Raises:
        jwt.InvalidTokenError: If the token fails validation.
    """
    return jwt.decode(
        token,
        rsa_key,
        algorithms=["RS256"],
        audience=settings.cloudflare_audience_tag,
        issuer=f"https://{settings.cloudflare_team_domain}",
        leeway=_JWT_LEEWAY_SECONDS,
    )


def _resolve_key_or_raise(jwks: JWKSData, token: str) -> RSAPublicKey:
    """Extract the ``kid`` from a token and resolve its RSA key.

    Args:
        jwks: JWKS dictionary.
        token: The JWT string (header is read unverified to get the ``kid``).

    Returns:
        The matching RSA public key.

    Raises:
        jwt.InvalidTokenError: If the token has no ``kid`` or no key matches.
    """
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        msg = "Token missing key ID"
        raise jwt.InvalidTokenError(msg)

    rsa_key = _select_rsa_key(jwks, kid)
    if not rsa_key:
        msg = f"Key {kid} not found in JWKS"
        raise jwt.InvalidTokenError(msg)
    return rsa_key


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

        # Bypass mode for local development. This grants every request a fixed
        # mock identity with the "developers" group, so it must never be enabled
        # in production. Log a critical warning on every request to make
        # misconfiguration obvious in production logs.
        if not settings.cloudflare_enabled:
            logger.critical(
                "Cloudflare auth is DISABLED - all requests are authenticated as "
                "the bypass user. This must only be used for local development.",
                path=request.url.path,
            )
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
        # Get JWKS for signature validation, resolve the signing key, then
        # validate/decode via the shared helpers (same logic as the WebSocket
        # path).
        jwks = await self._get_jwks()
        rsa_key = await _resolve_signing_key(jwks, token)
        payload = _decode_cf_jwt(token, rsa_key)

        # Parse claims and create user
        claims = TokenClaims(**payload)
        return claims.to_user()

    async def _get_jwks(self) -> JWKSData:
        """Fetch JWKS from Cloudflare with caching.

        Thin wrapper around the shared :func:`_load_jwks` loader. Kept as an
        instance method so it remains an overridable seam for tests.

        Returns:
            JWKS dictionary with public keys.
        """
        return await _load_jwks()

    def _find_key(self, jwks: JWKSData, kid: str) -> RSAPublicKey | None:
        """Find RSA key by key ID in JWKS.

        Args:
            jwks: JWKS dictionary.
            kid: Key ID to find.

        Returns:
            RSA public key or None if not found.
        """
        return _select_rsa_key(jwks, kid)

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


async def verify_cloudflare_token(token: str) -> dict[str, Any]:
    """Verify a Cloudflare Access JWT token.

    Standalone function for verifying tokens outside the middleware context,
    such as WebSocket connections.

    Args:
        token: JWT token string.

    Returns:
        Dictionary with user info (email, user_id).

    Raises:
        InvalidTokenError: If token is invalid or expired.
    """
    # Reuse the exact same JWKS loading, key resolution, and decode logic as
    # the HTTP middleware so HTTP and WebSocket auth accept identical tokens
    # (including the shared clock-skew leeway).
    jwks = await _load_jwks()
    rsa_key = await _resolve_signing_key(jwks, token)
    payload = _decode_cf_jwt(token, rsa_key)

    # Extract user info
    return {
        "email": payload.get("email"),
        "user_id": payload.get("sub"),
    }
