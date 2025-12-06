"""Redis data store for batches and jobs.

Provides Redis-based storage for batch and job metadata.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID  # noqa: TC003 - Used at runtime in function signatures

import redis

from rag_processor.core.config import settings
from rag_processor.models.batch import Batch
from rag_processor.models.job import Job
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)

# Redis key prefixes
BATCH_KEY_PREFIX = "batch:"
JOB_KEY_PREFIX = "job:"
BATCH_JOBS_KEY_PREFIX = "batch_jobs:"


class RedisStore:
    """Redis-based storage for batches and jobs.

    Stores batch and job metadata in Redis hashes for fast lookup.

    Example:
        store = RedisStore()
        store.save_batch(batch)
        loaded = store.get_batch(batch.batch_id)
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        """Initialize the Redis store.

        Args:
            redis_client: Optional Redis client. If not provided, creates
                one from settings.
        """
        if redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                db=settings.redis_db,
                decode_responses=True,
            )

    def save_batch(self, batch: Batch) -> None:
        """Save a batch to Redis.

        Args:
            batch: Batch to save.
        """
        key = f"{BATCH_KEY_PREFIX}{batch.batch_id}"
        self._redis.hset(key, mapping=batch.to_redis_dict())
        logger.debug("Batch saved to Redis", batch_id=str(batch.batch_id))

    def get_batch(self, batch_id: UUID | str) -> Batch | None:
        """Load a batch from Redis.

        Args:
            batch_id: Batch identifier.

        Returns:
            Batch if found, None otherwise.
        """
        key = f"{BATCH_KEY_PREFIX}{batch_id}"
        data = self._redis.hgetall(key)

        if not data:
            return None

        return Batch.from_redis_dict(data)

    def update_batch_status(
        self,
        batch_id: UUID | str,
        *,
        completed_files: int | None = None,
        failed_files: int | None = None,
        status: str | None = None,
    ) -> None:
        """Update batch status fields.

        Args:
            batch_id: Batch identifier.
            completed_files: Number of completed files.
            failed_files: Number of failed files.
            status: New status value.
        """
        key = f"{BATCH_KEY_PREFIX}{batch_id}"
        updates: dict[str, str] = {}

        if completed_files is not None:
            updates["completed_files"] = str(completed_files)
        if failed_files is not None:
            updates["failed_files"] = str(failed_files)
        if status is not None:
            updates["status"] = status

        if updates:
            self._redis.hset(key, mapping=updates)
            logger.debug("Batch status updated", batch_id=str(batch_id), updates=updates)

    def save_job(self, job: Job) -> None:
        """Save a job to Redis.

        Args:
            job: Job to save.
        """
        key = f"{JOB_KEY_PREFIX}{job.job_id}"
        self._redis.hset(key, mapping=job.to_redis_dict())

        # Add to batch's job list
        batch_jobs_key = f"{BATCH_JOBS_KEY_PREFIX}{job.batch_id}"
        self._redis.sadd(batch_jobs_key, str(job.job_id))

        logger.debug(
            "Job saved to Redis",
            job_id=str(job.job_id),
            batch_id=str(job.batch_id),
        )

    def get_job(self, job_id: UUID | str) -> Job | None:
        """Load a job from Redis.

        Args:
            job_id: Job identifier.

        Returns:
            Job if found, None otherwise.
        """
        key = f"{JOB_KEY_PREFIX}{job_id}"
        data = self._redis.hgetall(key)

        if not data:
            return None

        return Job.from_redis_dict(data)

    def update_job_status(
        self,
        job_id: UUID | str,
        *,
        status: str | None = None,
        error_message: str | None = None,
        retry_count: int | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        """Update job status fields.

        Args:
            job_id: Job identifier.
            status: New status value.
            error_message: Error message if failed.
            retry_count: Updated retry count.
            started_at: Processing start time (ISO format).
            completed_at: Processing completion time (ISO format).
        """
        key = f"{JOB_KEY_PREFIX}{job_id}"
        updates: dict[str, str] = {}

        if status is not None:
            updates["status"] = status
        if error_message is not None:
            updates["error_message"] = error_message
        if retry_count is not None:
            updates["retry_count"] = str(retry_count)
        if started_at is not None:
            updates["started_at"] = started_at
        if completed_at is not None:
            updates["completed_at"] = completed_at

        if updates:
            updates["updated_at"] = datetime.now(tz=UTC).isoformat()
            self._redis.hset(key, mapping=updates)
            logger.debug("Job status updated", job_id=str(job_id), updates=updates)

    def get_batch_jobs(self, batch_id: UUID | str) -> list[Job]:
        """Get all jobs for a batch.

        Args:
            batch_id: Batch identifier.

        Returns:
            List of jobs in the batch.
        """
        batch_jobs_key = f"{BATCH_JOBS_KEY_PREFIX}{batch_id}"
        job_ids = self._redis.smembers(batch_jobs_key)

        jobs = []
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job:
                jobs.append(job)

        return jobs

    def delete_batch(self, batch_id: UUID | str) -> None:
        """Delete a batch and its jobs from Redis.

        Args:
            batch_id: Batch identifier.
        """
        # Get all job IDs
        batch_jobs_key = f"{BATCH_JOBS_KEY_PREFIX}{batch_id}"
        job_ids = self._redis.smembers(batch_jobs_key)

        # Delete jobs
        for job_id in job_ids:
            self._redis.delete(f"{JOB_KEY_PREFIX}{job_id}")

        # Delete batch jobs set
        self._redis.delete(batch_jobs_key)

        # Delete batch
        self._redis.delete(f"{BATCH_KEY_PREFIX}{batch_id}")

        logger.info("Batch deleted", batch_id=str(batch_id), jobs_deleted=len(job_ids))

    def ping(self) -> bool:
        """Check Redis connection.

        Returns:
            True if Redis is reachable.
        """
        try:
            return self._redis.ping()
        except redis.ConnectionError:
            return False


# Global store instance
_redis_store: RedisStore | None = None


def get_redis_store() -> RedisStore:
    """Get the global Redis store instance.

    Returns:
        RedisStore singleton.
    """
    global _redis_store  # noqa: PLW0603 - Singleton pattern
    if _redis_store is None:
        _redis_store = RedisStore()
    return _redis_store
