"""File routing to processing pipelines.

Routes classified files to appropriate processing pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag_processor.models.job import FileClassification, Pipeline
from rag_processor.routing.classifier import FileClassifier
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)


# Default mapping from classification to pipeline
DEFAULT_ROUTING: dict[FileClassification, Pipeline] = {
    FileClassification.SCANNED_PDF: Pipeline.OCR,
    FileClassification.BORN_DIGITAL_PDF: Pipeline.DOC_PROCESSING,
    FileClassification.IMAGE: Pipeline.OCR,
    FileClassification.AUDIO: Pipeline.TRANSCRIPTION,
    FileClassification.VIDEO: Pipeline.TRANSCRIPTION,
    FileClassification.DOCUMENT: Pipeline.DOC_PROCESSING,
    FileClassification.UNKNOWN: Pipeline.NONE,
}


@dataclass
class RoutingResult:
    """Result of file routing decision.

    Attributes:
        classification: The file classification.
        pipeline: The target processing pipeline.
        confidence: Confidence level of the routing decision.
        details: Additional routing details.
    """

    classification: FileClassification
    pipeline: Pipeline
    confidence: str
    details: dict[str, str | int | float]


class FileRouter:
    """Routes files to appropriate processing pipelines.

    Combines file classification with routing logic to determine
    which pipeline should process each file.

    Example:
        router = FileRouter()
        result = router.route_from_bytes(file_content, "document.pdf")
        print(f"Route to: {result.pipeline}")
    """

    def __init__(
        self,
        routing_config: dict[FileClassification, Pipeline] | None = None,
    ) -> None:
        """Initialize the file router.

        Args:
            routing_config: Optional custom routing configuration.
                If not provided, uses DEFAULT_ROUTING.
        """
        self._classifier = FileClassifier()
        self._routing = routing_config or DEFAULT_ROUTING

    def route_from_bytes(
        self,
        content: bytes,
        filename: str | None = None,
    ) -> RoutingResult:
        """Route a file based on its content bytes.

        Args:
            content: File content as bytes.
            filename: Optional filename for type detection.

        Returns:
            RoutingResult with routing decision.
        """
        # Classify the file
        classification_result = self._classifier.classify_from_bytes(content, filename)

        # Look up the pipeline
        pipeline = self._routing.get(
            classification_result.classification,
            Pipeline.NONE,
        )

        logger.info(
            "File routed",
            classification=classification_result.classification.value,
            pipeline=pipeline.value,
            confidence=classification_result.confidence,
            filename=filename,
        )

        return RoutingResult(
            classification=classification_result.classification,
            pipeline=pipeline,
            confidence=classification_result.confidence,
            details=classification_result.details,
        )

    def route_from_path(self, file_path: str | Path) -> RoutingResult:
        """Route a file based on its path.

        Args:
            file_path: Path to the file.

        Returns:
            RoutingResult with routing decision.
        """
        path = Path(file_path)
        with path.open("rb") as f:
            content = f.read()

        return self.route_from_bytes(content, path.name)

    def get_pipeline_for_classification(
        self,
        classification: FileClassification,
    ) -> Pipeline:
        """Get the pipeline for a given classification.

        Args:
            classification: File classification.

        Returns:
            Target pipeline for the classification.
        """
        return self._routing.get(classification, Pipeline.NONE)

    def is_supported(self, classification: FileClassification) -> bool:
        """Check if a classification has a supported pipeline.

        Args:
            classification: File classification.

        Returns:
            True if classification has a non-NONE pipeline.
        """
        pipeline = self._routing.get(classification, Pipeline.NONE)
        return pipeline != Pipeline.NONE


# Module-level shared instance used by the API layer.
file_router = FileRouter()


def get_file_router() -> FileRouter:
    """FastAPI dependency returning the shared FileRouter instance.

    Using a dependency (rather than referencing the module-level singleton
    directly in handlers) lets callers and tests override routing via
    ``app.dependency_overrides`` without monkeypatching module globals.

    Returns:
        The shared FileRouter singleton.
    """
    return file_router
