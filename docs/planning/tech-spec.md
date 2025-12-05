# Technical Implementation Spec: RAG Processor WebUI

> **Status**: Draft | **Version**: 1.0 | **Updated**: 2025-12-04

## TL;DR

RAG Processor WebUI is a React 18 + FastAPI web application providing authenticated file ingestion for multi-pipeline RAG systems. It uses Cloudflare Access for authentication, Redis + RQ for job queuing, WebSocket for real-time updates, and Docker Compose for deployment.

## 1. Technology Stack

### Core

- **Language**: Python 3.12+ (backend), TypeScript 5.0+ (frontend)
- **Package Manager**: UV (backend), npm (frontend)
- **Backend Framework**: FastAPI 0.109+
- **Frontend Framework**: React 18.2+
- **Build Tool**: Vite 5.0+ (frontend)

### Code Quality

- **Linter**: Ruff (backend), ESLint (frontend)
- **Type Checker**: BasedPyright (backend), TypeScript (frontend)
- **Formatter**: Ruff (backend, 88 chars), Prettier (frontend)
- **Testing**: pytest + pytest-cov (backend), Vitest + React Testing Library (frontend)

### Data Layer

- **Job Queue**: Redis 7+ with Python RQ - See [ADR-002](./adr/adr-002-redis-job-queue.md)
- **Cache**: Redis (shared with job queue)
- **File Storage**: Local filesystem (Docker volume-mounted) for uploads and processing

### Infrastructure

- **CI/CD**: GitHub Actions
- **Container**: Docker + Docker Compose
- **Ingress**: Cloudflare Tunnel (cloudflared)
- **Authentication**: Cloudflare Access with williaby/testing middleware - See [ADR-003](./adr/adr-003-cloudflare-auth.md)

### Key Dependencies

**Backend (Python)**:

```toml
[project.dependencies]
fastapi = ">=0.109.0"
uvicorn = {extras = ["standard"], version = ">=0.25.0"}
python-multipart = ">=0.0.6"  # File upload support
redis = ">=5.0.0"
rq = ">=1.15.0"
pydantic = ">=2.5.0"
pydantic-settings = ">=2.1.0"
httpx = ">=0.26.0"  # Async HTTP client for Projects A-E
python-magic = ">=0.4.27"  # File type detection
pdfplumber = ">=0.10.0"  # PDF text extraction for classification
cloudflare-auth = {git = "https://github.com/williaby/testing.git"}
```

**Frontend (TypeScript)**:

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-dropzone": "^14.2.3",
    "zustand": "^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0"
  }
}
```

## 2. Architecture

### Pattern

**Microservices with API Gateway** - Frontend and gateway are separate services communicating via REST + WebSocket. Gateway orchestrates calls to external processing pipelines (Projects A-E). See [ADR-001](./adr/adr-001-initial-architecture.md)

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE EDGE                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Cloudflare Access (OAuth/SSO)                               │   │
│  │  • JWT generation                                            │   │
│  │  • Session management                                        │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                         │
│  ┌────────────────────────┴─────────────────────────────────────┐   │
│  │  Cloudflare Tunnel (cloudflared)                             │   │
│  │  • Secure ingress (no exposed ports)                         │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
└────────────────────────────┼─────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
┌─────────────▼──────────┐    ┌─────────────▼────────────┐
│   Frontend (rag-ui)    │    │   Gateway API            │
│                        │    │   (FastAPI)              │
│  • React 18            │    │                          │
│  • File upload UI      │◄───┤  • CloudflareAuth        │
│  • Job status display  │    │  • File router           │
│  • WebSocket client    │    │  • Job queue manager     │
│  • Batch management    │    │  • WebSocket server      │
└────────────────────────┘    └──────────┬───────────────┘
                                         │
                      ┌──────────────────┼───────────────────┐
                      │                  │                   │
         ┌────────────▼─────┐  ┌─────────▼────────┐  ┌──────▼──────┐
         │  Redis + RQ      │  │  File Storage    │  │  Projects   │
         │                  │  │  (Docker Volume) │  │  A-E APIs   │
         │  • Job queue     │  │                  │  │             │
         │  • Priority mgmt │  │  • Uploads       │  │  • HTTP     │
         │  • Status cache  │  │  • Results       │  │  • External │
         └──────────────────┘  └──────────────────┘  └─────────────┘
```

### Component Responsibilities

| Component | Purpose | Key Functions |
|-----------|---------|---------------|
| Frontend (rag-ui) | User interface for file upload and monitoring | File upload with drag-and-drop, batch creation, WebSocket status updates, result download |
| Gateway API | Request authentication, routing, orchestration | JWT validation, file type detection, pipeline routing, job queue submission, WebSocket broadcasting |
| Redis + RQ | Asynchronous job processing | Priority queue management, job persistence, retry logic, status tracking |
| RQ Worker | Execute pipeline API calls | Submit files to Projects A-E, poll for completion, update job status, handle errors |
| Cloudflare Access | Authentication and authorization | OAuth flow, JWT issuance, session management, email whitelist enforcement |
| Projects A-E | File processing pipelines | Image IQA (A), Audio transcription (E), Docling processing (B), Fusion (C), Vector storage (D) |

## 3. Data Model

### Core Entities

```python
# Batch: Collection of files uploaded together
class Batch(BaseModel):
    batch_id: str  # UUID
    created_by_email: str  # From CloudflareUser
    created_by_user_id: str
    created_at: datetime
    status: BatchStatus  # queued | processing | completed | failed | partial
    total_files: int
    completed_files: int
    failed_files: int
    target_project_d: str | None  # Project D variant ID for handoff
    metadata: dict[str, Any] | None  # Custom user metadata

# Job: Single file processing task
class Job(BaseModel):
    job_id: str  # UUID
    batch_id: str
    filename: str
    file_path: Path  # Path in upload storage
    file_type: str  # MIME type
    file_size_bytes: int
    classification: FileClassification  # scanned_pdf | born_digital_pdf | image | audio | video | office | text
    routed_to: Pipeline  # project-a | project-e | project-b | project-c
    status: JobStatus  # queued | processing | completed | failed
    priority: Priority  # high | normal | low
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    retry_count: int
    result_path: Path | None  # Path to processed output from Project C
    created_by_email: str
    created_by_user_id: str

# Enums
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class BatchStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some jobs succeeded, some failed

class FileClassification(str, Enum):
    SCANNED_PDF = "scanned_pdf"
    BORN_DIGITAL_PDF = "born_digital_pdf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    OFFICE = "office"
    TEXT = "text"

class Pipeline(str, Enum):
    PROJECT_A = "project-a"  # Image IQA + OCR
    PROJECT_E = "project-e"  # Audio transcription
    PROJECT_B = "project-b"  # Docling processing
    PROJECT_C = "project-c"  # Fusion pipeline

class Priority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
```

### Relationships

- **Batch** → **Job**: One-to-many (one batch contains multiple jobs)
- **Job** → **Pipeline**: Many-to-one (jobs routed to specific pipeline)
- **Batch** → **ProjectD Target**: Many-to-one (batch specifies handoff destination)

## 4. API Specification

### Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | /api/v1/ingest | Upload files for processing | Yes |
| GET | /api/v1/batch/{batch_id} | Get batch status | Yes |
| GET | /api/v1/batch/{batch_id}/jobs | List jobs in batch | Yes |
| GET | /api/v1/job/{job_id} | Get job details | Yes |
| GET | /api/v1/job/{job_id}/result | Download processed result | Yes |
| POST | /api/v1/batch/{batch_id}/handoff | Trigger handoff to Project D | Yes |
| GET | /api/v1/targets | List registered Project D targets | Yes |
| POST | /api/v1/targets/register | Register new Project D target | No (internal) |
| WS | /ws/batch/{batch_id} | Real-time batch status updates | Yes (token in query) |
| GET | /health | Health check | No |
| GET | /metrics | Prometheus metrics | No |

### Request/Response Format

#### POST /api/v1/ingest

Request (multipart/form-data):

```http
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="files"; filename="document.pdf"
Content-Type: application/pdf

[binary data]
------WebKitFormBoundary
Content-Disposition: form-data; name="priority"

high
------WebKitFormBoundary
Content-Disposition: form-data; name="target_project_d"

project-d-variant-a
------WebKitFormBoundary--
```

Response (application/json):

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_by": "user@example.com",
  "created_at": "2025-12-04T10:30:00Z",
  "status": "queued",
  "total_files": 1,
  "jobs": [
    {
      "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "filename": "document.pdf",
      "file_type": "application/pdf",
      "file_size_bytes": 2048576,
      "classification": "born_digital_pdf",
      "routed_to": "project-b",
      "status": "queued",
      "priority": "high"
    }
  ],
  "status_url": "/api/v1/batch/550e8400-e29b-41d4-a716-446655440000",
  "websocket_url": "wss://host/ws/batch/550e8400-e29b-41d4-a716-446655440000"
}
```

#### WebSocket Message Format

Client → Server (connection):

```
wss://host/ws/batch/{batch_id}?cf_access_token={JWT}
```

Server → Client (status update):

```json
{
  "type": "batch_update",
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "completed_files": 5,
  "total_files": 10,
  "jobs": [
    {
      "job_id": "...",
      "status": "completed",
      "completed_at": "2025-12-04T10:35:23Z"
    }
  ]
}
```

## 5. Security

### Authentication

**Method**: Cloudflare Access with JWT validation - See [ADR-003](./adr/adr-003-cloudflare-auth.md)

**Flow**:

1. User navigates to WebUI URL
2. Cloudflare Access intercepts request → OAuth login
3. After successful auth, Cloudflare adds `Cf-Access-Jwt-Assertion` header
4. Request forwarded to gateway via Cloudflare Tunnel
5. CloudflareAuthMiddleware validates JWT signature and audience
6. User context (email, user_id) available in all API endpoints

### Authorization

**Current**: All authenticated users have equal access (no role-based access control in MVP)

**Future** (Phase 2): Evaluate Cloudflare Access groups for admin vs. user roles

### Data Protection

- **At Rest**: Uploaded files stored on Docker volume with filesystem permissions (0600)
- **In Transit**: All traffic via Cloudflare Tunnel (TLS 1.3)
- **Sensitive Data**:
  - JWT tokens never logged
  - User emails logged only in audit fields
  - File contents not logged (only metadata: filename, size, MIME type)

### Input Validation

- **File Upload**:
  - Max file size: 500MB (enforced by FastAPI)
  - Allowed MIME types validated via magic bytes
  - Filename sanitization (reject path traversal characters: `..`, `/`, `\`)
- **API Parameters**: Pydantic validation on all request bodies and query parameters

## 6. Error Handling

### Strategy

Fail Fast for User Errors, Graceful Degradation for External Services:

- User input errors (invalid file types, missing parameters) → immediate 400 Bad Request
- External pipeline failures → retry up to 3 times with exponential backoff, mark job as failed if exhausted

### Error Codes

| Code | HTTP Status | Meaning | User Action |
|------|-------------|---------|-------------|
| AUTH_REQUIRED | 401 | Missing or invalid JWT | Re-authenticate via Cloudflare |
| FORBIDDEN | 403 | User not authorized | Contact admin |
| INVALID_FILE_TYPE | 400 | Unsupported file format | Upload PDF, image, audio, or Office doc |
| FILE_TOO_LARGE | 413 | File exceeds 500MB | Reduce file size or split |
| BATCH_NOT_FOUND | 404 | Invalid batch_id | Check batch_id correctness |
| JOB_NOT_FOUND | 404 | Invalid job_id | Check job_id correctness |
| PIPELINE_ERROR | 500 | Downstream pipeline failure | Retry or contact support |
| QUEUE_FULL | 503 | Job queue at capacity | Wait and retry |

### Logging

- **Format**: Structured JSON via Python `logging` with correlation IDs
- **Levels**:
  - DEBUG: File type detection details, routing decisions
  - INFO: Job lifecycle events (queued → processing → completed)
  - WARNING: Retry attempts, slow external API calls
  - ERROR: Pipeline failures, unexpected exceptions
- **Sensitive Data**: Never log JWT tokens, file contents, or full user objects (log email only)

### Example Log Entry

```json
{
  "timestamp": "2025-12-04T10:30:00Z",
  "level": "INFO",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "job_queued",
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "filename": "document.pdf",
  "routed_to": "project-b",
  "user_email": "user@example.com"
}
```

## 7. Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| File Upload Latency | <2s for 10MB file | Time from POST /api/v1/ingest to 201 response |
| WebSocket Latency | <500ms | Time from job status change to client receiving WS message |
| Concurrent Users | 100 | Simulate 100 users uploading files simultaneously (load test) |
| Job Throughput | 1000 files/hour | Aggregate across all pipelines (measured via RQ queue metrics) |
| Frontend Bundle Size | <500KB gzipped | `vite build` output size |
| API Response Time (p95) | <200ms | GET /api/v1/batch/{id} (excluding file upload endpoints) |

## 8. Testing Strategy

### Coverage Target

- **Minimum**: 80% line coverage (enforced by pytest --cov-fail-under=80)
- **Critical Paths**: 100% coverage for file routing logic, authentication middleware, job queue submission

### Test Types

- **Unit Tests**:
  - Backend: File type detection, PDF classification, job queue logic (using fakeredis)
  - Frontend: React components with mocked API/WebSocket (Vitest + React Testing Library)
- **Integration Tests**:
  - Full cycle: File upload → queue submission → worker processing → WebSocket broadcast (using real Redis in Docker)
  - Authentication flow: Mocked Cloudflare JWT validation
- **E2E Tests**:
  - User workflow: Upload file → monitor status → download result (Playwright)
  - Test against staging environment with real Cloudflare Access

### Test Fixtures

- Sample files: PDF (scanned + born-digital), images (JPEG, PNG), audio (MP3, WAV), Office docs (DOCX)
- Mock external APIs: Projects A-E endpoints with configurable latency and failure rates

## 9. Deployment

### Docker Compose Services

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      - rag-network

  gateway:
    build: ./gateway
    expose:
      - "8000"
    environment:
      CLOUDFLARE_TEAM_DOMAIN: ${CLOUDFLARE_TEAM_DOMAIN}
      CLOUDFLARE_AUDIENCE_TAG: ${CLOUDFLARE_AUDIENCE_TAG}
      REDIS_URL: redis://redis:6379
    volumes:
      - ${RAG_DATA_PATH}/uploads:/data/uploads
    depends_on:
      - redis

  worker:
    build: ./gateway
    command: rq worker high default low
    environment:
      REDIS_URL: redis://redis:6379
    volumes:
      - ${RAG_DATA_PATH}/uploads:/data/uploads
    depends_on:
      - redis

  rag-ui:
    build: ./rag-ui
    expose:
      - "3000"
    environment:
      VITE_API_URL: /api

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data

networks:
  rag-network:
    driver: bridge

volumes:
  redis-data:
```

## Related Documents

- [Project Vision](./project-vision.md)
- [Architecture Decisions](./adr/)
  - [ADR-001: React + FastAPI Architecture](./adr/adr-001-initial-architecture.md)
  - [ADR-002: Redis Job Queue](./adr/adr-002-redis-job-queue.md)
  - [ADR-003: Cloudflare Authentication](./adr/adr-003-cloudflare-auth.md)
- [Development Roadmap](./roadmap.md)
- [WebUI Specification](../webui_spec.md) (original requirements)
