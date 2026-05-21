"""Batch and job status API endpoints.

Provides endpoints for querying batch and job status.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from rag_processor.models.batch import (
    BatchStatus,
)
from rag_processor.models.job import (
    FileClassification,
    JobStatus,
    Pipeline,
)
from rag_processor.queue.jobs import get_batch_status, get_job_status
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


class JobDetailResponse(BaseModel):
    """Response model for job details.

    Attributes:
        job_id: Unique job identifier.
        batch_id: Parent batch identifier.
        filename: Original filename.
        file_type: MIME type of the file.
        file_size_bytes: Size in bytes.
        classification: File classification.
        pipeline: Target processing pipeline.
        status: Current job status.
        error_message: Error message if failed.
        retry_count: Number of retry attempts.
        created_at: When the job was created.
        started_at: When processing started.
        completed_at: When processing completed.
    """

    job_id: UUID
    batch_id: UUID
    filename: str
    file_type: str
    file_size_bytes: int
    classification: FileClassification
    pipeline: Pipeline
    status: JobStatus
    error_message: str | None = None
    retry_count: int = 0
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class BatchDetailResponse(BaseModel):
    """Response model for batch details.

    Attributes:
        batch_id: Unique batch identifier.
        created_by_email: Email of the user who created the batch.
        status: Current batch status.
        total_files: Total number of files in the batch.
        completed_files: Number of completed files.
        failed_files: Number of failed files.
        target_vector_store: Target vector store for handoff.
        created_at: When the batch was created.
        jobs: List of jobs in the batch.
    """

    batch_id: UUID
    created_by_email: str
    status: BatchStatus
    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    target_vector_store: str | None = None
    created_at: str
    jobs: list[JobDetailResponse] = Field(default_factory=list)


@router.get(
    "/{batch_id}",
    response_model=BatchDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get batch status",
    description=(
        "Get the status and details of a batch including all of its jobs, "
        "file metadata, and timestamps. Requires Cloudflare Access "
        "authentication."
    ),
    responses={
        404: {"description": "Batch not found"},
    },
)
async def get_batch(batch_id: UUID) -> BatchDetailResponse:
    """Get batch status and job list.

    Returns the current status of a batch and a detail record for every
    job that belongs to it, including classification, pipeline, retry
    count, and timestamps.

    Authentication: Requires a valid Cloudflare Access JWT.

    Args:
        batch_id: Batch identifier (UUID).

    Returns:
        BatchDetailResponse with batch metadata and the list of jobs.

    Raises:
        HTTPException: 404 if no batch with the given ID exists.
    """
    batch, jobs = get_batch_status(batch_id)

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )

    # Convert jobs to response format
    job_responses = [
        JobDetailResponse(
            job_id=job.job_id,
            batch_id=job.batch_id,
            filename=job.filename,
            file_type=job.file_type,
            file_size_bytes=job.file_size_bytes,
            classification=job.classification,
            pipeline=job.routed_to,
            status=job.status,
            error_message=job.error_message,
            retry_count=job.retry_count,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
        )
        for job in jobs
    ]

    return BatchDetailResponse(
        batch_id=batch.batch_id,
        created_by_email=batch.created_by_email,
        status=batch.status,
        total_files=batch.total_files,
        completed_files=batch.completed_files,
        failed_files=batch.failed_files,
        target_vector_store=batch.target_vector_store,
        created_at=batch.created_at.isoformat(),
        jobs=job_responses,
    )


@router.get(
    "/job/{job_id}",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job status",
    description=(
        "Get the status and details of a specific job, including pipeline "
        "routing, error message, retry count, and timestamps. Requires "
        "Cloudflare Access authentication."
    ),
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job(job_id: UUID) -> JobDetailResponse:
    """Get job status and details.

    Returns the current state of a single processing job, including the
    target pipeline, file metadata, retry information, and lifecycle
    timestamps.

    Authentication: Requires a valid Cloudflare Access JWT.

    Args:
        job_id: Job identifier (UUID).

    Returns:
        JobDetailResponse with job metadata and processing state.

    Raises:
        HTTPException: 404 if no job with the given ID exists.
    """
    job = get_job_status(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return JobDetailResponse(
        job_id=job.job_id,
        batch_id=job.batch_id,
        filename=job.filename,
        file_type=job.file_type,
        file_size_bytes=job.file_size_bytes,
        classification=job.classification,
        pipeline=job.routed_to,
        status=job.status,
        error_message=job.error_message,
        retry_count=job.retry_count,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
