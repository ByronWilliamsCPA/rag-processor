"""Export the FastAPI OpenAPI schema to ``docs/api/openapi.json``.

Imports the FastAPI ``app`` object and serializes ``app.openapi()`` to a
formatted JSON file. Does not start an HTTP server.

Usage:
    uv run python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Disable Cloudflare auth so the app object can be imported without secrets.
os.environ.setdefault("RAG_PROCESSOR_CLOUDFLARE_ENABLED", "false")
os.environ.setdefault("RAG_PROCESSOR_RATE_LIMITING_ENABLED", "false")

# Ensure ``src`` is importable when running directly.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rag_processor.main import app  # noqa: E402

OUTPUT_PATH = ROOT / "docs" / "api" / "openapi.json"


def main() -> int:
    """Generate and write the OpenAPI schema to ``docs/api/openapi.json``."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=False) + "\n")
    sys.stdout.write(
        f"Wrote OpenAPI schema with {len(schema.get('paths', {}))} paths "
        f"to {OUTPUT_PATH.relative_to(ROOT)}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
