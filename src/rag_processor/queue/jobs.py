"""Job submission and status tracking.

Functions for enqueuing jobs and checking their status.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID  # noqa: TC003 - Used at runtime in function signatures

from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import Job, JobStatus
from rag_processor.queue.client import get_queue_client
from rag_processor.queue.redis_store import get_redis_store
from rag_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from rag_processor.queue.redis_store import RedisStore

UTC = timezone.utc  # noqa: UP017

logger = get_logger(__name__)

# Default per-job processing timeout (seconds) applied when enqueuing to RQ.
JOB_TIMEOUT_SECONDS = 600


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
        job_timeout=JOB_TIMEOUT_SECONDS,
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
    """Submit a batch of jobs to the queue with all-or-nothing semantics.

    Saves the batch and each job to Redis and enqueues them to RQ, tracking the
    RQ jobs as they are created. If any enqueue fails partway through, every
    already-enqueued RQ job is cancelled and the batch's Redis state is removed
    before re-raising, so a caller never observes a partially-enqueued batch
    (which would otherwise leave orphaned RQ jobs whose metadata was deleted).

    Args:
        batch: Parent batch.
        jobs: Jobs to enqueue.

    Returns:
        List of RQ job IDs.

    Raises:
        Exception: Re-raises any enqueue failure after rolling back.
    """
    store = get_redis_store()
    client = get_queue_client()

    # Save batch first
    store.save_batch(batch)

    enqueued_rq_jobs: list[Any] = []
    try:
        for job in jobs:
            # Persist job metadata, then enqueue. Tracking the RQ job lets us
            # cancel it during rollback if a later job fails to enqueue.
            store.save_job(job)
            rq_job = client.enqueue(
                process_job_task,
                str(job.job_id),
                priority=job.priority,
                job_timeout=JOB_TIMEOUT_SECONDS,
            )
            enqueued_rq_jobs.append(rq_job)
    except Exception:
        logger.exception(
            "Failed to enqueue batch; rolling back",
            batch_id=str(batch.batch_id),
            enqueued=len(enqueued_rq_jobs),
        )
        _rollback_enqueued_batch(store, batch, enqueued_rq_jobs)
        raise

    logger.info(
        "Batch jobs enqueued",
        batch_id=str(batch.batch_id),
        total_jobs=len(jobs),
    )

    return [rq_job.id for rq_job in enqueued_rq_jobs]


def _rollback_enqueued_batch(
    store: RedisStore,
    batch: Batch,
    enqueued_rq_jobs: list[Any],
) -> None:
    """Cancel already-enqueued RQ jobs and delete the batch's Redis state.

    Best-effort: individual cancellation failures are logged but do not prevent
    the remaining cleanup, since this runs while handling an enqueue failure.

    Note: ``rq_job.cancel()`` only removes a job that is still *queued*; it
    cannot stop one a worker has already started. A worker mid-run could write
    job status after ``delete_batch`` here, recreating an orphaned ``job:{id}``
    hash. ``process_job_task`` guards against this by bailing if its parent
    batch has disappeared, which closes all but a narrow TOCTOU window.

    Args:
        store: Redis store used to delete the batch and its jobs.
        batch: The batch being rolled back.
        enqueued_rq_jobs: RQ jobs that were successfully enqueued before failure.
    """
    for rq_job in enqueued_rq_jobs:
        try:
            rq_job.cancel()
            rq_job.delete()
        except Exception:  # noqa: BLE001 - best-effort cleanup during rollback
            logger.warning(
                "Failed to cancel enqueued RQ job during rollback",
                rq_job_id=getattr(rq_job, "id", None),
            )
    store.delete_batch(batch.batch_id)


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


async def get_job_status_async(job_id: UUID | str) -> Job | None:
    """Async, non-blocking wrapper around :func:`get_job_status`.

    The underlying store uses a synchronous Redis client (shared with the RQ
    worker), so the blocking call is offloaded to a worker thread to avoid
    stalling the event loop in async HTTP/WebSocket handlers.

    Args:
        job_id: Job identifier.

    Returns:
        Job if found, None otherwise.
    """
    return await asyncio.to_thread(get_job_status, job_id)


async def get_batch_status_async(
    batch_id: UUID | str,
) -> tuple[Batch | None, list[Job]]:
    """Async, non-blocking wrapper around :func:`get_batch_status`.

    Offloads the synchronous Redis reads to a worker thread so async handlers
    do not block the event loop.

    Args:
        batch_id: Batch identifier.

    Returns:
        Tuple of (Batch, list of Jobs). Batch is None if not found.
    """
    return await asyncio.to_thread(get_batch_status, batch_id)


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

    # Guard against the enqueue-rollback orphan race: if the parent batch has
    # been deleted (e.g. _rollback_enqueued_batch ran after this job was already
    # picked up by a worker), do not write any job status — doing so would
    # recreate an orphaned job:{id} hash with no parent batch. Bail cleanly.
    # A narrow TOCTOU window remains between this check and the writes below;
    # it is acceptable given enqueue is gated behind enqueue_enabled and the
    # rollback path is itself an error path.
    # FIXME(reconciliation): there is currently no automated reconciler for jobs
    # orphaned by this race or left in PROCESSING when failure recording fails
    # (see the best-effort handler below). Recovery is manual until a periodic
    # sweep (e.g. reconcile_orphaned_jobs) is added alongside the rollback path.
    if store.get_batch(job.batch_id) is None:
        logger.warning(
            "Parent batch missing; skipping job to avoid orphan",
            job_id=job_id,
            batch_id=str(job.batch_id),
        )
        return {
            "status": "skipped",
            "job_id": job_id,
            "error": "Parent batch not found",
        }

    # Mark job as processing
    store.update_job_status(
        job_id,
        status=JobStatus.PROCESSING.value,
        started_at=datetime.now(tz=UTC).isoformat(),
    )

    # Update batch progress
    update_batch_progress(job.batch_id)

    try:
        # TODO: Actually call the pipeline adapter here (Sprint 1.15)
        # For now, we just simulate success
        # In production, this would:
        # 1. Call the appropriate PipelineAdapter based on job.routed_to
        # 2. Poll for completion
        _run_pipeline(job)
    except Exception as exc:
        # Worker boundary: any pipeline failure must be recorded against the
        # job and reflected in the batch rather than crashing the worker and
        # leaving the batch stuck in PROCESSING forever.
        logger.exception(
            "Job processing failed",
            job_id=job_id,
            batch_id=str(job.batch_id),
        )
        # Best-effort failure recording. If the pipeline failed because Redis
        # itself is down (a likely correlated cause), these writes can raise
        # too; swallow so the worker exits cleanly. RQ will mark the task
        # failed, and a later reconciliation/retry can recover the stuck job —
        # better than crashing the worker here.
        try:
            store.update_job_status(
                job_id,
                status=JobStatus.FAILED.value,
                error_message=str(exc),
                completed_at=datetime.now(tz=UTC).isoformat(),
            )
            update_batch_progress(job.batch_id)
        except Exception:
            logger.exception(
                "Failed to record job failure (Redis may be unavailable)",
                job_id=job_id,
                batch_id=str(job.batch_id),
            )
        return {"status": "failed", "job_id": job_id, "error": str(exc)}

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


def _run_pipeline(job: Job) -> None:
    """Execute the processing pipeline for a job.

    Placeholder for the pipeline adapter call (Sprint 1.15). Isolated into its
    own function so the failure-handling boundary in ``process_job_task`` has a
    single, mockable seam and real pipeline errors are captured per-job.

    Args:
        job: The job to process.
    """
    # Intentionally a no-op until the pipeline adapter lands. The job is logged
    # so the seam is observable and the argument is meaningfully used.
    logger.debug(
        "Running pipeline (no-op placeholder)",
        job_id=str(job.job_id),
        pipeline=job.routed_to.value,
    )
