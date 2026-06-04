"""Tests for configurable classification thresholds."""

from __future__ import annotations

from rag_processor.core.config import settings
from rag_processor.routing.classifier import FileClassifier


class TestClassifierThresholds:
    """FileClassifier thresholds default to settings and accept overrides."""

    def test_defaults_come_from_settings(self) -> None:
        clf = FileClassifier()
        assert clf._scanned_chars_threshold == settings.pdf_scanned_chars_threshold
        assert (
            clf._scanned_high_confidence_chars
            == settings.pdf_scanned_high_confidence_chars
        )
        assert (
            clf._digital_high_confidence_chars
            == settings.pdf_digital_high_confidence_chars
        )

    def test_overrides_are_applied(self) -> None:
        clf = FileClassifier(
            scanned_chars_threshold=5,
            scanned_high_confidence_chars=2,
            digital_high_confidence_chars=500,
        )
        assert clf._scanned_chars_threshold == 5
        assert clf._scanned_high_confidence_chars == 2
        assert clf._digital_high_confidence_chars == 500
