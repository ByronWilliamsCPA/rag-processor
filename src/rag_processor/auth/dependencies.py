"""FastAPI dependencies for authentication.

Provides injectable dependencies for accessing the current user
in protected endpoints.
"""

from __future__ import annotations

from typing import cast

from fastapi import HTTPException, Request, status

from rag_processor.auth.models import CloudflareUser


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
