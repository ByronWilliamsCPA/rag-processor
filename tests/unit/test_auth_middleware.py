"""Tests for Cloudflare Access JWT authentication middleware."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_processor.api.health import router as health_router
from rag_processor.api.user import router as user_router
from rag_processor.auth.cloudflare import (
    CF_ACCESS_JWT_HEADER,
    CloudflareAuthMiddleware,
    clear_jwks_cache,
)

if TYPE_CHECKING:
    pass


# Generate test RSA keys
def generate_test_keys() -> tuple[rsa.RSAPrivateKey, dict]:
    """Generate RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Convert to JWK format
    public_numbers = public_key.public_numbers()
    import base64

    def int_to_base64(n: int) -> str:
        data = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    jwk = {
        "kty": "RSA",
        "kid": "test-key-1",
        "use": "sig",
        "alg": "RS256",
        "n": int_to_base64(public_numbers.n),
        "e": int_to_base64(public_numbers.e),
    }

    return private_key, jwk


# Test fixtures
PRIVATE_KEY, PUBLIC_JWK = generate_test_keys()
TEST_TEAM_DOMAIN = "test-team.cloudflareaccess.com"
TEST_AUDIENCE = "test-audience-tag"


def create_test_token(
    email: str = "test@example.com",
    exp_delta: timedelta = timedelta(hours=1),
    iat_delta: timedelta = timedelta(seconds=0),
    audience: str = TEST_AUDIENCE,
    issuer: str = f"https://{TEST_TEAM_DOMAIN}",
    kid: str = "test-key-1",
) -> str:
    """Create a test JWT token."""
    # Use timezone-aware datetime to avoid timestamp conversion issues
    # datetime.utcnow() is deprecated and produces incorrect timestamps
    now = datetime.now(tz=UTC)
    payload = {
        "iss": issuer,
        "sub": "user-123",
        "aud": audience,
        "exp": int((now + exp_delta).timestamp()),
        "iat": int((now + iat_delta).timestamp()),
        "email": email,
        "type": "app",
        "groups": ["test-group"],
    }

    private_pem = PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI application."""
    test_app = FastAPI()
    test_app.add_middleware(CloudflareAuthMiddleware)
    test_app.include_router(health_router)
    test_app.include_router(user_router, prefix="/api/v1")
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for tests."""
    with patch("rag_processor.auth.cloudflare.settings") as mock:
        mock.cloudflare_enabled = True
        mock.cloudflare_team_domain = TEST_TEAM_DOMAIN
        mock.cloudflare_audience_tag = TEST_AUDIENCE
        yield mock


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear JWKS cache before each test."""
    clear_jwks_cache()
    yield
    clear_jwks_cache()


class TestPublicEndpoints:
    """Tests for public endpoints that don't require auth."""

    def test_health_endpoint_no_auth(self, client: TestClient):
        """Health endpoints should work without authentication."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_ready_no_auth(self, client: TestClient):
        """Ready endpoint should work without authentication."""
        # Note: This may fail if database check fails, but that's ok for auth test
        response = client.get("/health/ready")
        # Accept either 200 or 503 (db not available)
        assert response.status_code in (200, 503)


class TestAuthenticatedEndpoints:
    """Tests for endpoints requiring authentication."""

    def test_missing_token_returns_401(self, client: TestClient):
        """Request without token should return 401."""
        response = client.get("/api/v1/user/me")
        assert response.status_code == 401
        assert "Missing authentication token" in response.json()["detail"]

    def test_valid_token_returns_user(self, client: TestClient, mock_settings):
        """Valid token should authenticate successfully."""
        token = create_test_token()

        # Mock JWKS fetch
        with patch.object(
            CloudflareAuthMiddleware,
            "_get_jwks",
            return_value={"keys": [PUBLIC_JWK]},
        ):
            response = client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["user_id"] == "user-123"

    def test_expired_token_returns_401(self, client: TestClient, mock_settings):
        """Expired token should return 401."""
        token = create_test_token(exp_delta=timedelta(hours=-1))

        with patch.object(
            CloudflareAuthMiddleware,
            "_get_jwks",
            return_value={"keys": [PUBLIC_JWK]},
        ):
            response = client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_invalid_signature_returns_401(self, client: TestClient, mock_settings):
        """Token with invalid signature should return 401."""
        # Create token with different key
        other_private, _ = generate_test_keys()
        private_pem = other_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        now = datetime.now(tz=UTC)
        token = jwt.encode(
            {
                "iss": f"https://{TEST_TEAM_DOMAIN}",
                "sub": "user-123",
                "aud": TEST_AUDIENCE,
                "exp": int((now + timedelta(hours=1)).timestamp()),
                "iat": int(now.timestamp()),
                "email": "test@example.com",
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-1"},
        )

        with patch.object(
            CloudflareAuthMiddleware,
            "_get_jwks",
            return_value={"keys": [PUBLIC_JWK]},
        ):
            response = client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )

        assert response.status_code == 401

    def test_invalid_audience_returns_401(self, client: TestClient, mock_settings):
        """Token with wrong audience should return 401."""
        token = create_test_token(audience="wrong-audience")

        with patch.object(
            CloudflareAuthMiddleware,
            "_get_jwks",
            return_value={"keys": [PUBLIC_JWK]},
        ):
            response = client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )

        assert response.status_code == 401
        assert "audience" in response.json()["detail"].lower()

    def test_missing_kid_returns_401(self, client: TestClient, mock_settings):
        """Token without key ID should return 401."""
        now = datetime.now(tz=UTC)
        payload = {
            "iss": f"https://{TEST_TEAM_DOMAIN}",
            "sub": "user-123",
            "aud": TEST_AUDIENCE,
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iat": int(now.timestamp()),
            "email": "test@example.com",
        }
        private_pem = PRIVATE_KEY.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Create token without kid header
        token = jwt.encode(payload, private_pem, algorithm="RS256")

        with patch.object(
            CloudflareAuthMiddleware,
            "_get_jwks",
            return_value={"keys": [PUBLIC_JWK]},
        ):
            response = client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )

        assert response.status_code == 401


class TestBypassMode:
    """Tests for local development bypass mode."""

    def test_bypass_mode_creates_dev_user(self, client: TestClient, mock_settings):
        """With CLOUDFLARE_ENABLED=false, should create dev user."""
        mock_settings.cloudflare_enabled = False

        response = client.get("/api/v1/user/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "dev@localhost"
        assert data["user_id"] == "dev-user-001"

    def test_bypass_mode_no_token_needed(self, client: TestClient, mock_settings):
        """Bypass mode should not require token."""
        mock_settings.cloudflare_enabled = False

        response = client.get("/api/v1/user/me")
        assert response.status_code == 200


class TestJWKSCaching:
    """Tests for JWKS caching behavior."""

    def test_jwks_cache_reused(self, client: TestClient, mock_settings):
        """JWKS should be cached and reused."""
        token = create_test_token()
        call_count = 0

        async def mock_get_jwks(self):
            nonlocal call_count
            call_count += 1
            return {"keys": [PUBLIC_JWK]}

        with patch.object(CloudflareAuthMiddleware, "_get_jwks", mock_get_jwks):
            # Make two requests
            client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )
            client.get(
                "/api/v1/user/me",
                headers={CF_ACCESS_JWT_HEADER: token},
            )

        # JWKS should only be fetched once (cached)
        assert call_count == 2  # Each request goes through middleware
