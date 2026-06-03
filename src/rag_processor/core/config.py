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
        upload_dir: Directory for uploaded files.
        result_dir: Directory for processing results.
        max_file_size_mb: Maximum file size in megabytes.
        allowed_mime_types: Allowed MIME types for upload.
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

    # CORS
    # Empty by default so production deployments must opt in explicitly via
    # RAG_PROCESSOR_CORS_ALLOWED_ORIGINS. The previous version of this setting
    # shipped dev http://localhost origins as defaults, which SonarCloud S5332
    # flagged for the obvious reason that they're plaintext http; more
    # importantly, baked-in defaults make it too easy to ship a production
    # build that accidentally trusts dev origins.
    # Local dev: see .env.example / docs for the recommended dev value.
    cors_allowed_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Allowed CORS origins. Must be an explicit list of origins (no "
            "wildcard) because allow_credentials=True. Set via "
            "RAG_PROCESSOR_CORS_ALLOWED_ORIGINS as a JSON array; empty by "
            "default."
        ),
    )

    # Background processing
    enqueue_enabled: bool = Field(
        default=False,
        description=(
            "Persist uploaded batches/jobs to Redis and enqueue them to RQ for "
            "background processing. Disabled by default so deployments without "
            "a Redis/RQ worker accept uploads without attempting to queue them. "
            "Set to true once a worker is running."
        ),
    )

    # Rate Limiting
    rate_limiting_enabled: bool = Field(
        default=True,
        description="Enable rate limiting middleware (set to false for testing)",
    )
    rate_limit_rpm: int = Field(
        default=60,
        ge=1,
        description="Rate limit requests per minute per IP",
    )

    # Redis
    redis_host: str = Field(
        default="localhost",
        description="Redis server hostname",
    )
    redis_port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis server port",
    )
    redis_password: str = Field(
        default="",
        description="Redis password (empty for no auth)",
    )
    redis_db: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number",
    )

    # File Upload
    upload_dir: str = Field(
        default="/data/uploads",
        description="Directory for uploaded files",
    )
    result_dir: str = Field(
        default="/data/results",
        description="Directory for processing results",
    )
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum file size in megabytes",
    )
    allowed_mime_types: list[str] = Field(
        default=[
            # PDF
            "application/pdf",
            # Images
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "image/tiff",
            # Audio
            "audio/mpeg",
            "audio/wav",
            "audio/mp4",
            "audio/ogg",
            "audio/flac",
            # Video
            "video/mp4",
            "video/webm",
            "video/quicktime",
            # Documents
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            # Text
            "text/plain",
            "text/markdown",
            "text/csv",
        ],
        description="Allowed MIME types for upload",
    )

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes.

        Returns:
            Maximum file size in bytes.
        """
        return self.max_file_size_mb * 1024 * 1024


# A single, global instance of the settings
settings = Settings()
