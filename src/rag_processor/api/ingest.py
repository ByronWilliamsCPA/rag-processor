"""File ingestion API endpoints.

Provides endpoints for uploading files for RAG pipeline processing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated
from uuid import UUID  # noqa: TC003 - Used at runtime by Pydantic models

import aiofiles
import magic
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from rag_processor.auth.dependencies import get_current_user
from rag_processor.auth.models import (
    CloudflareUser,  # noqa: TC001 - Used at runtime by FastAPI
)
from rag_processor.core.config import settings
from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import (
    FileClassification,
    Job,
    JobStatus,
    Pipeline,
    Priority,
)
from rag_processor.routing import FileRouter
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Compile regex for filename sanitization
SAFE_FILENAME_PATTERN = re.compile(r"[^\w\s\-.]")

# File router for classification and pipeline routing
file_router = FileRouter()


class JobResponse(BaseModel):
    """Response model for a job.

    Attributes:
        job_id: Unique job identifier.
        filename: Original filename.
        file_type: MIME type of the file.
        file_size_bytes: Size in bytes.
        status: Current job status.
        classification: File classification for routing.
        pipeline: Target processing pipeline.
    """

    job_id: UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: JobStatus
    classification: FileClassification
    pipeline: Pipeline


class IngestResponse(BaseModel):
    """Response model for file ingestion.

    Attributes:
        batch_id: Unique batch identifier.
        status: Batch status.
        total_files: Total number of files uploaded.
        jobs: List of created jobs.
        message: Human-readable message.
    """

    batch_id: UUID
    status: BatchStatus
    total_files: int
    jobs: list[JobResponse]
    message: str = Field(default="Files uploaded successfully")


class FileValidationError(BaseModel):
    """Error details for file validation failures.

    Attributes:
        filename: The problematic filename.
        error: Description of the validation error.
    """

    filename: str
    error: str


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other issues.

    Args:
        filename: Original filename from upload.

    Returns:
        Sanitized filename safe for filesystem use.
    """
    # Remove any path components
    filename = Path(filename).name

    # Replace unsafe characters
    filename = SAFE_FILENAME_PATTERN.sub("_", filename)

    # Limit length
    max_length = 200
    if len(filename) > max_length:
        name, ext = Path(filename).stem, Path(filename).suffix
        filename = name[: max_length - len(ext)] + ext

    # Ensure not empty
    if not filename or filename in (".", ".."):
        filename = "unnamed_file"

    return filename


def detect_mime_type(content: bytes) -> str:
    """Detect MIME type using magic bytes.

    Args:
        content: File content bytes.

    Returns:
        Detected MIME type string.
    """
    return magic.from_buffer(content, mime=True)


async def validate_file(
    file: UploadFile,
) -> tuple[bytes, str, list[FileValidationError]]:
    """Validate an uploaded file.

    Args:
        file: The uploaded file to validate.

    Returns:
        Tuple of (content, mime_type, errors).
    """
    errors: list[FileValidationError] = []
    filename = file.filename or "unknown"

    # Read content
    content = await file.read()
    await file.seek(0)  # Reset for potential re-read

    # Check file size
    if len(content) > settings.max_file_size_bytes:
        errors.append(
            FileValidationError(
                filename=filename,
                error=f"File exceeds maximum size of {settings.max_file_size_mb}MB",
            )
        )
        return content, "", errors

    # Check empty file
    if len(content) == 0:
        errors.append(
            FileValidationError(
                filename=filename,
                error="File is empty",
            )
        )
        return content, "", errors

    # Detect MIME type
    mime_type = detect_mime_type(content)

    # Check MIME type
    if mime_type not in settings.allowed_mime_types:
        errors.append(
            FileValidationError(
                filename=filename,
                error=f"File type '{mime_type}' is not allowed",
            )
        )

    return content, mime_type, errors


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload files for processing",
    description="Upload one or more files for RAG pipeline processing.",
    responses={
        400: {"description": "Invalid file(s) provided"},
        413: {"description": "File(s) too large"},
    },
)
async def ingest_files(
    files: Annotated[
        list[UploadFile],
        File(description="Files to upload for processing"),
    ],
    priority: Annotated[
        Priority,
        Form(description="Processing priority"),
    ] = Priority.NORMAL,
    target_vector_store: Annotated[
        str | None,
        Form(description="Target vector store for handoff"),
    ] = None,
    user: CloudflareUser = Depends(get_current_user),
) -> IngestResponse:
    """Upload files for RAG pipeline processing.

    Accepts multiple files via multipart/form-data. Each file is validated
    for size and type, then saved to the upload directory.

    Args:
        files: List of files to upload.
        priority: Processing priority (high, normal, low).
        target_vector_store: Optional target vector store.
        user: Authenticated user from Cloudflare Access.

    Returns:
        IngestResponse with batch and job information.

    Raises:
        HTTPException: If no valid files provided or validation fails.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    # Create batch
    batch = Batch(
        created_by_email=user.email,
        created_by_user_id=user.user_id,
        target_vector_store=target_vector_store,
        total_files=len(files),
    )

    # Create upload directory
    batch_dir = Path(settings.upload_dir) / str(batch.batch_id)
    batch_dir.mkdir(parents=True, exist_ok=True)

    # Process and validate files
    jobs: list[Job] = []
    validation_errors: list[FileValidationError] = []

    for file in files:
        original_filename = file.filename or "unknown"
        content, mime_type, errors = await validate_file(file)

        if errors:
            validation_errors.extend(errors)
            continue

        # Sanitize filename and save
        safe_filename = sanitize_filename(original_filename)
        file_path = batch_dir / safe_filename

        # Handle duplicate filenames
        counter = 1
        while file_path.exists():
            name, ext = Path(safe_filename).stem, Path(safe_filename).suffix
            file_path = batch_dir / f"{name}_{counter}{ext}"
            counter += 1

        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Route file to determine classification and pipeline
        routing_result = file_router.route_from_bytes(content, original_filename)

        # Create job
        job = Job(
            batch_id=batch.batch_id,
            filename=original_filename,
            file_path=str(file_path),
            file_type=mime_type,
            file_size_bytes=len(content),
            priority=priority,
            classification=routing_result.classification,
            routed_to=routing_result.pipeline,
        )
        jobs.append(job)

        logger.info(
            "File uploaded",
            job_id=str(job.job_id),
            batch_id=str(batch.batch_id),
            filename=original_filename,
            file_type=mime_type,
            file_size=len(content),
            classification=routing_result.classification.value,
            pipeline=routing_result.pipeline.value,
            user_email=user.email,
        )

    # Check if any files were valid
    if not jobs:
        # Clean up batch directory
        batch_dir.rmdir()

        error_messages = [f"{e.filename}: {e.error}" for e in validation_errors]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "No valid files uploaded", "errors": error_messages},
        )

    # Update batch with actual valid file count
    batch.total_files = len(jobs)

    # TODO: Store batch and jobs in Redis (Sprint 1.14)
    # TODO: Enqueue jobs in RQ (Sprint 1.14)

    logger.info(
        "Batch created",
        batch_id=str(batch.batch_id),
        total_files=batch.total_files,
        user_email=user.email,
        validation_errors=len(validation_errors),
    )

    # Build response
    job_responses = [
        JobResponse(
            job_id=job.job_id,
            filename=job.filename,
            file_type=job.file_type,
            file_size_bytes=job.file_size_bytes,
            status=job.status,
            classification=job.classification,
            pipeline=job.routed_to,
        )
        for job in jobs
    ]

    message = f"Successfully uploaded {len(jobs)} file(s)"
    if validation_errors:
        message += f" ({len(validation_errors)} file(s) rejected)"

    return IngestResponse(
        batch_id=batch.batch_id,
        status=batch.status,
        total_files=batch.total_files,
        jobs=job_responses,
        message=message,
    )


@router.get(
    "/health",
    summary="Check ingest endpoint health",
    description="Verify that the ingest endpoint is ready to accept uploads.",
)
async def ingest_health() -> dict[str, str]:
    """Check ingest endpoint health.

    Returns:
        Health status dictionary.

    Raises:
        HTTPException: If upload directory is not writable.
    """
    # Check upload directory is writable
    upload_dir = Path(settings.upload_dir)

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        test_file = upload_dir / ".health_check"
        test_file.touch()
        test_file.unlink()
        return {"status": "healthy", "upload_dir": str(upload_dir)}
    except (OSError, PermissionError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Upload directory not writable: {e}",
        ) from e
