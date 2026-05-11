#!/bin/bash -eu
# ClusterFuzzLite Build Script
# Compiles Python fuzz targets with coverage instrumentation
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python-lang/

# Install the project
pip3 install .

# Build each fuzzer as a single self-contained binary named fuzz_<name>
for fuzzer in $(find $SRC/rag_processor/fuzz -name 'fuzz_*.py'); do
    fuzzer_basename=$(basename -s .py "$fuzzer")

    echo "Building fuzzer: $fuzzer_basename"

    # --onefile creates a single ELF at $OUT/<name> that bad-build-check can validate
    pyinstaller --distpath "$OUT" --onefile --name "$fuzzer_basename" "$fuzzer"

    chmod +x "$OUT/$fuzzer_basename"
done

# List what was created
echo "=== Fuzz targets in $OUT ==="
ls -la "$OUT"/fuzz_* 2>/dev/null || echo "No fuzz targets found"
