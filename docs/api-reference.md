---
title: "API Reference"
schema_type: common
status: published
owner: core-maintainer
purpose: "API documentation for RAG Processor."
tags:
  - api
  - reference
---

API documentation for RAG Processor.

> **Status**: This page documents only the `core.config` and `utils.logging` modules. The HTTP API (ingest, batch and
> job status, user, health, WebSocket) is served with interactive docs at `/docs` when the app runs; the routes are in
> `src/rag_processor/api/` and `src/rag_processor/websocket/`.

## Core Module

::: rag_processor.core.config
    options:
      show_root_heading: true
      members_order: source

## Utils Module

### Logging

::: rag_processor.utils.logging
    options:
      show_root_heading: true
      members_order: source
