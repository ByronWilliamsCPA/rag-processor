"""Tests for the readiness probe: real Redis check + schema-consistent 503."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from rag_processor.api.health import ReadinessStatus, check_redis, readiness


def _redis_client(*, ping_result: object = True) -> MagicMock:
    client = MagicMock()
    client.ping.return_value = ping_result
    return client


class TestCheckRedis:
    @pytest.mark.asyncio
    async def test_healthy_when_ping_succeeds(self) -> None:
        with patch(
            "rag_processor.core.redis.get_redis_client",
            return_value=_redis_client(ping_result=True),
        ):
            check = await check_redis()
        assert check.name == "redis"
        assert check.healthy is True

    @pytest.mark.asyncio
    async def test_unhealthy_when_ping_raises(self) -> None:
        client = MagicMock()
        client.ping.side_effect = ConnectionError("refused")
        with patch("rag_processor.core.redis.get_redis_client", return_value=client):
            check = await check_redis()
        assert check.healthy is False
        assert "unreachable" in check.message.lower()


class TestReadiness:
    @pytest.mark.asyncio
    async def test_ready_when_redis_healthy(self) -> None:
        with patch(
            "rag_processor.core.redis.get_redis_client",
            return_value=_redis_client(ping_result=True),
        ):
            result = await readiness()
        assert result.status == "ready"
        assert any(c.name == "redis" and c.healthy for c in result.checks)

    @pytest.mark.asyncio
    async def test_returns_ready_when_redis_down_but_not_required(self) -> None:
        client = MagicMock()
        client.ping.side_effect = ConnectionError("refused")
        with (
            patch("rag_processor.core.redis.get_redis_client", return_value=client),
            patch("rag_processor.api.health.settings") as mock_settings,
        ):
            mock_settings.readiness_require_redis = False
            result = await readiness()
        # Truthful check (unhealthy) but probe still ready since Redis not required.
        assert result.status == "ready"
        assert any(c.name == "redis" and not c.healthy for c in result.checks)

    @pytest.mark.asyncio
    async def test_503_with_schema_body_when_required_redis_down(self) -> None:
        client = MagicMock()
        client.ping.side_effect = ConnectionError("refused")
        with (
            patch("rag_processor.core.redis.get_redis_client", return_value=client),
            patch("rag_processor.api.health.settings") as mock_settings,
        ):
            mock_settings.readiness_require_redis = True
            with pytest.raises(HTTPException) as exc:
                await readiness()

        assert exc.value.status_code == 503
        # The 503 body must conform to the ReadinessStatus schema (L5).
        detail = exc.value.detail
        assert ReadinessStatus.model_validate(detail).status == "unavailable"
