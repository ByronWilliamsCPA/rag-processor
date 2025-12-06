"""File type detection using magic bytes.

Provides MIME type detection using python-magic library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import magic

from rag_processor.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DetectionResult:
    """Result of file type detection.

    Attributes:
        mime_type: Detected MIME type.
        extension: Recommended file extension.
        confidence: Confidence level (high, medium, low).
        magic_match: Whether magic bytes matched.
        extension_match: Whether file extension matched MIME type.
    """

    mime_type: str
    extension: str
    confidence: str
    magic_match: bool
    extension_match: bool


# Common MIME type to extension mapping
MIME_EXTENSIONS: dict[str, str] = {
    # PDF
    "application/pdf": ".pdf",
    # Images
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    # Audio
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-wav": ".wav",
    # Video
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    # Documents
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    # Text
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "text/html": ".html",
    "application/json": ".json",
    "application/xml": ".xml",
}

# Reverse mapping: extension to MIME types
EXTENSION_MIMES: dict[str, list[str]] = {}
for mime_type, ext in MIME_EXTENSIONS.items():
    if ext not in EXTENSION_MIMES:
        EXTENSION_MIMES[ext] = []
    EXTENSION_MIMES[ext].append(mime_type)


class FileTypeDetector:
    """Detects file types using magic bytes and file extensions.

    Uses python-magic for magic byte scanning with file extension
    as a fallback for ambiguous cases.

    Example:
        detector = FileTypeDetector()
        result = detector.detect_from_bytes(file_content, "document.pdf")
        print(f"MIME: {result.mime_type}, Confidence: {result.confidence}")
    """

    def __init__(self) -> None:
        """Initialize the file type detector."""
        self._magic = magic.Magic(mime=True)

    def detect_from_bytes(
        self,
        content: bytes,
        filename: str | None = None,
    ) -> DetectionResult:
        """Detect file type from content bytes.

        Args:
            content: File content as bytes.
            filename: Optional filename for extension-based fallback.

        Returns:
            DetectionResult with detected type and confidence.
        """
        # Detect via magic bytes
        magic_mime = self._detect_magic(content)
        magic_ext = MIME_EXTENSIONS.get(magic_mime, "")

        # Get extension from filename
        file_ext = ""
        if filename:
            file_ext = Path(filename).suffix.lower()

        # Check if extension matches magic detection
        extension_match = False
        if file_ext and magic_mime:
            expected_mimes = EXTENSION_MIMES.get(file_ext, [])
            extension_match = magic_mime in expected_mimes

        # Determine confidence
        if magic_mime and magic_mime != "application/octet-stream":
            confidence = "high" if extension_match else "medium"
        elif file_ext in EXTENSION_MIMES:
            # Fall back to extension-based detection
            magic_mime = EXTENSION_MIMES[file_ext][0]
            confidence = "low"
        else:
            confidence = "low"

        logger.debug(
            "File type detected",
            mime_type=magic_mime,
            extension=magic_ext or file_ext,
            confidence=confidence,
            filename=filename,
        )

        return DetectionResult(
            mime_type=magic_mime,
            extension=magic_ext or file_ext,
            confidence=confidence,
            magic_match=magic_mime != "application/octet-stream",
            extension_match=extension_match,
        )

    def detect_from_path(self, file_path: str | Path) -> DetectionResult:
        """Detect file type from file path.

        Args:
            file_path: Path to the file.

        Returns:
            DetectionResult with detected type and confidence.
        """
        path = Path(file_path)
        with path.open("rb") as f:
            content = f.read(8192)  # Read first 8KB for detection

        return self.detect_from_bytes(content, path.name)

    def _detect_magic(self, content: bytes) -> str:
        """Detect MIME type using magic bytes.

        Args:
            content: File content bytes.

        Returns:
            Detected MIME type string.
        """
        return self._magic.from_buffer(content)

    def is_pdf(self, content: bytes) -> bool:
        """Check if content is a PDF file.

        Args:
            content: File content bytes.

        Returns:
            True if content is PDF.
        """
        result = self.detect_from_bytes(content)
        return result.mime_type == "application/pdf"

    def is_image(self, content: bytes) -> bool:
        """Check if content is an image file.

        Args:
            content: File content bytes.

        Returns:
            True if content is an image.
        """
        result = self.detect_from_bytes(content)
        return result.mime_type.startswith("image/")

    def is_audio(self, content: bytes) -> bool:
        """Check if content is an audio file.

        Args:
            content: File content bytes.

        Returns:
            True if content is audio.
        """
        result = self.detect_from_bytes(content)
        return result.mime_type.startswith("audio/")

    def is_video(self, content: bytes) -> bool:
        """Check if content is a video file.

        Args:
            content: File content bytes.

        Returns:
            True if content is a video.
        """
        result = self.detect_from_bytes(content)
        return result.mime_type.startswith("video/")

    def is_document(self, content: bytes) -> bool:
        """Check if content is an office document.

        Args:
            content: File content bytes.

        Returns:
            True if content is a document.
        """
        result = self.detect_from_bytes(content)
        document_types = {
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        return result.mime_type in document_types
