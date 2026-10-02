---
title: "RAG Processor"
schema_type: common
status: published
owner: core-maintainer
purpose: "Documentation home page for RAG Processor."
tags:
  - documentation
  - home
---

Ingest gateway and router for the Foundry RAG pipeline: FastAPI backend with a React upload and status UI

## Quick Start

```bash
# Install from source with development dependencies
uv sync --all-extras
```

## Features

- Multi-file ingest endpoint with file type checks, scanned vs born-digital classification, and routing
- Batch and job status over REST and WebSocket
- Redis and RQ queue (off by default) and Cloudflare Access JWT auth
- React upload and status UI
- Docker support

The step that hands files to Prepare-Doc and Prepare-Audio is not built yet; see the
[Level 1 architecture](architecture/diagrams/level-1/index.md).

## Documentation

- [User Guide](guides/overview.md) - Getting started and usage
- [API Reference](api-reference.md) - Complete API documentation
- [Development](development/architecture.md) - Architecture and contributing
- [Project](project/roadmap.md) - Roadmap and changelog

## License

This project is licensed under the MIT License - see the [LICENSE](project/license.md) file for details.
