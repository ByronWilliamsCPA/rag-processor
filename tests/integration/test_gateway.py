"""Integration tests for the FastAPI gateway application.

Tests the gateway endpoints including health checks and root endpoint.
Uses FastAPI's TestClient for synchronous testing.
"""

import pytest
from fastapi.testclient import TestClient

from rag_processor.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient for the FastAPI app.

    Returns:
        TestClient instance for making test requests.
    """
    return TestClient(app)


@pytest.mark.integration
class TestHealthEndpoints:
    """Integration tests for health check endpoints."""

    def test_health_live_returns_ok(self, client: TestClient) -> None:
        """Test that /health/live returns 200 with ok status."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert "version" in data
        assert "python_version" in data

    def test_health_root_returns_ok(self, client: TestClient) -> None:
        """Test that /health returns 200 (alias for /health/live)."""
        response = client.get("/health/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_startup_returns_started(self, client: TestClient) -> None:
        """Test that /health/startup returns started status."""
        response = client.get("/health/startup")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"


@pytest.mark.integration
class TestRootEndpoint:
    """Integration tests for root endpoint."""

    def test_root_returns_api_info(self, client: TestClient) -> None:
        """Test that / returns API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RAG Processor Gateway"
        assert "version" in data
        assert data["docs"] == "/docs"


@pytest.mark.integration
class TestCORSHeaders:
    """Integration tests for CORS configuration."""

    def test_cors_headers_present_on_get(self, client: TestClient) -> None:
        """Test that CORS headers are present on GET response."""
        response = client.get(
            "/health/live",
            headers={
                "Origin": "http://localhost:3000",
            },
        )

        assert response.status_code == 200
        # CORS headers should be present when Origin header is sent
        assert "access-control-allow-origin" in response.headers
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )


@pytest.mark.integration
class TestCorrelationID:
    """Integration tests for correlation ID middleware."""

    def test_correlation_id_generated_when_not_provided(
        self, client: TestClient
    ) -> None:
        """Test that correlation ID is generated if not provided."""
        response = client.get("/health/live")

        assert response.status_code == 200
        # Correlation ID should be in response headers
        assert "x-correlation-id" in response.headers
        assert response.headers["x-correlation-id"] != ""

    def test_correlation_id_preserved_when_provided(self, client: TestClient) -> None:
        """Test that provided correlation ID is preserved."""
        custom_correlation_id = "test-correlation-12345"
        response = client.get(
            "/health/live",
            headers={"X-Correlation-ID": custom_correlation_id},
        )

        assert response.status_code == 200
        assert response.headers["x-correlation-id"] == custom_correlation_id


@pytest.mark.integration
class TestOpenAPIDocs:
    """Integration tests for OpenAPI documentation."""

    def test_openapi_schema_available(self, client: TestClient) -> None:
        """Test that OpenAPI schema is accessible."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "RAG Processor Gateway"
        assert "paths" in data

    def test_swagger_docs_available(self, client: TestClient) -> None:
        """Test that Swagger UI is accessible."""
        response = client.get("/docs")

        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_redoc_available(self, client: TestClient) -> None:
        """Test that ReDoc is accessible."""
        response = client.get("/redoc")

        assert response.status_code == 200
        assert "redoc" in response.text.lower()
