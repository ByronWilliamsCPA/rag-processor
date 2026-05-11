#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamscpa.dev>
# SPDX-License-Identifier: MIT
"""Fuzz harness for FileTypeDetector.

Tests the MIME type detection logic with random binary input to detect
crashes, hangs, and unexpected behavior in magic byte parsing.
"""

from __future__ import annotations

import sys

import atheris


def test_one_input(data: bytes) -> None:
    """Fuzz target for FileTypeDetector.detect_from_bytes().

    Args:
        data: Random byte sequence from the fuzzer.
    """
    # Import inside function to ensure proper coverage tracking
    from rag_processor.routing.detector import FileTypeDetector

    detector = FileTypeDetector()

    try:
        # Test MIME detection with random bytes
        detector.detect_from_bytes(data)
    except Exception:
        # Expected exceptions from malformed input are acceptable
        # Atheris will catch actual crashes/hangs
        pass

    try:
        # Also test with filename hint
        detector.detect_from_bytes(data, filename="test.pdf")
    except Exception:
        pass


def main() -> None:
    """Entry point for fuzzing."""
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
