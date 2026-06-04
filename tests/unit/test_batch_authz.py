"""Authorization tests for batch and job read endpoints.

These tests exercise the ownership check added in
src/rag_processor/api/batch.py so SonarCloud / Codecov see the new branches as
covered. We don't use the running TestClient transport here because that
requires booting the auth middleware and Redis; instead we drive the handler
functions directly with mocks for `get_batch_status_async` / `get_job_status_async`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from rag_processor.api.batch import get_batch, get_job
from rag_processor.auth.dependencies import batch_is_owned_by, ensure_batch_owned
from rag_processor.auth.models import CloudflareUser
from rag_processor.models.batch import Batch, BatchStatus
from rag_processor.models.job import (
    FileClassification,
    Job,
    JobStatus,
    Pipeline,
)


def _user(
    email: str = "owner@example.com", user_id: str | None = "u-1"
) -> CloudflareUser:
    now = datetime.now(tz=UTC)
    return CloudflareUser(
        email=email,
        user_id=user_id,
        groups=[],
        issued_at=now,
        expires_at=now,
    )


def _batch(
    *,
    created_by_email: str = "owner@example.com",
    created_by_user_id: str | None = "u-1",
) -> Batch:
    return Batch(
        batch_id=uuid4(),
        created_by_email=created_by_email,
        created_by_user_id=created_by_user_id,
        status=BatchStatus.QUEUED,
        total_files=1,
    )


def _job(batch_id) -> Job:
    return Job(
        job_id=uuid4(),
        batch_id=batch_id,
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        file_type="application/pdf",
        file_size_bytes=10,
        status=JobStatus.QUEUED,
        classification=FileClassification.BORN_DIGITAL_PDF,
        routed_to=Pipeline.DOC_PROCESSING,
    )


def _owns(batch, user) -> bool:
    """Thin wrapper so tests read like the previous _user_owns_batch(batch, user)."""
    return batch_is_owned_by(
        batch, requester_user_id=user.user_id, requester_email=user.email
    )


class TestBatchIsOwnedBy:
    """Direct tests for the ownership helper."""

    def test_matches_on_user_id(self):
        assert _owns(_batch(), _user()) is True

    def test_user_id_mismatch_rejects(self):
        assert _owns(_batch(created_by_user_id="someone-else"), _user()) is False

    def test_falls_back_to_email_when_user_id_missing(self):
        assert _owns(_batch(created_by_user_id=None), _user(user_id=None)) is True

    def test_email_mismatch_rejects(self):
        assert (
            _owns(
                _batch(created_by_email="someone@else.com", created_by_user_id=None),
                _user(user_id=None),
            )
            is False
        )

    def test_empty_email_does_not_grant_access(self):
        # Both sides empty must not collide into "owner".
        assert (
            _owns(
                _batch(created_by_email="", created_by_user_id=None),
                _user(email="", user_id=None),
            )
            is False
        )

    def test_user_id_mismatch_does_not_fall_back_to_email(self):
        # Regression: when both user_ids are present and differ, a
        # coincidentally-matching email must NOT grant access. (CodeRabbit
        # PR #26 review.)
        assert (
            _owns(
                _batch(
                    created_by_user_id="u-owner",
                    created_by_email="match@example.com",
                ),
                _user(user_id="u-intruder", email="match@example.com"),
            )
            is False
        )


class TestEnsureBatchOwned:
    """Direct tests for the shared ownership/404 helper."""

    def test_returns_batch_for_owner(self):
        batch = _batch()
        assert (
            ensure_batch_owned(
                batch, batch_id=batch.batch_id, user=_user(), not_found_detail="x"
            )
            is batch
        )

    def test_raises_404_for_missing_batch(self):
        with pytest.raises(HTTPException) as exc:
            ensure_batch_owned(
                None, batch_id=uuid4(), user=_user(), not_found_detail="nope"
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "nope"

    def test_raises_404_for_non_owner(self):
        batch = _batch(created_by_user_id="other", created_by_email="other@x")
        with pytest.raises(HTTPException) as exc:
            ensure_batch_owned(
                batch,
                batch_id=batch.batch_id,
                user=_user(),
                not_found_detail="hidden",
            )
        # 404, not 403 — existence must not leak.
        assert exc.value.status_code == 404


class TestGetBatchAuthz:
    """Authorization branches on GET /api/v1/batch/{batch_id}."""

    @pytest.mark.asyncio
    async def test_owner_can_read_batch(self):
        batch = _batch()
        with patch(
            "rag_processor.api.batch.get_batch_status_async",
            new_callable=AsyncMock,
            return_value=(batch, []),
        ):
            resp = await get_batch(batch.batch_id, user=_user())
        assert resp.batch_id == batch.batch_id

    @pytest.mark.asyncio
    async def test_non_owner_gets_404_not_403(self):
        batch = _batch(created_by_user_id="other-user", created_by_email="other@x")
        with (
            patch(
                "rag_processor.api.batch.get_batch_status_async",
                new_callable=AsyncMock,
                return_value=(batch, []),
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await get_batch(batch.batch_id, user=_user())
        # 404 not 403 — must not leak existence.
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_batch_returns_404(self):
        with (
            patch(
                "rag_processor.api.batch.get_batch_status_async",
                new_callable=AsyncMock,
                return_value=(None, []),
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await get_batch(uuid4(), user=_user())
        assert exc.value.status_code == 404


class TestGetJobAuthz:
    """Authorization branches on GET /api/v1/batch/job/{job_id}."""

    @pytest.mark.asyncio
    async def test_owner_can_read_job(self):
        batch = _batch()
        job = _job(batch.batch_id)
        with (
            patch(
                "rag_processor.api.batch.get_job_status_async",
                new_callable=AsyncMock,
                return_value=job,
            ),
            patch(
                "rag_processor.api.batch.get_batch_status_async",
                new_callable=AsyncMock,
                return_value=(batch, [job]),
            ),
        ):
            resp = await get_job(job.job_id, user=_user())
        assert resp.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_non_owner_gets_404(self):
        batch = _batch(created_by_user_id="other-user", created_by_email="other@x")
        job = _job(batch.batch_id)
        with (
            patch(
                "rag_processor.api.batch.get_job_status_async",
                new_callable=AsyncMock,
                return_value=job,
            ),
            patch(
                "rag_processor.api.batch.get_batch_status_async",
                new_callable=AsyncMock,
                return_value=(batch, [job]),
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await get_job(job.job_id, user=_user())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_job_returns_404(self):
        with (
            patch(
                "rag_processor.api.batch.get_job_status_async",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await get_job(uuid4(), user=_user())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_orphaned_job_with_missing_batch_returns_404(self):
        # Defensive: a job whose batch row has been deleted must not be readable.
        job = _job(uuid4())
        with (
            patch(
                "rag_processor.api.batch.get_job_status_async",
                new_callable=AsyncMock,
                return_value=job,
            ),
            patch(
                "rag_processor.api.batch.get_batch_status_async",
                new_callable=AsyncMock,
                return_value=(None, []),
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await get_job(job.job_id, user=_user())
        assert exc.value.status_code == 404
