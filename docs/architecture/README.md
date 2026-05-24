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

- **Architecture Decision Records (ADRs)**: Stored under `docs/ADRs/`. Each ADR documents a
  significant design choice, its context, consequences, and alternatives considered.
- **System diagrams**: Will be added here as the system grows (component diagrams, sequence
  diagrams, data-flow diagrams).

## Overview

RAG Processor is a Python package that provides a RAG (Retrieval-Augmented Generation)
pipeline with a FastAPI backend integration. Key architectural layers:

| Layer | Location | Responsibility |
|-------|----------|---------------|
| Core | `src/rag_processor/core/` | Configuration, exception hierarchy |
| Middleware | `src/rag_processor/middleware/` | Security headers (OWASP), request correlation |
| Utilities | `src/rag_processor/utils/` | Structured logging, financial precision helpers |

## Related Docs

- [Architecture Decision Records](../ADRs/README.md): Individual ADRs with decision rationale.
- [Project Vision](../planning/project-vision.md): Problem statement and success metrics.
- [Tech Spec](../planning/tech-spec.md): Detailed technical specification.

## Contributing

When adding significant architectural changes, create a new ADR in `docs/ADRs/` following
the template at `docs/ADRs/adr-template.md` before or alongside the implementation PR.
