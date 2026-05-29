"""Tests for async wrappers and worker failure handling in queue/jobs.py."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import fakeredis
import pytest

from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import (
    FileClassification,
    Job,
    JobStatus,
    Pipeline,
)
from rag_processor.queue.redis_store import RedisStore


def _job(batch_id) -> Job:
    return Job(
        batch_id=batch_id,
        filename="x.pdf",
        file_path="/data/uploads/x.pdf",
        file_type="application/pdf",
        file_size_bytes=10,
        classification=FileClassification.BORN_DIGITAL_PDF,
        routed_to=Pipeline.DOC_PROCESSING,
    )


class TestAsyncWrappers:
    """The async wrappers must offload to a thread and return the value."""

    @pytest.mark.asyncio
    async def test_get_batch_status_async_returns_value(self) -> None:
        batch = Batch(created_by_email="a@b.c", status=BatchStatus.QUEUED)
        with patch(
            "rag_processor.queue.jobs.get_batch_status",
            return_value=(batch, []),
        ):
            from rag_processor.queue.jobs import get_batch_status_async

            result_batch, jobs = await get_batch_status_async(batch.batch_id)

        assert result_batch is batch
        assert jobs == []

    @pytest.mark.asyncio
    async def test_get_job_status_async_returns_value(self) -> None:
        job = _job(uuid4())
        with patch("rag_processor.queue.jobs.get_job_status", return_value=job):
            from rag_processor.queue.jobs import get_job_status_async

            result = await get_job_status_async(job.job_id)

        assert result is job


class TestProcessJobTaskFailure:
    """process_job_task must record pipeline failures against the job/batch."""

    def setup_method(self) -> None:
        self.fake_redis = fakeredis.FakeRedis(decode_responses=True)
        self.store = RedisStore(redis_client=self.fake_redis)

    def test_pipeline_failure_marks_job_failed(self) -> None:
        batch = Batch(created_by_email="a@b.c", total_files=1)
        job = _job(batch.batch_id)
        self.store.save_batch(batch)
        self.store.save_job(job)

        with (
            patch(
                "rag_processor.queue.jobs.get_redis_store",
                return_value=self.store,
            ),
            patch(
                "rag_processor.queue.jobs._run_pipeline",
                side_effect=RuntimeError("pipeline boom"),
            ),
        ):
            from rag_processor.queue.jobs import process_job_task

            result = process_job_task(str(job.job_id))

        assert result["status"] == "failed"
        assert "pipeline boom" in result["error"]

        stored = self.store.get_job(job.job_id)
        assert stored is not None
        assert stored.status == JobStatus.FAILED
        assert stored.error_message == "pipeline boom"

        # Batch must reflect the failure, not remain stuck in PROCESSING.
        stored_batch = self.store.get_batch(batch.batch_id)
        assert stored_batch is not None
        assert stored_batch.status == BatchStatus.FAILED

    def test_pipeline_success_marks_job_completed(self) -> None:
        batch = Batch(created_by_email="a@b.c", total_files=1)
        job = _job(batch.batch_id)
        self.store.save_batch(batch)
        self.store.save_job(job)

        with patch(
            "rag_processor.queue.jobs.get_redis_store",
            return_value=self.store,
        ):
            from rag_processor.queue.jobs import process_job_task

            result = process_job_task(str(job.job_id))

        assert result["status"] == "completed"
        stored = self.store.get_job(job.job_id)
        assert stored is not None
        assert stored.status == JobStatus.COMPLETED
