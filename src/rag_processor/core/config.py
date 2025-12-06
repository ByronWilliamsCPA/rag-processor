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

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
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
