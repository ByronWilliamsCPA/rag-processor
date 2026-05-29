"""Integration tests proving the ingest -> persist -> status pipeline works.

Before the pipeline was wired up, ``POST /api/v1/ingest`` built jobs in memory
but never persisted or enqueued them, so the batch-status endpoints always
returned 404. These tests inject a fakeredis-backed store and a stubbed queue
client to verify that an upload is now persisted, enqueued, and retrievable via
the status API, and that lifecycle events are published.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from io import BytesIO
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rag_processor.main import app
from rag_processor.queue.redis_store import RedisStore


@pytest.fixture
def temp_upload_dir() -> Generator[str, None, None]:
    """Create a temporary upload directory, cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """In-memory Redis shared by the store and the event publisher."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(fake_redis: fakeredis.FakeRedis) -> RedisStore:
    """RedisStore backed by fakeredis."""
    return RedisStore(redis_client=fake_redis)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the gateway app."""
    return TestClient(app)


@pytest.fixture
def sample_pdf() -> BytesIO:
    """A minimal valid PDF used as upload content."""
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 0\ntrailer\n<<>>\nstartxref\n0\n%%EOF"
    return BytesIO(content)


@pytest.fixture
def mock_ingest_settings(temp_upload_dir: str) -> Generator[MagicMock, None, None]:
    """Patch ingest settings with persistence enabled and a temp upload dir."""
    with patch("rag_processor.api.ingest.settings") as mock:
        mock.max_file_size_mb = 100
        mock.max_file_size_bytes = 100 * 1024 * 1024
        mock.allowed_mime_types = ["application/pdf", "text/plain"]
        mock.upload_dir = temp_upload_dir
        mock.persist_enabled = True
        yield mock


@pytest.fixture
def patched_backends(
    store: RedisStore, fake_redis: fakeredis.FakeRedis
) -> Generator[MagicMock, None, None]:
    """Route the store/queue/event-publisher at the fakeredis backend.

    Yields the mock queue client so tests can assert on enqueue calls.
    """
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="rq-test-1")

    with (
        patch("rag_processor.queue.jobs.get_redis_store", return_value=store),
        patch("rag_processor.queue.jobs.get_queue_client", return_value=mock_queue),
        patch(
            "rag_processor.websocket.events.get_redis_client", return_value=fake_redis
        ),
    ):
        yield mock_queue


@pytest.mark.integration
class TestIngestPersistsAndStatus:
    """End-to-end: upload becomes retrievable via the status API."""

    def test_upload_persists_enqueues_and_is_retrievable(
        self,
        client: TestClient,
        sample_pdf: BytesIO,
        mock_ingest_settings: MagicMock,
        patched_backends: MagicMock,
    ) -> None:
        """Uploading a file persists the batch and exposes it via /batch/{id}."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"
            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        batch_id = response.json()["batch_id"]

        # The job was enqueued for background processing.
        assert patched_backends.enqueue.called

        # The batch is now retrievable (previously always 404).
        status_resp = client.get(f"/api/v1/batch/{batch_id}")
        assert status_resp.status_code == status.HTTP_200_OK
        body = status_resp.json()
        assert body["batch_id"] == batch_id
        assert body["total_files"] == 1
        assert len(body["jobs"]) == 1
        assert body["jobs"][0]["filename"] == "test.pdf"

    def test_upload_publishes_lifecycle_events(
        self,
        client: TestClient,
        sample_pdf: BytesIO,
        fake_redis: fakeredis.FakeRedis,
        mock_ingest_settings: MagicMock,
        patched_backends: MagicMock,
    ) -> None:
        """A BATCH_CREATED + JOB_QUEUED event are recorded in event history."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"
            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        batch_id = response.json()["batch_id"]

        history_key = f"batch:{batch_id}:event_history"
        events = fake_redis.lrange(history_key, 0, -1)
        event_types = {json.loads(e)["event_type"] for e in events}
        assert "batch_created" in event_types
        assert "job_queued" in event_types

    def test_upload_succeeds_when_persistence_disabled(
        self,
        client: TestClient,
        sample_pdf: BytesIO,
        mock_ingest_settings: MagicMock,
        patched_backends: MagicMock,
    ) -> None:
        """With persist_enabled=False the upload still succeeds (no enqueue)."""
        mock_ingest_settings.persist_enabled = False

        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"
            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert not patched_backends.enqueue.called


@pytest.mark.integration
class TestWorkerPublishesEvents:
    """The background worker publishes job lifecycle events."""

    def test_process_job_task_publishes_processing_and_completed(
        self,
        store: RedisStore,
        fake_redis: fakeredis.FakeRedis,
    ) -> None:
        """Running a job emits job_processing and job_completed events."""
        from rag_processor.models.batch import Batch
        from rag_processor.models.job import Job
        from rag_processor.queue.jobs import process_job_task

        batch = Batch(created_by_email="dev@localhost", total_files=1)
        job = Job(
            batch_id=batch.batch_id,
            filename="doc.pdf",
            file_path="/tmp/doc.pdf",
            file_type="application/pdf",
            file_size_bytes=10,
        )
        store.save_batch(batch)
        store.save_job(job)

        with (
            patch("rag_processor.queue.jobs.get_redis_store", return_value=store),
            patch(
                "rag_processor.websocket.events.get_redis_client",
                return_value=fake_redis,
            ),
        ):
            result = process_job_task(str(job.job_id))

        assert result["status"] == "completed"

        history_key = f"batch:{batch.batch_id}:event_history"
        events = fake_redis.lrange(history_key, 0, -1)
        event_types = {json.loads(e)["event_type"] for e in events}
        assert "job_processing" in event_types
        assert "job_completed" in event_types
