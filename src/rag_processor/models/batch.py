"""Batch model for file upload batches.

A batch represents a group of files uploaded together by a user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BatchStatus(str, Enum):
    """Status of a batch of uploaded files.

    Attributes:
        QUEUED: Batch is queued for processing.
        PROCESSING: At least one job is being processed.
        COMPLETED: All jobs completed successfully.
        PARTIAL: Some jobs completed, some failed.
        FAILED: All jobs failed.
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class Batch(BaseModel):
    """A batch of files uploaded together.

    Attributes:
        batch_id: Unique identifier for the batch.
        created_by_email: Email of the user who created the batch.
        created_by_user_id: User ID of the creator.
        status: Current status of the batch.
        total_files: Total number of files in the batch.
        completed_files: Number of successfully completed files.
        failed_files: Number of failed files.
        target_vector_store: Target vector store for handoff.
        created_at: When the batch was created.
        updated_at: When the batch was last updated.
    """

    batch_id: UUID = Field(default_factory=uuid4, description="Unique batch identifier")
    created_by_email: str = Field(..., description="Email of the batch creator")
    created_by_user_id: str | None = Field(None, description="User ID of the creator")
    status: BatchStatus = Field(
        default=BatchStatus.QUEUED, description="Batch processing status"
    )
    total_files: int = Field(default=0, ge=0, description="Total files in batch")
    completed_files: int = Field(default=0, ge=0, description="Completed files count")
    failed_files: int = Field(default=0, ge=0, description="Failed files count")
    target_vector_store: str | None = Field(
        None, description="Target vector store for handoff"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Batch creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Last update timestamp",
    )

    def update_status(self) -> None:
        """Update batch status based on job counts.

        Calculates the appropriate status based on completed and failed counts.
        """
        self.updated_at = datetime.now(tz=timezone.utc)

        if self.completed_files + self.failed_files < self.total_files:
            self.status = BatchStatus.PROCESSING
        elif self.failed_files == 0:
            self.status = BatchStatus.COMPLETED
        elif self.completed_files == 0:
            self.status = BatchStatus.FAILED
        else:
            self.status = BatchStatus.PARTIAL

    def to_redis_dict(self) -> dict[str, str]:
        """Convert batch to Redis hash format.

        Returns:
            Dictionary suitable for Redis HSET.
        """
        return {
            "batch_id": str(self.batch_id),
            "created_by_email": self.created_by_email,
            "created_by_user_id": self.created_by_user_id or "",
            "status": self.status.value,
            "total_files": str(self.total_files),
            "completed_files": str(self.completed_files),
            "failed_files": str(self.failed_files),
            "target_vector_store": self.target_vector_store or "",
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, str]) -> Batch:
        """Create Batch from Redis hash data.

        Args:
            data: Dictionary from Redis HGETALL.

        Returns:
            Batch instance.
        """
        return cls(
            batch_id=UUID(data["batch_id"]),
            created_by_email=data["created_by_email"],
            created_by_user_id=data["created_by_user_id"] or None,
            status=BatchStatus(data["status"]),
            total_files=int(data["total_files"]),
            completed_files=int(data["completed_files"]),
            failed_files=int(data["failed_files"]),
            target_vector_store=data["target_vector_store"] or None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
