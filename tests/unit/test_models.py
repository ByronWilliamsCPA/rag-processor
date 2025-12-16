"""Tests for Batch and Job models."""

from datetime import UTC, datetime, timezone
from uuid import UUID

from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import (
    FileClassification,
    Job,
    JobStatus,
    Pipeline,
    Priority,
)


class TestBatchModel:
    """Tests for Batch model."""

    def test_batch_creation_with_defaults(self):
        """Test creating a batch with minimal required fields."""
        batch = Batch(created_by_email="test@example.com")

        assert batch.created_by_email == "test@example.com"
        assert batch.created_by_user_id is None
        assert batch.status == BatchStatus.QUEUED
        assert batch.total_files == 0
        assert batch.completed_files == 0
        assert batch.failed_files == 0
        assert batch.target_vector_store is None
        assert isinstance(batch.batch_id, UUID)
        assert isinstance(batch.created_at, datetime)
        assert isinstance(batch.updated_at, datetime)

    def test_batch_creation_with_all_fields(self):
        """Test creating a batch with all fields."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
            target_vector_store="qdrant-prod",
            total_files=5,
        )

        assert batch.created_by_email == "test@example.com"
        assert batch.created_by_user_id == "user-123"
        assert batch.target_vector_store == "qdrant-prod"
        assert batch.total_files == 5

    def test_batch_update_status_processing(self):
        """Test status update when processing is incomplete."""
        batch = Batch(
            created_by_email="test@example.com",
            total_files=3,
            completed_files=1,
            failed_files=0,
        )

        batch.update_status()

        assert batch.status == BatchStatus.PROCESSING

    def test_batch_update_status_completed(self):
        """Test status update when all files complete successfully."""
        batch = Batch(
            created_by_email="test@example.com",
            total_files=3,
            completed_files=3,
            failed_files=0,
        )

        batch.update_status()

        assert batch.status == BatchStatus.COMPLETED

    def test_batch_update_status_failed(self):
        """Test status update when all files fail."""
        batch = Batch(
            created_by_email="test@example.com",
            total_files=3,
            completed_files=0,
            failed_files=3,
        )

        batch.update_status()

        assert batch.status == BatchStatus.FAILED

    def test_batch_update_status_partial(self):
        """Test status update when some files complete and some fail."""
        batch = Batch(
            created_by_email="test@example.com",
            total_files=3,
            completed_files=2,
            failed_files=1,
        )

        batch.update_status()

        assert batch.status == BatchStatus.PARTIAL

    def test_batch_to_redis_dict(self):
        """Test conversion to Redis hash format."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
        )

        redis_dict = batch.to_redis_dict()

        assert redis_dict["created_by_email"] == "test@example.com"
        assert redis_dict["created_by_user_id"] == "user-123"
        assert redis_dict["status"] == "queued"
        assert redis_dict["total_files"] == "0"

    def test_batch_from_redis_dict(self):
        """Test creation from Redis hash data."""
        now = datetime.now(tz=UTC)
        data = {
            "batch_id": "550e8400-e29b-41d4-a716-446655440000",
            "created_by_email": "test@example.com",
            "created_by_user_id": "user-123",
            "status": "processing",
            "total_files": "3",
            "completed_files": "1",
            "failed_files": "0",
            "target_vector_store": "qdrant",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        batch = Batch.from_redis_dict(data)

        assert str(batch.batch_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert batch.created_by_email == "test@example.com"
        assert batch.status == BatchStatus.PROCESSING
        assert batch.total_files == 3


class TestJobModel:
    """Tests for Job model."""

    def test_job_creation_with_required_fields(self):
        """Test creating a job with required fields only."""
        batch_id = UUID("550e8400-e29b-41d4-a716-446655440000")

        job = Job(
            batch_id=batch_id,
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )

        assert job.batch_id == batch_id
        assert job.filename == "test.pdf"
        assert job.file_path == "/data/uploads/test.pdf"
        assert job.file_type == "application/pdf"
        assert job.file_size_bytes == 1024
        assert job.status == JobStatus.QUEUED
        assert job.priority == Priority.NORMAL
        assert job.classification == FileClassification.UNKNOWN
        assert job.routed_to == Pipeline.NONE
        assert job.error_message is None
        assert job.retry_count == 0
        assert job.max_retries == 3

    def test_job_mark_processing(self):
        """Test marking job as processing."""
        job = Job(
            batch_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )

        job.mark_processing()

        assert job.status == JobStatus.PROCESSING
        assert job.started_at is not None

    def test_job_mark_completed(self):
        """Test marking job as completed."""
        job = Job(
            batch_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )

        job.mark_completed()

        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None

    def test_job_mark_failed(self):
        """Test marking job as failed."""
        job = Job(
            batch_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )

        job.mark_failed("Connection timeout")

        assert job.status == JobStatus.FAILED
        assert job.error_message == "Connection timeout"
        assert job.completed_at is not None

    def test_job_can_retry(self):
        """Test retry eligibility check."""
        job = Job(
            batch_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )

        assert job.can_retry() is True

        job.retry_count = 3
        assert job.can_retry() is False

    def test_job_to_redis_dict(self):
        """Test conversion to Redis hash format."""
        job = Job(
            batch_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
            priority=Priority.HIGH,
            classification=FileClassification.BORN_DIGITAL_PDF,
            routed_to=Pipeline.DOC_PROCESSING,
        )

        redis_dict = job.to_redis_dict()

        assert redis_dict["filename"] == "test.pdf"
        assert redis_dict["file_type"] == "application/pdf"
        assert redis_dict["priority"] == "high"
        assert redis_dict["classification"] == "born_digital_pdf"
        assert redis_dict["routed_to"] == "doc_processing"
        assert redis_dict["status"] == "queued"

    def test_job_from_redis_dict(self):
        """Test creation from Redis hash data."""
        now = datetime.now(tz=UTC)
        data = {
            "job_id": "12345678-1234-1234-1234-123456789012",
            "batch_id": "550e8400-e29b-41d4-a716-446655440000",
            "filename": "test.pdf",
            "file_path": "/data/uploads/test.pdf",
            "file_type": "application/pdf",
            "file_size_bytes": "1024",
            "classification": "scanned_pdf",
            "routed_to": "ocr",
            "status": "processing",
            "priority": "high",
            "error_message": "",
            "retry_count": "1",
            "max_retries": "3",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "started_at": now.isoformat(),
            "completed_at": "",
        }

        job = Job.from_redis_dict(data)

        assert job.filename == "test.pdf"
        assert job.classification == FileClassification.SCANNED_PDF
        assert job.routed_to == Pipeline.OCR
        assert job.status == JobStatus.PROCESSING
        assert job.priority == Priority.HIGH
        assert job.retry_count == 1


class TestEnums:
    """Tests for enum values."""

    def test_batch_status_values(self):
        """Test BatchStatus enum values."""
        assert BatchStatus.QUEUED == "queued"
        assert BatchStatus.PROCESSING == "processing"
        assert BatchStatus.COMPLETED == "completed"
        assert BatchStatus.PARTIAL == "partial"
        assert BatchStatus.FAILED == "failed"

    def test_job_status_values(self):
        """Test JobStatus enum values."""
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"

    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.HIGH == "high"
        assert Priority.NORMAL == "normal"
        assert Priority.LOW == "low"

    def test_file_classification_values(self):
        """Test FileClassification enum values."""
        assert FileClassification.SCANNED_PDF == "scanned_pdf"
        assert FileClassification.BORN_DIGITAL_PDF == "born_digital_pdf"
        assert FileClassification.IMAGE == "image"
        assert FileClassification.AUDIO == "audio"
        assert FileClassification.VIDEO == "video"
        assert FileClassification.DOCUMENT == "document"
        assert FileClassification.UNKNOWN == "unknown"

    def test_pipeline_values(self):
        """Test Pipeline enum values."""
        assert Pipeline.OCR == "ocr"
        assert Pipeline.TRANSCRIPTION == "transcription"
        assert Pipeline.DOC_PROCESSING == "doc_processing"
        assert Pipeline.FUSION == "fusion"
        assert Pipeline.NONE == "none"
