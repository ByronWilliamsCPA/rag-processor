#!/bin/bash -eu
# ClusterFuzzLite Build Script
# Compiles Python fuzz targets with coverage instrumentation
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python-lang/

# Install the project
pip3 install .

# Build each fuzzer
for fuzzer in $(find $SRC/rag_processor/fuzz -name 'fuzz_*.py'); do
    fuzzer_basename=$(basename -s .py "$fuzzer")
    fuzzer_package=${fuzzer_basename}.pkg

    echo "Building fuzzer: $fuzzer_basename"

    # Package the fuzzer using pyinstaller for reproducibility
    pyinstaller --distpath "$OUT" --onefile --name "$fuzzer_package" "$fuzzer"

    # Create the execution wrapper script
    # Note: No LD_PRELOAD for pure Python code (no C extensions)
    cat > "$OUT/$fuzzer_basename" << EOF
#!/bin/bash
# Wrapper script for $fuzzer_basename fuzzer
# LF
this_dir=\$(dirname "\$0")
exec "\$this_dir/$fuzzer_package" "\$@"
EOF
    chmod +x "$OUT/$fuzzer_basename"
done

# List what was created
echo "=== Fuzz targets in $OUT ==="
ls -la "$OUT"/fuzz_* 2>/dev/null || echo "No fuzz targets found"
