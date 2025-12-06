"""Tests for queue module.

Tests Redis store, queue client, and job operations using fakeredis.
"""

from __future__ import annotations

from uuid import uuid4

import fakeredis
from rq import Queue

from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import (
    FileClassification,
    Job,
    JobStatus,
    Pipeline,
    Priority,
)
from rag_processor.queue.client import (
    PRIORITY_QUEUE_MAP,
    QUEUE_DEFAULT,
    QUEUE_HIGH,
    QUEUE_LOW,
    QueueClient,
)
from rag_processor.queue.redis_store import (
    BATCH_JOBS_KEY_PREFIX,
    BATCH_KEY_PREFIX,
    JOB_KEY_PREFIX,
    RedisStore,
)

# =============================================================================
# RedisStore Tests
# =============================================================================


class TestRedisStore:
    """Tests for RedisStore class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.fake_redis = fakeredis.FakeRedis(decode_responses=True)
        self.store = RedisStore(redis_client=self.fake_redis)

    def test_save_and_get_batch(self) -> None:
        """Test saving and retrieving a batch."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
            total_files=3,
        )

        self.store.save_batch(batch)
        loaded = self.store.get_batch(batch.batch_id)

        assert loaded is not None
        assert loaded.batch_id == batch.batch_id
        assert loaded.created_by_email == "test@example.com"
        assert loaded.total_files == 3
        assert loaded.status == BatchStatus.QUEUED

    def test_get_batch_not_found(self) -> None:
        """Test getting a non-existent batch."""
        loaded = self.store.get_batch(uuid4())
        assert loaded is None

    def test_update_batch_status(self) -> None:
        """Test updating batch status fields."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
            total_files=5,
        )
        self.store.save_batch(batch)

        self.store.update_batch_status(
            batch.batch_id,
            completed_files=3,
            failed_files=1,
            status=BatchStatus.PROCESSING.value,
        )

        loaded = self.store.get_batch(batch.batch_id)
        assert loaded is not None
        assert loaded.completed_files == 3
        assert loaded.failed_files == 1
        assert loaded.status == BatchStatus.PROCESSING

    def test_save_and_get_job(self) -> None:
        """Test saving and retrieving a job."""
        batch_id = uuid4()
        job = Job(
            batch_id=batch_id,
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
            classification=FileClassification.BORN_DIGITAL_PDF,
            routed_to=Pipeline.DOC_PROCESSING,
        )

        self.store.save_job(job)
        loaded = self.store.get_job(job.job_id)

        assert loaded is not None
        assert loaded.job_id == job.job_id
        assert loaded.batch_id == batch_id
        assert loaded.filename == "test.pdf"
        assert loaded.classification == FileClassification.BORN_DIGITAL_PDF
        assert loaded.routed_to == Pipeline.DOC_PROCESSING

    def test_get_job_not_found(self) -> None:
        """Test getting a non-existent job."""
        loaded = self.store.get_job(uuid4())
        assert loaded is None

    def test_update_job_status(self) -> None:
        """Test updating job status fields."""
        batch_id = uuid4()
        job = Job(
            batch_id=batch_id,
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )
        self.store.save_job(job)

        self.store.update_job_status(
            job.job_id,
            status=JobStatus.PROCESSING.value,
            started_at="2024-01-01T10:00:00Z",
        )

        loaded = self.store.get_job(job.job_id)
        assert loaded is not None
        assert loaded.status == JobStatus.PROCESSING
        assert loaded.started_at is not None

    def test_update_job_status_with_error(self) -> None:
        """Test updating job status with error message."""
        batch_id = uuid4()
        job = Job(
            batch_id=batch_id,
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )
        self.store.save_job(job)

        self.store.update_job_status(
            job.job_id,
            status=JobStatus.FAILED.value,
            error_message="Pipeline timeout",
            retry_count=3,
        )

        loaded = self.store.get_job(job.job_id)
        assert loaded is not None
        assert loaded.status == JobStatus.FAILED
        assert loaded.error_message == "Pipeline timeout"
        assert loaded.retry_count == 3

    def test_get_batch_jobs(self) -> None:
        """Test getting all jobs for a batch."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
            total_files=3,
        )
        self.store.save_batch(batch)

        # Create jobs
        jobs = []
        for i in range(3):
            job = Job(
                batch_id=batch.batch_id,
                filename=f"file{i}.pdf",
                file_path=f"/data/uploads/file{i}.pdf",
                file_type="application/pdf",
                file_size_bytes=1024,
            )
            self.store.save_job(job)
            jobs.append(job)

        # Get jobs
        loaded_jobs = self.store.get_batch_jobs(batch.batch_id)
        assert len(loaded_jobs) == 3

        job_ids = {job.job_id for job in jobs}
        loaded_ids = {job.job_id for job in loaded_jobs}
        assert job_ids == loaded_ids

    def test_delete_batch(self) -> None:
        """Test deleting a batch and its jobs."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
            total_files=2,
        )
        self.store.save_batch(batch)

        # Create jobs
        job1 = Job(
            batch_id=batch.batch_id,
            filename="file1.pdf",
            file_path="/data/uploads/file1.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )
        job2 = Job(
            batch_id=batch.batch_id,
            filename="file2.pdf",
            file_path="/data/uploads/file2.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )
        self.store.save_job(job1)
        self.store.save_job(job2)

        # Delete batch
        self.store.delete_batch(batch.batch_id)

        # Verify deletion
        assert self.store.get_batch(batch.batch_id) is None
        assert self.store.get_job(job1.job_id) is None
        assert self.store.get_job(job2.job_id) is None
        assert len(self.store.get_batch_jobs(batch.batch_id)) == 0

    def test_ping(self) -> None:
        """Test Redis ping."""
        assert self.store.ping() is True

    def test_batch_key_format(self) -> None:
        """Test batch key format in Redis."""
        batch = Batch(
            created_by_email="test@example.com",
            created_by_user_id="user-123",
            total_files=1,
        )
        self.store.save_batch(batch)

        key = f"{BATCH_KEY_PREFIX}{batch.batch_id}"
        assert self.fake_redis.exists(key) == 1

    def test_job_key_format(self) -> None:
        """Test job key format in Redis."""
        batch_id = uuid4()
        job = Job(
            batch_id=batch_id,
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )
        self.store.save_job(job)

        key = f"{JOB_KEY_PREFIX}{job.job_id}"
        assert self.fake_redis.exists(key) == 1

    def test_batch_jobs_set_key_format(self) -> None:
        """Test batch jobs set key format in Redis."""
        batch_id = uuid4()
        job = Job(
            batch_id=batch_id,
            filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="application/pdf",
            file_size_bytes=1024,
        )
        self.store.save_job(job)

        key = f"{BATCH_JOBS_KEY_PREFIX}{batch_id}"
        assert self.fake_redis.exists(key) == 1
        assert str(job.job_id) in self.fake_redis.smembers(key)


# =============================================================================
# QueueClient Tests
# =============================================================================


class TestQueueClient:
    """Tests for QueueClient class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        # Note: fakeredis doesn't fully support RQ, so we test what we can
        self.fake_redis = fakeredis.FakeRedis()
        self.client = QueueClient(redis_client=self.fake_redis)

    def test_queue_creation(self) -> None:
        """Test that priority queues are created."""
        assert QUEUE_HIGH in self.client._queues
        assert QUEUE_DEFAULT in self.client._queues
        assert QUEUE_LOW in self.client._queues

    def test_get_queue_by_priority(self) -> None:
        """Test getting queue by priority."""
        high_queue = self.client.get_queue(Priority.HIGH)
        assert isinstance(high_queue, Queue)
        assert high_queue.name == QUEUE_HIGH

        normal_queue = self.client.get_queue(Priority.NORMAL)
        assert isinstance(normal_queue, Queue)
        assert normal_queue.name == QUEUE_DEFAULT

        low_queue = self.client.get_queue(Priority.LOW)
        assert isinstance(low_queue, Queue)
        assert low_queue.name == QUEUE_LOW

    def test_get_queue_lengths_empty(self) -> None:
        """Test getting queue lengths when empty."""
        lengths = self.client.get_queue_lengths()

        assert QUEUE_HIGH in lengths
        assert QUEUE_DEFAULT in lengths
        assert QUEUE_LOW in lengths
        assert all(length == 0 for length in lengths.values())

    def test_priority_queue_mapping(self) -> None:
        """Test priority to queue name mapping."""
        assert PRIORITY_QUEUE_MAP[Priority.HIGH] == QUEUE_HIGH
        assert PRIORITY_QUEUE_MAP[Priority.NORMAL] == QUEUE_DEFAULT
        assert PRIORITY_QUEUE_MAP[Priority.LOW] == QUEUE_LOW

    def test_ping(self) -> None:
        """Test Redis ping via queue client."""
        assert self.client.ping() is True


# =============================================================================
# Integration Tests
# =============================================================================


class TestQueueIntegration:
    """Integration tests for queue operations."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.fake_redis = fakeredis.FakeRedis(decode_responses=True)
        self.store = RedisStore(redis_client=self.fake_redis)

    def test_batch_and_jobs_workflow(self) -> None:
        """Test complete workflow of batch and jobs."""
        # Create batch
        batch = Batch(
            created_by_email="user@example.com",
            created_by_user_id="user-abc",
            total_files=2,
            target_vector_store="qdrant-prod",
        )
        self.store.save_batch(batch)

        # Create jobs
        job1 = Job(
            batch_id=batch.batch_id,
            filename="doc1.pdf",
            file_path="/uploads/doc1.pdf",
            file_type="application/pdf",
            file_size_bytes=5000,
            classification=FileClassification.SCANNED_PDF,
            routed_to=Pipeline.OCR,
            priority=Priority.HIGH,
        )
        job2 = Job(
            batch_id=batch.batch_id,
            filename="audio.mp3",
            file_path="/uploads/audio.mp3",
            file_type="audio/mpeg",
            file_size_bytes=10000,
            classification=FileClassification.AUDIO,
            routed_to=Pipeline.TRANSCRIPTION,
            priority=Priority.NORMAL,
        )
        self.store.save_job(job1)
        self.store.save_job(job2)

        # Mark job1 as processing
        self.store.update_job_status(
            job1.job_id,
            status=JobStatus.PROCESSING.value,
            started_at="2024-01-01T10:00:00Z",
        )

        # Update batch progress
        self.store.update_batch_status(
            batch.batch_id,
            status=BatchStatus.PROCESSING.value,
        )

        # Mark job1 as completed
        self.store.update_job_status(
            job1.job_id,
            status=JobStatus.COMPLETED.value,
            completed_at="2024-01-01T10:01:00Z",
        )
        self.store.update_batch_status(
            batch.batch_id,
            completed_files=1,
        )

        # Verify state
        loaded_batch = self.store.get_batch(batch.batch_id)
        assert loaded_batch is not None
        assert loaded_batch.completed_files == 1
        assert loaded_batch.status == BatchStatus.PROCESSING

        loaded_job1 = self.store.get_job(job1.job_id)
        assert loaded_job1 is not None
        assert loaded_job1.status == JobStatus.COMPLETED

        loaded_job2 = self.store.get_job(job2.job_id)
        assert loaded_job2 is not None
        assert loaded_job2.status == JobStatus.QUEUED  # Still queued

    def test_job_failure_workflow(self) -> None:
        """Test job failure and retry workflow."""
        batch = Batch(
            created_by_email="user@example.com",
            created_by_user_id="user-abc",
            total_files=1,
        )
        self.store.save_batch(batch)

        job = Job(
            batch_id=batch.batch_id,
            filename="doc.pdf",
            file_path="/uploads/doc.pdf",
            file_type="application/pdf",
            file_size_bytes=1000,
        )
        self.store.save_job(job)

        # First attempt fails
        self.store.update_job_status(
            job.job_id,
            status=JobStatus.FAILED.value,
            error_message="OCR service unavailable",
            retry_count=1,
        )

        loaded = self.store.get_job(job.job_id)
        assert loaded is not None
        assert loaded.status == JobStatus.FAILED
        assert loaded.retry_count == 1
        assert loaded.can_retry() is True

        # Retry succeeds
        self.store.update_job_status(
            job.job_id,
            status=JobStatus.PROCESSING.value,
            error_message="",
            retry_count=2,
        )
        self.store.update_job_status(
            job.job_id,
            status=JobStatus.COMPLETED.value,
        )

        final = self.store.get_job(job.job_id)
        assert final is not None
        assert final.status == JobStatus.COMPLETED
        assert final.retry_count == 2
