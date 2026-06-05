"""User API endpoints.

Provides endpoints for accessing current user information.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from rag_processor.auth.dependencies import get_current_user
from rag_processor.auth.models import CloudflareUser

router = APIRouter(prefix="/user", tags=["user"])


class UserResponse(BaseModel):
    """Response model for user endpoints.

    Contains essential user information for the frontend.
    """

    email: str
    user_id: str | None = None
    groups: list[str] = Field(default_factory=list)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description=(
        "Returns the currently authenticated user's identity information "
        "(email, user ID, and group memberships) extracted from the "
        "Cloudflare Access JWT. Requires Cloudflare Access authentication."
    ),
)
async def get_me(
    user: CloudflareUser = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user information.

    Reads the verified Cloudflare Access user attached to the request
    by the auth middleware and returns the subset of fields safe to
    expose to the frontend.

    Authentication: Requires a valid Cloudflare Access JWT.

    Args:
        user (CloudflareUser): The authenticated user from Cloudflare Access (injected).

    Returns:
        UserResponse: UserResponse with `email`, optional `user_id`, and `groups`.
    """
    return UserResponse(
        email=user.email,
        user_id=user.user_id,
        groups=user.groups,
    )
