"""Unit tests for the application factory ``create_app``.

Guards the wiring that ``create_app`` performs, in particular the proxy-aware
rate-limiting configuration that must be passed through to ``SecurityConfig``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import rag_processor.main as main_module
from rag_processor.core.config import settings


@pytest.mark.unit
class TestCreateAppSecurityWiring:
    """The factory must forward proxy-aware rate-limiting settings."""

    def test_create_app_passes_proxy_rate_limit_settings(self) -> None:
        """``create_app`` wires trust_proxy_headers and client_ip_header.

        Regression: an earlier app-factory refactor dropped these two kwargs,
        silently reverting per-IP rate limiting to keying on the proxy IP behind
        Cloudflare. ``create_app`` must always forward both from settings.
        """
        # wraps=... keeps the real SecurityConfig behavior so the rest of
        # create_app (middleware registration) still runs, while recording the
        # call so we can assert the proxy kwargs were forwarded.
        real_security_config = main_module.SecurityConfig
        with patch.object(
            main_module,
            "SecurityConfig",
            wraps=real_security_config,
        ) as spy:
            main_module.create_app()

        spy.assert_called_once()
        kwargs = spy.call_args.kwargs
        assert kwargs["trust_proxy_headers"] == settings.rate_limit_trust_proxy
        assert kwargs["client_ip_header"] == settings.rate_limit_client_ip_header
