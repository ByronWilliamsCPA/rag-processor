"""Batch and job status API endpoints.

Provides endpoints for querying batch and job status.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from rag_processor.auth.dependencies import batch_is_owned_by, get_current_user
from rag_processor.auth.models import CloudflareUser
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
    summary="Get batch status",
    description="Get the status and details of a batch and its jobs.",
    responses={
        404: {"description": "Batch not found"},
    },
)
async def get_batch(
    batch_id: UUID,
    user: Annotated[CloudflareUser, Depends(get_current_user)],
) -> BatchDetailResponse:
    """Get batch status and job list.

    Args:
        batch_id: Batch identifier.
        user: Authenticated user from Cloudflare Access.

    Returns:
        BatchDetailResponse with batch and job details.

    Raises:
        HTTPException: If batch not found or caller does not own it.
    """
    batch, jobs = get_batch_status(batch_id)

    # Return 404 (not 403) for non-owners to avoid leaking batch existence.
    if batch is None or not batch_is_owned_by(
        batch, requester_user_id=user.user_id, requester_email=user.email
    ):
        if batch is not None:
            # Minimal log context: opaque IDs only. Don't include the requester
            # email or the owner's email/identity (attacker-controlled probes
            # could otherwise extract owner info from logs).
            logger.warning(
                "Unauthorized batch access attempt",
                batch_id=str(batch_id),
                requester_user_id=user.user_id,
            )
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
    summary="Get job status",
    description="Get the status and details of a specific job.",
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job(
    job_id: UUID,
    user: Annotated[CloudflareUser, Depends(get_current_user)],
) -> JobDetailResponse:
    """Get job status and details.

    Args:
        job_id: Job identifier.
        user: Authenticated user from Cloudflare Access.

    Returns:
        JobDetailResponse with job details.

    Raises:
        HTTPException: If job not found or caller does not own its batch.
    """
    job = get_job_status(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # A job inherits ownership from its parent batch.
    batch, _ = get_batch_status(job.batch_id)
    if batch is None or not batch_is_owned_by(
        batch, requester_user_id=user.user_id, requester_email=user.email
    ):
        if batch is not None:
            # Minimal log context: opaque IDs only. See note in get_batch.
            logger.warning(
                "Unauthorized job access attempt",
                job_id=str(job_id),
                batch_id=str(job.batch_id),
                requester_user_id=user.user_id,
            )
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
