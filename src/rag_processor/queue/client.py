"""RQ Queue client for job submission.

Provides interface for enqueueing jobs to Redis queues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import redis
from rq import Queue

from rag_processor.core.redis import get_redis_client
from rag_processor.models.job import Priority
from rag_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

# Queue names by priority
QUEUE_HIGH = "high"
QUEUE_DEFAULT = "default"
QUEUE_LOW = "low"

# Priority to queue mapping
PRIORITY_QUEUE_MAP = {
    Priority.HIGH: QUEUE_HIGH,
    Priority.NORMAL: QUEUE_DEFAULT,
    Priority.LOW: QUEUE_LOW,
}


class QueueClient:
    """RQ-based queue client for job submission.

    Manages priority queues and job submission to Redis.

    Args:
        redis_client (redis.Redis | None): Optional Redis client. If not provided, creates
            one from settings.

    Example:
        client = QueueClient()
        rq_job = client.enqueue(process_job, job_id, priority=Priority.HIGH)
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        if redis_client is not None:
            self._redis = redis_client
        else:
            # RQ requires raw (bytes) responses; use the shared raw pool.
            self._redis = get_redis_client(decode_responses=False)

        # Create priority queues
        self._queues = {
            QUEUE_HIGH: Queue(QUEUE_HIGH, connection=self._redis),
            QUEUE_DEFAULT: Queue(QUEUE_DEFAULT, connection=self._redis),
            QUEUE_LOW: Queue(QUEUE_LOW, connection=self._redis),
        }

    def enqueue(
        self,
        func: Callable[..., Any],
        *args: Any,
        priority: Priority = Priority.NORMAL,
        job_timeout: int | None = None,
        retry: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Enqueue a job to the appropriate priority queue.

        Args:
            func (Callable[..., Any]): Function to execute.
            *args (Any): Positional arguments for the function.
            priority (Priority): Job priority (determines queue).
            job_timeout (int | None): Optional timeout in seconds.
            retry (int | None): Optional number of retries on failure.
            **kwargs (Any): Keyword arguments for the function.

        Returns:
            Any: RQ Job instance.
        """
        queue_name = PRIORITY_QUEUE_MAP.get(priority, QUEUE_DEFAULT)
        queue = self._queues[queue_name]

        # Build job options
        job_kwargs: dict[str, Any] = {}
        if job_timeout is not None:
            job_kwargs["job_timeout"] = job_timeout
        if retry is not None:
            job_kwargs["retry"] = retry

        rq_job = queue.enqueue(func, *args, **kwargs, **job_kwargs)

        logger.info(
            "Job enqueued",
            rq_job_id=rq_job.id,
            queue=queue_name,
            priority=priority.value,
            func=func.__name__,
        )

        return rq_job

    def get_queue(self, priority: Priority = Priority.NORMAL) -> Queue:
        """Get the queue for a given priority.

        Args:
            priority (Priority): Queue priority.

        Returns:
            Queue: RQ Queue instance.
        """
        queue_name = PRIORITY_QUEUE_MAP.get(priority, QUEUE_DEFAULT)
        return self._queues[queue_name]

    def get_queue_lengths(self) -> dict[str, int]:
        """Get the length of all queues.

        Returns:
            dict[str, int]: Dictionary of queue name to job count.
        """
        return {name: len(queue) for name, queue in self._queues.items()}

    def clear_all_queues(self) -> int:
        """Clear all queues.

        Returns:
            int: Total number of jobs cleared.
        """
        total = 0
        for queue in self._queues.values():
            cleared = cast("int", queue.empty())
            total += cleared
        logger.warning("All queues cleared", total_jobs=total)
        return total

    def ping(self) -> bool:
        """Check Redis connection.

        Returns:
            bool: True if Redis is reachable.
        """
        try:
            return cast("bool", self._redis.ping())
        except redis.ConnectionError:
            return False


# Global client instance
_queue_client: QueueClient | None = None


def get_queue_client() -> QueueClient:
    """Get the global queue client instance.

    Returns:
        QueueClient: QueueClient singleton.
    """
    global _queue_client  # noqa: PLW0603 - Singleton pattern
    if _queue_client is None:
        _queue_client = QueueClient()
    return _queue_client
