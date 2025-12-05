# Development Roadmap: RAG Processor WebUI

> **Status**: Active | **Updated**: 2025-12-04

## TL;DR

Building a React + FastAPI web interface for RAG pipeline file ingestion in 4 phases over 6 weeks: Foundation (week 1), Core MVP (weeks 2-4), Enhancement (week 5), and Polish (week 6).

## Timeline Overview

```
Phase 0: Foundation    ████████░░░░░░░░░░░░░░░░░░░░ (Week 1)  - Setup
Phase 1: MVP Core      ░░░░░░░░████████████████░░░░ (Weeks 2-4) - Core features
Phase 2: Enhancement   ░░░░░░░░░░░░░░░░░░░░████████ (Week 5) - Additional features
Phase 3: Polish        ░░░░░░░░░░░░░░░░░░░░░░░░████ (Week 6) - Testing & docs
```

## Milestones

| Milestone | Target | Status | Dependencies |
|-----------|--------|--------|--------------|
| M0: Dev Environment Ready | Week 1 | ⏸️ Planned | None |
| M1: Authentication Working | Week 2 | ⏸️ Planned | M0 |
| M2: File Upload + Routing | Week 3 | ⏸️ Planned | M1 |
| M3: Real-Time Status | Week 4 | ⏸️ Planned | M2 |
| M4: MVP Complete | End of Week 4 | ⏸️ Planned | M3 |
| M5: Handoff Integration | Week 5 | ⏸️ Planned | M4 |
| M6: Production Ready | Week 6 | ⏸️ Planned | M5 |

---

## Phase 0: Foundation (Week 1)

### Objective

Establish development environment, project structure, and core infrastructure to enable rapid feature development in subsequent phases.

### Deliverables

- [ ] Local development environment documented and working (Docker Compose, hot reload)
- [ ] CI/CD pipeline configured with quality gates (Ruff, BasedPyright, pytest)
- [ ] Project structure finalized (gateway/, rag-ui/, shared models)
- [ ] Dependencies locked (UV for backend, npm for frontend)
- [ ] Cloudflare Tunnel configured for local testing

### Success Criteria

- ✅ Developer can clone → run locally in < 15 minutes following README
- ✅ CI pipeline passes on main branch (linting, type checking, unit tests)
- ✅ Pre-commit hooks working (Ruff, markdownlint)
- ✅ Hot reload works for both frontend (Vite) and backend (uvicorn --reload)

### Tasks

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Create Docker Compose with Redis, gateway, worker, rag-ui services | 3 | ⏸️ | feat/docker-setup |
| Configure UV dependencies (FastAPI, Redis, RQ, cloudflare-auth) | 2 | ⏸️ | feat/docker-setup |
| Set up Vite React project with TypeScript + TailwindCSS | 2 | ⏸️ | feat/react-setup |
| Configure GitHub Actions CI workflow (test, lint, type-check) | 2 | ⏸️ | feat/ci-pipeline |
| Install pre-commit hooks (Ruff, BasedPyright, markdownlint) | 1 | ⏸️ | feat/pre-commit |
| Write local dev guide in README.md | 2 | ⏸️ | docs/dev-guide |

---

## Phase 1: MVP Core (Weeks 2-4)

### Objective

Implement minimum viable product with core user workflows: authenticated file upload, automatic pipeline routing, and real-time job monitoring.

### Deliverables

- [ ] Cloudflare Access authentication integrated (JWT validation, user context)
- [ ] File upload API with drag-and-drop frontend (multi-file support)
- [ ] Automatic file type detection and pipeline routing logic
- [ ] Redis job queue with priority support (high/normal/low)
- [ ] Real-time WebSocket status updates
- [ ] Basic error handling and user feedback

### Success Criteria

- ✅ User can upload PDF → routed to correct pipeline (Project A or B based on scan detection)
- ✅ WebSocket shows live status updates every 2-5 seconds
- ✅ Failed jobs display error messages in UI
- ✅ Job queue persists across gateway restart
- ✅ 80%+ test coverage on backend core logic

### User Stories

#### US-001: User Authentication

**As a** data engineer
**I want** to authenticate via Cloudflare Access
**So that** only authorized users can submit files to the pipeline

**Acceptance Criteria**:

- [ ] Unauthenticated users redirected to Cloudflare OAuth login
- [ ] Authenticated users see upload interface immediately
- [ ] User email displayed in UI header
- [ ] JWT validation middleware rejects tampered tokens (401 Unauthorized)

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Integrate cloudflare-auth middleware in FastAPI | 2 | ⏸️ | feat/auth-middleware |
| Configure CLOUDFLARE_TEAM_DOMAIN and AUDIENCE_TAG | 1 | ⏸️ | feat/auth-middleware |
| Add get_current_user dependency to protected endpoints | 1 | ⏸️ | feat/auth-middleware |
| Display user email in React UI header | 1 | ⏸️ | feat/user-context |
| Write tests for JWT validation (valid/invalid/expired tokens) | 2 | ⏸️ | test/auth |

#### US-002: Multi-File Upload

**As a** data engineer
**I want** to drag-and-drop multiple files for upload
**So that** I can batch-process documents efficiently

**Acceptance Criteria**:

- [ ] Drag-and-drop zone accepts multiple files simultaneously
- [ ] Upload progress indicator shows per-file progress
- [ ] Batch ID returned after successful upload
- [ ] Unsupported file types rejected with clear error message

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Implement POST /api/v1/ingest endpoint (multipart/form-data) | 3 | ⏸️ | feat/upload-api |
| Add file validation (size limit 500MB, MIME type check) | 2 | ⏸️ | feat/upload-api |
| Create Batch and Job models (Pydantic) | 2 | ⏸️ | feat/data-models |
| Build React drag-and-drop component (react-dropzone) | 3 | ⏸️ | feat/upload-ui |
| Display upload progress with file list | 2 | ⏸️ | feat/upload-ui |
| Write tests for file upload (single, multi, oversized, invalid type) | 3 | ⏸️ | test/upload |

#### US-003: Automatic Pipeline Routing

**As a** data engineer
**I want** files automatically routed to the correct pipeline
**So that** I don't need to manually classify each file

**Acceptance Criteria**:

- [ ] PDFs classified as scanned (→ Project A) or born-digital (→ Project B) based on text extraction
- [ ] Audio/video files routed to Project E
- [ ] Images routed to Project A
- [ ] Office documents routed to Project B
- [ ] Routing decision visible in job details

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Implement magic byte file type detection (python-magic) | 2 | ⏸️ | feat/file-router |
| Add PDF classification logic (pdfplumber text extraction ratio) | 3 | ⏸️ | feat/pdf-classifier |
| Create routing decision engine (file type → Pipeline enum) | 2 | ⏸️ | feat/file-router |
| Map file types to pipeline URLs (config: PROJECT_A_URL, etc.) | 1 | ⏸️ | feat/file-router |
| Write tests for routing (all file types, edge cases) | 3 | ⏸️ | test/routing |

#### US-004: Job Queue Management

**As a** data engineer
**I want** high-priority files processed before low-priority ones
**So that** urgent documents are handled first

**Acceptance Criteria**:

- [ ] Users can specify priority (high/normal/low) on upload
- [ ] High-priority jobs processed before normal/low when queue is full
- [ ] Jobs persist across worker restart
- [ ] Failed jobs automatically retry up to 3 times

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Set up Redis connection with persistence (AOF enabled) | 2 | ⏸️ | feat/redis-setup |
| Implement RQ job submission for pipeline API calls | 3 | ⏸️ | feat/job-queue |
| Create RQ worker with priority queues (high, default, low) | 2 | ⏸️ | feat/job-queue |
| Add retry logic with exponential backoff (RQ decorator) | 2 | ⏸️ | feat/job-queue |
| Write tests for queue (priority ordering, persistence, retries) | 3 | ⏸️ | test/queue |

#### US-005: Real-Time Status Updates

**As a** data engineer
**I want** to see live job progress without refreshing the page
**So that** I know when processing is complete

**Acceptance Criteria**:

- [ ] WebSocket connection established on batch detail page
- [ ] Status updates appear within 2 seconds of job state change
- [ ] Batch completion triggers visual notification
- [ ] Connection auto-reconnects if dropped

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Implement WebSocket endpoint /ws/batch/{id} (FastAPI) | 3 | ⏸️ | feat/websocket |
| Add JWT authentication to WebSocket (query param token) | 2 | ⏸️ | feat/websocket |
| Create React WebSocket hook (useWebSocket) | 3 | ⏸️ | feat/websocket-ui |
| Build batch status display component (progress bar, job list) | 3 | ⏸️ | feat/status-ui |
| Add auto-reconnect logic (exponential backoff) | 2 | ⏸️ | feat/websocket-ui |
| Write tests for WebSocket (connection, auth, messages, reconnect) | 3 | ⏸️ | test/websocket |

### Dependencies

- **Requires**: Phase 0 complete (Docker Compose, CI pipeline)
- **Blocks**: Phase 2 (handoff integration requires working job queue)

---

## Phase 2: Enhancement (Week 5)

### Objective

Add Project D handoff integration and improve user experience with result download and batch management features.

### Deliverables

- [ ] Project D target registration API (internal endpoint)
- [ ] Batch handoff trigger (manual and automatic modes)
- [ ] Result download from completed jobs
- [ ] Batch history view (list past batches)
- [ ] Enhanced error messages with retry suggestions

### Success Criteria

- ✅ Completed batches automatically handed off to registered Project D variant
- ✅ Users can download processed results (ZIP archive)
- ✅ Batch history page shows last 50 batches with filter by status
- ✅ Error messages include actionable next steps

### User Stories

#### US-006: Project D Handoff

**As a** data engineer
**I want** processed files automatically delivered to my vector database
**So that** I don't need to manually move files between systems

**Acceptance Criteria**:

- [ ] Users can select Project D target on upload (dropdown)
- [ ] Completed batches trigger handoff to selected target
- [ ] Handoff status visible in UI (pending/success/failed)
- [ ] Failed handoffs can be retried manually

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Implement POST /api/v1/targets/register (internal API) | 2 | ⏸️ | feat/handoff-api |
| Create ProjectDTarget model (URL, auth credentials) | 1 | ⏸️ | feat/handoff-api |
| Add handoff logic to job completion handler | 3 | ⏸️ | feat/handoff-logic |
| Build target selection dropdown in upload UI | 2 | ⏸️ | feat/handoff-ui |
| Display handoff status in batch details | 2 | ⏸️ | feat/handoff-ui |
| Write tests for handoff (success, failure, retry) | 3 | ⏸️ | test/handoff |

#### US-007: Result Download

**As a** data engineer
**I want** to download processed files from completed jobs
**So that** I can review outputs before vector storage

**Acceptance Criteria**:

- [ ] Download button appears on completed jobs
- [ ] ZIP archive contains all results from batch
- [ ] Download includes metadata JSON (filenames, processing times)
- [ ] Large result sets (>100MB) stream efficiently

**Tasks**:

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Implement GET /api/v1/job/{id}/result (file download) | 2 | ⏸️ | feat/result-download |
| Add ZIP archive creation for batch results | 2 | ⏸️ | feat/result-download |
| Build download button component in UI | 1 | ⏸️ | feat/download-ui |
| Add streaming response for large files | 2 | ⏸️ | feat/result-download |
| Write tests for download (single, batch, large files) | 2 | ⏸️ | test/download |

### Dependencies

- **Requires**: Phase 1 complete (job queue, status updates)
- **Blocks**: Phase 3 (polish phase requires complete feature set)

---

## Phase 3: Polish (Week 6)

### Objective

Finalize testing, documentation, and release preparation to ensure production readiness and smooth user onboarding.

### Deliverables

- [ ] Test coverage ≥ 80% (enforced by CI)
- [ ] User documentation complete (upload guide, API reference, troubleshooting)
- [ ] Performance validated (100 concurrent users, 1000 files/hour)
- [ ] Security review complete (OWASP Top 10 checklist)
- [ ] Docker images optimized (multi-stage builds, <500MB total)

### Success Criteria

- ✅ All tests passing (unit, integration, E2E)
- ✅ No critical/high security issues (Bandit, Safety scans)
- ✅ README covers all setup steps (< 15 min to working state)
- ✅ CHANGELOG updated with MVP features
- ✅ Load test passes (100 users × 10 files each in < 5 min)

### Tasks

| Task | Est. Hours | Status | Branch |
|------|------------|--------|--------|
| Increase test coverage to 80%+ (missing edge cases) | 6 | ⏸️ | test/coverage |
| Write user documentation (upload guide, troubleshooting) | 4 | ⏸️ | docs/user-guide |
| Write API reference documentation (OpenAPI spec) | 2 | ⏸️ | docs/api-reference |
| Run load test with Locust (100 users, 1000 files) | 3 | ⏸️ | test/load |
| Run security scans (Bandit, Safety, npm audit) | 2 | ⏸️ | test/security |
| Optimize Docker images (multi-stage builds, Alpine base) | 3 | ⏸️ | feat/docker-optimize |
| Update CHANGELOG with MVP features | 1 | ⏸️ | docs/changelog |
| Final code review and refactoring | 4 | ⏸️ | refactor/cleanup |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Cloudflare Access integration delays due to missing credentials | M | H | Obtain credentials in Phase 0; implement bypass mode (CLOUDFLARE_ENABLED=false) for local dev |
| Projects A-E APIs unstable or undocumented | H | H | Mock external APIs in tests; allocate 2 days buffer for API discovery/debugging |
| WebSocket scaling issues at >100 concurrent connections | L | M | Load test early (Phase 3); fallback to polling if needed (acceptable for MVP) |
| PDF classification accuracy <95% (text extraction false negatives) | M | M | Validate with sample dataset (Phase 1); add manual re-route option if needed |
| File upload size limits (500MB) too restrictive | L | M | Validate with user; if needed, implement chunked upload in Phase 2 extension |
| Redis memory exhaustion with long job retention | L | M | Configure TTL for completed jobs (7 days); monitor Redis memory usage |

## Definition of Done

A feature is complete when:

- [ ] Code reviewed and approved (PR review by AI assistant or manual review)
- [ ] Tests written and passing (unit + integration)
- [ ] Documentation updated (inline docstrings + user guide if user-facing)
- [ ] No linting errors (Ruff, ESLint, markdownlint)
- [ ] Type checking passes (BasedPyright, TypeScript)
- [ ] Merged to main branch
- [ ] Feature flag removed (if applicable)

## Related Documents

- [Project Vision](./project-vision.md)
- [Technical Spec](./tech-spec.md)
- [Architecture Decisions](./adr/)
  - [ADR-001: React + FastAPI Architecture](./adr/adr-001-initial-architecture.md)
  - [ADR-002: Redis Job Queue](./adr/adr-002-redis-job-queue.md)
  - [ADR-003: Cloudflare Authentication](./adr/adr-003-cloudflare-auth.md)
