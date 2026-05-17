"""FastAPI dependencies for authentication.

Provides injectable dependencies for accessing the current user
in protected endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, Request, status

from rag_processor.auth.models import CloudflareUser

if TYPE_CHECKING:
    from rag_processor.models.batch import Batch


async def get_current_user(request: Request) -> CloudflareUser:
    """Get the current authenticated user from request state.

    This dependency extracts the user set by CloudflareAuthMiddleware
    and makes it available to route handlers.

    Args:
        request: The incoming HTTP request.

    Returns:
        The authenticated CloudflareUser.

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
        batch: The batch being accessed.
        requester_user_id: The caller's Cloudflare user ID (sub), or None.
        requester_email: The caller's email, or None.

    Returns:
        True if the caller created the batch.
    """
    if batch.created_by_user_id and requester_user_id:
        return batch.created_by_user_id == requester_user_id
    return bool(batch.created_by_email) and batch.created_by_email == requester_email


async def get_optional_user(request: Request) -> CloudflareUser | None:
    """Get the current user if authenticated, or None.

    Use this for endpoints that work with or without authentication
    but may provide different responses based on auth status.

    Args:
        request: The incoming HTTP request.

    Returns:
        The authenticated CloudflareUser or None.
    """
    return cast("CloudflareUser | None", getattr(request.state, "user", None))
