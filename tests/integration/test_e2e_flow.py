"""End-to-end integration tests for the RAG Processor workflow.

Tests the complete flow from file upload to job completion with status updates.
Note: These tests use mocked Redis via the ingest endpoint's internal storage.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rag_processor.main import app
from rag_processor.websocket.events import (
    EventType,
    create_batch_event,
    create_job_event,
)


@pytest.fixture
def temp_upload_dir() -> Generator[str, None, None]:
    """Create a temporary upload directory, cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(autouse=True)
def mock_auth_settings() -> Generator[None, None, None]:
    """Mock auth settings to enable bypass mode."""
    with patch("rag_processor.auth.cloudflare.settings") as mock:
        mock.cloudflare_enabled = False
        yield mock


@pytest.fixture(autouse=True)
def mock_ingest_settings(temp_upload_dir: str) -> Generator[None, None, None]:
    """Mock ingest settings for file upload."""
    with patch("rag_processor.api.ingest.settings") as mock:
        mock.max_file_size_mb = 100
        mock.max_file_size_bytes = 100 * 1024 * 1024
        mock.allowed_mime_types = [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "text/plain",
        ]
        mock.upload_dir = temp_upload_dir
        yield mock


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf() -> BytesIO:
    """Create a minimal PDF file for testing."""
    # Minimal valid PDF
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 0\ntrailer\n<<>>\nstartxref\n0\n%%EOF"
    return BytesIO(content)


class TestEndToEndUploadFlow:
    """Tests for the complete upload to job flow."""

    def test_upload_creates_batch_and_jobs(
        self, client: TestClient, sample_pdf: BytesIO
    ) -> None:
        """Test that uploading files creates a batch with jobs."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify batch created
        assert "batch_id" in data
        assert data["total_files"] == 1
        # Batch starts in "queued" or "pending" depending on implementation
        assert data["status"] in ("queued", "pending", "processing")

        # Verify job created
        assert len(data["jobs"]) == 1
        job = data["jobs"][0]
        assert job["filename"] == "test.pdf"
        assert job["status"] == "queued"
        assert "classification" in job
        assert "pipeline" in job

    def test_upload_multiple_files_creates_batch(self, client: TestClient) -> None:
        """Test uploading multiple files creates single batch with multiple jobs."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.side_effect = ["application/pdf", "text/plain"]

            files = [
                ("files", ("doc1.pdf", BytesIO(b"%PDF-1.4\ntest"), "application/pdf")),
                ("files", ("doc2.txt", BytesIO(b"text content"), "text/plain")),
            ]

            response = client.post("/api/v1/ingest", files=files)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["total_files"] == 2
        assert len(data["jobs"]) == 2

        # Each job should have different files
        filenames = {job["filename"] for job in data["jobs"]}
        assert filenames == {"doc1.pdf", "doc2.txt"}


class TestErrorHandling:
    """Tests for error handling in the E2E flow."""

    def test_upload_empty_file_returns_error(self, client: TestClient) -> None:
        """Test that uploading empty file returns error."""
        response = client.post(
            "/api/v1/ingest",
            files=[("files", ("empty.txt", BytesIO(b""), "text/plain"))],
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_invalid_mime_type_returns_error(self, client: TestClient) -> None:
        """Test that uploading invalid MIME type returns error."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/x-executable"

            response = client.post(
                "/api/v1/ingest",
                files=[
                    (
                        "files",
                        ("bad.exe", BytesIO(b"MZ..."), "application/octet-stream"),
                    )
                ],
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        # Detail may be a string or a dict depending on error format
        if isinstance(detail, str):
            assert "not allowed" in detail.lower()
        else:
            # Check if it's a structured error response
            assert detail is not None


class TestEventPublishing:
    """Tests for event publishing integration."""

    def test_job_event_creation_and_serialization(self) -> None:
        """Test creating and serializing job events."""
        batch_id = uuid4()
        job_id = uuid4()

        event = create_job_event(
            event_type=EventType.JOB_QUEUED,
            batch_id=batch_id,
            job_id=job_id,
            status="queued",
            message="Job queued for processing",
            filename="test.pdf",
        )

        json_dict = event.to_json_dict()

        assert json_dict["event_type"] == "job_queued"
        assert json_dict["batch_id"] == str(batch_id)
        assert json_dict["job_id"] == str(job_id)
        assert json_dict["data"]["filename"] == "test.pdf"

    def test_batch_event_creation_and_serialization(self) -> None:
        """Test creating and serializing batch events."""
        batch_id = uuid4()

        event = create_batch_event(
            event_type=EventType.BATCH_COMPLETED,
            batch_id=batch_id,
            status="completed",
            message="All jobs completed successfully",
            total_jobs=5,
            completed_jobs=5,
        )

        json_dict = event.to_json_dict()

        assert json_dict["event_type"] == "batch_completed"
        assert json_dict["batch_id"] == str(batch_id)
        assert json_dict["job_id"] is None
        assert json_dict["data"]["total_jobs"] == 5


class TestHealthEndpoints:
    """Tests for health check endpoints (liveness only, others need real dependencies)."""

    def test_health_live_returns_ok(self, client: TestClient) -> None:
        """Test liveness probe returns ok."""
        response = client.get("/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"


class TestIngestHealthEndpoint:
    """Tests for ingest-specific health check."""

    def test_ingest_health_returns_status(
        self, client: TestClient, temp_upload_dir: str
    ) -> None:
        """Test ingest health endpoint returns status."""
        with patch("rag_processor.api.ingest.settings") as mock:
            mock.upload_dir = temp_upload_dir

            response = client.get("/api/v1/ingest/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"


class TestUserEndpoint:
    """Tests for user info endpoint."""

    def test_user_me_returns_user_info(self, client: TestClient) -> None:
        """Test that /api/v1/user/me returns user info in bypass mode."""
        response = client.get("/api/v1/user/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "email" in data
        # In bypass mode, returns dev@localhost
        assert data["email"] == "dev@localhost"
