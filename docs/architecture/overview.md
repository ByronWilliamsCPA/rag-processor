---
title: "Architecture Overview"
schema_type: common
status: published
owner: core-maintainer
purpose: "High-level system architecture overview for the RAG Processor pipeline."
tags:
  - architecture
  - overview
---

> For formal design decisions with rationale, see the ADR log at
> [docs/ADRs/](../ADRs/).

## System Summary

RAG Processor is a FastAPI application that sits at the center of a
retrieval-augmented generation pipeline. A React frontend communicates with it
over REST endpoints and WebSockets. Document ingestion, vector routing, and async
job processing are the three primary data flows.

## Entry Points

| Path | Purpose |
|------|---------|
| `src/rag_processor/main.py` | FastAPI application factory and lifespan wiring |
| `src/rag_processor/api/ingest.py` | Document ingestion endpoints |
| `src/rag_processor/api/batch.py` | Batch processing endpoints |
| `src/rag_processor/api/health.py` | Health and readiness probes |
| `src/rag_processor/api/user.py` | User-facing API surface |
| `src/rag_processor/websocket/` | WebSocket handlers for real-time updates |

## Core Subsystems

### Configuration

`src/rag_processor/core/config.py` uses Pydantic Settings. All tuneable
parameters are sourced from environment variables or a `.env` file. No secrets
are hard-coded.

### Exception Hierarchy

`src/rag_processor/core/exceptions.py` defines a typed exception tree. All
application code raises from this hierarchy rather than bare `Exception` or
framework exceptions. This ensures consistent error serialization at API
boundaries.

| Exception | HTTP status | Use case |
|-----------|-------------|----------|
| `ValidationError` | 422 | Input schema or business rule violation |
| `ResourceNotFoundError` | 404 | Missing document, job, or user |
| `AuthenticationError` | 401 | Missing or invalid credentials |
| `AuthorizationError` | 403 | Insufficient permissions |
| `ExternalServiceError` | 502 | Upstream LLM or vector DB failure |
| `DatabaseError` | 500 | Persistence layer failure |
| `BusinessLogicError` | 422 | Domain rule violation |

### Middleware Stack

Middleware is registered in `src/rag_processor/main.py` in this order:

1. **CorrelationMiddleware** (`middleware/correlation.py`): generates or
   propagates a UUID correlation ID from incoming headers
   (`X-Correlation-ID`, `X-Request-ID`, `X-Trace-ID`, `X-Span-ID`). The ID is
   available anywhere in the request context via `get_correlation_id()`.

2. **SecurityMiddleware** (`middleware/security.py`): adds OWASP-recommended
   HTTP response headers (CSP, HSTS, X-Frame-Options, etc.) and enforces
   request-level guards.

### Structured Logging

`src/rag_processor/utils/logging.py` configures structlog for JSON output. Every
log record emitted inside a request context automatically includes the
correlation ID. Background jobs call `set_correlation_id(generate_correlation_id())`
before doing any logging so their records are equally traceable.

### Async Queue

`src/rag_processor/queue/` wraps RQ (Redis Queue) for background job dispatch:

- `client.py`: enqueue helper with typed job payloads
- `jobs.py`: worker-side job implementations
- `redis_store.py`: Redis connection factory with health-check support

### Caching and Pipeline Configuration

- `core/cache.py`: Redis-backed cache layer for pipeline results
- `core/pipeline_config.py`: per-pipeline tuneable parameters loaded at startup

### Auth

`src/rag_processor/auth/` contains authentication helpers. The security
middleware integrates with this layer for request-level enforcement.

## Data Flow: Document Ingestion

```
Client POST /ingest
  -> SecurityMiddleware (header enforcement)
  -> CorrelationMiddleware (attach correlation ID)
  -> IngestRouter
  -> validate input (ValidationError on failure)
  -> enqueue RQ job (queue/client.py)
  -> return 202 Accepted with job ID

RQ Worker
  -> pick up job (queue/jobs.py)
  -> chunk + embed document
  -> write vectors to store
  -> update job status in Redis
```

## Deployment

The application is containerized via `Dockerfile` and `docker-compose.yml`.
Environment variables control all runtime configuration. The CI pipeline builds,
lints, type-checks, and tests the image before any deployment artifact is
produced.

## Related Documents

- Architecture Decision Records: [docs/ADRs/](../ADRs/)
- Security policy: [SECURITY.md](../../SECURITY.md)
- Known vulnerabilities: [docs/known-vulnerabilities.md](../known-vulnerabilities.md)
- Agent conventions: [AGENTS.md](../../AGENTS.md)
