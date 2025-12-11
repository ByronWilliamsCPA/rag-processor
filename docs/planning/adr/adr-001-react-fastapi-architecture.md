---
title: "ADR-001: React + FastAPI Microservices Architecture"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Document the decision to use React + FastAPI microservices architecture for RAG Processor WebUI."
tags:
  - planning
  - architecture
  - decisions
component: Strategy
source: "Initial architecture planning"
---

> **Status**: Accepted
> **Date**: 2025-12-05

## TL;DR

We will use a microservices architecture with React 18 frontend and FastAPI gateway to orchestrate file ingestion across external processing pipelines, chosen for rapid development with existing Python/TypeScript expertise and straightforward Docker deployment.

## Context

### Problem

RAG Processor WebUI needs to:

1. Accept multi-file uploads from authenticated users
2. Route files to appropriate external processing pipelines (OCR, transcription, document processing, fusion)
3. Monitor job status in real-time via WebSocket
4. Hand off processed results to configurable vector storage systems

The system is an **orchestration layer** between users and existing pipeline infrastructure, not a monolithic application implementing the pipelines themselves.

### Constraints

- **Technical**: Single developer, 4-6 week MVP timeline, must integrate with existing Cloudflare Access, Docker Compose deployment
- **Business**: No budget for managed services (e.g., AWS Lambda, GCP Cloud Run), must run on self-hosted infrastructure
- **Operational**: Support 100+ concurrent users, 1000+ files/hour throughput, <2s WebSocket latency

### Significance

Architecture choice determines:

- Development velocity (time to MVP)
- Operational complexity (deployment, scaling, debugging)
- Integration surface with external pipelines
- Cost of future changes (adding new pipelines, scaling beyond 100 users)

**Cost of wrong choice**: Delayed MVP, poor WebSocket performance, difficult pipeline integration, or expensive rewrites when scaling beyond initial 100 users.

## Decision

**We will use a React 18 frontend with FastAPI backend gateway in a microservices architecture because it provides the fastest path to MVP with familiar technologies while maintaining clear separation between UI, orchestration, and processing concerns.**

### Rationale

1. **Rapid Development**: React + FastAPI are well-known technologies with existing expertise, minimizing learning curve
2. **Clean Separation**: Frontend (UI) → Gateway (orchestration) → External Pipelines (processing) creates clear boundaries
3. **WebSocket Support**: FastAPI has native async WebSocket support, critical for real-time status updates
4. **Docker-Ready**: Both React (Nginx static serve) and FastAPI (Uvicorn) have standard containerization patterns
5. **Scalability Path**: Can horizontally scale gateway instances behind load balancer when exceeding 100 concurrent users

## Options Considered

### Option 1: React + FastAPI Microservices ✓

**Architecture**:

```text
[React SPA] ← HTTP/WS → [FastAPI Gateway] ← HTTP → [External Pipelines]
                              ↓
                         [Redis Queue]
```

**Pros**:

- ✅ **Fast development**: Familiar tech stack, rich ecosystem (React libraries, FastAPI middleware)
- ✅ **Native async**: FastAPI async/await simplifies WebSocket and HTTP client code
- ✅ **Clear boundaries**: Frontend, gateway, and pipelines are independently deployable
- ✅ **WebSocket-first**: FastAPI WebSocket support is production-ready
- ✅ **Type safety**: TypeScript frontend, Python type hints backend

**Cons**:

- ❌ **More moving parts**: Requires coordinating React build, FastAPI server, Redis queue
- ❌ **Deployment complexity**: Multiple containers vs single monolith

### Option 2: Next.js Full-Stack

**Architecture**:

```text
[Next.js App (React + API Routes)] ← HTTP → [External Pipelines]
                ↓
          [Redis Queue]
```

**Pros**:

- ✅ **Single codebase**: Frontend and backend in one TypeScript project
- ✅ **Simplified deployment**: Single Node.js container

**Cons**:

- ❌ **Learning curve**: Next.js API routes and server-side rendering unfamiliar
- ❌ **WebSocket awkward**: Next.js API routes don't natively support WebSocket (requires custom server)
- ❌ **Python expertise lost**: Backend would be TypeScript instead of Python
- ❌ **Redis integration**: Node.js Redis clients less mature than Python's rq library

**Why not chosen**: WebSocket complexity and loss of Python backend expertise outweigh single-codebase benefits.

### Option 3: FastAPI Monolith with Jinja Templates

**Architecture**:

```text
[FastAPI + Jinja2 Templates] ← HTTP → [External Pipelines]
            ↓
       [Redis Queue]
```

**Pros**:

- ✅ **Simplicity**: Single Python application, server-side rendering
- ✅ **Fewer dependencies**: No frontend build toolchain

**Cons**:

- ❌ **Poor UX**: Server-side rendering causes page refreshes, slow drag-and-drop experience
- ❌ **WebSocket UI complexity**: Real-time updates require JavaScript anyway, defeating server-side benefits
- ❌ **Outdated pattern**: Modern file upload UX (drag-drop, progress bars) difficult with Jinja templates

**Why not chosen**: Cannot achieve required real-time WebSocket UX with server-side rendering.

### Option 4: Serverless (AWS Lambda + S3 + API Gateway)

**Architecture**:

```text
[React S3 Static] → [API Gateway] → [Lambda Functions] → [External Pipelines]
```

**Pros**:

- ✅ **Auto-scaling**: AWS handles scaling beyond 100 users
- ✅ **Low operational burden**: No server management

**Cons**:

- ❌ **Cost**: Lambda + API Gateway charges exceed self-hosted budget
- ❌ **WebSocket limitations**: API Gateway WebSocket connections have 2-hour timeout
- ❌ **Cold starts**: Lambda cold starts (100-500ms) add latency to file uploads
- ❌ **Vendor lock-in**: Migration away from AWS requires full rewrite

**Why not chosen**: Exceeds budget constraint, WebSocket limitations, vendor lock-in.

## Consequences

### Positive

- ✅ **Fast MVP delivery**: Using familiar React + FastAPI accelerates development, meeting 4-6 week timeline
- ✅ **Modern UX**: React enables drag-and-drop file upload, real-time progress bars, smooth WebSocket updates
- ✅ **Testability**: Clear boundaries enable unit testing (React components), integration testing (FastAPI endpoints), E2E testing (Playwright)
- ✅ **Debugging ease**: Separate frontend/backend logs, can debug independently

### Trade-offs

- ⚠️ **Deployment complexity**: Requires orchestrating 3+ containers (React Nginx, FastAPI, Redis, RQ worker) vs single monolith
  - **Mitigation**: Docker Compose manages multi-container orchestration, single `docker-compose up` command
- ⚠️ **Horizontal scaling requires load balancer**: When exceeding 100 users, need Nginx/HAProxy in front of multiple FastAPI instances
  - **Mitigation**: Deferred to Phase 2, acceptable for MVP with <100 users
- ⚠️ **CORS configuration**: React development server (localhost:3000) → FastAPI (localhost:8000) requires CORS middleware
  - **Mitigation**: FastAPI CORS middleware is standard, one-line configuration

### Technical Debt

- **WebSocket scaling**: Single FastAPI instance handles all WebSocket connections. Beyond 100 concurrent connections, need Redis Pub/Sub to broadcast status across multiple gateway instances.
  - **Address when**: User load approaches 80-90 concurrent connections
- **Static file serving**: Development uses React dev server, production uses Nginx. Requires separate Docker build stages.
  - **Address when**: Preparing production deployment (end of MVP)

## Implementation

### Components Affected

1. **Frontend (rag-ui)**:
   - React 18 app built with Vite
   - Drag-and-drop file upload component (react-dropzone)
   - WebSocket client for status updates
   - Deployed as static files via Nginx container

2. **Backend Gateway (gateway API)**:
   - FastAPI application with async endpoints
   - POST /api/v1/ingest (file upload)
   - WebSocket /ws/batch/{id} (status updates)
   - HTTP clients to external pipeline APIs
   - Deployed via Uvicorn in Docker container

3. **Job Queue (Redis + RQ)**:
   - Redis container for job persistence
   - Python RQ worker container for async job execution
   - Priority queues (high, normal, low)

4. **Deployment (Docker Compose)**:
   - Cloudflare Tunnel (cloudflared) for ingress
   - React Nginx (static files)
   - FastAPI Gateway
   - RQ Worker
   - Redis

### Integration Contracts

**External Pipeline API:**

- **Protocol**: HTTP REST
- **Authentication**: Bearer token (shared secret per pipeline, stored in Docker secrets)
- **Request format**: `POST /process` with multipart form-data

  ```json
  {
    "file": "<binary>",
    "job_id": "uuid",
    "priority": "high|normal|low",
    "callback_url": "https://gateway/api/v1/callbacks/pipeline"
  }
  ```

- **Response**: `{"job_id": "uuid", "status": "queued", "status_url": "/status/{job_id}"}`
- **Status polling**: `GET /status/{job_id}` returns `{"status": "processing|completed|failed", "progress": 0.75, "result_url": "/results/{job_id}"}`
- **Polling interval**: 5 seconds

**Vector Storage Interface:**

- **Protocols supported**: Qdrant HTTP API, Milvus gRPC (configurable per batch)
- **Configuration**: Environment variables (`VECTOR_STORE_TYPE`, `VECTOR_STORE_URL`, `VECTOR_STORE_API_KEY`)
- **Handoff mechanism**: POST processed embeddings to vector store `/collections/{collection_name}/points` endpoint
- **Retry logic**: 3 attempts with exponential backoff (2s, 4s, 8s)

### Security Model

**Authentication:**

- Cloudflare Access handles SSO (SAML/OIDC) at edge
- JWT injected via `Cf-Access-Jwt-Assertion` header on all requests
- FastAPI validates JWT signature using Cloudflare public keys (fetched from JWKS endpoint, cached 1 hour)
- User context (email, user_id) extracted from JWT claims and attached to request state

**Authorization:**

- **MVP**: All authenticated users can upload files (no role-based access control)
- **Phase 2**: Role-based pipeline access via JWT custom claims (`cf_groups`: `["admins", "data-engineers"]`)

**Input Validation:**

- **File types**: Whitelist (`.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.mp3`, `.mp4`, `.wav`)
- **Size limits**: 100MB per file, 500MB per batch (enforced by FastAPI `max_content_length`)
- **Filename sanitization**: Remove path traversal characters (`..`, `/`, `\`), limit to 255 chars
- **MIME type validation**: Magic byte scanning with `python-magic` (reject if MIME mismatch with extension)
- **Malware scanning**: Deferred to Phase 2 (ClamAV integration planned)

**Secrets Management:**

- **Development**: `.env` file (gitignored, template in `.env.example`)
- **Production**: Docker secrets (mounted at `/run/secrets/`)
  - `PIPELINE_BEARER_TOKEN_OCR`
  - `PIPELINE_BEARER_TOKEN_TRANSCRIPTION`
  - `REDIS_PASSWORD`
  - `CLOUDFLARE_TEAM_DOMAIN`
  - `CLOUDFLARE_AUDIENCE_TAG`
- **JWT public keys**: Fetched from Cloudflare JWKS endpoint (`https://{team}.cloudflareaccess.com/cdn-cgi/access/certs`), cached in-memory

### Error Handling Strategy

**Pipeline Failures:**

- **Retry**: 3 attempts with exponential backoff (1s, 2s, 4s)
- **Timeout**: 5 minutes per pipeline HTTP call (configurable via `PIPELINE_TIMEOUT_SECONDS`)
- **User notification**: WebSocket message `{"type": "job_failed", "job_id": "uuid", "error": "Pipeline returned 500", "retry_count": 2}`
- **Dead letter queue**: After 3 failures, job moved to `failed` queue for manual inspection

**WebSocket Disconnection:**

- **Client reconnect**: Exponential backoff (1s, 2s, 4s, max 30s), retry up to 10 times
- **Server state**: Job status persisted in Redis (survives reconnect), key: `job:{job_id}:events`
- **Idempotency**: Client sends `last_event_id` on reconnect, server resumes stream from Redis event log
- **Graceful shutdown**: SIGTERM handler broadcasts `{"type": "server_restarting"}` to all connections, waits 5s before closing

**Redis Failure:**

- **Impact**: Job queue unavailable, in-flight jobs lost if not persisted
- **Mitigation**: Redis AOF persistence mode (`appendfsync everysec`), Docker volume backup to host filesystem
- **Recovery**: Restart Redis container, replays AOF log to restore state
- **User experience**: During outage, file uploads return `503 Service Unavailable` with retry-after header
- **Monitoring**: Health check endpoint (`GET /health`) returns `{"status": "unhealthy"}` if Redis connection fails

**Network Partitions:**

- **Gateway → Pipeline**: HTTP client timeout (5min), retry logic catches transient failures
- **Gateway → Redis**: Connection pool with health checks (1s interval), circuit breaker opens after 3 consecutive failures
- **Client → Gateway**: Browser retry + exponential backoff on 5xx errors

### WebSocket Resilience

**Session Persistence:**

- Job events stored in Redis list: `RPUSH job:{job_id}:events '{"event_id": 1, "type": "status_update", "data": {...}}'`
- Client sends `last_event_id` parameter on WebSocket connect: `ws://host/ws/batch/{id}?last_event_id=42`
- Server resumes from Redis: `LRANGE job:{job_id}:events {last_event_id + 1} -1`
- Event deduplication: Server tracks sent event IDs per connection (in-memory LRU cache, 5min TTL)

**Graceful Shutdown:**

- SIGTERM handler:
  1. Stop accepting new WebSocket connections
  2. Broadcast `{"type": "server_restarting", "reconnect_after_seconds": 5}` to all connections
  3. Wait 5 seconds for clients to disconnect
  4. Close remaining connections with WebSocket close frame (code 1012: Service Restart)
  5. Shutdown FastAPI gracefully
- Client behavior: On close code 1012, auto-reconnect after 5 seconds

**Connection Limits:**

- Max WebSocket connections: 200 per FastAPI instance (configurable via `MAX_WS_CONNECTIONS`)
- Exceeded limit: Return HTTP 503 with `Retry-After: 60` header on WebSocket upgrade request
- Monitoring: Prometheus metric `websocket_active_connections` (alert if >180 for 5min)

### Performance Budget

| Operation | Target | Measurement |
| --------- | ------ | ----------- |
| File upload (10MB) | less than 2s | 95th percentile (Nginx access logs) |
| WebSocket latency | less than 2s | Job status change to client receipt (custom instrumentation) |
| Queue depth | less than 100 jobs | Redis `LLEN high:queue` under load |
| Gateway CPU (single instance) | less than 70% | Docker stats, 1min average |
| Gateway memory (single instance) | less than 512MB | Docker stats, resident set size |
| RQ worker memory | less than 1GB | Per-worker process RSS |
| Redis memory | less than 2GB | `INFO memory` used_memory_human |

**Load Testing:**

- **Tool**: Locust
- **Scenario**: 100 concurrent users, each uploading 10 files/hour (mix of PDFs, images, audio)
- **Duration**: 1 hour sustained load
- **Pass criteria**:
  - All performance targets met
  - Zero 5xx errors
  - <1% 4xx errors (excluding intentional validation failures)
  - WebSocket reconnect success rate >99%

### Redis High Availability (MVP)

**Persistence:**

- **Mode**: AOF (Append-Only File) with `appendfsync everysec` (balance durability + performance)
- **Backup**: Docker volume mounted to host filesystem (`/var/lib/redis/data`), daily snapshots via cron
- **Recovery**: On container restart, Redis replays AOF log (typically <10s for 1GB AOF file)
- **Data retention**: Job events TTL 7 days (`EXPIRE job:{job_id}:events 604800`)

**Not Implemented in MVP:**

- Redis Sentinel (automatic failover to replica)
- Redis Cluster (horizontal sharding for >10GB datasets)
- **Address in Phase 2** if:
  - Redis memory exceeds 8GB (add Sentinel replica)
  - Queue depth consistently exceeds 1000 jobs (consider cluster)

### Pipeline Adapter Pattern

**Design:**

- Abstract `PipelineAdapter` interface:

  ```python
  class PipelineAdapter(ABC):
      @abstractmethod
      async def submit_job(self, file: UploadFile, job_id: str) -> dict: ...
      @abstractmethod
      async def check_status(self, pipeline_job_id: str) -> JobStatus: ...
      @abstractmethod
      async def fetch_result(self, pipeline_job_id: str) -> bytes: ...
  ```

- Concrete adapters: `OCRAdapter`, `TranscriptionAdapter`, `DocumentProcessingAdapter`, `FusionAdapter`
- Configuration: YAML file (`config/pipelines.yaml`) maps file types to adapter classes

**Example Configuration:**

```yaml
pipelines:
  - name: ocr
    adapter: OCRAdapter
    url: http://ocr-service:8080
    bearer_token_secret: PIPELINE_BEARER_TOKEN_OCR
    file_types: [.pdf, .png, .jpg]
    timeout_seconds: 300
  - name: transcription
    adapter: TranscriptionAdapter
    url: http://whisper-service:8000
    bearer_token_secret: PIPELINE_BEARER_TOKEN_TRANSCRIPTION
    file_types: [.mp3, .mp4, .wav]
    timeout_seconds: 600
```

**Benefit:** New pipelines added via configuration + concrete adapter implementation, no changes to core routing logic.

### Testing Strategy

- **Unit**:
  - React: Component tests with Vitest + React Testing Library
  - FastAPI: Endpoint tests with pytest + httpx AsyncClient
  - Coverage requirement: 80%+

- **Integration**:
  - **Scenarios**:
    1. Happy path: Single file → OCR pipeline → vector store handoff
    2. Batch upload: 10 mixed files → multiple pipelines → status aggregation
    3. Pipeline failure: External API 500 → retry 3x → job marked failed
    4. WebSocket reconnect: Disconnect mid-job → reconnect with `last_event_id` → resume stream
    5. Cloudflare Auth: Invalid JWT → 401 Unauthorized
  - Mock external pipeline APIs with configurable latency/failures (using `respx` library)
  - Test Cloudflare Access JWT validation with fake JWKS endpoint

- **E2E**:
  - Playwright tests: User authentication → file upload → status monitoring → result download
  - Run against staging environment with real Cloudflare Access

### Validation Instrumentation

**Metrics Collection:**

- **Tool**: Prometheus + Grafana (Docker Compose stack)
- **WebSocket latency**:
  - Custom timer: Job status change in RQ worker → Redis PUBLISH → FastAPI broadcast → client receipt
  - Instrumentation: Client sends acknowledgment with `event_id` + `client_received_timestamp`
  - Server calculates latency: `client_received_timestamp - server_sent_timestamp`
  - Metric: `histogram('websocket_event_latency_seconds')`
- **File upload duration**: Nginx access logs + FastAPI middleware timer (start: request received, end: 201 response)
- **Queue depth**: Redis metrics exporter (`oliver006/redis_exporter`) exposes `LLEN` for each priority queue
- **Error rates**: FastAPI middleware increments `counter('http_requests_total', labels=['status_code', 'method', 'path'])`

**Dashboards:**

- **Upload Performance**: File upload duration histogram, bytes uploaded/sec
- **Job Queue**: Queue depth by priority, job processing time, success/failure rate
- **WebSocket Health**: Active connections, event latency, reconnect rate
- **System Resources**: CPU, memory, network I/O per container

## Validation

### Success Criteria

- [ ] MVP deployed to staging within 4 weeks
- [ ] WebSocket latency <2 seconds (measured from job status change to client receipt)
- [ ] 100 concurrent users supported (load test with Locust)
- [ ] File upload completes in <2 seconds for 10MB file
- [ ] All integration tests passing with >80% coverage

### Review Schedule

- **Initial**: End of Phase 0 (Week 1) - Re-evaluate if Docker Compose setup exceeds 1 day
- **Ongoing**: After Phase 1 (Week 4) - Review WebSocket scaling approach if approaching 80 concurrent users

## Related

- [Project Vision](../project-vision.md#solution-overview): Defines key capabilities
- [Tech Spec](../tech-spec.md): Will detail API contracts and data models
- [Roadmap](../roadmap.md): Phase 0 includes Docker Compose setup
