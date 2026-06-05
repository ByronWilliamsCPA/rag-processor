"""FastAPI dependencies for authentication.

Provides injectable dependencies for accessing the current user
in protected endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, Request, status

from rag_processor.auth.models import CloudflareUser
from rag_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from rag_processor.models.batch import Batch

logger = get_logger(__name__)


async def get_current_user(request: Request) -> CloudflareUser:
    """Get the current authenticated user from request state.

    This dependency extracts the user set by CloudflareAuthMiddleware
    and makes it available to route handlers.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        CloudflareUser: The authenticated CloudflareUser.

    Raises:
        HTTPException: 401 if user is not authenticated.

    Example:
        ```python
        @router.get("/me")
        async def get_me(user: CloudflareUser = Depends(get_current_user)):
            return {"email": user.email}
        ```
    """
    user = cast("CloudflareUser | None", getattr(request.state, "user", None))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def batch_is_owned_by(
    batch: Batch,
    *,
    requester_user_id: str | None,
    requester_email: str | None,
) -> bool:
    """Check whether the caller owns the given batch.

    Ownership precedence:
    1. If both the batch and the caller have a Cloudflare user_id, that must
       match. Email is NOT checked as a fallback in this case — a different
       user_id with a coincidentally matching email must not grant access.
    2. Otherwise (legacy batches without user_id, or callers without one),
       fall back to email match.

    Empty strings on either side never grant access.

    Keyword-only requester args so REST callers (which have a CloudflareUser)
    and WebSocket callers (which only have a dict from verify_cloudflare_token)
    can both pass primitives without constructing a model.

    Args:
        batch (Batch): The batch being accessed.
        requester_user_id (str | None): The caller's Cloudflare user ID (sub), or None.
        requester_email (str | None): The caller's email, or None.

    Returns:
        bool: True if the caller created the batch.
    """
    if batch.created_by_user_id and requester_user_id:
        return batch.created_by_user_id == requester_user_id
    return bool(batch.created_by_email) and batch.created_by_email == requester_email


def ensure_batch_owned(
    batch: Batch | None,
    *,
    batch_id: UUID | str,
    user: CloudflareUser,
    not_found_detail: str,
) -> Batch:
    """Return the batch if the caller owns it, otherwise raise 404.

    Centralizes the access-control behavior shared by the batch and job status
    endpoints: a missing batch and a batch owned by someone else both yield 404
    (never 403) so batch existence is not leaked. Unauthorized attempts are
    logged with opaque IDs only.

    Args:
        batch (Batch | None): The batch that was looked up (or None if not found).
        batch_id (UUID | str): Batch identifier, used for logging and the 404 message.
        user (CloudflareUser): The authenticated caller.
        not_found_detail (str): Detail message for the 404 response.

    Returns:
        Batch: The batch, when the caller owns it.

    Raises:
        HTTPException: 404 if the batch is missing or not owned by the caller.
    """
    if batch is not None and batch_is_owned_by(
        batch, requester_user_id=user.user_id, requester_email=user.email
    ):
        return batch

    if batch is not None:
        # Minimal log context: opaque IDs only. Don't include the requester or
        # owner email/identity (attacker-controlled probes could otherwise
        # extract owner info from logs).
        logger.warning(
            "Unauthorized batch access attempt",
            batch_id=str(batch_id),
            requester_user_id=user.user_id,
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=not_found_detail,
    )


async def get_optional_user(request: Request) -> CloudflareUser | None:
    """Get the current user if authenticated, or None.

    Use this for endpoints that work with or without authentication
    but may provide different responses based on auth status.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        CloudflareUser | None: The authenticated CloudflareUser or None.
    """
    return cast("CloudflareUser | None", getattr(request.state, "user", None))
