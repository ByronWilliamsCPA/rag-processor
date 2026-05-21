"""Export the FastAPI OpenAPI schema to ``docs/api/openapi.json``.

Imports the FastAPI ``app`` object and serializes ``app.openapi()`` to a
formatted JSON file. Does not start an HTTP server.

Authentication is enforced by ``CloudflareAuthMiddleware`` rather than by
FastAPI ``Security`` dependencies, so ``app.openapi()`` does not emit a
``components.securitySchemes`` block on its own. This script post-processes
the schema to add the Cloudflare Access JWT scheme and apply it to every
operation outside the public allowlist (root, health, docs).

Usage:
    uv run python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "api" / "openapi.json"

SECURITY_SCHEME_NAME = "CloudflareAccessJwt"

# Exact paths reachable without a Cloudflare Access token.
PUBLIC_PATHS = {"/", "/docs", "/redoc", "/openapi.json"}

# Path-segment prefixes whose sub-paths are also public (trailing slash
# enforces segment boundary so /health-debug is not treated as public).
PUBLIC_PATH_PREFIXES = ("/health/", "/docs/", "/redoc/")


def _is_public(path: str) -> bool:
    """Return True if ``path`` is reachable without authentication.

    Uses exact-path matching for leaf endpoints and segment-boundary prefix
    matching for path families (e.g. ``/health/live``) to avoid false
    positives such as ``/health-debug`` or ``/openapi.jsonl``.
    """
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _apply_security(schema: dict[str, object]) -> None:
    """Inject the Cloudflare Access JWT security scheme into ``schema``."""
    components = schema.setdefault("components", {})
    if not isinstance(components, dict):
        return
    schemes = components.setdefault("securitySchemes", {})
    if isinstance(schemes, dict):
        schemes[SECURITY_SCHEME_NAME] = {
            "type": "apiKey",
            "in": "header",
            "name": "Cf-Access-Jwt-Assertion",
            "description": (
                "Cloudflare Access JWT assertion forwarded by the Cloudflare "
                "Access edge. Validated by CloudflareAuthMiddleware."
            ),
        }

    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        return
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        public = _is_public(str(path))
        for op in methods.values():
            if not isinstance(op, dict):
                continue
            if public:
                op.setdefault("security", [])
            else:
                op.setdefault("security", [{SECURITY_SCHEME_NAME: []}])


def main() -> int:
    """Generate and write the OpenAPI schema to ``docs/api/openapi.json``.

    Returns:
        Process exit code; 0 on success.

    Raises:
        OSError: If ``docs/api/openapi.json`` cannot be created or written.
    """
    # #CRITICAL: security: Disable Cloudflare auth + rate limiting so the app
    # object can be imported without secrets for offline OpenAPI export. These
    # defaults must NEVER be set in a runtime/production process.
    # #VERIFY: Confirm this script is only invoked from CI / local dev tooling.
    os.environ.setdefault("RAG_PROCESSOR_CLOUDFLARE_ENABLED", "false")
    os.environ.setdefault("RAG_PROCESSOR_RATE_LIMITING_ENABLED", "false")

    from rag_processor.main import app  # import after env vars are configured

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    _apply_security(schema)
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=False) + "\n")
    sys.stdout.write(
        f"Wrote OpenAPI schema with {len(schema.get('paths', {}))} paths "
        f"to {OUTPUT_PATH.relative_to(ROOT)}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
