"""Pipeline routing module.

This package contains components for detecting file types,
classifying files, and routing them to appropriate processing pipelines.
"""

from __future__ import annotations

from rag_processor.routing.classifier import FileClassifier
from rag_processor.routing.detector import FileTypeDetector
from rag_processor.routing.router import FileRouter

__all__ = [
    "FileClassifier",
    "FileRouter",
    "FileTypeDetector",
]
