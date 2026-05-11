"""Tests for pipeline configuration loader."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from rag_processor.core.pipeline_config import (
    AuthConfig,
    PipelineConfig,
    PipelineConfiguration,
    RateLimitConfig,
    RetryConfig,
    VectorStoreConfig,
    load_pipeline_config,
    process_config_values,
    substitute_env_vars,
)
from rag_processor.models.job import FileClassification, Pipeline


class TestEnvVarSubstitution:
    """Tests for environment variable substitution."""

    def test_substitute_with_default(self) -> None:
        """Test substitution with default value."""
        result = substitute_env_vars("${UNDEFINED_VAR:-default}")
        assert result == "default"

    def test_substitute_with_env_var(self) -> None:
        """Test substitution with defined env var."""
        with patch.dict(os.environ, {"MY_VAR": "my_value"}):
            result = substitute_env_vars("${MY_VAR:-default}")
        assert result == "my_value"

    def test_substitute_without_default(self) -> None:
        """Test substitution without default returns empty string."""
        result = substitute_env_vars("${UNDEFINED_VAR}")
        assert result == ""

    def test_substitute_multiple_vars(self) -> None:
        """Test substituting multiple variables."""
        with patch.dict(os.environ, {"VAR1": "one", "VAR2": "two"}):
            result = substitute_env_vars("prefix_${VAR1}_middle_${VAR2}_suffix")
        assert result == "prefix_one_middle_two_suffix"

    def test_no_substitution_needed(self) -> None:
        """Test string without env vars is unchanged."""
        result = substitute_env_vars("plain string")
        assert result == "plain string"


class TestProcessConfigValues:
    """Tests for recursive config processing."""

    def test_process_dict(self) -> None:
        """Test processing nested dict."""
        with patch.dict(os.environ, {"MY_URL": "http://test.com"}):
            config = {"url": "${MY_URL:-default}", "port": 8080}
            result = process_config_values(config)
        assert result == {"url": "http://test.com", "port": 8080}

    def test_process_list(self) -> None:
        """Test processing list."""
        with patch.dict(os.environ, {"VAL": "test"}):
            config = ["${VAL:-default}", "plain"]
            result = process_config_values(config)
        assert result == ["test", "plain"]

    def test_process_nested(self) -> None:
        """Test processing nested structures."""
        config = {
            "level1": {
                "level2": "${NESTED:-nested_default}",
                "list": ["${ITEM:-item_default}"],
            }
        }
        result = process_config_values(config)
        assert result["level1"]["level2"] == "nested_default"
        assert result["level1"]["list"][0] == "item_default"


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default retry config values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_multiplier == 2.0
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0

    def test_custom_values(self) -> None:
        """Test custom retry config values."""
        config = RetryConfig(
            max_attempts=5,
            backoff_multiplier=3.0,
            initial_delay=2.0,
            max_delay=120.0,
        )
        assert config.max_attempts == 5
        assert config.backoff_multiplier == 3.0


class TestAuthConfig:
    """Tests for AuthConfig dataclass."""

    def test_token_from_env(self) -> None:
        """Test getting token from environment."""
        with patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            config = AuthConfig(type="bearer", token_env="MY_TOKEN")
            assert config.token == "secret123"

    def test_token_missing(self) -> None:
        """Test missing token returns None."""
        config = AuthConfig(type="bearer", token_env="NONEXISTENT_TOKEN")
        assert config.token is None

    def test_no_token_env(self) -> None:
        """Test empty token_env returns None."""
        config = AuthConfig(type="bearer", token_env="")
        assert config.token is None


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_pipeline_config_defaults(self) -> None:
        """Test default pipeline config values."""
        config = PipelineConfig(
            name="Test Pipeline",
            description="Test description",
            url="http://localhost:8000",
        )
        assert config.timeout == 30
        assert config.auth.type == "bearer"
        assert config.health_check.enabled is True
        assert config.retries.max_attempts == 3


class TestVectorStoreConfig:
    """Tests for VectorStoreConfig dataclass."""

    def test_api_key_from_env(self) -> None:
        """Test getting API key from environment."""
        with patch.dict(os.environ, {"QDRANT_KEY": "api123"}):
            config = VectorStoreConfig(
                name="test",
                type="qdrant",
                url="http://localhost:6333",
                collection="docs",
                api_key_env="QDRANT_KEY",
            )
            assert config.api_key == "api123"


class TestPipelineConfiguration:
    """Tests for PipelineConfiguration."""

    def test_get_pipeline(self) -> None:
        """Test getting pipeline config by enum."""
        config = PipelineConfiguration(
            version="1.0",
            default_timeout=30,
            default_retries=RetryConfig(),
            pipelines={
                "ocr": PipelineConfig(
                    name="OCR",
                    description="OCR Pipeline",
                    url="http://localhost:8001",
                )
            },
            routing={},
            vector_stores={},
            rate_limiting=RateLimitConfig(),
        )

        result = config.get_pipeline(Pipeline.OCR)
        assert result is not None
        assert result.name == "OCR"

    def test_get_pipeline_none(self) -> None:
        """Test getting NONE pipeline returns None."""
        config = PipelineConfiguration(
            version="1.0",
            default_timeout=30,
            default_retries=RetryConfig(),
            pipelines={},
            routing={},
            vector_stores={},
            rate_limiting=RateLimitConfig(),
        )

        result = config.get_pipeline(Pipeline.NONE)
        assert result is None

    def test_get_pipeline_for_classification(self) -> None:
        """Test getting pipeline for file classification."""
        config = PipelineConfiguration(
            version="1.0",
            default_timeout=30,
            default_retries=RetryConfig(),
            pipelines={},
            routing={
                FileClassification.SCANNED_PDF: Pipeline.OCR,
                FileClassification.AUDIO: Pipeline.TRANSCRIPTION,
            },
            vector_stores={},
            rate_limiting=RateLimitConfig(),
        )

        assert (
            config.get_pipeline_for_classification(FileClassification.SCANNED_PDF)
            == Pipeline.OCR
        )
        assert (
            config.get_pipeline_for_classification(FileClassification.AUDIO)
            == Pipeline.TRANSCRIPTION
        )
        assert (
            config.get_pipeline_for_classification(FileClassification.UNKNOWN)
            == Pipeline.NONE
        )


class TestLoadPipelineConfig:
    """Tests for loading pipeline configuration from file."""

    def test_load_from_yaml_file(self) -> None:
        """Test loading config from YAML file."""
        yaml_content = """
version: "1.0"
default_timeout: 60
default_retries:
  max_attempts: 5
pipelines:
  ocr:
    name: "Test OCR"
    description: "Test OCR Pipeline"
    url: "http://localhost:8001"
    timeout: 120
routing:
  scanned_pdf: ocr
  image: ocr
"""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = load_pipeline_config(f.name)

            assert config.version == "1.0"
            assert config.default_timeout == 60
            assert config.default_retries.max_attempts == 5
            assert "ocr" in config.pipelines
            assert config.pipelines["ocr"].name == "Test OCR"
            assert config.pipelines["ocr"].timeout == 120
            assert FileClassification.SCANNED_PDF in config.routing

            Path(f.name).unlink()

    def test_load_nonexistent_file_returns_default(self) -> None:
        """Test loading nonexistent file returns default config."""
        config = load_pipeline_config("/nonexistent/path/config.yaml")

        # Should return default config
        assert config.version == "1.0"
        assert "ocr" in config.pipelines
        assert FileClassification.SCANNED_PDF in config.routing

    def test_env_var_substitution_in_yaml(self) -> None:
        """Test env var substitution when loading YAML."""
        yaml_content = """
version: "1.0"
default_timeout: 30
pipelines:
  ocr:
    name: "OCR"
    description: "OCR Pipeline"
    url: "${OCR_URL:-http://default:8001}"
routing: {}
"""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            # Test with env var
            with patch.dict(os.environ, {"OCR_URL": "http://custom:9000"}):
                config = load_pipeline_config(f.name)
                assert config.pipelines["ocr"].url == "http://custom:9000"

            # Test without env var (default)
            config = load_pipeline_config(f.name)
            assert config.pipelines["ocr"].url == "http://default:8001"

            Path(f.name).unlink()
