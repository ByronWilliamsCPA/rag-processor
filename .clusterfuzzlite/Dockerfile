# ClusterFuzzLite Build Container
# This Dockerfile builds the fuzz targets for ClusterFuzzLite
#
# Reference: https://google.github.io/clusterfuzzlite/build-integration/python-lang/

FROM gcr.io/oss-fuzz-base/base-builder-python:v1

# Copy project source
COPY . $SRC/rag_processor
WORKDIR $SRC/rag_processor

# Install dependencies for fuzzing
# atheris is pre-installed in base-builder-python, reinstalling pins a known version
RUN pip3 install --upgrade pip && \
    pip3 install atheris && \
    pip3 install .

# Copy build script
COPY .clusterfuzzlite/build.sh $SRC/
