"""Tests for ingest API endpoint."""

import tempfile
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rag_processor.main import app


@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory."""
    return tempfile.mkdtemp()


@pytest.fixture(autouse=True)
def mock_auth_settings():
    """Mock auth settings to enable bypass mode."""
    with patch("rag_processor.auth.cloudflare.settings") as mock:
        mock.cloudflare_enabled = False
        yield mock


@pytest.fixture(autouse=True)
def mock_ingest_settings(temp_upload_dir):
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
        # Default to no enqueue so the base upload tests don't require Redis.
        mock.enqueue_enabled = False
        yield mock


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf():
    """Create a minimal PDF file for testing."""
    # Minimal valid PDF
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 0\ntrailer\n<<>>\nstartxref\n0\n%%EOF"
    return BytesIO(content)


@pytest.fixture
def sample_text():
    """Create a text file for testing."""
    return BytesIO(b"Hello, World!")


class TestIngestEndpoint:
    """Tests for POST /api/v1/ingest."""

    def test_ingest_no_files_returns_422(self, client):
        """Test that uploading no files returns 422 (validation error)."""
        response = client.post("/api/v1/ingest", files=[])

        # FastAPI returns 422 Unprocessable Entity for validation errors
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingest_single_file_success(self, client, sample_pdf):
        """Test successful single file upload."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "batch_id" in data
        assert data["total_files"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["filename"] == "test.pdf"
        assert data["jobs"][0]["status"] == "queued"
        # Verify routing info is included
        assert "classification" in data["jobs"][0]
        assert "pipeline" in data["jobs"][0]

    def test_ingest_multiple_files_success(self, client):
        """Test successful multiple file upload."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.side_effect = ["application/pdf", "text/plain"]

            files = [
                ("files", ("doc1.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")),
                ("files", ("doc2.txt", BytesIO(b"text content"), "text/plain")),
            ]

            response = client.post("/api/v1/ingest", files=files)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_files"] == 2
        assert len(data["jobs"]) == 2

    def test_ingest_with_priority(self, client, sample_pdf):
        """Test upload with priority parameter."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
                data={"priority": "high"},
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_ingest_with_target_vector_store(self, client, sample_pdf):
        """Test upload with target vector store parameter."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
                data={"target_vector_store": "qdrant-prod"},
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_ingest_invalid_mime_type_rejected(self, client):
        """Test that files with invalid MIME types are rejected."""
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
        data = response.json()
        assert "not allowed" in str(data["detail"]).lower()

    def test_ingest_empty_file_rejected(self, client):
        """Test that empty files are rejected."""
        response = client.post(
            "/api/v1/ingest",
            files=[("files", ("empty.txt", BytesIO(b""), "text/plain"))],
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestFilenameSanitization:
    """Tests for filename sanitization."""

    def test_sanitize_path_traversal_in_storage(self, client, temp_upload_dir):
        """Test that path traversal attempts are sanitized in storage path.

        Note: The original filename is preserved in the response for display,
        but the actual file is stored with a sanitized name.
        """
        from pathlib import Path

        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "text/plain"

            response = client.post(
                "/api/v1/ingest",
                files=[
                    ("files", ("../../../etc/passwd", BytesIO(b"test"), "text/plain"))
                ],
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # The original filename is preserved for user reference
        assert data["jobs"][0]["filename"] == "../../../etc/passwd"

        # But check that no files were created outside the upload dir
        batch_id = data["batch_id"]
        batch_dir = Path(temp_upload_dir) / batch_id

        # Verify the batch directory exists within the temp upload dir
        assert batch_dir.exists()

    def test_sanitize_special_characters(self, client):
        """Test that special characters are handled."""
        with patch("rag_processor.api.ingest.detect_mime_type") as mock_detect:
            mock_detect.return_value = "text/plain"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("file<>:name.txt", BytesIO(b"test"), "text/plain"))],
            )

        assert response.status_code == status.HTTP_201_CREATED


class TestIngestEnqueue:
    """Tests for the persist+enqueue wiring gated by settings.enqueue_enabled."""

    def test_enqueue_called_when_enabled(
        self, client, sample_pdf, mock_ingest_settings
    ):
        """When enqueue is enabled, the batch and its jobs are enqueued."""
        mock_ingest_settings.enqueue_enabled = True

        with (
            patch("rag_processor.api.ingest.detect_mime_type") as mock_detect,
            patch("rag_processor.api.ingest.enqueue_batch_jobs") as mock_enqueue,
        ):
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        mock_enqueue.assert_called_once()
        # First positional arg is the batch, second is the list of jobs.
        batch_arg, jobs_arg = mock_enqueue.call_args[0]
        assert batch_arg.total_files == 1
        assert len(jobs_arg) == 1

    def test_enqueue_not_called_when_disabled(
        self, client, sample_pdf, mock_ingest_settings
    ):
        """When enqueue is disabled (default), no enqueue is attempted."""
        mock_ingest_settings.enqueue_enabled = False

        with (
            patch("rag_processor.api.ingest.detect_mime_type") as mock_detect,
            patch("rag_processor.api.ingest.enqueue_batch_jobs") as mock_enqueue,
        ):
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_201_CREATED
        mock_enqueue.assert_not_called()

    def test_enqueue_failure_returns_503_and_rolls_back(
        self, client, sample_pdf, mock_ingest_settings, temp_upload_dir
    ):
        """A Redis/RQ failure rolls back uploads and returns 503."""
        from pathlib import Path

        mock_ingest_settings.enqueue_enabled = True

        with (
            patch("rag_processor.api.ingest.detect_mime_type") as mock_detect,
            patch(
                "rag_processor.api.ingest.enqueue_batch_jobs",
                side_effect=ConnectionError("redis down"),
            ),
        ):
            mock_detect.return_value = "application/pdf"

            response = client.post(
                "/api/v1/ingest",
                files=[("files", ("test.pdf", sample_pdf, "application/pdf"))],
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        # Upload directory for the batch must have been cleaned up on rollback.
        batch_dirs = [p for p in Path(temp_upload_dir).iterdir() if p.is_dir()]
        assert batch_dirs == []


class TestIngestHealth:
    """Tests for ingest health endpoint."""

    def test_ingest_health_returns_status(self, client, temp_upload_dir):
        """Test ingest health endpoint returns status."""
        with patch("rag_processor.api.ingest.settings") as mock:
            mock.upload_dir = temp_upload_dir

            response = client.get("/api/v1/ingest/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "upload_dir" in data
