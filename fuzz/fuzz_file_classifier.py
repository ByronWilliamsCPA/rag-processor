#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamscpa.dev>
# SPDX-License-Identifier: MIT
"""Fuzz harness for FileClassifier.

Tests the PDF classification logic with random binary input to detect
crashes, hangs, and unexpected behavior in file parsing.
"""

from __future__ import annotations

import sys

import atheris


def test_one_input(data: bytes) -> None:
    """Fuzz target for FileClassifier.classify_from_bytes().

    Args:
        data: Random byte sequence from the fuzzer.
    """
    # Import inside function to ensure proper coverage tracking
    from rag_processor.routing.classifier import FileClassifier

    classifier = FileClassifier()

    try:
        # Test with raw bytes - this exercises PDF parsing code
        classifier.classify_from_bytes(data, filename="fuzz_test.pdf")
    except Exception:
        # Expected exceptions from malformed input are acceptable
        # Atheris will catch actual crashes/hangs
        pass


def main() -> None:
    """Entry point for fuzzing."""
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
