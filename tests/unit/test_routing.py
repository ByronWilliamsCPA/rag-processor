"""Tests for pipeline routing module.

Tests file type detection, PDF classification, and pipeline routing.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rag_processor.models.job import FileClassification, Pipeline
from rag_processor.routing.classifier import (
    ClassificationResult,
    FileClassifier,
)
from rag_processor.routing.detector import (
    EXTENSION_MIMES,
    MIME_EXTENSIONS,
    DetectionResult,
    FileTypeDetector,
)
from rag_processor.routing.router import (
    DEFAULT_ROUTING,
    FileRouter,
    RoutingResult,
)

# =============================================================================
# FileTypeDetector Tests
# =============================================================================


class TestFileTypeDetector:
    """Tests for FileTypeDetector class."""

    def test_detect_pdf_from_bytes(self) -> None:
        """Test detecting PDF from magic bytes."""
        # PDF magic bytes
        pdf_content = b"%PDF-1.4 fake pdf content"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="application/pdf",
        ):
            detector = FileTypeDetector()
            result = detector.detect_from_bytes(pdf_content, "test.pdf")

            assert result.mime_type == "application/pdf"
            assert result.extension == ".pdf"
            assert result.confidence == "high"
            assert result.magic_match is True
            assert result.extension_match is True

    def test_detect_image_from_bytes(self) -> None:
        """Test detecting image from magic bytes."""
        # PNG magic bytes
        png_content = b"\x89PNG\r\n\x1a\n fake png"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="image/png",
        ):
            detector = FileTypeDetector()
            result = detector.detect_from_bytes(png_content, "test.png")

            assert result.mime_type == "image/png"
            assert result.confidence == "high"
            assert result.magic_match is True

    def test_detect_audio_from_bytes(self) -> None:
        """Test detecting audio from magic bytes."""
        mp3_content = b"ID3\x04\x00\x00 fake mp3"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="audio/mpeg",
        ):
            detector = FileTypeDetector()
            result = detector.detect_from_bytes(mp3_content, "test.mp3")

            assert result.mime_type == "audio/mpeg"
            assert result.extension == ".mp3"
            assert result.confidence == "high"

    def test_detect_video_from_bytes(self) -> None:
        """Test detecting video from magic bytes."""
        mp4_content = b"\x00\x00\x00\x1cftyp fake mp4"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="video/mp4",
        ):
            detector = FileTypeDetector()
            result = detector.detect_from_bytes(mp4_content, "test.mp4")

            assert result.mime_type == "video/mp4"
            assert result.extension == ".mp4"
            assert result.confidence == "high"

    def test_detect_unknown_mime_type(self) -> None:
        """Test detecting unknown/binary file type."""
        binary_content = b"\x00\x01\x02\x03 binary"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="application/octet-stream",
        ):
            detector = FileTypeDetector()
            result = detector.detect_from_bytes(binary_content, "test.bin")

            assert result.mime_type == "application/octet-stream"
            assert result.confidence == "low"
            assert result.magic_match is False

    def test_extension_fallback_when_magic_fails(self) -> None:
        """Test falling back to extension when magic bytes don't match."""
        content = b"some content"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="application/octet-stream",
        ):
            detector = FileTypeDetector()
            result = detector.detect_from_bytes(content, "test.pdf")

            # Falls back to extension-based detection
            assert result.mime_type == "application/pdf"
            assert result.confidence == "low"

    def test_extension_mismatch_lowers_confidence(self) -> None:
        """Test that extension mismatch lowers confidence to medium."""
        content = b"%PDF-1.4 fake pdf"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="application/pdf",
        ):
            detector = FileTypeDetector()
            # Extension doesn't match detected MIME type
            result = detector.detect_from_bytes(content, "test.jpg")

            assert result.mime_type == "application/pdf"
            assert result.confidence == "medium"
            assert result.extension_match is False

    def test_is_pdf_helper(self) -> None:
        """Test is_pdf helper method."""
        pdf_content = b"%PDF-1.4"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="application/pdf",
        ):
            detector = FileTypeDetector()
            assert detector.is_pdf(pdf_content) is True

    def test_is_image_helper(self) -> None:
        """Test is_image helper method."""
        png_content = b"\x89PNG"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="image/png",
        ):
            detector = FileTypeDetector()
            assert detector.is_image(png_content) is True

    def test_is_audio_helper(self) -> None:
        """Test is_audio helper method."""
        mp3_content = b"ID3"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="audio/mpeg",
        ):
            detector = FileTypeDetector()
            assert detector.is_audio(mp3_content) is True

    def test_is_video_helper(self) -> None:
        """Test is_video helper method."""
        mp4_content = b"ftyp"

        with patch.object(
            FileTypeDetector,
            "_detect_magic",
            return_value="video/mp4",
        ):
            detector = FileTypeDetector()
            assert detector.is_video(mp4_content) is True

    def test_mime_extensions_mapping(self) -> None:
        """Test MIME to extension mapping is complete."""
        assert MIME_EXTENSIONS["application/pdf"] == ".pdf"
        assert MIME_EXTENSIONS["image/png"] == ".png"
        assert MIME_EXTENSIONS["audio/mpeg"] == ".mp3"
        assert MIME_EXTENSIONS["video/mp4"] == ".mp4"

    def test_extension_mimes_reverse_mapping(self) -> None:
        """Test extension to MIME reverse mapping."""
        assert "application/pdf" in EXTENSION_MIMES[".pdf"]
        assert "image/png" in EXTENSION_MIMES[".png"]


# =============================================================================
# FileClassifier Tests
# =============================================================================


class TestFileClassifier:
    """Tests for FileClassifier class."""

    def test_classify_image_file(self) -> None:
        """Test classifying an image file."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="image/png",
                extension=".png",
                confidence="high",
                magic_match=True,
                extension_match=True,
            ),
        ):
            result = classifier.classify_from_bytes(b"png content", "test.png")

            assert result.classification == FileClassification.IMAGE
            assert result.confidence == "high"
            assert result.details["mime_type"] == "image/png"

    def test_classify_audio_file(self) -> None:
        """Test classifying an audio file."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="audio/mpeg",
                extension=".mp3",
                confidence="high",
                magic_match=True,
                extension_match=True,
            ),
        ):
            result = classifier.classify_from_bytes(b"mp3 content", "test.mp3")

            assert result.classification == FileClassification.AUDIO
            assert result.confidence == "high"

    def test_classify_video_file(self) -> None:
        """Test classifying a video file."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="video/mp4",
                extension=".mp4",
                confidence="high",
                magic_match=True,
                extension_match=True,
            ),
        ):
            result = classifier.classify_from_bytes(b"mp4 content", "test.mp4")

            assert result.classification == FileClassification.VIDEO
            assert result.confidence == "high"

    def test_classify_document_docx(self) -> None:
        """Test classifying a Word document."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                extension=".docx",
                confidence="high",
                magic_match=True,
                extension_match=True,
            ),
        ):
            result = classifier.classify_from_bytes(b"docx content", "test.docx")

            assert result.classification == FileClassification.DOCUMENT
            assert result.confidence == "high"

    def test_classify_document_xlsx(self) -> None:
        """Test classifying an Excel spreadsheet."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                extension=".xlsx",
                confidence="high",
                magic_match=True,
                extension_match=True,
            ),
        ):
            result = classifier.classify_from_bytes(b"xlsx content", "test.xlsx")

            assert result.classification == FileClassification.DOCUMENT
            assert result.confidence == "high"

    def test_classify_text_plain(self) -> None:
        """Test classifying a plain text file."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="text/plain",
                extension=".txt",
                confidence="high",
                magic_match=True,
                extension_match=True,
            ),
        ):
            result = classifier.classify_from_bytes(b"text content", "test.txt")

            assert result.classification == FileClassification.DOCUMENT
            assert result.confidence == "high"

    def test_classify_unknown_file_type(self) -> None:
        """Test classifying an unknown file type."""
        classifier = FileClassifier()

        with patch.object(
            classifier._detector,
            "detect_from_bytes",
            return_value=DetectionResult(
                mime_type="application/x-unknown",
                extension="",
                confidence="low",
                magic_match=False,
                extension_match=False,
            ),
        ):
            result = classifier.classify_from_bytes(b"unknown", "test.xyz")

            assert result.classification == FileClassification.UNKNOWN
            assert result.confidence == "low"

    def test_classify_born_digital_pdf(self) -> None:
        """Test classifying a born-digital PDF with text."""
        classifier = FileClassifier()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 500  # 500 chars per page

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch("pdfplumber.open", return_value=mock_pdf),
        ):
            result = classifier.classify_from_bytes(b"%PDF-1.4", "test.pdf")

            assert result.classification == FileClassification.BORN_DIGITAL_PDF
            assert result.confidence == "high"
            assert result.details["chars_per_page"] == 500.0
            assert result.details["total_pages"] == 1

    def test_classify_scanned_pdf(self) -> None:
        """Test classifying a scanned PDF with minimal text."""
        classifier = FileClassifier()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 5  # Only 5 chars

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch("pdfplumber.open", return_value=mock_pdf),
        ):
            result = classifier.classify_from_bytes(b"%PDF-1.4", "test.pdf")

            assert result.classification == FileClassification.SCANNED_PDF
            assert result.confidence == "high"
            assert result.details["chars_per_page"] == 5.0

    def test_classify_pdf_medium_confidence_scanned(self) -> None:
        """Test scanned PDF with medium confidence (borderline chars)."""
        classifier = FileClassifier()

        mock_page = MagicMock()
        # Between 10 and threshold (50) = medium confidence scanned
        mock_page.extract_text.return_value = "A" * 30

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch("pdfplumber.open", return_value=mock_pdf),
        ):
            result = classifier.classify_from_bytes(b"%PDF-1.4", "test.pdf")

            assert result.classification == FileClassification.SCANNED_PDF
            assert result.confidence == "medium"

    def test_classify_pdf_medium_confidence_born_digital(self) -> None:
        """Test born-digital PDF with medium confidence (borderline chars)."""
        classifier = FileClassifier()

        mock_page = MagicMock()
        # Between threshold (50) and 200 = medium confidence born-digital
        mock_page.extract_text.return_value = "A" * 100

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch("pdfplumber.open", return_value=mock_pdf),
        ):
            result = classifier.classify_from_bytes(b"%PDF-1.4", "test.pdf")

            assert result.classification == FileClassification.BORN_DIGITAL_PDF
            assert result.confidence == "medium"

    def test_classify_pdf_empty_pages(self) -> None:
        """Test classifying a PDF with no pages."""
        classifier = FileClassifier()

        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch("pdfplumber.open", return_value=mock_pdf),
        ):
            result = classifier.classify_from_bytes(b"%PDF-1.4", "test.pdf")

            assert result.classification == FileClassification.UNKNOWN
            assert result.confidence == "low"
            assert result.details["error"] == "PDF has no pages"

    def test_classify_corrupted_pdf(self) -> None:
        """Test classifying a corrupted PDF."""
        from pdfminer.pdfparser import PDFSyntaxError

        classifier = FileClassifier()

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch("pdfplumber.open", side_effect=PDFSyntaxError("Invalid PDF")),
        ):
            result = classifier.classify_from_bytes(b"corrupt", "test.pdf")

            assert result.classification == FileClassification.UNKNOWN
            assert result.confidence == "low"
            assert "error" in result.details

    def test_classify_encrypted_pdf(self) -> None:
        """Test classifying an encrypted PDF."""
        from pdfminer.pdfdocument import PDFPasswordIncorrect

        classifier = FileClassifier()

        with (
            patch.object(
                classifier._detector,
                "detect_from_bytes",
                return_value=DetectionResult(
                    mime_type="application/pdf",
                    extension=".pdf",
                    confidence="high",
                    magic_match=True,
                    extension_match=True,
                ),
            ),
            patch(
                "pdfplumber.open", side_effect=PDFPasswordIncorrect("Password required")
            ),
        ):
            result = classifier.classify_from_bytes(b"%PDF-1.4", "encrypted.pdf")

            assert result.classification == FileClassification.UNKNOWN
            assert result.confidence == "low"

    def test_scanned_pdf_chars_threshold(self) -> None:
        """Test that the configured threshold default is reasonable."""
        from rag_processor.core.config import settings

        assert settings.pdf_scanned_chars_threshold == 50


# =============================================================================
# FileRouter Tests
# =============================================================================


class TestFileRouter:
    """Tests for FileRouter class."""

    def test_default_routing_config(self) -> None:
        """Test default routing configuration."""
        assert DEFAULT_ROUTING[FileClassification.SCANNED_PDF] == Pipeline.OCR
        assert (
            DEFAULT_ROUTING[FileClassification.BORN_DIGITAL_PDF]
            == Pipeline.DOC_PROCESSING
        )
        assert DEFAULT_ROUTING[FileClassification.IMAGE] == Pipeline.OCR
        assert DEFAULT_ROUTING[FileClassification.AUDIO] == Pipeline.TRANSCRIPTION
        assert DEFAULT_ROUTING[FileClassification.VIDEO] == Pipeline.TRANSCRIPTION
        assert DEFAULT_ROUTING[FileClassification.DOCUMENT] == Pipeline.DOC_PROCESSING
        assert DEFAULT_ROUTING[FileClassification.UNKNOWN] == Pipeline.NONE

    def test_route_scanned_pdf_to_ocr(self) -> None:
        """Test routing scanned PDF to OCR pipeline."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.SCANNED_PDF,
                confidence="high",
                details={"chars_per_page": 5.0},
            ),
        ):
            result = router.route_from_bytes(b"%PDF-1.4", "scan.pdf")

            assert result.classification == FileClassification.SCANNED_PDF
            assert result.pipeline == Pipeline.OCR
            assert result.confidence == "high"

    def test_route_born_digital_pdf_to_doc_processing(self) -> None:
        """Test routing born-digital PDF to doc processing."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.BORN_DIGITAL_PDF,
                confidence="high",
                details={"chars_per_page": 500.0},
            ),
        ):
            result = router.route_from_bytes(b"%PDF-1.4", "report.pdf")

            assert result.classification == FileClassification.BORN_DIGITAL_PDF
            assert result.pipeline == Pipeline.DOC_PROCESSING

    def test_route_image_to_ocr(self) -> None:
        """Test routing image to OCR pipeline."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.IMAGE,
                confidence="high",
                details={"mime_type": "image/png"},
            ),
        ):
            result = router.route_from_bytes(b"png content", "test.png")

            assert result.classification == FileClassification.IMAGE
            assert result.pipeline == Pipeline.OCR

    def test_route_audio_to_transcription(self) -> None:
        """Test routing audio to transcription pipeline."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.AUDIO,
                confidence="high",
                details={"mime_type": "audio/mpeg"},
            ),
        ):
            result = router.route_from_bytes(b"mp3 content", "test.mp3")

            assert result.classification == FileClassification.AUDIO
            assert result.pipeline == Pipeline.TRANSCRIPTION

    def test_route_video_to_transcription(self) -> None:
        """Test routing video to transcription pipeline."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.VIDEO,
                confidence="high",
                details={"mime_type": "video/mp4"},
            ),
        ):
            result = router.route_from_bytes(b"mp4 content", "test.mp4")

            assert result.classification == FileClassification.VIDEO
            assert result.pipeline == Pipeline.TRANSCRIPTION

    def test_route_document_to_doc_processing(self) -> None:
        """Test routing document to doc processing pipeline."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.DOCUMENT,
                confidence="high",
                details={
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                },
            ),
        ):
            result = router.route_from_bytes(b"docx content", "test.docx")

            assert result.classification == FileClassification.DOCUMENT
            assert result.pipeline == Pipeline.DOC_PROCESSING

    def test_route_unknown_to_none(self) -> None:
        """Test routing unknown type to NONE pipeline."""
        router = FileRouter()

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.UNKNOWN,
                confidence="low",
                details={"mime_type": "application/octet-stream"},
            ),
        ):
            result = router.route_from_bytes(b"unknown", "test.bin")

            assert result.classification == FileClassification.UNKNOWN
            assert result.pipeline == Pipeline.NONE

    def test_custom_routing_config(self) -> None:
        """Test using custom routing configuration."""
        custom_routing = {
            FileClassification.IMAGE: Pipeline.DOC_PROCESSING,  # Override
        }
        router = FileRouter(routing_config=custom_routing)

        with patch.object(
            router._classifier,
            "classify_from_bytes",
            return_value=ClassificationResult(
                classification=FileClassification.IMAGE,
                confidence="high",
                details={"mime_type": "image/png"},
            ),
        ):
            result = router.route_from_bytes(b"png", "test.png")

            # Uses custom routing
            assert result.pipeline == Pipeline.DOC_PROCESSING

    def test_get_pipeline_for_classification(self) -> None:
        """Test getting pipeline for a classification."""
        router = FileRouter()

        assert (
            router.get_pipeline_for_classification(
                FileClassification.SCANNED_PDF,
            )
            == Pipeline.OCR
        )
        assert (
            router.get_pipeline_for_classification(
                FileClassification.AUDIO,
            )
            == Pipeline.TRANSCRIPTION
        )
        assert (
            router.get_pipeline_for_classification(
                FileClassification.UNKNOWN,
            )
            == Pipeline.NONE
        )

    def test_is_supported(self) -> None:
        """Test checking if classification is supported."""
        router = FileRouter()

        assert router.is_supported(FileClassification.SCANNED_PDF) is True
        assert router.is_supported(FileClassification.BORN_DIGITAL_PDF) is True
        assert router.is_supported(FileClassification.IMAGE) is True
        assert router.is_supported(FileClassification.AUDIO) is True
        assert router.is_supported(FileClassification.VIDEO) is True
        assert router.is_supported(FileClassification.DOCUMENT) is True
        assert router.is_supported(FileClassification.UNKNOWN) is False

    def test_routing_result_dataclass(self) -> None:
        """Test RoutingResult dataclass structure."""
        result = RoutingResult(
            classification=FileClassification.IMAGE,
            pipeline=Pipeline.OCR,
            confidence="high",
            details={"mime_type": "image/png"},
        )

        assert result.classification == FileClassification.IMAGE
        assert result.pipeline == Pipeline.OCR
        assert result.confidence == "high"
        assert result.details["mime_type"] == "image/png"


# =============================================================================
# Integration Tests
# =============================================================================


class TestRoutingIntegration:
    """Integration tests for the routing pipeline."""

    def test_full_routing_pipeline_pdf(self) -> None:
        """Test full routing pipeline for PDF files."""
        router = FileRouter()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 500

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(
                router._classifier._detector,
                "_detect_magic",
                return_value="application/pdf",
            ),
            patch("pdfplumber.open", return_value=mock_pdf),
        ):
            result = router.route_from_bytes(b"%PDF-1.4", "report.pdf")

            assert result.classification == FileClassification.BORN_DIGITAL_PDF
            assert result.pipeline == Pipeline.DOC_PROCESSING

    def test_full_routing_pipeline_image(self) -> None:
        """Test full routing pipeline for image files."""
        router = FileRouter()

        with patch.object(
            router._classifier._detector,
            "_detect_magic",
            return_value="image/jpeg",
        ):
            result = router.route_from_bytes(b"\xff\xd8\xff", "photo.jpg")

            assert result.classification == FileClassification.IMAGE
            assert result.pipeline == Pipeline.OCR
