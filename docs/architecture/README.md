---
title: "Architecture Documentation"
schema_type: common
status: published
owner: core-maintainer
purpose: "Index of architecture documentation for RAG Processor."
tags:
  - architecture
  - overview
---

This directory contains architecture documentation for RAG Processor.

## Contents

- **[Pipeline Level 0](pipeline-level-0.md)**: Shared page showing how the five Foundry pipeline repositories link
  together. This repository is Ingest. See also the [Level 0 pointer](diagrams/level-0/index.md).
- **[Level 1: Ingest](diagrams/level-1/index.md)**: Components, data flow, interfaces, and build status of this service.
- **Architecture Decision Records (ADRs)**: The current ADR is
  [adr-001-react-fastapi-architecture.md](../planning/adr/adr-001-react-fastapi-architecture.md). `docs/ADRs/` holds
  only the ADR template and index.

## Overview

RAG Processor is the Ingest gateway and router of the Foundry pipeline: a FastAPI backend with a React upload and
status UI. Key architectural layers:

| Layer | Location | Responsibility |
|-------|----------|---------------|
| Core | `src/rag_processor/core/` | Configuration, exception hierarchy |
| Middleware | `src/rag_processor/middleware/` | Security headers (OWASP), request correlation |
| Utilities | `src/rag_processor/utils/` | Structured logging, time helpers |
| API, auth, routing, queue, websocket | `src/rag_processor/{api,auth,routing,queue,websocket}/` | See Level 1 |

## Related Docs

- [ADR-001](../planning/adr/adr-001-react-fastapi-architecture.md): React and FastAPI architecture decision.
- [Project Vision](../planning/project-vision.md): Problem statement and success metrics.
- [Tech Spec](../planning/tech-spec.md): Detailed technical specification.

## Contributing

When adding significant architectural changes, create a new ADR in `docs/planning/adr/`
following the template at `docs/ADRs/adr-template.md` before or alongside the implementation PR.
