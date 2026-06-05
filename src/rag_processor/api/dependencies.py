"""Shared FastAPI dependency providers for the API layer.

These providers give route handlers an injectable seam for collaborators that
were previously instantiated as module-level globals. Using ``Depends`` keeps
construction lazy (nothing is built at import time) and lets tests override
collaborators via ``app.dependency_overrides`` instead of monkeypatching module
globals.
"""

from __future__ import annotations

from functools import lru_cache

from rag_processor.routing import FileRouter


@lru_cache(maxsize=1)
def get_file_router() -> FileRouter:
    """Return the process-wide :class:`FileRouter` instance.

    The router (and the magic/pdf parsers it wraps) is comparatively expensive
    to build, so it is cached for the lifetime of the process. Tests can
    override this dependency to inject a stub router.

    Returns:
        FileRouter: The shared FileRouter instance.
    """
    return FileRouter()
