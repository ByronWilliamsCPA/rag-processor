"""Pipeline configuration loader.

Loads pipeline configuration from YAML file with environment variable substitution.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from rag_processor.core.exceptions import ConfigurationError
from rag_processor.models.job import FileClassification, Pipeline
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)


# Environment variable pattern: ${VAR_NAME:-default_value} or ${VAR_NAME}
ENV_VAR_PATTERN = re.compile(r"\$\{([^}:-]+)(?::-([^}]*))?\}")


def substitute_env_vars(value: str) -> str:
    """Substitute environment variables in a string.

    Supports format: ${VAR_NAME:-default_value}

    Args:
        value (str): String potentially containing env var references.

    Returns:
        str: String with env vars substituted.
    """

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2) or ""
        return os.environ.get(var_name, default_value)

    return ENV_VAR_PATTERN.sub(replacer, value)


def process_config_values(obj: Any) -> Any:
    """Recursively process config values, substituting env vars in strings.

    Args:
        obj (Any): Config object (dict, list, or value).

    Returns:
        Any: Processed config with env vars substituted.
    """
    if isinstance(obj, dict):
        return {k: process_config_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [process_config_values(item) for item in obj]
    if isinstance(obj, str):
        return substitute_env_vars(obj)
    return obj


@dataclass
class RetryConfig:
    """Retry configuration for pipeline calls."""

    max_attempts: int = 3
    backoff_multiplier: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0


@dataclass
class HealthCheckConfig:
    """Health check configuration for a pipeline."""

    enabled: bool = True
    path: str = "/health"
    interval: int = 60


@dataclass
class AuthConfig:
    """Authentication configuration for a pipeline."""

    type: str = "bearer"
    token_env: str = ""

    @property
    def token(self) -> str | None:
        """Get the auth token from environment.

        Returns:
            str | None: Auth token string or None if not configured.
        """
        if not self.token_env:
            return None
        return os.environ.get(self.token_env)


@dataclass
class PipelineConfig:
    """Configuration for a single processing pipeline."""

    name: str
    description: str
    url: str
    timeout: int = 30
    auth: AuthConfig = field(default_factory=AuthConfig)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    retries: RetryConfig = field(default_factory=RetryConfig)


@dataclass
class VectorStoreConfig:
    """Configuration for a vector store."""

    name: str
    type: str
    url: str
    collection: str
    api_key_env: str = ""

    @property
    def api_key(self) -> str | None:
        """Get the API key from environment.

        Returns:
            str | None: API key string or None if not configured.
        """
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = True
    requests_per_minute: int = 100
    burst_size: int = 20


@dataclass
class PipelineConfiguration:
    """Complete pipeline configuration."""

    version: str
    default_timeout: int
    default_retries: RetryConfig
    pipelines: dict[str, PipelineConfig]
    routing: dict[FileClassification, Pipeline]
    vector_stores: dict[str, VectorStoreConfig]
    rate_limiting: RateLimitConfig

    def get_pipeline(self, pipeline: Pipeline) -> PipelineConfig | None:
        """Get configuration for a specific pipeline.

        Args:
            pipeline (Pipeline): The pipeline enum value.

        Returns:
            PipelineConfig | None: Pipeline configuration or None if not found.
        """
        if pipeline == Pipeline.NONE:
            return None
        return self.pipelines.get(pipeline.value)

    def get_pipeline_for_classification(
        self, classification: FileClassification
    ) -> Pipeline:
        """Get the target pipeline for a file classification.

        Args:
            classification (FileClassification): The file classification.

        Returns:
            Pipeline: Target pipeline.
        """
        return self.routing.get(classification, Pipeline.NONE)


def load_pipeline_config(
    config_path: str | Path | None = None,
    *,
    strict: bool = False,
) -> PipelineConfiguration:
    """Load pipeline configuration from YAML file.

    Falls back to default configuration if the file doesn't exist, unless
    strict mode is enabled.

    Args:
        config_path (str | Path | None): Path to the config file. If None, uses default location.
        strict (bool): If True, raise ConfigurationError when the file is missing
            instead of silently falling back to the built-in localhost
            defaults. Use in production to fail fast on misconfiguration.

    Returns:
        PipelineConfiguration: Loaded pipeline configuration.

    Raises:
        ConfigurationError: In strict mode, when the config file is missing.
    """
    if config_path is None:
        # Default to config/pipelines.yaml relative to project root
        config_path = (
            Path(__file__).parent.parent.parent.parent / "config" / "pipelines.yaml"
        )
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        if strict:
            msg = f"Pipeline config file not found: {config_path}"
            raise ConfigurationError(msg, details={"path": str(config_path)})
        logger.warning(
            "Pipeline config not found, using built-in defaults (which point at "
            "localhost and are NOT production-safe)",
            path=str(config_path),
        )
        return _create_default_config()

    logger.info("Loading pipeline configuration", path=str(config_path))

    with config_path.open("r") as f:
        raw_config = yaml.safe_load(f)

    # Process env vars
    config = process_config_values(raw_config)

    return _parse_config(config)


def _create_default_config() -> PipelineConfiguration:
    """Create default configuration when no config file exists.

    Returns:
        PipelineConfiguration: Default pipeline configuration with standard pipelines.
    """
    default_retries = RetryConfig()

    return PipelineConfiguration(
        version="1.0",
        default_timeout=30,
        default_retries=default_retries,
        pipelines={
            "ocr": PipelineConfig(
                name="OCR Pipeline",
                description="Optical character recognition",
                url="http://localhost:8001/api/v1/ocr",
                timeout=120,
            ),
            "transcription": PipelineConfig(
                name="Transcription Pipeline",
                description="Audio/video transcription",
                url="http://localhost:8002/api/v1/transcribe",
                timeout=300,
            ),
            "doc_processing": PipelineConfig(
                name="Document Processing",
                description="Document text extraction",
                url="http://localhost:8003/api/v1/extract",
                timeout=60,
            ),
            "fusion": PipelineConfig(
                name="Fusion Pipeline",
                description="Multi-modal fusion",
                url="http://localhost:8004/api/v1/fuse",
                timeout=180,
            ),
        },
        routing={
            FileClassification.SCANNED_PDF: Pipeline.OCR,
            FileClassification.BORN_DIGITAL_PDF: Pipeline.DOC_PROCESSING,
            FileClassification.IMAGE: Pipeline.OCR,
            FileClassification.AUDIO: Pipeline.TRANSCRIPTION,
            FileClassification.VIDEO: Pipeline.TRANSCRIPTION,
            FileClassification.DOCUMENT: Pipeline.DOC_PROCESSING,
            FileClassification.UNKNOWN: Pipeline.NONE,
        },
        vector_stores={},
        rate_limiting=RateLimitConfig(),
    )


def _parse_config(config: dict[str, Any]) -> PipelineConfiguration:
    """Parse raw config dict into typed configuration.

    Args:
        config (dict[str, Any]): Raw config dictionary.

    Returns:
        PipelineConfiguration: Typed pipeline configuration.
    """
    # Parse default retries
    default_retries_raw = config.get("default_retries", {})
    default_retries = RetryConfig(
        max_attempts=default_retries_raw.get("max_attempts", 3),
        backoff_multiplier=default_retries_raw.get("backoff_multiplier", 2.0),
        initial_delay=default_retries_raw.get("initial_delay", 1.0),
        max_delay=default_retries_raw.get("max_delay", 60.0),
    )

    # Parse pipelines
    pipelines: dict[str, PipelineConfig] = {}
    for name, pipeline_raw in config.get("pipelines", {}).items():
        auth_raw = pipeline_raw.get("auth", {})
        health_raw = pipeline_raw.get("health_check", {})
        retries_raw = pipeline_raw.get("retries", {})

        pipelines[name] = PipelineConfig(
            name=pipeline_raw.get("name", name),
            description=pipeline_raw.get("description", ""),
            url=pipeline_raw.get("url", ""),
            timeout=pipeline_raw.get("timeout", config.get("default_timeout", 30)),
            auth=AuthConfig(
                type=auth_raw.get("type", "bearer"),
                token_env=auth_raw.get("token_env", ""),
            ),
            health_check=HealthCheckConfig(
                enabled=health_raw.get("enabled", True),
                path=health_raw.get("path", "/health"),
                interval=health_raw.get("interval", 60),
            ),
            retries=RetryConfig(
                max_attempts=retries_raw.get(
                    "max_attempts", default_retries.max_attempts
                ),
                backoff_multiplier=retries_raw.get(
                    "backoff_multiplier", default_retries.backoff_multiplier
                ),
                initial_delay=retries_raw.get(
                    "initial_delay", default_retries.initial_delay
                ),
                max_delay=retries_raw.get("max_delay", default_retries.max_delay),
            ),
        )

    # Parse routing
    routing: dict[FileClassification, Pipeline] = {}
    for classification_str, pipeline_str in config.get("routing", {}).items():
        try:
            classification = FileClassification(classification_str)
            pipeline = Pipeline(pipeline_str)
            routing[classification] = pipeline
        except ValueError:
            logger.warning(
                "Invalid routing entry",
                classification=classification_str,
                pipeline=pipeline_str,
            )

    # Parse vector stores
    vector_stores: dict[str, VectorStoreConfig] = {}
    for name, store_raw in config.get("vector_stores", {}).items():
        vector_stores[name] = VectorStoreConfig(
            name=store_raw.get("name", name),
            type=store_raw.get("type", "qdrant"),
            url=store_raw.get("url", ""),
            collection=store_raw.get("collection", ""),
            api_key_env=store_raw.get("api_key_env", ""),
        )

    # Parse rate limiting
    rate_limit_raw = config.get("rate_limiting", {})
    rate_limiting = RateLimitConfig(
        enabled=rate_limit_raw.get("enabled", True),
        requests_per_minute=rate_limit_raw.get("requests_per_minute", 100),
        burst_size=rate_limit_raw.get("burst_size", 20),
    )

    return PipelineConfiguration(
        version=config.get("version", "1.0"),
        default_timeout=config.get("default_timeout", 30),
        default_retries=default_retries,
        pipelines=pipelines,
        routing=routing,
        vector_stores=vector_stores,
        rate_limiting=rate_limiting,
    )


# Global config instance (lazy loaded)
_config: PipelineConfiguration | None = None


def get_pipeline_config() -> PipelineConfiguration:
    """Get the global pipeline configuration.

    Returns:
        PipelineConfiguration: Pipeline configuration (lazy loaded).
    """
    global _config  # noqa: PLW0603
    if _config is None:
        _config = load_pipeline_config()
    return _config


def reload_pipeline_config(
    config_path: str | Path | None = None,
) -> PipelineConfiguration:
    """Reload the pipeline configuration.

    Args:
        config_path (str | Path | None): Optional path to config file.

    Returns:
        PipelineConfiguration: Reloaded pipeline configuration.
    """
    global _config  # noqa: PLW0603
    _config = load_pipeline_config(config_path)
    return _config
