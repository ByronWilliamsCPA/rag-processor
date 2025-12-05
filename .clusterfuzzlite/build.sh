#!/bin/bash -eu
# ClusterFuzzLite Build Script
# Compiles Python fuzz targets with coverage instrumentation
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python/

# Install the package with fuzzing support
pip3 install -e .

# Copy fuzz targets to the output directory
# Each Python file in fuzz/ directory becomes a fuzz target
for fuzzer in $SRC/rag_processor/fuzz/fuzz_*.py; do
    if [ -f "$fuzzer" ]; then
        fuzzer_basename=$(basename -s .py $fuzzer)
        cp $fuzzer $OUT/$fuzzer_basename
        chmod +x $OUT/$fuzzer_basename
    fi
done
