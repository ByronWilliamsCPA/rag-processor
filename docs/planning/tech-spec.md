---
title: "Technical Implementation Spec: RAG Processor WebUI"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Define the technical architecture, data model, APIs, and security requirements for RAG Processor WebUI."
tags:
  - planning
  - tech_spec
  - architecture
component: Strategy
source: "Initial project planning"
---

> **Status**: Draft | **Version**: 1.0 | **Updated**: 2025-12-05

## TL;DR

RAG Processor WebUI is a React 18 + FastAPI microservices architecture with Redis job queue, providing authenticated file ingestion for RAG pipelines. Stack: Python 3.12, TypeScript, Docker Compose deployment, targeting 100 concurrent users with sub-2s WebSocket latency.

## 1. Technology Stack

### Core

- **Language**: Python 3.12+ (backend), TypeScript 5.0+ (frontend)
- **Package Manager**: UV (backend), pnpm (frontend)
- **Backend Framework**: FastAPI 0.109+
- **Frontend Framework**: React 18.2+ with Vite 5.0+

### Code Quality

- **Linter**: Ruff (backend), ESLint (frontend)
- **Type Checker**: BasedPyright strict mode (backend), TypeScript (frontend)
- **Formatter**: Ruff 88 chars (backend), Prettier (frontend)
- **Testing**: pytest + pytest-cov 80%+ (backend), Vitest + React Testing Library (frontend)

### Data Layer

- **Job Queue**: Redis 7+ with Python RQ - See [ADR-001](./adr/adr-001-react-fastapi-architecture.md#redis-high-availability-mvp)
- **Cache**: Redis (shared with job queue)
- **File Storage**: Docker volumes for uploads and results

### Infrastructure

- **CI/CD**: GitHub Actions
- **Container**: Docker + Docker Compose
- **Ingress**: Cloudflare Tunnel (cloudflared)
- **Authentication**: Cloudflare Access JWT - See [ADR-001](./adr/adr-001-react-fastapi-architecture.md#security-model)
- **Monitoring**: Prometheus + Grafana

### Key Dependencies

**Backend**:

```toml
fastapi = ">=0.109.0"
uvicorn = {extras = ["standard"], version = ">=0.25.0"}
python-multipart = ">=0.0.6"
redis = ">=5.0.0"
rq = ">=1.15.0"
httpx = ">=0.26.0"
python-magic = ">=0.4.27"
pdfplumber = ">=0.10.0"
```

**Frontend**:

```json
{
  "react": "^18.2.0",
  "react-dropzone": "^14.2.3",
  "zustand": "^4.4.0",
  "vite": "^5.0.0"
}
```

## 2. Architecture

### Pattern

Microservices with API Gateway - See [ADR-001](./adr/adr-001-react-fastapi-architecture.md)

### Component Diagram

```text
┌────────────────────────────────────────┐
│      Cloudflare Edge                   │
│  ┌──────────────────────────────────┐  │
│  │  Access (OAuth) + Tunnel         │  │
│  └───────────────┬──────────────────┘  │
└──────────────────┼─────────────────────┘
                   │
        ┌──────────┴────────┐
        │                   │
┌───────▼────────┐  ┌───────▼────────┐
│  React SPA     │  │  FastAPI       │
│  (Nginx)       │◄─┤  Gateway       │
│                │  │                │
│  • Upload UI   │  │  • Auth        │
│  • WebSocket   │  │  • Router      │
└────────────────┘  │  • Job Queue   │
                    └───────┬────────┘
                            │
            ┌───────────────┼──────────────┐
            │               │              │
    ┌───────▼───┐  ┌────────▼────┐  ┌─────▼──────┐
    │  Redis    │  │  File       │  │  External  │
    │  + RQ     │  │  Storage    │  │  Pipelines │
    └───────────┘  └─────────────┘  └────────────┘
```

### Component Responsibilities

| Component | Purpose | Key Functions |
| --------- | ------- | ------------- |
| React SPA | File upload and status monitoring | Drag-drop upload, batch management, WebSocket client |
| FastAPI Gateway | Authentication, routing, orchestration | JWT validation, file classification, job queue, WebSocket server |
| Redis + RQ | Job queue with priority and persistence | Priority queues (high/normal/low), event log for WebSocket replay |
| RQ Worker | Execute pipeline API calls | Submit files, poll status, publish events |
| Cloudflare Access | SSO authentication | OAuth, JWT issuance |

## 3. Data Model

### Core Entities

```python
from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from uuid import UUID

class Batch(BaseModel):
    batch_id: UUID
    created_by_email: str
    status: BatchStatus  # queued | processing | completed | failed | partial
    total_files: int
    completed_files: int = 0
    target_vector_store: str | None = None

class Job(BaseModel):
    job_id: UUID
    batch_id: UUID
    filename: str
    file_type: str  # MIME type
    classification: FileClassification  # scanned_pdf | born_digital_pdf | image | audio
    routed_to: Pipeline  # ocr | transcription | doc_processing | fusion
    status: JobStatus  # queued | processing | completed | failed
    priority: Priority  # high | normal | low
    error_message: str | None = None
    retry_count: int = 0

class FileClassification(str, Enum):
    SCANNED_PDF = "scanned_pdf"
    BORN_DIGITAL_PDF = "born_digital_pdf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class Pipeline(str, Enum):
    OCR = "ocr"
    TRANSCRIPTION = "transcription"
    DOC_PROCESSING = "doc_processing"
    FUSION = "fusion"
```

### Relationships

- Batch → Job: One-to-many
- Job → Pipeline: Many-to-one
- Batch → Vector Store: Many-to-one

### Storage

- **Redis**: Batch/job metadata, event logs, RQ queues
- **File System**: `/data/uploads/{batch_id}/`, `/data/results/{batch_id}/{job_id}/`

## 4. API Specification

### Endpoints

| Method | Path | Purpose | Auth |
| ------ | ---- | ------- | ---- |
| POST | /api/v1/ingest | Upload files | Yes (JWT) |
| GET | /api/v1/batch/{id} | Get batch status | Yes |
| GET | /api/v1/batch/{id}/jobs | List jobs | Yes |
| GET | /api/v1/job/{id} | Get job details | Yes |
| GET | /api/v1/job/{id}/result | Download result | Yes |
| POST | /api/v1/batch/{id}/handoff | Trigger vector store handoff | Yes |
| WS | /ws/batch/{id} | Real-time status | Yes (token param) |
| GET | /health | Health check | No |
| GET | /metrics | Prometheus metrics | No |

### Request/Response Examples

**POST /api/v1/ingest**:

Request (multipart/form-data):

```http
Cf-Access-Jwt-Assertion: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: multipart/form-data

files=<binary>
priority=high
target_vector_store=qdrant-prod
```

Response:

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_by": "user@example.com",
  "status": "queued",
  "total_files": 1,
  "jobs": [{
    "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "filename": "document.pdf",
    "classification": "born_digital_pdf",
    "routed_to": "doc_processing",
    "status": "queued"
  }],
  "websocket_url": "wss://host/ws/batch/550e8400-e29b-41d4-a716-446655440000"
}
```

**WebSocket** (`/ws/batch/{id}?cf_access_token={JWT}&last_event_id={N}`):

```json
{
  "event_id": 42,
  "type": "job_update",
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "completed",
  "result_url": "/api/v1/job/7c9e6679-7425-40de-944b-e07fc1f90ae7/result"
}
```

## 5. Security

### Authentication

- **Method**: Cloudflare Access JWT validation
- **Flow**: OAuth at edge → JWT in `Cf-Access-Jwt-Assertion` header → FastAPI validates signature using JWKS
- **Details**: See [ADR-001 Security Model](./adr/adr-001-react-fastapi-architecture.md#security-model)

### Authorization

- **MVP**: All authenticated users can upload
- **Phase 2**: Role-based access via JWT `cf_groups` claim

### Data Protection

- **At Rest**: Docker volume permissions (0600), Redis password, AOF encryption
- **In Transit**: TLS 1.3 (Cloudflare Tunnel), internal Docker network unencrypted
- **Sensitive Data**: JWT never logged, email logged in `created_by` only

### Input Validation

- **File types**: Whitelist (`.pdf`, `.docx`, `.png`, `.jpg`, `.mp3`, `.mp4`, `.wav`)
- **Size limits**: 100MB/file, 500MB/batch
- **MIME validation**: Magic byte scanning with `python-magic`
- **Details**: See [ADR-001](./adr/adr-001-react-fastapi-architecture.md#security-model)

## 6. Error Handling

### Strategy

Fail fast for user errors, graceful degradation for external services - See [ADR-001](./adr/adr-001-react-fastapi-architecture.md#error-handling-strategy)

### Error Codes

| Code | HTTP | Meaning | Action |
| ---- | ---- | ------- | ------ |
| AUTH_REQUIRED | 401 | Missing/invalid JWT | Re-auth via Cloudflare |
| INVALID_FILE_TYPE | 400 | Unsupported format | Use PDF/image/audio/Office |
| FILE_TOO_LARGE | 413 | Exceeds size limit | Reduce file size |
| PIPELINE_ERROR | 500 | External pipeline failed | Auto-retried 3x |
| QUEUE_FULL | 503 | Queue at capacity | Wait and retry |

### Logging

- **Format**: Structured JSON with correlation IDs
- **Levels**: DEBUG (routing), INFO (lifecycle), WARNING (retries), ERROR (failures)
- **Sensitive**: Never log JWT, file contents, full user objects

## 7. Performance Requirements

| Metric | Target | Measurement |
| ------ | ------ | ----------- |
| File upload (10MB) | less than 2s | 95th percentile (Nginx logs) |
| WebSocket latency | less than 2s | Status change to client receipt |
| Concurrent users | 100+ | Locust load test |
| Job throughput | 1000+ files/hour | Aggregate across pipelines |
| Gateway CPU | less than 70% | Docker stats, 1min avg |
| Gateway memory | less than 512MB | Docker RSS |

**Details**: See [ADR-001 Performance Budget](./adr/adr-001-react-fastapi-architecture.md#performance-budget)

## 8. Testing Strategy

### Coverage

- **Minimum**: 80% (enforced by pytest --cov-fail-under=80)
- **Critical paths**: 100% (file routing, auth, queue)

### Test Types

- **Unit**: File detection, PDF classification, job queue (fakeredis), React components
- **Integration**: Upload → queue → worker → WebSocket broadcast, mocked pipeline APIs (respx)
- **E2E**: Playwright tests against staging with real Cloudflare Access

### Fixtures

- Sample files: PDFs (scanned/born-digital), images, audio, Office docs
- Mock pipelines with success/failure/timeout scenarios

## 9. Deployment

### Docker Compose

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}

  gateway:
    build: ./gateway
    environment:
      CLOUDFLARE_TEAM_DOMAIN: ${TEAM}
      CLOUDFLARE_AUDIENCE_TAG: ${AUDIENCE}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379
    volumes:
      - upload-data:/data/uploads
      - result-data:/data/results

  worker:
    build: ./gateway
    command: rq worker high default low
    volumes:
      - upload-data:/data/uploads
      - result-data:/data/results

  rag-ui:
    build: ./rag-ui

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
```

## Related Documents

- [Project Vision](./project-vision.md): Problem, scope, success metrics
- [ADR-001: Architecture](./adr/adr-001-react-fastapi-architecture.md): Detailed architecture decisions
- [Development Roadmap](./roadmap.md): Phased implementation plan
