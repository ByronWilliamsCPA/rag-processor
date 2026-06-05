"""Authentication models for Cloudflare Access.

Defines Pydantic models for JWT claims and user context.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

UTC = timezone.utc  # noqa: UP017


class CloudflareUser(BaseModel):
    """Authenticated user from Cloudflare Access.

    Attributes:
        email (str): User's email address from Cloudflare Access.
        user_id (str | None): Cloudflare user identifier (sub claim).
        groups (list[str]): List of group names the user belongs to.
        issued_at (datetime): When the token was issued.
        expires_at (datetime): When the token expires.
    """

    email: str = Field(..., description="User's email address")
    user_id: str | None = Field(None, description="Cloudflare user identifier")
    groups: list[str] = Field(default_factory=list, description="User's groups")
    issued_at: datetime = Field(..., description="Token issue time")
    expires_at: datetime = Field(..., description="Token expiration time")


class TokenClaims(BaseModel):
    """JWT claims structure from Cloudflare Access token.

    Follows Cloudflare Access JWT structure.
    See: https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/
    """

    # Standard JWT claims
    iss: str = Field(..., description="Issuer (Cloudflare team domain)")
    sub: str = Field(..., description="Subject (user identifier)")
    aud: list[str] | str = Field(..., description="Audience (application audience tag)")
    exp: int = Field(..., description="Expiration time (Unix timestamp)")
    iat: int = Field(..., description="Issued at (Unix timestamp)")
    nbf: int | None = Field(None, description="Not before (Unix timestamp)")

    # Cloudflare Access claims
    email: str = Field(..., description="User's email address")
    type: str | None = Field(None, description="Token type (app)")
    identity_nonce: str | None = Field(None, description="Identity nonce")
    custom: dict[str, str] | None = Field(None, description="Custom SAML attributes")

    # Group claims (from identity provider)
    groups: list[str] = Field(default_factory=list, description="User's groups")

    def to_user(self) -> CloudflareUser:
        """Convert token claims to CloudflareUser model.

        Returns:
            CloudflareUser: CloudflareUser with extracted user information.
        """
        return CloudflareUser(
            email=self.email,
            user_id=self.sub,
            groups=self.groups,
            issued_at=datetime.fromtimestamp(self.iat, tz=UTC),
            expires_at=datetime.fromtimestamp(self.exp, tz=UTC),
        )
