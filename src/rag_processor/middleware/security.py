"""Security middleware for FastAPI applications.

This module provides production-ready security middleware implementing OWASP best practices:
- CORS configuration (A05: Security Misconfiguration)
- Security headers (A05: Security Misconfiguration)
- Rate limiting (A07: Identification and Authentication Failures)
- Request validation (A03: Injection)
- SSRF prevention (A10: Server-Side Request Forgery)

Usage:
    from rag_processor.middleware.security import (
        add_security_middleware,
        SecurityHeadersMiddleware,
        RateLimitMiddleware,
    )

    app = FastAPI()
    add_security_middleware(app)
"""

from __future__ import annotations

import ipaddress
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fastapi import FastAPI, Request
    from starlette.types import ASGIApp


def _is_valid_ip(value: str) -> bool:
    """Return True if ``value`` parses as an IPv4 or IPv6 address.

    Used to reject non-IP values from a trusted proxy header before they become
    rate-limit keys, so a misconfigured upstream cannot inject arbitrary keys
    into the tracking table.

    Args:
        value: Candidate client IP string.

    Returns:
        True if the value is a valid IP address, False otherwise.
    """
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Implements OWASP recommended security headers to prevent:
    - XSS attacks
    - Clickjacking
    - MIME sniffing
    - Information leakage

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: HSTS for HTTPS
    - Content-Security-Policy: Prevent inline scripts
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Restrict browser features
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response.

        Args:
            request: The incoming HTTP request.
            call_next: Callable to invoke the next middleware or endpoint.

        Returns:
            Response with security headers added.
        """
        response = await call_next(request)

        # Prevent MIME sniffing (OWASP A05)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking (OWASP A05)
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection (OWASP A03)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS: Force HTTPS for 1 year (OWASP A02)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy: Prevent inline scripts (OWASP A03)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Control referrer information (OWASP A09)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features (OWASP A05)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # Remove server identification (OWASP A09)
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    Implements rate limiting to prevent:
    - Brute force attacks (OWASP A07)
    - DoS attacks (OWASP A04)
    - Credential stuffing (OWASP A07)

    Note: For production, use Redis-backed rate limiting:
        - slowapi (https://github.com/laurents/slowapi)
        - fastapi-limiter (https://github.com/long2ice/fastapi-limiter)

    Args:
        requests_per_minute: Maximum requests per IP per minute
        burst_size: Maximum burst requests allowed
        max_tracked_ips: Maximum IPs to track (prevents memory exhaustion)
        cleanup_interval: Seconds between full cleanup cycles
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        max_tracked_ips: int = 10000,
        cleanup_interval: int = 300,
        *,
        trust_proxy_headers: bool = False,
        client_ip_header: str = "CF-Connecting-IP",
    ) -> None:
        """Initialize rate limiter.

        Args:
            app: The ASGI application to wrap.
            requests_per_minute: Maximum requests per IP per minute.
            burst_size: Maximum burst requests allowed.
            max_tracked_ips: Maximum IPs to track (prevents memory exhaustion).
            cleanup_interval: Seconds between full cleanup cycles.
            trust_proxy_headers: Read the client IP from ``client_ip_header``
                instead of ``request.client.host``. Enable only behind a trusted
                proxy that overwrites the header, or clients can spoof it.
            client_ip_header: Header carrying the real client IP when
                ``trust_proxy_headers`` is true.
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.max_tracked_ips = max_tracked_ips
        self.cleanup_interval = cleanup_interval
        self.trust_proxy_headers = trust_proxy_headers
        self.client_ip_header = client_ip_header
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        """Resolve the client IP used as the rate-limit key.

        When ``trust_proxy_headers`` is enabled and the configured header is
        present, its first entry (the originating client for comma-separated
        forwarding headers) is used. Otherwise falls back to the direct peer
        address, or ``"unknown"`` when unavailable.

        Args:
            request: The incoming HTTP request.

        Returns:
            The client IP string to rate-limit on.
        """
        if self.trust_proxy_headers:
            forwarded = request.headers.get(self.client_ip_header)
            if forwarded:
                # X-Forwarded-For-style headers may list multiple hops; the
                # first is the originating client. Guard against a blank leading
                # entry (e.g. ", 10.0.0.1") so we don't key every malformed
                # request on "" — fall back to the peer address instead.
                client_ip = forwarded.split(",")[0].strip()
                if client_ip and _is_valid_ip(client_ip):
                    return client_ip
                # A blank or non-IP leading entry must not become the rate-limit
                # key: it would let malformed requests share one bucket and, worse,
                # let arbitrary header values inflate the tracking table. Fall back
                # to the direct peer address instead.
                logger.warning(
                    "%s header had no usable leading IP (got %r); falling "
                    "back to direct peer address",
                    self.client_ip_header,
                    client_ip,
                )
            else:
                logger.warning(
                    "trust_proxy_headers enabled but %s header missing; "
                    "falling back to direct peer address",
                    self.client_ip_header,
                )

        if request.client is None:
            logger.warning(
                "request.client is None - cannot determine client IP for rate "
                "limiting. Using 'unknown' as fallback. This may occur during "
                "testing or with certain proxy configurations."
            )
            return "unknown"
        return request.client.host

    def _cleanup_stale_entries(self, current_time: float) -> None:
        """Remove stale IP entries to prevent memory leaks.

        This method performs two types of cleanup:
        1. Removes expired timestamps from all tracked IPs
        2. If we exceed max_tracked_ips, removes least recently active IPs

        Args:
            current_time: Current timestamp for expiration checks
        """
        # Only run full cleanup periodically to avoid performance impact
        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        self._last_cleanup = current_time

        # Remove expired entries from all IPs
        stale_ips = []
        for ip, timestamps in self.requests.items():
            # Filter to only recent timestamps
            recent = [t for t in timestamps if current_time - t < 60]
            if recent:
                self.requests[ip] = recent
            else:
                stale_ips.append(ip)

        # Remove completely stale IPs
        for ip in stale_ips:
            del self.requests[ip]

        # Enforce the tracking-table cap after pruning stale entries.
        self._enforce_max_tracked_ips()

    def _enforce_max_tracked_ips(self) -> None:
        """Evict least-recently-active IPs when the table exceeds its cap.

        Bounds memory independently of the time-gated periodic cleanup. Once
        ``trust_proxy_headers`` is enabled the rate-limit key is the real,
        high-cardinality client IP, so a burst of distinct IPs could otherwise
        grow ``self.requests`` without limit between cleanup cycles. Keeps the
        ``max_tracked_ips`` most-recently-active entries (LRU eviction).
        """
        if len(self.requests) <= self.max_tracked_ips:
            return

        # Sort by most recent activity and keep only max_tracked_ips.
        sorted_ips = sorted(
            self.requests.items(),
            key=lambda item: max(item[1]) if item[1] else 0,
            reverse=True,
        )
        self.requests = defaultdict(
            list,
            dict(sorted_ips[: self.max_tracked_ips]),
        )

    def _evict_oldest_if_over_cap(self) -> None:
        """Evict oldest-inserted IPs until the table is within its cap (O(1)).

        Applied on the request fast path so a flood of distinct client IPs
        (possible once ``trust_proxy_headers`` is enabled) cannot grow the table
        without limit between the time-gated cleanup cycles. Uses cheap
        insertion-order eviction (dicts preserve insertion order, so
        ``next(iter(...))`` is the oldest key) rather than the full activity sort
        in :meth:`_enforce_max_tracked_ips`, avoiding an O(n log n) cost on every
        request under a high-cardinality flood. The periodic cleanup still does
        the activity-based LRU trim.
        """
        while len(self.requests) > self.max_tracked_ips:
            del self.requests[next(iter(self.requests))]

    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply rate limiting per IP address.

        Args:
            request: The incoming HTTP request.
            call_next: Callable to invoke the next middleware or endpoint.

        Returns:
            Response from downstream handler or 429 if rate limited.
        """
        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Periodic cleanup to prevent memory leaks
        self._cleanup_stale_entries(current_time)

        # A new key can push the table over max_tracked_ips between the
        # time-gated cleanup cycles; remember so we can re-bound it below.
        is_new_ip = client_ip not in self.requests

        # Clean up old entries for current IP (older than 1 minute)
        self.requests[client_ip] = [
            req_time
            for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]

        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # Check burst limit
        recent_requests = sum(
            1 for req_time in self.requests[client_ip] if current_time - req_time < 1
        )
        if recent_requests >= self.burst_size:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Burst limit exceeded: {self.burst_size} requests per second",
                    "retry_after": 1,
                },
                headers={"Retry-After": "1"},
            )

        # Record request
        self.requests[client_ip].append(current_time)

        # Bound the table immediately when a new IP pushed it over the cap,
        # instead of waiting for the next time-gated cleanup cycle. O(1)
        # insertion-order eviction on this fast path keeps max_tracked_ips
        # effective under a flood of distinct client IPs (possible once proxy
        # headers are trusted) without paying the periodic cleanup's full
        # activity-sort per request.
        if is_new_ip:
            self._evict_oldest_if_over_cap()

        return await call_next(request)


class SSRFPreventionMiddleware(BaseHTTPMiddleware):
    """Prevent Server-Side Request Forgery (SSRF) attacks.

    Blocks requests to internal/private IP ranges when making outbound HTTP calls.
    Implements OWASP A10 protection with proper IP address validation.

    Features:
    - Proper CIDR range validation using ipaddress module
    - Cloud metadata endpoint blocking (AWS, GCP, Azure)
    - DNS rebinding protection via hostname validation
    - IPv4 and IPv6 support

    Note: For production SSRF prevention, also consider:
    1. Use allowlists for external API endpoints
    2. Validate and sanitize URLs before making requests
    3. Use network segmentation
    4. Implement egress filtering at the network level
    """

    # Blocked hostnames (case-insensitive)
    BLOCKED_HOSTS: set[str] = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        # AWS metadata endpoints
        "169.254.169.254",
        "fd00:ec2::254",
        # GCP metadata endpoints
        "metadata.google.internal",
        "metadata.goog",
        # Azure metadata endpoints
        # Kubernetes
        "kubernetes.default",
        "kubernetes.default.svc",
    }

    # Blocked URL schemes
    BLOCKED_SCHEMES: set[str] = {
        "file",
        "gopher",
        "dict",
        "ftp",
        "ldap",
        "tftp",
    }

    @staticmethod
    def _is_internal_ip_type(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        """Check if IP is any internal type (private, loopback, link-local, etc).

        Args:
            ip: Parsed IP address object

        Returns:
            True if the IP is internal, False otherwise
        """
        internal_checks = [
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ]
        return any(internal_checks)

    @staticmethod
    def _is_private_ip(ip_str: str) -> bool:
        """Check if an IP address is private, loopback, or otherwise internal.

        Args:
            ip_str: IP address string to validate

        Returns:
            True if the IP is private/internal, False otherwise
        """
        try:
            ip = ipaddress.ip_address(ip_str)

            # Check standard internal IP properties
            if SSRFPreventionMiddleware._is_internal_ip_type(ip):
                return True

            # Additional check for IPv4-mapped IPv6 addresses
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
                return SSRFPreventionMiddleware._is_private_ip(str(ip.ipv4_mapped))

            return False
        except ValueError:
            # Not a valid IP address - let hostname checks handle it
            return False

    @staticmethod
    def _extract_host_from_url(url: str) -> str | None:
        """Extract hostname from URL string.

        Args:
            url: URL string to parse

        Returns:
            Hostname string or None if parsing fails
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            return parsed.hostname
        except Exception:
            return None

    @staticmethod
    def _extract_scheme_from_url(url: str) -> str | None:
        """Extract scheme from URL string.

        Args:
            url: URL string to parse

        Returns:
            Scheme string or None if parsing fails
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            return parsed.scheme.lower() if parsed.scheme else None
        except Exception:
            return None

    def _has_blocked_scheme(self, url: str) -> bool:
        """Check if URL uses a blocked scheme.

        Args:
            url: URL string to check

        Returns:
            True if scheme is blocked, False otherwise
        """
        scheme = self._extract_scheme_from_url(url)
        return scheme is not None and scheme in self.BLOCKED_SCHEMES

    def _is_blocked_host(self, host: str) -> bool:
        """Check if hostname is in blocklist or is a private IP.

        Args:
            host: Hostname to check

        Returns:
            True if host should be blocked, False otherwise
        """
        host_lower = host.lower()
        if host_lower in self.BLOCKED_HOSTS:
            return True
        return self._is_private_ip(host)

    def _is_obfuscated_private_ip(self, host: str) -> bool:
        """Check for numeric IP obfuscation (decimal notation).

        Detects attempts like 2130706433 = 127.0.0.1

        Args:
            host: Hostname that might be a decimal IP

        Returns:
            True if it's an obfuscated private IP, False otherwise
        """
        if not host.isdigit():
            return False

        try:
            ip_int = int(host)
            if 0 <= ip_int <= 0xFFFFFFFF:
                ip = ipaddress.ip_address(ip_int)
                return self._is_private_ip(str(ip))
        except (ValueError, OverflowError):
            # host is not a decimal integer IP literal; fall through to return False
            pass

        return False

    def _is_blocked_url(self, url: str) -> bool:
        """Check if a URL points to a blocked destination.

        Args:
            url: URL string to validate

        Returns:
            True if the URL should be blocked, False otherwise
        """
        if self._has_blocked_scheme(url):
            return True

        host = self._extract_host_from_url(url)
        if not host:
            return False

        return self._is_blocked_host(host) or self._is_obfuscated_private_ip(host)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check for SSRF patterns in request.

        Validates query parameters, form data, and JSON body for potential
        SSRF attempts targeting internal resources.

        Args:
            request: The incoming HTTP request.
            call_next: Callable to invoke the next middleware or endpoint.

        Returns:
            Response from downstream handler or 400 if SSRF detected.
        """
        # Check query parameters for URLs
        for param, value in request.query_params.items():
            if isinstance(value, str) and ("://" in value or value.startswith("//")):
                if self._is_blocked_url(value):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "Bad Request",
                            "message": "Request blocked: potential SSRF attempt",
                            "detail": f"Blocked URL detected in parameter: {param}",
                        },
                    )

        return await call_next(request)


@dataclass(frozen=True)
class SecurityConfig:
    """Configuration for security middleware.

    Attributes:
        enable_https_redirect: Redirect HTTP to HTTPS (production only)
        enable_rate_limiting: Enable rate limiting middleware
        enable_ssrf_prevention: Enable SSRF prevention middleware
        allowed_origins: CORS allowed origins (default: none)
        allowed_hosts: Trusted host names (default: all)
        rate_limit_rpm: Rate limit requests per minute
        trust_proxy_headers: Resolve the rate-limit client IP from
            ``client_ip_header`` instead of the direct peer. Enable only behind
            a trusted proxy that overwrites the header (default: False).
        client_ip_header: Header carrying the real client IP when
            ``trust_proxy_headers`` is True (default: ``CF-Connecting-IP``).
    """

    enable_https_redirect: bool = False
    enable_rate_limiting: bool = True
    enable_ssrf_prevention: bool = True
    allowed_origins: list[str] = field(default_factory=list)
    allowed_hosts: list[str] = field(default_factory=list)
    rate_limit_rpm: int = 60
    trust_proxy_headers: bool = False
    client_ip_header: str = "CF-Connecting-IP"


def add_security_middleware(app: FastAPI, config: SecurityConfig | None = None) -> None:
    """Add all security middleware to FastAPI application.

    This configures comprehensive security following OWASP best practices.

    Args:
        app: FastAPI application instance
        config: Security configuration options. Uses defaults if not provided.

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> config = SecurityConfig(
        ...     enable_https_redirect=True,
        ...     allowed_origins=["https://example.com"],
        ...     allowed_hosts=["example.com", "api.example.com"],
        ...     rate_limit_rpm=100,
        ... )
        >>> add_security_middleware(app, config)
    """
    if config is None:
        config = SecurityConfig()

    # HTTPS redirect (production only)
    if config.enable_https_redirect:
        app.add_middleware(HTTPSRedirectMiddleware)

    # Trusted hosts (OWASP A05)
    if config.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=config.allowed_hosts,
        )

    # CORS configuration (OWASP A05).
    #
    # CORS is only configured here when the caller explicitly supplies
    # ``allowed_origins``. The main application owns CORS in
    # ``rag_processor.main.create_app`` (driven by settings), so passing an
    # empty list keeps this helper from registering a *second*, conflicting
    # CORSMiddleware on top of it. Standalone users of this helper can still
    # opt in by providing origins.
    if config.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
            max_age=3600,
        )

    # Security headers (OWASP A05, A03, A09)
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting (OWASP A07)
    if config.enable_rate_limiting:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=config.rate_limit_rpm,
            burst_size=10,
            trust_proxy_headers=config.trust_proxy_headers,
            client_ip_header=config.client_ip_header,
        )

    # SSRF prevention (OWASP A10)
    if config.enable_ssrf_prevention:
        app.add_middleware(SSRFPreventionMiddleware)


# Example usage in main.py:
"""
from fastapi import FastAPI
from rag_processor.middleware.security import add_security_middleware, SecurityConfig

app = FastAPI()

# Add all security middleware
config = SecurityConfig(
    enable_https_redirect=True,  # Production only
    enable_rate_limiting=True,
    allowed_origins=[
        "https://example.com",
        "https://app.example.com",
    ],
    allowed_hosts=[
        "api.example.com",
        "localhost",  # Development only
    ],
    rate_limit_rpm=100,
)
add_security_middleware(app, config)

# Your routes here
@app.get("/")
async def root():
    return {"message": "Hello World"}
"""
