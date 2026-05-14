#!/usr/bin/env python
"""Performance benchmark script for RAG Processor.

This script runs benchmarks on key operations and outputs JSON metrics
for use with the performance regression workflow.

Usage:
    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --iterations 100
    uv run python scripts/benchmark.py --warmup 5 --iterations 50

Output format (JSON):
    {
        "p50_ms": 12.5,
        "p95_ms": 45.2,
        "p99_ms": 78.5,
        "mean_ms": 18.3,
        "min_ms": 8.1,
        "max_ms": 125.0,
        "throughput_ops": 55.2,
        "total_iterations": 100,
        "benchmarks": {
            "file_classification": {...},
            "file_routing": {...},
            "json_serialization": {...}
        }
    }
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any

# Suppress all logging during benchmarks for clean JSON output
# Set before any imports that configure logging
os.environ["LOG_LEVEL"] = "CRITICAL"
logging.disable(logging.CRITICAL)

# Configure structlog to be silent (must be before module imports)
import structlog

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
)

# Benchmark targets
from rag_processor.models.job import FileClassification, Pipeline
from rag_processor.routing.classifier import ClassificationResult, FileClassifier
from rag_processor.routing.router import FileRouter, RoutingResult


@dataclass
class BenchmarkResult:
    """Results from a single benchmark."""

    name: str
    iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    std_dev_ms: float
    throughput_ops: float


def percentile(data: list[float], p: float) -> float:
    """Calculate the p-th percentile of data.

    Args:
        data: List of values.
        p: Percentile (0-100).

    Returns:
        The p-th percentile value.
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def run_benchmark(
    name: str,
    func: Any,
    iterations: int,
    warmup: int = 10,
) -> BenchmarkResult:
    """Run a benchmark and collect timing statistics.

    Args:
        name: Benchmark name.
        func: Function to benchmark (called with no arguments).
        iterations: Number of iterations to run.
        warmup: Number of warmup iterations (not measured).

    Returns:
        BenchmarkResult with timing statistics.
    """
    # Warmup phase
    for _ in range(warmup):
        func()

    # Force garbage collection before measurement
    gc.collect()

    # Measurement phase
    timings: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        timings.append(elapsed)

    # Calculate statistics
    mean = statistics.mean(timings)
    std_dev = statistics.stdev(timings) if len(timings) > 1 else 0.0
    total_time_sec = sum(timings) / 1000

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        p50_ms=round(percentile(timings, 50), 3),
        p95_ms=round(percentile(timings, 95), 3),
        p99_ms=round(percentile(timings, 99), 3),
        mean_ms=round(mean, 3),
        min_ms=round(min(timings), 3),
        max_ms=round(max(timings), 3),
        std_dev_ms=round(std_dev, 3),
        throughput_ops=round(iterations / total_time_sec, 2) if total_time_sec > 0 else 0,
    )


# =============================================================================
# Benchmark Fixtures
# =============================================================================


def create_sample_pdf_content() -> bytes:
    """Create minimal PDF content for benchmarking.

    Returns:
        Bytes representing a minimal valid PDF.
    """
    # Minimal valid PDF with some text
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000360 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
435
%%EOF"""
    return pdf_content


def create_sample_image_content() -> bytes:
    """Create minimal PNG content for benchmarking.

    Returns:
        Bytes representing a minimal valid PNG.
    """
    # Minimal 1x1 white PNG
    return bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,  # PNG signature
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,  # IHDR chunk
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,
            0x54,  # IDAT chunk
            0x08,
            0xD7,
            0x63,
            0xF8,
            0xFF,
            0xFF,
            0xFF,
            0x00,
            0x05,
            0xFE,
            0x02,
            0xFE,
            0xA3,
            0x56,
            0x76,
            0x38,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,  # IEND chunk
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )


def create_sample_text_content() -> bytes:
    """Create sample text content for benchmarking.

    Returns:
        Bytes representing text content.
    """
    return b"This is a sample text document for benchmarking purposes.\n" * 100


# =============================================================================
# Benchmark Functions
# =============================================================================


def benchmark_file_classification(iterations: int, warmup: int) -> BenchmarkResult:
    """Benchmark file classification.

    Tests the FileClassifier.classify_from_bytes method with various file types.
    """
    classifier = FileClassifier()
    pdf_content = create_sample_pdf_content()
    image_content = create_sample_image_content()
    text_content = create_sample_text_content()

    # Rotate through different file types
    contents = [
        (pdf_content, "test.pdf"),
        (image_content, "test.png"),
        (text_content, "test.txt"),
    ]
    idx = 0

    def classify_func() -> ClassificationResult:
        nonlocal idx
        content, filename = contents[idx % len(contents)]
        idx += 1
        return classifier.classify_from_bytes(content, filename)

    return run_benchmark("file_classification", classify_func, iterations, warmup)


def benchmark_file_routing(iterations: int, warmup: int) -> BenchmarkResult:
    """Benchmark file routing.

    Tests the FileRouter.route_from_bytes method.
    """
    router = FileRouter()
    pdf_content = create_sample_pdf_content()
    image_content = create_sample_image_content()
    text_content = create_sample_text_content()

    contents = [
        (pdf_content, "test.pdf"),
        (image_content, "test.png"),
        (text_content, "test.txt"),
    ]
    idx = 0

    def route_func() -> RoutingResult:
        nonlocal idx
        content, filename = contents[idx % len(contents)]
        idx += 1
        return router.route_from_bytes(content, filename)

    return run_benchmark("file_routing", route_func, iterations, warmup)


def benchmark_json_serialization(iterations: int, warmup: int) -> BenchmarkResult:
    """Benchmark JSON serialization of classification results.

    Tests serialization performance for API responses.
    """
    # Sample data to serialize
    sample_data = {
        "classification": FileClassification.BORN_DIGITAL_PDF.value,
        "pipeline": Pipeline.DOC_PROCESSING.value,
        "confidence": "high",
        "details": {
            "total_pages": 10,
            "total_chars": 5000,
            "chars_per_page": 500.0,
            "threshold": 50,
            "mime_type": "application/pdf",
        },
        "metadata": {
            "filename": "document.pdf",
            "size_bytes": 102400,
            "processed_at": "2025-01-15T10:30:00Z",
        },
    }

    def serialize_func() -> str:
        return json.dumps(sample_data)

    return run_benchmark("json_serialization", serialize_func, iterations, warmup)


def benchmark_routing_lookup(iterations: int, warmup: int) -> BenchmarkResult:
    """Benchmark routing table lookup.

    Tests the classification-to-pipeline mapping lookup.
    """
    router = FileRouter()
    classifications = list(FileClassification)
    idx = 0

    def lookup_func() -> Pipeline:
        nonlocal idx
        classification = classifications[idx % len(classifications)]
        idx += 1
        return router.get_pipeline_for_classification(classification)

    return run_benchmark("routing_lookup", lookup_func, iterations, warmup)


def benchmark_classification_result_creation(iterations: int, warmup: int) -> BenchmarkResult:
    """Benchmark ClassificationResult dataclass creation.

    Tests object instantiation performance.
    """

    def create_func() -> ClassificationResult:
        return ClassificationResult(
            classification=FileClassification.BORN_DIGITAL_PDF,
            confidence="high",
            details={
                "total_pages": 10,
                "total_chars": 5000,
                "chars_per_page": 500.0,
            },
        )

    return run_benchmark("classification_result_creation", create_func, iterations, warmup)


# =============================================================================
# Main Entry Point
# =============================================================================


def run_all_benchmarks(iterations: int, warmup: int) -> dict[str, Any]:
    """Run all benchmarks and return aggregated results.

    Args:
        iterations: Number of iterations per benchmark.
        warmup: Number of warmup iterations.

    Returns:
        Dictionary with aggregated benchmark results.
    """
    benchmarks = [
        benchmark_file_classification,
        benchmark_file_routing,
        benchmark_json_serialization,
        benchmark_routing_lookup,
        benchmark_classification_result_creation,
    ]

    results: list[BenchmarkResult] = []

    for benchmark_func in benchmarks:
        result = benchmark_func(iterations, warmup)
        results.append(result)

    # Aggregate statistics (use the primary benchmark - file_routing)
    primary_result = next((r for r in results if r.name == "file_routing"), results[0])

    # Calculate overall statistics
    all_p95 = [r.p95_ms for r in results]
    all_throughput = [r.throughput_ops for r in results]

    return {
        # Primary metrics (used by regression detection)
        "p50_ms": primary_result.p50_ms,
        "p95_ms": primary_result.p95_ms,
        "p99_ms": primary_result.p99_ms,
        "mean_ms": primary_result.mean_ms,
        "min_ms": primary_result.min_ms,
        "max_ms": primary_result.max_ms,
        "throughput_ops": primary_result.throughput_ops,
        # Aggregated metrics
        "total_iterations": iterations * len(benchmarks),
        "avg_p95_all_benchmarks_ms": round(statistics.mean(all_p95), 3),
        "avg_throughput_all_benchmarks_ops": round(statistics.mean(all_throughput), 2),
    }


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(
        description="Run performance benchmarks for RAG Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=100,
        help="Number of iterations per benchmark (default: 100)",
    )
    parser.add_argument(
        "--warmup",
        "-w",
        type=int,
        default=10,
        help="Number of warmup iterations (default: 10)",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON output",
    )

    args = parser.parse_args()

    # Run benchmarks
    results = run_all_benchmarks(args.iterations, args.warmup)

    # Output JSON (required format for performance regression workflow)
    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print(json.dumps(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
