#!/bin/bash -eu
# ClusterFuzzLite Build Script
# Compiles Python fuzz targets with coverage instrumentation
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python-lang/

# Install the project so fuzz targets can import from rag_processor
pip3 install .

# compile_python_fuzzer (provided by base-builder-python:v1) creates an
# Atheris-instrumented binary with LibFuzzer entry points that the CFL
# run_fuzzers action can discover and execute. Plain pyinstaller ELFs are
# not recognized by the CFL Python runner.
for fuzzer in $(find $SRC/rag_processor/fuzz -name 'fuzz_*.py'); do
    fuzzer_basename=$(basename -s .py "$fuzzer")
    echo "Building fuzzer: $fuzzer_basename"
    compile_python_fuzzer "$fuzzer"
done

# List what was created
echo "=== Fuzz targets in $OUT ==="
ls -la "$OUT"/fuzz_* 2>/dev/null || echo "No fuzz targets found"
