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

### From PyPI

```bash
pip install rag-processor
```

### From Source

```bash
git clone https://github.com/ByronWilliamsCPA/rag-processor
cd rag_processor
uv sync --all-extras
```

## Library Usage

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
