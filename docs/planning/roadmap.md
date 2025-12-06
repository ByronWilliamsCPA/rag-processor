# Development Roadmap: RAG Processor WebUI

<!-- markdownlint-disable MD024 -->

> **Status**: Active | **Updated**: 2025-12-05

## TL;DR

Building a React + FastAPI file ingestion WebUI for RAG pipelines in 4 phases over 6 weeks: Foundation (Week 1), Core MVP (Weeks 2-4), Enhancement (Week 5), Polish (Week 6).

## Timeline Overview

```text
Phase 0: Foundation    ████████░░░░░░░░░░░░░░░░░░░░ (Week 1)  - Setup
Phase 1: MVP Core      ░░░░░░░░████████████████░░░░ (Weeks 2-4) - Core features
Phase 2: Enhancement   ░░░░░░░░░░░░░░░░░░░░████████ (Week 5) - Additional features
Phase 3: Polish        ░░░░░░░░░░░░░░░░░░░░░░░░████ (Week 6) - Testing & docs
```

## Milestones

| Milestone | Target | Status | Dependencies |
| --------- | ------ | ------ | ------------ |
| M0: Dev Environment Ready | Week 1 | ⏸️ Planned | None |
| M1: Authentication Working | Week 2 | ⏸️ Planned | M0 |
| M2: File Upload + Routing | Week 3 | ⏸️ Planned | M1 |
| M3: Real-Time Status | Week 4 | ⏸️ Planned | M2 |
| M4: MVP Complete | End of Week 4 | ⏸️ Planned | M3 |
| M5: Vector Store Handoff | Week 5 | ⏸️ Planned | M4 |
| M6: Production Ready | Week 6 | ⏸️ Planned | M5 |

---

## Phase 0: Foundation (Week 1)

### Phase Objective

Establish development environment, Docker Compose infrastructure, and CI/CD pipeline.

### Deliverables

- [ ] Docker Compose with all services (cloudflared, gateway, worker, rag-ui, Redis)
- [ ] UV dependencies locked (FastAPI, Redis, RQ)
- [ ] React + Vite project scaffolded
- [ ] GitHub Actions CI configured (lint, test, type-check)
- [ ] Pre-commit hooks installed
- [ ] Local dev guide in README

### Success Criteria

- ✅ `docker-compose up` starts all services successfully
- ✅ Gateway health check returns 200
- ✅ CI pipeline passes on main branch
- ✅ Developer can clone → run locally in <15 minutes

### Tasks

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Create Docker Compose with Redis, gateway, worker, rag-ui | 3 | ⏸️ |
| Configure UV dependencies (FastAPI, Redis, RQ) | 2 | ⏸️ |
| Set up Vite React project with TypeScript + Tailwind | 2 | ⏸️ |
| Configure GitHub Actions CI (test, lint, type-check) | 2 | ⏸️ |
| Install pre-commit hooks (Ruff, BasedPyright, markdownlint) | 1 | ⏸️ |
| Write local dev guide in README | 2 | ⏸️ |

---

## Phase 1: MVP Core (Weeks 2-4)

### Objective

Implement minimum viable product: authenticated file upload, automatic routing, real-time WebSocket status.

### Deliverables

- [ ] Cloudflare Access authentication (JWT validation)
- [ ] Multi-file upload API + React UI
- [ ] File type detection and pipeline routing
- [ ] Redis job queue with priority
- [ ] WebSocket status updates
- [ ] Basic error handling

### Success Criteria

- ✅ User uploads PDF → routed to correct pipeline
- ✅ WebSocket shows live updates every 2-5 seconds
- ✅ Failed jobs display error messages
- ✅ Job queue persists across restart
- ✅ 80%+ test coverage on core logic

### User Stories

#### US-001: User Authentication

**As a** data engineer
**I want** to authenticate via Cloudflare Access
**So that** only authorized users can submit files

**Acceptance Criteria**:

- [ ] Unauthenticated users redirected to Cloudflare OAuth
- [ ] Authenticated users see upload interface
- [ ] User email displayed in UI header
- [ ] JWT validation rejects tampered tokens (401)

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Integrate Cloudflare JWT middleware in FastAPI | 2 | ⏸️ |
| Configure CLOUDFLARE_TEAM_DOMAIN and AUDIENCE_TAG | 1 | ⏸️ |
| Add get_current_user dependency to protected endpoints | 1 | ⏸️ |
| Display user email in React UI header | 1 | ⏸️ |
| Write tests for JWT validation (valid/invalid/expired) | 2 | ⏸️ |

#### US-002: Multi-File Upload

**As a** data engineer
**I want** to drag-and-drop multiple files
**So that** I can batch-process documents

**Acceptance Criteria**:

- [ ] Drag-drop zone accepts multiple files
- [ ] Upload progress indicator per file
- [ ] Batch ID returned after upload
- [ ] Unsupported file types rejected with clear error

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Implement POST /api/v1/ingest (multipart/form-data) | 3 | ⏸️ |
| Add file validation (500MB limit, MIME check) | 2 | ⏸️ |
| Create Batch and Job Pydantic models | 2 | ⏸️ |
| Build React drag-drop component (react-dropzone) | 3 | ⏸️ |
| Display upload progress with file list | 2 | ⏸️ |
| Write tests (single, multi, oversized, invalid type) | 3 | ⏸️ |

#### US-003: Automatic Pipeline Routing

**As a** data engineer
**I want** files automatically routed to correct pipeline
**So that** I don't manually classify each file

**Acceptance Criteria**:

- [ ] PDFs classified as scanned (→ OCR) or born-digital (→ doc processing)
- [ ] Audio/video → transcription pipeline
- [ ] Images → OCR pipeline
- [ ] Routing decision visible in job details

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Implement magic byte detection (python-magic) | 2 | ⏸️ |
| Add PDF classification (pdfplumber text extraction) | 3 | ⏸️ |
| Create routing engine (FileClassification → Pipeline) | 2 | ⏸️ |
| Map pipelines to URLs (config) | 1 | ⏸️ |
| Write routing tests (all file types, edge cases) | 3 | ⏸️ |

#### US-004: Job Queue Management

**As a** data engineer
**I want** high-priority files processed first
**So that** urgent documents are handled quickly

**Acceptance Criteria**:

- [ ] Users specify priority (high/normal/low) on upload
- [ ] High-priority jobs processed before normal/low
- [ ] Jobs persist across worker restart
- [ ] Failed jobs auto-retry up to 3 times

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Set up Redis with AOF persistence | 2 | ⏸️ |
| Implement RQ job submission for pipeline calls | 3 | ⏸️ |
| Create RQ worker with priority queues | 2 | ⏸️ |
| Add retry logic with exponential backoff | 2 | ⏸️ |
| Write queue tests (priority, persistence, retries) | 3 | ⏸️ |

#### US-005: Real-Time Status Updates

**As a** data engineer
**I want** live job progress without page refresh
**So that** I know when processing completes

**Acceptance Criteria**:

- [ ] WebSocket connection on batch detail page
- [ ] Status updates within 2s of state change
- [ ] Batch completion triggers notification
- [ ] Auto-reconnect if connection drops

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Implement WebSocket endpoint /ws/batch/{id} | 3 | ⏸️ |
| Add JWT auth to WebSocket (query param token) | 2 | ⏸️ |
| Create React useWebSocket hook | 3 | ⏸️ |
| Build batch status display (progress bar, job list) | 3 | ⏸️ |
| Add auto-reconnect logic (exponential backoff) | 2 | ⏸️ |
| Write WebSocket tests (connection, auth, messages, reconnect) | 3 | ⏸️ |

### Dependencies

- **Requires**: Phase 0 complete
- **Blocks**: Phase 2

---

## Phase 2: Enhancement (Week 5)

### Objective

Add vector storage handoff and improve UX with result download and batch history.

### Deliverables

- [ ] Vector storage target registration API
- [ ] Batch handoff trigger (manual + automatic)
- [ ] Result download from completed jobs
- [ ] Batch history view (last 50 batches)
- [ ] Enhanced error messages with retry suggestions

### Success Criteria

- ✅ Completed batches auto-handed off to selected vector store
- ✅ Users download processed results (ZIP)
- ✅ Batch history shows last 50 with status filter
- ✅ Error messages include actionable steps

### User Stories

#### US-006: Vector Store Handoff

**As a** data engineer
**I want** processed files delivered to my vector database
**So that** I don't manually move files between systems

**Acceptance Criteria**:

- [ ] Users select vector store target on upload
- [ ] Completed batches trigger handoff
- [ ] Handoff status visible (pending/success/failed)
- [ ] Failed handoffs can be retried manually

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Implement POST /api/v1/targets/register | 2 | ⏸️ |
| Create VectorStoreTarget model | 1 | ⏸️ |
| Add handoff logic to job completion handler | 3 | ⏸️ |
| Build target selection dropdown in upload UI | 2 | ⏸️ |
| Display handoff status in batch details | 2 | ⏸️ |
| Write handoff tests (success, failure, retry) | 3 | ⏸️ |

#### US-007: Result Download

**As a** data engineer
**I want** to download processed files
**So that** I can review outputs before vector storage

**Acceptance Criteria**:

- [ ] Download button on completed jobs
- [ ] ZIP archive contains all batch results
- [ ] Download includes metadata JSON
- [ ] Large results (>100MB) stream efficiently

**Tasks**:

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Implement GET /api/v1/job/{id}/result | 2 | ⏸️ |
| Add ZIP creation for batch results | 2 | ⏸️ |
| Build download button component | 1 | ⏸️ |
| Add streaming response for large files | 2 | ⏸️ |
| Write download tests (single, batch, large) | 2 | ⏸️ |

### Dependencies

- **Requires**: Phase 1 complete
- **Blocks**: Phase 3

---

## Phase 3: Polish (Week 6)

### Objective

Finalize testing, documentation, and release preparation.

### Deliverables

- [ ] Test coverage ≥80% (enforced by CI)
- [ ] User documentation complete
- [ ] Performance validated (100 users, 1000 files/hour)
- [ ] Security review complete (OWASP Top 10)
- [ ] Docker images optimized (<500MB total)

### Success Criteria

- ✅ All tests passing (unit, integration, E2E)
- ✅ No critical/high security issues
- ✅ README covers setup (<15 min to working)
- ✅ CHANGELOG updated
- ✅ Load test passes (100 users × 10 files in <5 min)

### Tasks

| Task | Est. Hours | Status |
| ---- | ---------- | ------ |
| Increase test coverage to 80%+ | 6 | ⏸️ |
| Write user documentation (upload guide, troubleshooting) | 4 | ⏸️ |
| Write API reference (OpenAPI spec) | 2 | ⏸️ |
| Run load test with Locust (100 users, 1000 files) | 3 | ⏸️ |
| Run security scans (Bandit, Safety, npm audit) | 2 | ⏸️ |
| Optimize Docker images (multi-stage builds) | 3 | ⏸️ |
| Update CHANGELOG with MVP features | 1 | ⏸️ |
| Final code review and refactoring | 4 | ⏸️ |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Cloudflare Access integration delays | M | H | Obtain credentials in Phase 0; implement bypass mode for local dev |
| External pipeline APIs unstable/undocumented | H | H | Mock APIs in tests; allocate 2 days buffer for discovery |
| WebSocket scaling issues at >100 connections | L | M | Load test early (Phase 3); fallback to polling if needed |
| PDF classification accuracy <95% | M | M | Validate with sample dataset (Phase 1); add manual re-route option |
| File upload size limits (500MB) too restrictive | L | M | Validate with users; implement chunked upload in Phase 2 extension if needed |
| Redis memory exhaustion | L | M | Configure 7-day TTL for completed jobs; monitor memory |

## Definition of Done

A feature is complete when:

- [ ] Code reviewed and approved
- [ ] Tests written and passing (unit + integration)
- [ ] Documentation updated (docstrings + user guide if user-facing)
- [ ] No linting errors (Ruff, ESLint, markdownlint)
- [ ] Type checking passes (BasedPyright, TypeScript)
- [ ] Merged to main branch
- [ ] Feature flag removed (if applicable)

## Related Documents

- [Project Vision](./project-vision.md): Problem, scope, success metrics
- [Technical Spec](./tech-spec.md): Architecture, API, data model
- [ADR-001: Architecture](./adr/adr-001-react-fastapi-architecture.md): Architectural decisions
