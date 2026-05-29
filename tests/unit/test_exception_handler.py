"""Tests for the domain-exception HTTP mapping and FastAPI handler wiring."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag_processor.core.exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    ConfigurationError,
    DatabaseError,
    ExternalServiceError,
    ProjectBaseError,
    ResourceNotFoundError,
    ValidationError,
    http_status_for,
)
from rag_processor.main import handle_project_error


class TestHttpStatusFor:
    """Status-code mapping for each exception type."""

    @pytest.mark.parametrize(
        ("exc", "expected"),
        [
            (DatabaseError("db"), 503),
            (APIError("api"), 502),
            (ExternalServiceError("svc"), 502),
            (AuthenticationError(), 401),
            (AuthorizationError(), 403),
            (ResourceNotFoundError("missing"), 404),
            (ValidationError("bad"), 400),
            (BusinessLogicError("rule"), 409),
            (ConfigurationError("cfg"), 500),
            (ProjectBaseError("base"), 500),
        ],
    )
    def test_status_mapping(self, exc: ProjectBaseError, expected: int) -> None:
        assert http_status_for(exc) == expected

    def test_database_error_checked_before_external_service(self) -> None:
        # DatabaseError subclasses ExternalServiceError; must map to 503 not 502.
        assert http_status_for(DatabaseError("db")) == 503


class TestExceptionHandlerWiring:
    """The handler must render domain exceptions raised inside endpoints."""

    @pytest.mark.asyncio
    async def test_handler_returns_mapped_status_and_body(self) -> None:
        exc = ResourceNotFoundError("nope", resource_type="Batch")
        response = await handle_project_error(None, exc)  # type: ignore[arg-type]
        assert response.status_code == 404

    def test_app_translates_domain_exception(self) -> None:
        app = FastAPI()
        app.add_exception_handler(ProjectBaseError, handle_project_error)

        @app.get("/boom")
        async def boom() -> dict[str, str]:
            raise DatabaseError("connection refused", operation="hgetall")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/boom")

        assert response.status_code == 503
        body = response.json()
        assert body["error"] == "DatabaseError"
        assert body["message"] == "connection refused"
