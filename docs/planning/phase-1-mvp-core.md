---
title: "Phase 1: MVP Core - Detailed Plan"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Define the detailed sprint plan for Phase 1 MVP core features."
tags:
  - planning
  - implementation
  - mvp
component: Strategy
source: "Derived from roadmap.md Phase 1"
---

<!-- markdownlint-disable MD024 -->

> **Phase Duration**: Weeks 2-4 (15 working days, 120 hours)
> **Branch**: `feat/phase-1-mvp-core`
> **Status**: Planned
> **Updated**: 2025-12-05

## Overview

Implement minimum viable product with core user workflows: authenticated file upload, automatic pipeline routing, and real-time job monitoring via WebSocket.

**Parent Plan**: [PROJECT-PLAN.md](./PROJECT-PLAN.md#phase-1-mvp-core-weeks-2-4)

## Phase Objectives

- ✅ User authenticates via Cloudflare Access and sees upload interface
- ✅ PDF files automatically classified (scanned vs born-digital) and routed to correct pipeline
- ✅ WebSocket displays live job status updates every 2-5 seconds
- ✅ Failed jobs retry automatically (up to 3 attempts) with user notification
- ✅ 80%+ test coverage on backend core logic

## Milestones

| Milestone | Target | Exit Criteria | Sprints |
| --------- | ------ | ------------- | ------- |
| M1.1: Authentication Working | Week 2 End | JWT validation, user context in API | S1.1-S1.4 |
| M1.2: File Upload API | Week 3 Mid | Multi-file upload to Redis queue | S1.5-S1.8 |
| M1.3: Pipeline Routing | Week 3 End | All file types routed correctly | S1.9-S1.12 |
| M1.4: Job Queue Complete | Week 4 Mid | Priority queues, retries working | S1.13-S1.16 |
| M1.5: WebSocket Live | Week 4 End | Real-time status, auto-reconnect | S1.17-S1.20 |
| M1.6: MVP Complete | Week 4 End | All US passing, 80%+ coverage | S1.21-S1.24 |

## Sprint Breakdown (3-4 hour sprints)

### User Story 1: Authentication (Week 2 - Sprints 1.1-1.4)

#### Sprint 1.1: Cloudflare JWT Middleware (4 hours)

**Goal**: Implement JWT validation middleware in FastAPI

**Tasks**:

1. Create CloudflareAuthMiddleware class (2 hours)
   - Fetch JWKS from Cloudflare endpoint
   - Cache public keys (1 hour TTL)
   - Validate JWT signature using PyJWT
   - Extract user claims (email, user_id)

2. Add middleware to FastAPI app (1 hour)
   - Register middleware in `main.py`
   - Configure team domain and audience from env vars
   - Add exception handling for invalid tokens

3. Write middleware tests (1 hour)
   - Test valid JWT (mocked JWKS)
   - Test invalid signature → 401
   - Test expired token → 401
   - Test missing token → 401

**Exit Criteria**:

- [ ] Middleware validates JWT signature
- [ ] User context available in `request.state.user`
- [ ] Invalid tokens return 401 Unauthorized
- [ ] Tests pass with 100% coverage

---

#### Sprint 1.2: get_current_user Dependency (3 hours)

**Goal**: Create FastAPI dependency for accessing current user

**Tasks**:

1. Implement get_current_user dependency (1 hour)
   - Extract user from `request.state.user`
   - Raise HTTPException if not authenticated
   - Return CloudflareUser model

2. Add to protected endpoints (1 hour)
   - Update `/api/v1/ingest` endpoint
   - Add user context to log entries
   - Include created_by_email in responses

3. Write dependency tests (1 hour)
   - Test with valid user
   - Test with missing user → 401
   - Test user context in endpoint

**Exit Criteria**:

- [ ] `get_current_user()` returns user context
- [ ] Protected endpoints require authentication
- [ ] User email logged in audit fields
- [ ] Tests pass

---

#### Sprint 1.3: Frontend Auth UI (4 hours)

**Goal**: Display user email in React UI header

**Tasks**:

1. Create useAuth hook (1.5 hours)
   - Fetch user info from gateway
   - Handle loading/error states
   - Store in zustand state

2. Create Header component (1.5 hours)
   - Display user email
   - Logout placeholder (Cloudflare logout URL)
   - Loading spinner while fetching

3. Add to App layout (0.5 hours)
   - Wrap app in auth provider
   - Show header on all pages

4. Write component tests (0.5 hours)
   - Test header displays email
   - Test loading state
   - Mock auth hook

**Exit Criteria**:

- [ ] User email displayed in UI header
- [ ] Loading state handled gracefully
- [ ] Component tests pass
- [ ] UI updates automatically on auth change

---

#### Sprint 1.4: End-to-End Auth Test (3 hours)

**Goal**: E2E test for complete auth flow

**Tasks**:

1. Set up Playwright (1 hour)
   - Install Playwright
   - Configure for TypeScript
   - Create test fixtures

2. Write auth E2E test (1.5 hours)
   - Mock Cloudflare Access (bypass or test account)
   - Navigate to app
   - Verify redirect to login
   - Verify header shows email after auth

3. Run E2E tests in CI (0.5 hours)
   - Add Playwright to GitHub Actions
   - Configure test environment

**Exit Criteria**:

- [ ] E2E auth test passes locally
- [ ] E2E test passes in CI
- [ ] Auth flow validated end-to-end

---

### User Story 2: Multi-File Upload (Week 2-3 - Sprints 1.5-1.8)

#### Sprint 1.5: Upload API Endpoint (4 hours)

**Goal**: Implement POST /api/v1/ingest with file validation

**Tasks**:

1. Create ingest endpoint (2 hours)
   - Accept multipart/form-data
   - Parse files, priority, target_vector_store
   - Validate file size (<100MB per file)
   - Save files to upload directory

2. Add file validation (1 hour)
   - Check file type whitelist
   - Validate MIME type with python-magic
   - Sanitize filename (remove path traversal)
   - Return 400 for invalid files

3. Write endpoint tests (1 hour)
   - Test single file upload
   - Test multi-file upload
   - Test oversized file → 413
   - Test invalid file type → 400

**Exit Criteria**:

- [ ] POST /api/v1/ingest accepts files
- [ ] Files saved to `/data/uploads/{batch_id}/`
- [ ] Validation rejects invalid inputs
- [ ] Tests pass with 100% coverage

---

#### Sprint 1.6: Batch and Job Models (3 hours)

**Goal**: Create Pydantic models for Batch and Job

**Tasks**:

1. Define Batch model (1 hour)
   - UUID batch_id
   - created_by_email, created_by_user_id
   - status (BatchStatus enum)
   - total_files, completed_files, failed_files
   - target_vector_store

2. Define Job model (1 hour)
   - UUID job_id, batch_id
   - filename, file_path, file_type, file_size_bytes
   - classification (FileClassification enum)
   - routed_to (Pipeline enum)
   - status (JobStatus enum), priority
   - Timestamps, error_message, retry_count

3. Write model tests (1 hour)
   - Test model validation
   - Test enum constraints
   - Test serialization to JSON

**Exit Criteria**:

- [ ] Batch and Job models defined
- [ ] All enums defined (FileClassification, Pipeline, JobStatus, BatchStatus, Priority)
- [ ] Models serialize to/from JSON
- [ ] Validation tests pass

---

#### Sprint 1.7: React Drag-Drop Component (4 hours)

**Goal**: Build file upload UI with react-dropzone

**Tasks**:

1. Create FileUpload component (2 hours)
   - Use react-dropzone for drag-drop
   - Accept multiple files
   - Display file list with sizes
   - Show validation errors (file type, size)

2. Add upload progress UI (1 hour)
   - Progress bar per file
   - Overall batch progress
   - Upload button (disabled until files selected)

3. Write component tests (1 hour)
   - Test file selection
   - Test drag-drop
   - Test validation errors
   - Mock file upload API

**Exit Criteria**:

- [ ] Drag-drop accepts multiple files
- [ ] File list displays names and sizes
- [ ] Invalid files show error messages
- [ ] Component tests pass

---

#### Sprint 1.8: Upload Integration (3 hours)

**Goal**: Connect frontend upload to backend API

**Tasks**:

1. Create API client for upload (1 hour)
   - POST multipart/form-data to /api/v1/ingest
   - Include JWT token in headers
   - Handle upload progress events

2. Integrate with FileUpload component (1 hour)
   - Call API on button click
   - Show upload progress
   - Handle success (navigate to batch status page)
   - Handle errors (display message)

3. Integration test (1 hour)
   - Upload test file through UI
   - Verify batch created in backend
   - Verify files saved to disk
   - Check Redis for job entries

**Exit Criteria**:

- [ ] Frontend uploads files to backend
- [ ] Backend creates batch and jobs
- [ ] Files saved to upload directory
- [ ] Integration test passes

---

### User Story 3: Pipeline Routing (Week 3 - Sprints 1.9-1.12)

#### Sprint 1.9: File Type Detection (3 hours)

**Goal**: Implement magic byte MIME type detection

**Tasks**:

1. Create FileTypeDetector class (1.5 hours)
   - Use python-magic for magic byte scanning
   - Fallback to file extension
   - Return MIME type and confidence

2. Write detection tests (1.5 hours)
   - Test PDFs, images, audio, Office docs
   - Test MIME mismatch (wrong extension)
   - Test corrupted files
   - Test with sample files from fixtures

**Exit Criteria**:

- [ ] Detector identifies MIME types correctly
- [ ] Tests pass with sample files
- [ ] MIME mismatch detection works

---

#### Sprint 1.10: PDF Classification (4 hours)

**Goal**: Classify PDFs as scanned vs born-digital

**Tasks**:

1. Create PDFClassifier class (2.5 hours)
   - Use pdfplumber to extract text
   - Calculate text extraction ratio (chars/page)
   - Threshold: <50 chars/page = scanned, else born-digital
   - Handle encrypted PDFs (mark as failed)

2. Write classification tests (1.5 hours)
   - Test scanned PDF (image-based)
   - Test born-digital PDF (text-based)
   - Test hybrid PDF (mixed)
   - Test encrypted PDF
   - Use actual PDF samples

**Exit Criteria**:

- [ ] Scanned PDFs classified correctly (→ OCR pipeline)
- [ ] Born-digital PDFs classified correctly (→ doc processing)
- [ ] Tests pass with real PDF samples
- [ ] Edge cases handled (encrypted, corrupted)

---

#### Sprint 1.11: Routing Engine (3 hours)

**Goal**: Create file → pipeline routing logic

**Tasks**:

1. Create FileRouter class (1.5 hours)
   - Map FileClassification to Pipeline enum
   - Configuration: file type → pipeline URL
   - Handle unsupported file types

2. Integrate with upload endpoint (0.5 hours)
   - Run detector + classifier on uploaded files
   - Set Job.classification and Job.routed_to
   - Store routing decision in job metadata

3. Write routing tests (1 hour)
   - Test all file type → pipeline mappings
   - Test scanned PDF → OCR
   - Test born-digital PDF → doc processing
   - Test audio → transcription
   - Test unsupported type → error

**Exit Criteria**:

- [ ] All file types route to correct pipeline
- [ ] Routing decision stored in job metadata
- [ ] Unsupported types rejected with clear error
- [ ] Tests pass

---

#### Sprint 1.12: Pipeline Configuration (3 hours)

**Goal**: External pipeline URL configuration

**Tasks**:

1. Create pipeline config (1 hour)
   - YAML file: `config/pipelines.yaml`
   - Map pipeline names to URLs
   - Bearer token secret names
   - Timeout configurations

2. Create PipelineAdapter interface (1.5 hours)
   - Abstract base class
   - Methods: submit_job, check_status, fetch_result
   - Concrete adapters: OCRAdapter, TranscriptionAdapter, etc.

3. Write adapter tests (0.5 hours)
   - Test adapter interface compliance
   - Mock HTTP responses
   - Test timeout handling

**Exit Criteria**:

- [ ] Pipeline URLs configurable via YAML
- [ ] PipelineAdapter interface defined
- [ ] Concrete adapters implemented
- [ ] Tests pass

---

### User Story 4: Job Queue (Week 3-4 - Sprints 1.13-1.16)

#### Sprint 1.13: Redis Queue Setup (3 hours)

**Goal**: Configure Redis with priority queues

**Tasks**:

1. Update Redis Docker config (0.5 hours)
   - Enable AOF persistence
   - Set password from environment
   - Configure appendfsync everysec

2. Create RQ queue client (1.5 hours)
   - Initialize Redis connection
   - Create priority queues (high, default, low)
   - Add job to appropriate queue based on priority

3. Write queue tests with fakeredis (1 hour)
   - Test job enqueueing
   - Test priority order
   - Test persistence (AOF)

**Exit Criteria**:

- [ ] Redis configured with AOF
- [ ] Priority queues created
- [ ] Jobs enqueue successfully
- [ ] Tests pass with fakeredis

---

#### Sprint 1.14: Job Submission (4 hours)

**Goal**: Enqueue jobs from upload endpoint

**Tasks**:

1. Create job submission function (2 hours)
   - Accept Job model
   - Determine priority
   - Enqueue to appropriate queue
   - Store job metadata in Redis (hash)

2. Integrate with ingest endpoint (1 hour)
   - After file upload, create jobs
   - Enqueue each job
   - Return batch response with job list

3. Write submission tests (1 hour)
   - Test high priority → high queue
   - Test batch creates multiple jobs
   - Test job metadata stored in Redis

**Exit Criteria**:

- [ ] Upload creates jobs in Redis queue
- [ ] Priority correctly assigned
- [ ] Job metadata stored
- [ ] Tests pass

---

#### Sprint 1.15: RQ Worker Pipeline Calls (4 hours)

**Goal**: Worker processes jobs and calls external pipelines

**Tasks**:

1. Create job processing function (2.5 hours)
   - Load job from Redis
   - Call appropriate PipelineAdapter.submit_job
   - Poll pipeline status every 5s
   - Update job status in Redis
   - Publish event to Redis (for WebSocket)

2. Add retry logic decorator (1 hour)
   - RQ retry decorator with exponential backoff
   - Max 3 retries
   - Move to failed queue after exhaustion

3. Write worker tests (0.5 hours)
   - Test successful processing
   - Test retry on failure
   - Test dead letter queue

**Exit Criteria**:

- [ ] Worker calls pipeline APIs
- [ ] Job status updates in Redis
- [ ] Retry logic works
- [ ] Tests pass

---

#### Sprint 1.16: Job Status API (3 hours)

**Goal**: Endpoints to query batch and job status

**Tasks**:

1. Implement GET /api/v1/batch/{id} (1 hour)
   - Load batch from Redis
   - Load all jobs for batch
   - Calculate aggregate status
   - Return batch response

2. Implement GET /api/v1/job/{id} (0.5 hours)
   - Load job from Redis
   - Return job details

3. Write API tests (1.5 hours)
   - Test batch status aggregation
   - Test job not found → 404
   - Test batch with mixed job statuses

**Exit Criteria**:

- [ ] Batch status endpoint works
- [ ] Job status endpoint works
- [ ] 404 for invalid IDs
- [ ] Tests pass

---

### User Story 5: WebSocket Status (Week 4 - Sprints 1.17-1.20)

#### Sprint 1.17: WebSocket Endpoint (4 hours)

**Goal**: Implement WebSocket connection with JWT auth

**Tasks**:

1. Create WebSocket endpoint (2 hours)
   - `/ws/batch/{batch_id}` route
   - Accept JWT in query param (`cf_access_token`)
   - Validate token on connection
   - Keep connection alive with ping/pong

2. Add connection manager (1 hour)
   - Track active connections per batch
   - Handle connection/disconnection
   - Broadcast messages to all connections for batch

3. Write WebSocket tests (1 hour)
   - Test connection with valid token
   - Test invalid token → 401
   - Test broadcast to multiple clients
   - Test disconnect handling

**Exit Criteria**:

- [ ] WebSocket accepts connections
- [ ] JWT validation on connect
- [ ] Connection manager tracks clients
- [ ] Tests pass

---

#### Sprint 1.18: Event Publishing (3 hours)

**Goal**: Worker publishes job events to Redis for WebSocket

**Tasks**:

1. Create event publishing function (1.5 hours)
   - Publish to Redis channel: `batch:{batch_id}:events`
   - Store event in Redis list (for replay)
   - Include event_id, type, timestamp, job_id, status

2. Integrate with worker (0.5 hours)
   - Publish on job status change
   - Publish on error
   - Publish on completion

3. Write publishing tests (1 hour)
   - Test event structure
   - Test event stored in Redis
   - Test multiple events

**Exit Criteria**:

- [ ] Events published to Redis on job updates
- [ ] Events stored in list for replay
- [ ] Event structure valid
- [ ] Tests pass

---

#### Sprint 1.19: WebSocket Broadcasting (4 hours)

**Goal**: Gateway subscribes to Redis and broadcasts to WebSocket clients

**Tasks**:

1. Create Redis subscriber (2 hours)
   - Subscribe to `batch:*:events` pattern
   - Parse event messages
   - Route to appropriate connection manager

2. Broadcast to WebSocket clients (1 hour)
   - Connection manager sends event to all clients for batch
   - Handle client disconnection gracefully
   - Log broadcast errors

3. Write broadcast tests (1 hour)
   - Test Redis → WebSocket flow
   - Test multiple clients receive same event
   - Test client disconnect doesn't affect others

**Exit Criteria**:

- [ ] Events broadcast from Redis to WebSocket
- [ ] All connected clients receive events
- [ ] Disconnected clients handled gracefully
- [ ] Tests pass

---

#### Sprint 1.20: WebSocket Reconnect & Replay (3 hours)

**Goal**: Client reconnect with event replay from Redis

**Tasks**:

1. Implement event replay (1.5 hours)
   - Client sends `last_event_id` on connect
   - Server loads events from Redis list
   - Send missed events to client
   - Resume live stream

2. Create React useWebSocket hook (1 hour)
   - Auto-reconnect with exponential backoff
   - Track last_event_id
   - Send on reconnect
   - Handle server_restarting message

3. Write reconnect tests (0.5 hours)
   - Test disconnect → reconnect → replay
   - Test no duplicate events
   - Test graceful shutdown handling

**Exit Criteria**:

- [ ] Client reconnects automatically
- [ ] Missed events replayed from Redis
- [ ] No duplicate events received
- [ ] Tests pass

---

### Integration & Polish (Week 4 End - Sprints 1.21-1.24)

#### Sprint 1.21: End-to-End Happy Path (4 hours)

**Goal**: Complete flow from upload to WebSocket status

**Tasks**:

1. Write E2E test (2 hours)
   - Upload PDF file
   - Mock external pipeline response
   - Verify WebSocket receives updates
   - Verify job completes successfully

2. Fix integration issues (1.5 hours)
   - Debug any failures
   - Adjust timing/retry logic
   - Ensure events flow correctly

3. Performance validation (0.5 hours)
   - Measure upload latency
   - Measure WebSocket latency
   - Verify <2s targets

**Exit Criteria**:

- [ ] Upload → queue → worker → pipeline → WebSocket complete
- [ ] WebSocket latency <2s
- [ ] No errors in happy path
- [ ] E2E test passes

---

#### Sprint 1.22: Error Handling Polish (3 hours)

**Goal**: Comprehensive error messages and retry UX

**Tasks**:

1. Add error message mapping (1 hour)
   - Map pipeline errors to user-friendly messages
   - Include suggested actions
   - Add error codes

2. Update WebSocket error events (1 hour)
   - Send job_failed event with details
   - Include retry_count
   - Include error_message and suggested_action

3. Update UI to display errors (1 hour)
   - Show error messages in job list
   - Display retry count
   - Add retry button (manual)

**Exit Criteria**:

- [ ] Errors displayed clearly in UI
- [ ] Retry count visible
- [ ] Suggested actions helpful
- [ ] Manual retry button works

---

#### Sprint 1.23: Test Coverage Push (4 hours)

**Goal**: Increase coverage to 80%+

**Tasks**:

1. Run coverage report (0.5 hours)
   - `uv run pytest --cov=src --cov-report=html`
   - Identify uncovered lines

2. Write missing tests (3 hours)
   - Edge cases in file routing
   - Error handling paths
   - WebSocket disconnect scenarios
   - Redis failure recovery

3. Verify coverage threshold (0.5 hours)
   - Run `pytest --cov-fail-under=80`
   - Fix any remaining gaps

**Exit Criteria**:

- [ ] Backend coverage ≥80%
- [ ] Frontend coverage ≥80%
- [ ] Critical paths at 100%
- [ ] CI enforces coverage threshold

---

#### Sprint 1.24: Phase 1 PR & Merge (3 hours)

**Goal**: Complete Phase 1 and merge to main

**Tasks**:

1. Run all quality checks (1 hour)
   - Backend: ruff, basedpyright, pytest
   - Frontend: eslint, tsc, vitest
   - Pre-commit: run --all-files
   - E2E: playwright tests

2. Update CHANGELOG (0.5 hours)
   - Add Phase 1 MVP features
   - List user stories completed

3. Create Phase 1 PR (1 hour)
   - Push branch
   - Create PR with comprehensive description
   - Include demo screenshots/video
   - Reference user stories

4. Merge (0.5 hours)
   - Address CI feedback
   - Merge to main

**Exit Criteria**:

- [ ] All checks passing
- [ ] PR created and approved
- [ ] Merged to main
- [ ] Phase 1 complete

---

## Phase 1 Deliverables Checklist

### Authentication

- [ ] Cloudflare JWT validation middleware
- [ ] get_current_user dependency
- [ ] User email displayed in UI
- [ ] Auth tests (unit + E2E)

### File Upload

- [ ] POST /api/v1/ingest endpoint
- [ ] File validation (size, type, MIME)
- [ ] Batch and Job models
- [ ] React drag-drop component
- [ ] Upload progress UI
- [ ] Integration tests

### Pipeline Routing

- [ ] Magic byte detection (python-magic)
- [ ] PDF classification (pdfplumber)
- [ ] FileRouter class
- [ ] Pipeline configuration (YAML)
- [ ] Routing tests (all file types)

### Job Queue

- [ ] Redis AOF persistence
- [ ] RQ job submission
- [ ] Priority queues (high, normal, low)
- [ ] Retry logic (3x exponential backoff)
- [ ] Worker processing
- [ ] Queue tests

### WebSocket

- [ ] WebSocket endpoint with JWT auth
- [ ] Connection manager
- [ ] Event publishing from worker
- [ ] Redis subscription and broadcast
- [ ] Client reconnect with replay
- [ ] React useWebSocket hook
- [ ] WebSocket tests

### Quality

- [ ] 80%+ test coverage (backend + frontend)
- [ ] All linting passing
- [ ] Type checking passing
- [ ] E2E tests passing

## Sprint Schedule

| Sprint | Week | Day | Focus | Hours |
| ------ | ---- | --- | ----- | ----- |
| S1.1 | 2 | Mon AM | Cloudflare JWT Middleware | 4 |
| S1.2 | 2 | Mon PM | get_current_user Dependency | 3 |
| S1.3 | 2 | Tue AM | Frontend Auth UI | 4 |
| S1.4 | 2 | Tue PM | E2E Auth Test | 3 |
| S1.5 | 2 | Wed AM | Upload API Endpoint | 4 |
| S1.6 | 2 | Wed PM | Batch and Job Models | 3 |
| S1.7 | 2 | Thu AM | React Drag-Drop Component | 4 |
| S1.8 | 2 | Thu PM | Upload Integration | 3 |
| S1.9 | 3 | Mon AM | File Type Detection | 3 |
| S1.10 | 3 | Mon PM | PDF Classification | 4 |
| S1.11 | 3 | Tue AM | Routing Engine | 3 |
| S1.12 | 3 | Tue PM | Pipeline Configuration | 3 |
| S1.13 | 3 | Wed AM | Redis Queue Setup | 3 |
| S1.14 | 3 | Wed PM | Job Submission | 4 |
| S1.15 | 3 | Thu AM | RQ Worker Pipeline Calls | 4 |
| S1.16 | 3 | Thu PM | Job Status API | 3 |
| S1.17 | 4 | Mon AM | WebSocket Endpoint | 4 |
| S1.18 | 4 | Mon PM | Event Publishing | 3 |
| S1.19 | 4 | Tue AM | WebSocket Broadcasting | 4 |
| S1.20 | 4 | Tue PM | WebSocket Reconnect & Replay | 3 |
| S1.21 | 4 | Wed AM | E2E Happy Path | 4 |
| S1.22 | 4 | Wed PM | Error Handling Polish | 3 |
| S1.23 | 4 | Thu AM | Test Coverage Push | 4 |
| S1.24 | 4 | Thu PM | Phase 1 PR & Merge | 3 |

**Total Estimated Hours**: 85 hours (with 35 hours buffer for Phase 1)

## Dependencies

**Requires**:

- Phase 0 complete (Docker Compose, CI, pre-commit)

**Blocks**:

- Phase 2 (handoff integration requires working queue)

## Validation Checklist

Before completing Phase 1:

- [ ] **Authentication**: User can log in via Cloudflare Access
- [ ] **Upload**: Multi-file drag-drop works
- [ ] **Routing**: PDFs classified correctly (scanned vs born-digital)
- [ ] **Queue**: Jobs prioritized and persistent
- [ ] **WebSocket**: Live status updates <2s latency
- [ ] **Error Handling**: Failed jobs retry 3x, display errors
- [ ] **Tests**: 80%+ coverage, all passing
- [ ] **CI**: All checks passing
- [ ] **E2E**: Happy path test passes

## Risk Mitigation

| Risk | Mitigation | Sprint |
| ---- | ---------- | ------ |
| Cloudflare Access integration complex | Implement bypass mode for local dev | S1.1 |
| PDF classification accuracy low | Validate with diverse sample set, adjust threshold | S1.10 |
| WebSocket state management difficult | Use Redis for event log, enable replay | S1.20 |
| External pipeline APIs unavailable | Mock all pipeline responses in tests | S1.15 |

## Next Phase

After Phase 1:

1. Merge `feat/phase-1-mvp-core` to main
2. Review [Phase 2 Plan](./phase-2-enhancement.md)
3. Create branch: `git checkout -b feat/phase-2-enhancement`
4. Begin Sprint 2.1: Vector Store Target Registration

## Related Documents

- [PROJECT-PLAN.md](./PROJECT-PLAN.md): Overall project plan
- [Roadmap](./roadmap.md#phase-1-mvp-core-weeks-2-4): Phase overview
- [Tech Spec](./tech-spec.md): API specifications
- [ADR-001](./adr/adr-001-react-fastapi-architecture.md): Architecture details
