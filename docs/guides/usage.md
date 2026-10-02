---
title: "Usage"
schema_type: common
status: published
owner: core-maintainer
purpose: "Usage guide for RAG Processor."
tags:
  - guide
  - usage
---

This guide covers common usage patterns for RAG Processor.

## Installation

### From Source

```bash
git clone https://github.com/ByronWilliamsCPA/rag-processor
cd rag-processor
uv sync --all-extras
```

## Library Usage

> **Status**: RAG Processor is a service used through its HTTP API (`POST /api/v1/ingest`, batch and job status
> endpoints, `WS /ws/batch/{batch_id}`), not a published library. The snippets below only exercise the package
> internals. See the [README](https://github.com/ByronWilliamsCPA/rag-processor#readme) for running the stack.

### Basic Import

```python
from rag_processor import __version__

print(f"Version: {__version__}")
```

### Logging

```python
from rag_processor.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging(level="DEBUG", json_logs=False)

# Get a logger
logger = get_logger(__name__)
logger.info("Hello from RAG Processor")
```
