"""Tests for src/rag_processor/middleware/security.py."""

from __future__ import annotations

import dataclasses
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_processor.middleware.security import (
    RateLimitMiddleware,
    SecurityConfig,
    SecurityHeadersMiddleware,
    SSRFPreventionMiddleware,
    add_security_middleware,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bare_app() -> FastAPI:
    """FastAPI app with a single GET /test route and no middleware."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    @pytest.fixture
    def client(self) -> TestClient:
        app = _bare_app()
        app.add_middleware(SecurityHeadersMiddleware)
        return TestClient(app)

    def test_x_content_type_options_present(self, client: TestClient) -> None:
        response = client.get("/test")
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_x_frame_options_present(self, client: TestClient) -> None:
        response = client.get("/test")
        assert response.headers["x-frame-options"] == "DENY"

    def test_x_xss_protection_present(self, client: TestClient) -> None:
        response = client.get("/test")
        assert response.headers["x-xss-protection"] == "1; mode=block"

    def test_csp_present(self, client: TestClient) -> None:
        response = client.get("/test")
        assert "content-security-policy" in response.headers
        assert "default-src 'self'" in response.headers["content-security-policy"]

    def test_referrer_policy_present(self, client: TestClient) -> None:
        response = client.get("/test")
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_present(self, client: TestClient) -> None:
        response = client.get("/test")
        assert "permissions-policy" in response.headers
        assert "geolocation=()" in response.headers["permissions-policy"]

    def test_no_hsts_for_http(self, client: TestClient) -> None:
        response = client.get("/test")
        assert "strict-transport-security" not in response.headers

    def test_hsts_added_for_https(self) -> None:
        app = _bare_app()
        app.add_middleware(SecurityHeadersMiddleware)
        # base_url with https makes request.url.scheme == "https"
        https_client = TestClient(app, base_url="https://testserver")
        response = https_client.get("/test")
        assert "strict-transport-security" in response.headers
        assert "max-age=31536000" in response.headers["strict-transport-security"]

    def test_server_header_removed(self) -> None:
        """Server header is stripped even when a downstream component sets it."""
        from starlette.middleware.base import BaseHTTPMiddleware

        class _InjectServerHeader(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                response.headers["Server"] = "uvicorn/0.0.0"
                return response

        app = _bare_app()
        # add_middleware uses insert(0); last added = outermost = sees response last
        app.add_middleware(_InjectServerHeader)  # inner: injects Server first
        app.add_middleware(SecurityHeadersMiddleware)  # outer: strips Server last
        client = TestClient(app)
        response = client.get("/test")
        assert "server" not in response.headers


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    def test_init_defaults(self) -> None:
        app = FastAPI()
        mw = RateLimitMiddleware(app)
        assert mw.requests_per_minute == 60
        assert mw.burst_size == 10
        assert mw.max_tracked_ips == 10000
        assert mw.cleanup_interval == 300

    def test_normal_request_passes(self) -> None:
        app = _bare_app()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=5, burst_size=5)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_rate_limit_exceeded_returns_429(self) -> None:
        app = _bare_app()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2, burst_size=100)
        client = TestClient(app)
        # Use up the per-minute quota
        client.get("/test")
        client.get("/test")
        response = client.get("/test")
        assert response.status_code == 429
        body = response.json()
        assert body["error"] == "Too Many Requests"
        assert body["retry_after"] == 60
        assert response.headers["retry-after"] == "60"

    def test_burst_limit_exceeded_returns_429(self) -> None:
        app = _bare_app()
        # Allow many per minute but only 1 per second burst
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1000, burst_size=1)
        client = TestClient(app)
        client.get("/test")
        response = client.get("/test")
        assert response.status_code == 429
        body = response.json()
        assert body["retry_after"] == 1
        assert response.headers["retry-after"] == "1"

    def test_cleanup_removes_stale_entries(self) -> None:
        app = FastAPI()
        mw = RateLimitMiddleware(
            app,
            requests_per_minute=100,
            burst_size=100,
            cleanup_interval=0,  # always clean
        )
        # Add a stale entry (61 seconds old)
        mw.requests["old-ip"] = [time.time() - 61]
        mw._last_cleanup = 0  # force cleanup on next call
        mw._cleanup_stale_entries(time.time())
        assert "old-ip" not in mw.requests

    def test_cleanup_removes_lru_ips_when_over_limit(self) -> None:
        app = FastAPI()
        mw = RateLimitMiddleware(
            app,
            max_tracked_ips=2,
            cleanup_interval=0,
        )
        now = time.time()
        # Add 3 IPs all with recent activity
        mw.requests["ip-a"] = [now - 5]
        mw.requests["ip-b"] = [now - 10]
        mw.requests["ip-c"] = [now - 15]
        mw._last_cleanup = 0
        mw._cleanup_stale_entries(now)
        # Only the 2 most recently active should remain
        assert len(mw.requests) <= 2
        assert "ip-a" in mw.requests
        assert "ip-b" in mw.requests

    def test_cleanup_skipped_within_interval(self) -> None:
        app = FastAPI()
        mw = RateLimitMiddleware(app, cleanup_interval=300)
        mw.requests["ip-a"] = [time.time() - 61]
        # Cleanup was just done (timestamp very recent)
        mw._last_cleanup = time.time()
        mw._cleanup_stale_entries(time.time())
        # Entry should NOT be removed because the interval has not elapsed
        assert "ip-a" in mw.requests


# ---------------------------------------------------------------------------
# SSRFPreventionMiddleware
# ---------------------------------------------------------------------------


class TestSSRFPreventionMiddleware:
    @pytest.fixture
    def mw(self) -> SSRFPreventionMiddleware:
        return SSRFPreventionMiddleware(MagicMock())

    # _is_private_ip
    def test_is_private_ip_loopback(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_private_ip("127.0.0.1") is True

    def test_is_private_ip_rfc1918(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_private_ip("10.0.0.1") is True
        assert mw._is_private_ip("192.168.1.1") is True
        assert mw._is_private_ip("172.16.0.1") is True

    def test_is_private_ip_public(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_private_ip("8.8.8.8") is False

    def test_is_private_ip_invalid(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_private_ip("not-an-ip") is False

    def test_is_private_ip_ipv4_mapped_ipv6(self, mw: SSRFPreventionMiddleware) -> None:
        # ::ffff:127.0.0.1 is IPv4-mapped loopback
        assert mw._is_private_ip("::ffff:127.0.0.1") is True

    # _extract_host_from_url
    def test_extract_host_from_url(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._extract_host_from_url("http://example.com/path") == "example.com"

    def test_extract_host_from_url_invalid(self, mw: SSRFPreventionMiddleware) -> None:
        # urlparse is lenient so even odd strings return something or None hostname
        result = mw._extract_host_from_url("http://")
        assert result is None or result == ""

    # _extract_scheme_from_url
    def test_extract_scheme_https(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._extract_scheme_from_url("https://example.com") == "https"

    def test_extract_scheme_file(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._extract_scheme_from_url("file:///etc/passwd") == "file"

    # _has_blocked_scheme
    def test_has_blocked_scheme_file(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._has_blocked_scheme("file:///etc/passwd") is True

    def test_has_blocked_scheme_gopher(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._has_blocked_scheme("gopher://example.com") is True

    def test_has_blocked_scheme_https_allowed(
        self, mw: SSRFPreventionMiddleware
    ) -> None:
        assert mw._has_blocked_scheme("https://example.com") is False

    # _is_blocked_host
    def test_is_blocked_host_localhost(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_host("localhost") is True

    def test_is_blocked_host_metadata(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_host("169.254.169.254") is True

    def test_is_blocked_host_public(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_host("example.com") is False

    # _is_obfuscated_private_ip
    def test_obfuscated_loopback(self, mw: SSRFPreventionMiddleware) -> None:
        # 2130706433 == 127.0.0.1
        assert mw._is_obfuscated_private_ip("2130706433") is True

    def test_obfuscated_public_ip(self, mw: SSRFPreventionMiddleware) -> None:
        # 134744072 == 8.8.8.8
        assert mw._is_obfuscated_private_ip("134744072") is False

    def test_obfuscated_not_digit(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_obfuscated_private_ip("localhost") is False

    # _is_blocked_url
    def test_is_blocked_url_localhost(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_url("http://localhost/api") is True

    def test_is_blocked_url_file_scheme(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_url("file:///etc/passwd") is True

    def test_is_blocked_url_public(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_url("https://api.example.com/data") is False

    def test_is_blocked_url_no_host(self, mw: SSRFPreventionMiddleware) -> None:
        assert mw._is_blocked_url("/relative/path") is False

    # dispatch
    def test_dispatch_blocks_ssrf_query_param(self) -> None:
        app = _bare_app()
        app.add_middleware(SSRFPreventionMiddleware)
        client = TestClient(app)
        response = client.get("/test?url=http://localhost/internal")
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "Bad Request"

    def test_dispatch_allows_safe_request(self) -> None:
        app = _bare_app()
        app.add_middleware(SSRFPreventionMiddleware)
        client = TestClient(app)
        response = client.get("/test?url=https://api.example.com/data")
        assert response.status_code == 200

    def test_dispatch_ignores_non_url_params(self) -> None:
        app = _bare_app()
        app.add_middleware(SSRFPreventionMiddleware)
        client = TestClient(app)
        response = client.get("/test?name=alice&page=1")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# SecurityConfig
# ---------------------------------------------------------------------------


class TestSecurityConfig:
    def test_defaults(self) -> None:
        config = SecurityConfig()
        assert config.enable_https_redirect is False
        assert config.enable_rate_limiting is True
        assert config.enable_ssrf_prevention is True
        assert config.allowed_origins == []
        assert config.allowed_hosts == []
        assert config.rate_limit_rpm == 60

    def test_custom_values(self) -> None:
        config = SecurityConfig(
            enable_https_redirect=True,
            rate_limit_rpm=120,
            allowed_origins=["https://example.com"],
        )
        assert config.enable_https_redirect is True
        assert config.rate_limit_rpm == 120
        assert config.allowed_origins == ["https://example.com"]

    def test_frozen(self) -> None:
        config = SecurityConfig()
        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign"):
            config.rate_limit_rpm = 999  # type: ignore[misc]

    def test_frozen_raises_on_bool_mutation(self) -> None:
        config = SecurityConfig()
        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign"):
            config.enable_rate_limiting = False  # type: ignore[misc]



# ---------------------------------------------------------------------------
# add_security_middleware
# ---------------------------------------------------------------------------


class TestAddSecurityMiddleware:
    def test_default_config_adds_middleware(self) -> None:
        app = _bare_app()
        add_security_middleware(app)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "x-content-type-options" in response.headers

    def test_none_config_uses_defaults(self) -> None:
        app = _bare_app()
        add_security_middleware(app, config=None)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_with_allowed_hosts(self) -> None:
        app = _bare_app()
        config = SecurityConfig(
            allowed_hosts=["testserver"],
            enable_rate_limiting=False,
            enable_ssrf_prevention=False,
        )
        add_security_middleware(app, config)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_with_rate_limiting_enabled(self) -> None:
        app = _bare_app()
        config = SecurityConfig(
            enable_rate_limiting=True,
            rate_limit_rpm=1000,
            enable_ssrf_prevention=False,
        )
        add_security_middleware(app, config)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_with_ssrf_prevention_disabled(self) -> None:
        app = _bare_app()
        config = SecurityConfig(
            enable_ssrf_prevention=False, enable_rate_limiting=False
        )
        add_security_middleware(app, config)
        client = TestClient(app)
        response = client.get("/test?url=http://localhost/internal")
        # Without SSRF middleware the request passes through
        assert response.status_code == 200
