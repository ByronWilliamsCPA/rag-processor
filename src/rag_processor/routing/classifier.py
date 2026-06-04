"""PDF and file classification.

Classifies PDFs as scanned (image-based) or born-digital (text-based).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException

from rag_processor.core.config import settings
from rag_processor.models.job import FileClassification
from rag_processor.routing.detector import FileTypeDetector
from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """Result of file classification.

    Attributes:
        classification: The file classification enum value.
        confidence: Confidence level (high, medium, low).
        details: Additional classification details.
    """

    classification: FileClassification
    confidence: str
    details: dict[str, str | int | float]


class FileClassifier:
    """Classifies files for pipeline routing.

    Determines the appropriate processing pipeline based on file type
    and content analysis. For PDFs, distinguishes between scanned
    (image-based) and born-digital (text-based) documents.

    Example:
        classifier = FileClassifier()
        result = classifier.classify_from_bytes(pdf_content, "document.pdf")
        print(f"Classification: {result.classification}")
    """

    def __init__(
        self,
        *,
        scanned_chars_threshold: int | None = None,
        scanned_high_confidence_chars: int | None = None,
        digital_high_confidence_chars: int | None = None,
    ) -> None:
        """Initialize the file classifier.

        Args:
            scanned_chars_threshold: Chars/page below which a PDF is scanned.
                Defaults to the configured ``pdf_scanned_chars_threshold``.
            scanned_high_confidence_chars: Chars/page below which a scanned
                classification is 'high' confidence. Defaults to settings.
            digital_high_confidence_chars: Chars/page above which a born-digital
                classification is 'high' confidence. Defaults to settings.
        """
        self._detector = FileTypeDetector()
        self._scanned_chars_threshold = (
            scanned_chars_threshold
            if scanned_chars_threshold is not None
            else settings.pdf_scanned_chars_threshold
        )
        self._scanned_high_confidence_chars = (
            scanned_high_confidence_chars
            if scanned_high_confidence_chars is not None
            else settings.pdf_scanned_high_confidence_chars
        )
        self._digital_high_confidence_chars = (
            digital_high_confidence_chars
            if digital_high_confidence_chars is not None
            else settings.pdf_digital_high_confidence_chars
        )

    def classify_from_bytes(
        self,
        content: bytes,
        filename: str | None = None,
    ) -> ClassificationResult:
        """Classify a file from its content bytes.

        Args:
            content: File content as bytes.
            filename: Optional filename for type detection.

        Returns:
            ClassificationResult with classification and confidence.
        """
        # First, detect the file type
        detection = self._detector.detect_from_bytes(content, filename)
        mime_type = detection.mime_type

        # Classify based on MIME type
        if mime_type == "application/pdf":
            return self._classify_pdf(content)
        if mime_type.startswith("image/"):
            return ClassificationResult(
                classification=FileClassification.IMAGE,
                confidence="high",
                details={"mime_type": mime_type},
            )
        if mime_type.startswith("audio/"):
            return ClassificationResult(
                classification=FileClassification.AUDIO,
                confidence="high",
                details={"mime_type": mime_type},
            )
        if mime_type.startswith("video/"):
            return ClassificationResult(
                classification=FileClassification.VIDEO,
                confidence="high",
                details={"mime_type": mime_type},
            )
        if self._is_document_mime(mime_type):
            return ClassificationResult(
                classification=FileClassification.DOCUMENT,
                confidence="high",
                details={"mime_type": mime_type},
            )
        return ClassificationResult(
            classification=FileClassification.UNKNOWN,
            confidence="low",
            details={"mime_type": mime_type},
        )

    def classify_from_path(self, file_path: str | Path) -> ClassificationResult:
        """Classify a file from its path.

        Args:
            file_path: Path to the file.

        Returns:
            ClassificationResult with classification and confidence.
        """
        path = Path(file_path)
        with path.open("rb") as f:
            content = f.read()

        return self.classify_from_bytes(content, path.name)

    def _classify_pdf(self, content: bytes) -> ClassificationResult:
        """Classify a PDF as scanned or born-digital.

        Uses pdfplumber to extract text and calculate the text density.
        PDFs with low text density are classified as scanned.

        Args:
            content: PDF file content.

        Returns:
            ClassificationResult for the PDF.
        """
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                total_pages = len(pdf.pages)

                if total_pages == 0:
                    return ClassificationResult(
                        classification=FileClassification.UNKNOWN,
                        confidence="low",
                        details={
                            "error": "PDF has no pages",
                            "total_pages": 0,
                        },
                    )

                total_chars = 0
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    total_chars += len(text)

                chars_per_page = total_chars / total_pages

                if chars_per_page < self._scanned_chars_threshold:
                    classification = FileClassification.SCANNED_PDF
                    confidence = (
                        "high"
                        if chars_per_page < self._scanned_high_confidence_chars
                        else "medium"
                    )
                else:
                    classification = FileClassification.BORN_DIGITAL_PDF
                    confidence = (
                        "high"
                        if chars_per_page > self._digital_high_confidence_chars
                        else "medium"
                    )

                logger.debug(
                    "PDF classified",
                    classification=classification.value,
                    total_pages=total_pages,
                    total_chars=total_chars,
                    chars_per_page=round(chars_per_page, 2),
                )

                return ClassificationResult(
                    classification=classification,
                    confidence=confidence,
                    details={
                        "total_pages": total_pages,
                        "total_chars": total_chars,
                        "chars_per_page": round(chars_per_page, 2),
                        "threshold": self._scanned_chars_threshold,
                    },
                )

        except (
            PDFSyntaxError,
            PDFPasswordIncorrect,
            PDFEncryptionError,
            PdfminerException,
            ValueError,
            OSError,
        ) as e:
            # Handle encrypted, corrupted, or malformed PDFs
            logger.warning("PDF classification failed", error=str(e))
            return ClassificationResult(
                classification=FileClassification.UNKNOWN,
                confidence="low",
                details={"error": str(e)},
            )

    def _is_document_mime(self, mime_type: str) -> bool:
        """Check if MIME type is an office document.

        Args:
            mime_type: MIME type string.

        Returns:
            True if MIME type is a document.
        """
        document_types = {
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain",
            "text/markdown",
            "text/csv",
        }
        return mime_type in document_types
