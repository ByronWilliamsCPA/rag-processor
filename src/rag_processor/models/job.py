"""Job model for individual file processing jobs.

A job represents a single file being processed through a pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _parse_iso_datetime(value: str) -> datetime:
    """Parse ISO format datetime string with Python 3.10 compatibility.

    Python 3.10's fromisoformat() doesn't support 'Z' suffix for UTC.
    This function handles both 'Z' suffix and '+00:00' format.

    Args:
        value: ISO format datetime string.

    Returns:
        Parsed datetime object.
    """
    # Replace Z suffix with +00:00 for Python 3.10 compatibility
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class JobStatus(str, Enum):
    """Status of an individual job.

    Attributes:
        QUEUED: Job is queued for processing.
        PROCESSING: Job is currently being processed.
        COMPLETED: Job completed successfully.
        FAILED: Job failed after all retries.
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Priority(str, Enum):
    """Job priority levels.

    Attributes:
        HIGH: High priority, processed first.
        NORMAL: Normal priority.
        LOW: Low priority, processed last.
    """

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class FileClassification(str, Enum):
    """Classification of file types for routing.

    Attributes:
        SCANNED_PDF: PDF with image-based content (needs OCR).
        BORN_DIGITAL_PDF: PDF with extractable text.
        IMAGE: Image file (PNG, JPEG, etc.).
        AUDIO: Audio file (MP3, WAV, etc.).
        VIDEO: Video file (MP4, etc.).
        DOCUMENT: Office document (DOCX, XLSX, etc.).
        UNKNOWN: Unclassified file type.
    """

    SCANNED_PDF = "scanned_pdf"
    BORN_DIGITAL_PDF = "born_digital_pdf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class Pipeline(str, Enum):
    """Target processing pipelines.

    Attributes:
        OCR: Optical character recognition for scanned documents.
        TRANSCRIPTION: Audio/video transcription.
        DOC_PROCESSING: Document text extraction.
        FUSION: Multi-modal fusion pipeline.
        NONE: No pipeline (unsupported file).
    """

    OCR = "ocr"
    TRANSCRIPTION = "transcription"
    DOC_PROCESSING = "doc_processing"
    FUSION = "fusion"
    NONE = "none"


class Job(BaseModel):
    """A single file processing job.

    Attributes:
        job_id: Unique identifier for the job.
        batch_id: ID of the parent batch.
        filename: Original filename.
        file_path: Path to stored file.
        file_type: MIME type of the file.
        file_size_bytes: Size of the file in bytes.
        classification: File classification for routing.
        routed_to: Target pipeline for processing.
        status: Current job status.
        priority: Job priority level.
        error_message: Error message if failed.
        retry_count: Number of retry attempts.
        max_retries: Maximum retry attempts allowed.
        created_at: When the job was created.
        updated_at: When the job was last updated.
        started_at: When processing started.
        completed_at: When processing completed.
    """

    job_id: UUID = Field(default_factory=uuid4, description="Unique job identifier")
    batch_id: UUID = Field(..., description="Parent batch identifier")
    filename: str = Field(..., min_length=1, description="Original filename")
    file_path: str = Field(..., description="Path to stored file")
    file_type: str = Field(..., description="MIME type of the file")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    classification: FileClassification = Field(
        default=FileClassification.UNKNOWN, description="File classification"
    )
    routed_to: Pipeline = Field(default=Pipeline.NONE, description="Target pipeline")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Job status")
    priority: Priority = Field(default=Priority.NORMAL, description="Job priority")
    error_message: str | None = Field(default=None, description="Error message if failed")
    retry_count: int = Field(default=0, ge=0, description="Current retry count")
    max_retries: int = Field(default=3, ge=0, description="Maximum retries")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Job creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Last update timestamp",
    )
    started_at: datetime | None = Field(default=None, description="Processing start time")
    completed_at: datetime | None = Field(
        default=None, description="Processing completion time"
    )

    def mark_processing(self) -> None:
        """Mark job as processing."""
        self.status = JobStatus.PROCESSING
        self.started_at = datetime.now(tz=timezone.utc)
        self.updated_at = self.started_at

    def mark_completed(self) -> None:
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now(tz=timezone.utc)
        self.updated_at = self.completed_at

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed.

        Args:
            error_message: The error message describing the failure.
        """
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(tz=timezone.utc)
        self.updated_at = self.completed_at

    def can_retry(self) -> bool:
        """Check if job can be retried.

        Returns:
            True if retry count is below max_retries.
        """
        return self.retry_count < self.max_retries

    def to_redis_dict(self) -> dict[str, str]:
        """Convert job to Redis hash format.

        Returns:
            Dictionary suitable for Redis HSET.
        """
        return {
            "job_id": str(self.job_id),
            "batch_id": str(self.batch_id),
            "filename": self.filename,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_size_bytes": str(self.file_size_bytes),
            "classification": self.classification.value,
            "routed_to": self.routed_to.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "error_message": self.error_message or "",
            "retry_count": str(self.retry_count),
            "max_retries": str(self.max_retries),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else "",
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, str]) -> Job:
        """Create Job from Redis hash data.

        Args:
            data: Dictionary from Redis HGETALL.

        Returns:
            Job instance.
        """
        return cls(
            job_id=UUID(data["job_id"]),
            batch_id=UUID(data["batch_id"]),
            filename=data["filename"],
            file_path=data["file_path"],
            file_type=data["file_type"],
            file_size_bytes=int(data["file_size_bytes"]),
            classification=FileClassification(data["classification"]),
            routed_to=Pipeline(data["routed_to"]),
            status=JobStatus(data["status"]),
            priority=Priority(data["priority"]),
            error_message=data["error_message"] or None,
            retry_count=int(data["retry_count"]),
            max_retries=int(data["max_retries"]),
            created_at=_parse_iso_datetime(data["created_at"]),
            updated_at=_parse_iso_datetime(data["updated_at"]),
            started_at=(
                _parse_iso_datetime(data["started_at"])
                if data["started_at"]
                else None
            ),
            completed_at=(
                _parse_iso_datetime(data["completed_at"])
                if data["completed_at"]
                else None
            ),
        )
