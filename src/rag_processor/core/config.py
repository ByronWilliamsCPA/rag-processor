"""Configuration settings for RAG Processor.

Settings are loaded from environment variables with the prefix 'RAG_PROCESSOR_'.
Pydantic-settings handles the parsing and validation.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application.

    Loaded from environment variables with RAG_PROCESSOR_ prefix.

    Attributes:
        log_level: The logging level for the application.
        json_logs: Flag to enable or disable JSON formatted logs.
        include_timestamp: Flag to include timestamps in logs.
        cloudflare_team_domain: Cloudflare Access team domain.
        cloudflare_audience_tag: Cloudflare Access audience tag.
        cloudflare_enabled: Enable/disable Cloudflare authentication.
        redis_url: Redis connection URL.
    """

    model_config = SettingsConfigDict(
        env_prefix="rag_processor_",
        case_sensitive=False,
        extra="ignore",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    include_timestamp: bool = True

    # Cloudflare Access Authentication
    cloudflare_team_domain: str = Field(
        default="",
        description="Cloudflare Access team domain (e.g., myteam.cloudflareaccess.com)",
    )
    cloudflare_audience_tag: str = Field(
        default="",
        description="Cloudflare Access audience tag for this application",
    )
    cloudflare_enabled: bool = Field(
        default=True,
        description="Enable Cloudflare authentication (set to false for local dev)",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )


# A single, global instance of the settings
settings = Settings()
