"""Job submission and status tracking.

Functions for enqueuing jobs and checking their status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID  # noqa: TC003 - Used at runtime in function signatures

from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import Job, JobStatus
from rag_processor.queue.client import get_queue_client
from rag_processor.queue.redis_store import get_redis_store
from rag_processor.utils.logging import get_logger

UTC = timezone.utc  # noqa: UP017

logger = get_logger(__name__)


def enqueue_job(job: Job) -> str:
    """Submit a job to the queue.

    Saves the job to Redis and enqueues it for processing.

    Args:
        job: Job to enqueue.

    Returns:
        RQ job ID.
    """
    # Save job to Redis
    store = get_redis_store()
    store.save_job(job)

    # Enqueue to RQ
    client = get_queue_client()
    rq_job = client.enqueue(
        process_job_task,
        str(job.job_id),
        priority=job.priority,
        job_timeout=600,  # 10 minutes
    )

    logger.info(
        "Job enqueued for processing",
        job_id=str(job.job_id),
        batch_id=str(job.batch_id),
        rq_job_id=rq_job.id,
        priority=job.priority.value,
    )

    return rq_job.id


def enqueue_batch_jobs(batch: Batch, jobs: list[Job]) -> list[str]:
    """Submit a batch of jobs to the queue.

    Saves batch and all jobs to Redis and enqueues them.

    Args:
        batch: Parent batch.
        jobs: Jobs to enqueue.

    Returns:
        List of RQ job IDs.
    """
    store = get_redis_store()

    # Save batch first
    store.save_batch(batch)

    # Enqueue all jobs
    rq_job_ids = []
    for job in jobs:
        rq_job_id = enqueue_job(job)
        rq_job_ids.append(rq_job_id)

    logger.info(
        "Batch jobs enqueued",
        batch_id=str(batch.batch_id),
        total_jobs=len(jobs),
    )

    return rq_job_ids


def get_job_status(job_id: UUID | str) -> Job | None:
    """Get the current status of a job.

    Args:
        job_id: Job identifier.

    Returns:
        Job if found, None otherwise.
    """
    store = get_redis_store()
    return store.get_job(job_id)


def get_batch_status(batch_id: UUID | str) -> tuple[Batch | None, list[Job]]:
    """Get the current status of a batch and its jobs.

    Args:
        batch_id: Batch identifier.

    Returns:
        Tuple of (Batch, list of Jobs). Batch is None if not found.
    """
    store = get_redis_store()
    batch = store.get_batch(batch_id)

    if batch is None:
        return None, []

    jobs = store.get_batch_jobs(batch_id)
    return batch, jobs


def update_batch_progress(batch_id: UUID | str) -> None:
    """Update batch progress based on job statuses.

    Args:
        batch_id: Batch identifier.
    """
    store = get_redis_store()
    batch = store.get_batch(batch_id)

    if batch is None:
        logger.warning("Batch not found for progress update", batch_id=str(batch_id))
        return

    jobs = store.get_batch_jobs(batch_id)

    # Count job statuses
    completed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
    failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
    processing = sum(1 for j in jobs if j.status == JobStatus.PROCESSING)

    # Determine batch status
    if completed + failed == len(jobs) and len(jobs) > 0:
        if failed == 0:
            new_status = BatchStatus.COMPLETED
        elif completed == 0:
            new_status = BatchStatus.FAILED
        else:
            new_status = BatchStatus.PARTIAL
    elif processing > 0 or completed > 0:
        new_status = BatchStatus.PROCESSING
    else:
        new_status = BatchStatus.QUEUED

    store.update_batch_status(
        batch_id,
        completed_files=completed,
        failed_files=failed,
        status=new_status.value,
    )

    logger.debug(
        "Batch progress updated",
        batch_id=str(batch_id),
        status=new_status.value,
        completed=completed,
        failed=failed,
        total=len(jobs),
    )


def process_job_task(job_id: str) -> dict[str, str]:
    """RQ task to process a job.

    This function is called by RQ workers. It loads the job,
    simulates processing (for now), and updates the status.

    Args:
        job_id: Job identifier.

    Returns:
        Result dictionary with status.
    """
    store = get_redis_store()
    job = store.get_job(job_id)

    if job is None:
        logger.error("Job not found for processing", job_id=job_id)
        return {"status": "error", "error": "Job not found"}

    logger.info(
        "Processing job",
        job_id=job_id,
        batch_id=str(job.batch_id),
        filename=job.filename,
        pipeline=job.routed_to.value,
    )

    # Mark job as processing
    store.update_job_status(
        job_id,
        status=JobStatus.PROCESSING.value,
        started_at=datetime.now(tz=UTC).isoformat(),
    )

    # Update batch progress
    update_batch_progress(job.batch_id)

    # TODO: Actually call the pipeline adapter here (Sprint 1.15)
    # For now, we just simulate success
    # In production, this would:
    # 1. Call the appropriate PipelineAdapter based on job.routed_to
    # 2. Poll for completion
    # 3. Handle retries on failure

    # Mark job as completed
    store.update_job_status(
        job_id,
        status=JobStatus.COMPLETED.value,
        completed_at=datetime.now(tz=UTC).isoformat(),
    )

    # Update batch progress
    update_batch_progress(job.batch_id)

    logger.info(
        "Job completed",
        job_id=job_id,
        batch_id=str(job.batch_id),
    )

    return {"status": "completed", "job_id": job_id}
