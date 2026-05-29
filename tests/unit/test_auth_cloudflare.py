"""Tests for uncovered paths in src/rag_processor/auth/cloudflare.py.

Focuses on _JWKSCache unit behavior and verify_cloudflare_token() which
have 0% coverage in the existing test_auth_middleware.py suite.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from rag_processor.auth.cloudflare import (
    _jwks_cache,
    _JWKSCache,
    clear_jwks_cache,
    verify_cloudflare_token,
)

UTC = timezone.utc  # noqa: UP017  # Python 3.10 compat: datetime.UTC added in 3.11

TEST_TEAM_DOMAIN = "test-team.cloudflareaccess.com"
TEST_AUDIENCE = "test-audience-tag"


# ---------------------------------------------------------------------------
# Key generation helpers (shared across tests)
# ---------------------------------------------------------------------------


def _generate_keys() -> tuple[rsa.RSAPrivateKey, dict]:
    """Return (private_key, JWK dict) for RS256 test tokens."""
    import base64

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = private_key.public_key().public_numbers()

    def _b64(n: int) -> str:
        data = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    jwk = {
        "kty": "RSA",
        "kid": "cf-test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64(pub.n),
        "e": _b64(pub.e),
    }
    return private_key, jwk


PRIVATE_KEY, PUBLIC_JWK = _generate_keys()


def _make_token(
    exp_delta: timedelta = timedelta(hours=1),
    audience: str = TEST_AUDIENCE,
    kid: str = "cf-test-key",
    include_kid: bool = True,
) -> str:
    now = datetime.now(tz=UTC)
    payload = {
        "iss": f"https://{TEST_TEAM_DOMAIN}",
        "sub": "user-xyz",
        "aud": audience,
        "exp": int((now + exp_delta).timestamp()),
        "iat": int(now.timestamp()),
        "email": "cf@example.com",
        "groups": [],
    }
    private_pem = PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    headers = {"kid": kid} if include_kid else {}
    return jwt.encode(payload, private_pem, algorithm="RS256", headers=headers)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_jwks_cache()
    yield
    clear_jwks_cache()


@pytest.fixture(autouse=True)
def mock_cf_settings():
    with patch("rag_processor.auth.cloudflare.settings") as m:
        m.cloudflare_enabled = True
        m.cloudflare_team_domain = TEST_TEAM_DOMAIN
        m.cloudflare_audience_tag = TEST_AUDIENCE
        yield m


# ---------------------------------------------------------------------------
# _JWKSCache unit tests
# ---------------------------------------------------------------------------


class TestJWKSCache:
    def test_empty_cache_is_invalid(self) -> None:
        cache = _JWKSCache()
        assert cache.is_valid() is False

    def test_populated_cache_within_ttl_is_valid(self) -> None:
        cache = _JWKSCache()
        cache.update({"keys": [PUBLIC_JWK]})
        assert cache.is_valid() is True

    def test_expired_cache_is_invalid(self) -> None:
        cache = _JWKSCache()
        cache.update({"keys": [PUBLIC_JWK]})
        # Simulate TTL expiry by backdating the timestamp
        cache.timestamp = time.time() - cache.ttl - 1
        assert cache.is_valid() is False

    def test_update_stores_data(self) -> None:
        cache = _JWKSCache()
        data = {"keys": [PUBLIC_JWK]}
        cache.update(data)
        assert cache.data == data
        assert cache.timestamp > 0

    def test_update_refreshes_timestamp(self) -> None:
        cache = _JWKSCache()
        cache.update({"keys": []})
        old_ts = cache.timestamp
        cache.update({"keys": [PUBLIC_JWK]})
        assert cache.timestamp >= old_ts

    def test_clear_empties_data(self) -> None:
        cache = _JWKSCache()
        cache.update({"keys": [PUBLIC_JWK]})
        cache.clear()
        assert cache.data == {}
        assert cache.timestamp == 0
        assert cache.is_valid() is False

    def test_clear_jwks_cache_helper(self) -> None:
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        assert _jwks_cache.is_valid() is True
        clear_jwks_cache()
        assert _jwks_cache.is_valid() is False


# ---------------------------------------------------------------------------
# verify_cloudflare_token -- cache pre-populated path
# ---------------------------------------------------------------------------


class TestVerifyCloudflareToken:
    @pytest.mark.anyio
    async def test_valid_token_returns_user_info(self) -> None:
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        token = _make_token()
        result = await verify_cloudflare_token(token)
        assert result["email"] == "cf@example.com"
        assert result["user_id"] == "user-xyz"

    @pytest.mark.anyio
    async def test_expired_token_raises(self) -> None:
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        token = _make_token(exp_delta=timedelta(hours=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            await verify_cloudflare_token(token)

    @pytest.mark.anyio
    async def test_token_within_leeway_is_accepted(self) -> None:
        """Regression: WS path now shares the HTTP middleware's clock-skew leeway.

        A token expired by less than the leeway must be accepted, matching the
        middleware (previously verify_cloudflare_token used no leeway and would
        reject it).
        """
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        token = _make_token(exp_delta=timedelta(seconds=-3))
        result = await verify_cloudflare_token(token)
        assert result["email"] == "cf@example.com"

    @pytest.mark.anyio
    async def test_missing_kid_raises(self) -> None:
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        token = _make_token(include_kid=False)
        with pytest.raises(jwt.InvalidTokenError, match="missing key ID"):
            await verify_cloudflare_token(token)

    @pytest.mark.anyio
    async def test_unknown_kid_raises(self) -> None:
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        token = _make_token(kid="unknown-key")
        with pytest.raises(jwt.InvalidTokenError, match="not found in JWKS"):
            await verify_cloudflare_token(token)

    @pytest.mark.anyio
    async def test_wrong_audience_raises(self) -> None:
        _jwks_cache.update({"keys": [PUBLIC_JWK]})
        token = _make_token(audience="wrong-audience")
        with pytest.raises(jwt.InvalidAudienceError):
            await verify_cloudflare_token(token)

    @pytest.mark.anyio
    async def test_fetches_jwks_when_cache_empty(self) -> None:
        """When cache is empty the function should fetch from Cloudflare."""
        assert not _jwks_cache.is_valid()
        token = _make_token()
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [PUBLIC_JWK]}
        mock_response.raise_for_status = (
            MagicMock()
        )  # sync: httpx.Response.raise_for_status is not async

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch(
            "rag_processor.auth.cloudflare.httpx.AsyncClient", return_value=mock_client
        ):
            result = await verify_cloudflare_token(token)

        assert result["email"] == "cf@example.com"
        mock_client.get.assert_awaited_once()
        assert _jwks_cache.is_valid()
