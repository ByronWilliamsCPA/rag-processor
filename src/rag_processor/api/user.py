"""User API endpoints.

Provides endpoints for accessing current user information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from rag_processor.auth.dependencies import get_current_user

if TYPE_CHECKING:
    from rag_processor.auth.models import CloudflareUser

router = APIRouter(prefix="/user", tags=["user"])


class UserResponse(BaseModel):
    """Response model for user endpoints.

    Contains essential user information for the frontend.
    """

    email: str
    user_id: str | None = None
    groups: list[str] = []


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the currently authenticated user's information.",
)
async def get_me(
    user: CloudflareUser = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user information.

    Args:
        user: The authenticated user from Cloudflare Access.

    Returns:
        User information including email and groups.
    """
    return UserResponse(
        email=user.email,
        user_id=user.user_id,
        groups=user.groups,
    )
