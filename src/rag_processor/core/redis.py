"""Centralized synchronous Redis client construction.

RQ (the job queue) requires a *synchronous* redis-py client, and the worker
process shares Redis with the API. Rather than have ``queue/client.py``,
``queue/redis_store.py`` and ``websocket/events.py`` each hand-roll their own
``redis.Redis(...)`` with duplicated connection kwargs (and no shared pool or
cleanup), every sync consumer builds its client here from a process-wide
connection pool.

Two pools are maintained because ``decode_responses`` is a connection-level
setting in redis-py and cannot be mixed within a single pool:

* the **decoded** pool returns ``str`` responses and backs application data
  (``RedisStore``) and event publishing (``websocket/events.py``);
* the **raw** pool returns ``bytes`` responses and backs RQ, which requires
  un-decoded payloads.

IMPORTANT: these clients are synchronous. Async HTTP/WebSocket handlers must
never call them directly on the event loop; use the ``*_async`` helpers in
``rag_processor.queue.jobs`` which offload the blocking call to a worker
thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import threading

import redis

from rag_processor.core.config import settings
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)

# Process-wide connection pools, created lazily on first use.
_decoded_pool: redis.ConnectionPool | None = None
_raw_pool: redis.ConnectionPool | None = None

# Guards lazy pool construction/reset. get_redis_client is called from worker
# threads via asyncio.to_thread, so without this lock two threads racing on
# first use could build two pools (one of which leaks sockets until GC).
_pool_lock = threading.Lock()


def _build_pool(*, decode_responses: bool) -> redis.ConnectionPool:
    """Build a Redis connection pool from application settings.

    Args:
        decode_responses (bool): Whether connections decode responses to ``str``.

    Returns:
        redis.ConnectionPool: A configured Redis connection pool.
    """
    return redis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        db=settings.redis_db,
        decode_responses=decode_responses,
    )


def get_redis_client(*, decode_responses: bool = True) -> redis.Redis:
    """Return a synchronous Redis client backed by a shared connection pool.

    Args:
        decode_responses (bool): ``True`` (default) for ``str`` responses used by
            application data and event publishing; ``False`` for ``bytes``
            responses required by RQ.

    Returns:
        redis.Redis: A ``redis.Redis`` client sharing the appropriate process-wide pool.
    """
    global _decoded_pool, _raw_pool  # noqa: PLW0603 - module-level pool cache

    if decode_responses:
        if _decoded_pool is None:
            with _pool_lock:
                # Re-check under the lock so only one thread builds the pool.
                if _decoded_pool is None:
                    _decoded_pool = _build_pool(decode_responses=True)
        return redis.Redis(connection_pool=_decoded_pool)

    if _raw_pool is None:
        with _pool_lock:
            if _raw_pool is None:
                _raw_pool = _build_pool(decode_responses=False)
    return redis.Redis(connection_pool=_raw_pool)


def close_redis_pools() -> None:
    """Disconnect and reset the shared Redis pools.

    Intended to be called from the FastAPI shutdown lifespan so connections
    are released gracefully. Safe to call when no pools were created.
    """
    global _decoded_pool, _raw_pool  # noqa: PLW0603 - module-level pool cache

    with _pool_lock:
        for pool in (_decoded_pool, _raw_pool):
            if pool is not None:
                pool.disconnect()

        if _decoded_pool is not None or _raw_pool is not None:
            logger.info("Closed shared Redis connection pools")

        _decoded_pool = None
        _raw_pool = None


__all__ = ["close_redis_pools", "get_redis_client"]
