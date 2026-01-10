---
title: "Project Plan: RAG Processor WebUI"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Synthesized project plan with phased implementation strategy."
tags:
  - planning
  - roadmap
  - project
component: Strategy
source: "Synthesized from project-vision.md, tech-spec.md, roadmap.md, adr/adr-001-react-fastapi-architecture.md"
---

> **Generated**: 2025-12-05
> **Status**: Ready for Development
> **Source Documents**: project-vision.md, tech-spec.md, roadmap.md, adr/adr-001-react-fastapi-architecture.md

## Executive Summary

RAG Processor WebUI is a React 18 + FastAPI microservices application that provides authenticated file ingestion for RAG (Retrieval-Augmented Generation) pipelines. The system eliminates operational friction by automatically routing uploaded files (PDFs, images, audio, Office documents) to appropriate preprocessing pipelines (OCR, transcription, document processing, fusion), monitoring job progress in real-time via WebSocket, and delivering processed outputs to configurable vector storage backends—reducing ingestion time from 5+ minutes to <30 seconds while improving routing accuracy from 80-85% to >95%.

**Target Users**: Data engineers and ML engineers building RAG applications who need to ingest diverse document types into vector databases.

**Timeline**: 6 weeks (4-week MVP + 2 weeks enhancement/polish)

**Tech Stack**: Python 3.12, TypeScript, React 18, FastAPI, Redis + RQ, Docker Compose, Cloudflare Access

## Project Scope

### In Scope (MVP)

- ✅ **Cloudflare Access Authentication**: JWT validation, user attribution, session management
- ✅ **Multi-File Upload Interface**: Drag-drop, file validation, batch creation, upload progress
- ✅ **Automatic Content Detection**: Magic byte scanning, MIME validation, PDF classification (scanned vs born-digital)
- ✅ **Pipeline Routing**: Route to OCR, audio transcription, document processing, or fusion pipeline
- ✅ **Job Queue Management**: Redis-backed queue with priority (high/normal/low), batch grouping, lifecycle tracking
- ✅ **Real-Time Status WebSocket**: Per-batch connections with JWT auth, 2-5s updates, error notifications
- ✅ **Vector Storage Integration**: Target registration API, configurable handoff per batch, delivery confirmation
- ✅ **Basic Error Handling**: Unsupported type rejection, size limits, retry mechanism, user-facing errors

### Out of Scope

- ❌ **RAG Query Interface**: User-facing query/chat interfaces (handled by downstream systems)
- ❌ **Pipeline Implementation**: Internal workings of OCR, transcription, document processing (external dependencies)
- ❌ **Identity Provider Management**: Cloudflare Access config, OAuth setup (managed via Cloudflare dashboard)
- 🔄 **Advanced Analytics Dashboard**: Job statistics, processing analytics, cost tracking (Phase 2)
- 🔄 **Bulk Upload via S3/API**: S3 bucket monitoring, programmatic bulk ingestion (Phase 2)
- 🔄 **Custom Pipeline Configuration**: User-defined preprocessing rules (future)

## Git Branch Strategy

| Phase | Branch | Type | Version Impact |
| ----- | ------ | ---- | -------------- |
| Phase 0 | `feat/phase-0-foundation` | feat | Minor (0.X.0) |
| Phase 1 | `feat/phase-1-mvp-core` | feat | Minor (0.X.0) |
| Phase 2 | `feat/phase-2-enhancement` | feat | Minor (0.X.0) |
| Phase 3 | `docs/phase-3-polish` | docs | No release (docs only) |

**Start a phase**:

```bash
git checkout main && git pull origin main
git checkout -b feat/phase-0-foundation
```

**Complete a phase**:

```bash
# Commit all changes with conventional commits
git add .
git commit -m "feat: complete phase 0 foundation

- Docker Compose with all services
- CI/CD pipeline configured
- Local dev environment documented

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Create PR
gh pr create --title "Phase 0: Foundation" --body "$(cat <<'EOF'
## Summary
- Docker Compose with cloudflared, gateway, worker, rag-ui, Redis
- GitHub Actions CI (lint, test, type-check)
- Pre-commit hooks (Ruff, BasedPyright, markdownlint)
- Local dev guide in README

## Test Plan
- [ ] `docker-compose up` starts all services
- [ ] Gateway health check returns 200
- [ ] CI pipeline passes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Phased Development

> **Detailed Phase Plans**: Each phase has a comprehensive plan with 3-4 hour sprints, milestones, and validation checklists.

### Phase 0: Foundation (Week 1)

**Branch**: `feat/phase-0-foundation`
**Duration**: 1 week (10 sprints, 33 hours)
**Dependencies**: None

**📋 Detailed Plan**: [phase-0-foundation.md](./phase-0-foundation.md)

**Deliverables**:

- Docker Compose with all services (cloudflared, gateway, worker, rag-ui, Redis)
- UV dependencies locked (FastAPI, Redis, RQ)
- React + Vite project scaffolded
- GitHub Actions CI configured
- Pre-commit hooks installed
- Local dev guide in README

**Milestones**:

- M0.1: Docker Foundation (Day 1)
- M0.2: Frontend Scaffold (Day 2)
- M0.3: CI Pipeline (Day 3)
- M0.4: Dev Experience (Day 4)
- M0.5: Phase Complete (Day 5)

**Success Criteria**:

- ✅ `docker-compose up` starts all services successfully
- ✅ Gateway health check returns 200
- ✅ CI pipeline passes on main branch
- ✅ Developer can clone → run locally in <15 minutes

**Start Phase**:

```bash
git checkout -b feat/phase-0-foundation
# See phase-0-foundation.md for sprint-by-sprint breakdown
```

---

### Phase 1: MVP Core (Weeks 2-4)

**Branch**: `feat/phase-1-mvp-core`
**Duration**: 3 weeks (24 sprints, 85 hours)
**Dependencies**: Phase 0 complete

**📋 Detailed Plan**: [phase-1-mvp-core.md](./phase-1-mvp-core.md)

**Deliverables**:

- Cloudflare Access authentication (JWT validation)
- Multi-file upload API + React UI
- File type detection and pipeline routing
- Redis job queue with priority
- WebSocket status updates
- Basic error handling

**Milestones**:

- M1.1: Authentication Working (Week 2 End)
- M1.2: File Upload API (Week 3 Mid)
- M1.3: Pipeline Routing (Week 3 End)
- M1.4: Job Queue Complete (Week 4 Mid)
- M1.5: WebSocket Live (Week 4 End)
- M1.6: MVP Complete (Week 4 End)

**Success Criteria**:

- ✅ User uploads PDF → routed to correct pipeline
- ✅ WebSocket shows live updates every 2-5 seconds
- ✅ Failed jobs display error messages
- ✅ Job queue persists across restart
- ✅ 80%+ test coverage on core logic

**Key User Stories**:

1. **US-001: User Authentication** (4 sprints) - Cloudflare Access OAuth flow with JWT validation
2. **US-002: Multi-File Upload** (4 sprints) - Drag-and-drop interface with batch creation
3. **US-003: Automatic Pipeline Routing** (4 sprints) - PDF classification, MIME detection
4. **US-004: Job Queue Management** (4 sprints) - Redis RQ with priority queues, retry logic
5. **US-005: Real-Time Status Updates** (4 sprints) - WebSocket with auto-reconnect, event replay

**Start Phase**:

```bash
git checkout main && git pull
git checkout -b feat/phase-1-mvp-core
# See phase-1-mvp-core.md for 24 sprint breakdown
```

---

### Phase 2: Enhancement (Week 5)

**Branch**: `feat/phase-2-enhancement`
**Duration**: 1 week (10 sprints, 35 hours)
**Dependencies**: Phase 1 complete

**📋 Detailed Plan**: [phase-2-enhancement.md](./phase-2-enhancement.md)

**Deliverables**:

- Vector storage target registration API
- Batch handoff trigger (manual + automatic)
- Result download from completed jobs
- Batch history view (last 50 batches)
- Enhanced error messages

**Milestones**:

- M2.1: Vector Store Registration (Day 1)
- M2.2: Handoff Logic (Day 2)
- M2.3: Result Download (Day 3)
- M2.4: Batch History (Day 4)
- M2.5: Phase Complete (Day 5)

**Success Criteria**:

- ✅ Completed batches auto-handed off to selected vector store
- ✅ Users download processed results (ZIP)
- ✅ Batch history shows last 50 with status filter
- ✅ Error messages include actionable steps

**Key User Stories**:

1. **US-006: Vector Store Handoff** (4 sprints) - Target selection, automatic handoff on completion
2. **US-007: Result Download** (2 sprints) - ZIP archives with metadata

**Start Phase**:

```bash
git checkout main && git pull
git checkout -b feat/phase-2-enhancement
# See phase-2-enhancement.md for 10 sprint breakdown
```

---

### Phase 3: Polish (Week 6)

**Branch**: `docs/phase-3-polish`
**Duration**: 1 week (10 sprints, 35 hours)
**Dependencies**: Phase 2 complete

**📋 Detailed Plan**: [phase-3-polish.md](./phase-3-polish.md)

**Deliverables**:

- Test coverage ≥80% (enforced by CI)
- User documentation complete (user guide, API docs, troubleshooting)
- Performance validated (100 users, 1000 files/hour)
- Security review complete (OWASP Top 10, dependency scans)
- Docker images optimized (<500MB total)

**Milestones**:

- M3.1: Test Coverage Complete (Day 1-2)
- M3.2: Documentation Complete (Day 3)
- M3.3: Performance Validated (Day 4)
- M3.4: Security Validated (Day 4)
- M3.5: Production Ready (Day 5)

**Success Criteria**:

- ✅ All tests passing (unit, integration, E2E)
- ✅ No critical/high security issues
- ✅ README covers setup (<15 min)
- ✅ CHANGELOG updated
- ✅ Load test passes (100 users × 10 files in <5 min)

**Start Phase**:

```bash
git checkout main && git pull
git checkout -b docs/phase-3-polish
# See phase-3-polish.md for 10 sprint breakdown
```

---

## System Architecture

### Pattern

**Microservices with API Gateway** - See [ADR-001](./adr/adr-001-react-fastapi-architecture.md)

Frontend and gateway are separate services. Gateway orchestrates calls to external processing pipelines.

### Components

| Component | Purpose | Key Technologies |
| --------- | ------- | ---------------- |
| React SPA | File upload and monitoring UI | React 18, TypeScript, Vite, TailwindCSS |
| FastAPI Gateway | Authentication, routing, WebSocket | FastAPI, Uvicorn, python-magic, pdfplumber |
| Redis + RQ | Job queue with priority and persistence | Redis 7, Python RQ, AOF persistence |
| RQ Worker | Execute pipeline API calls | httpx (async HTTP client) |
| Cloudflare Access | SSO authentication | OAuth, JWT |
| Cloudflare Tunnel | Secure ingress | TLS 1.3, cloudflared |

### Data Flow

```text
1. User uploads files via React UI → 2. Gateway validates JWT
3. Files saved to Docker volume → 4. Jobs queued in Redis (priority-based)
5. RQ worker submits to external pipeline → 6. Pipeline processes file
7. Worker publishes status to Redis → 8. Gateway broadcasts via WebSocket to client
9. On completion, trigger vector store handoff
```

## Technology Stack

**Backend**: Python 3.12, FastAPI, Redis, RQ, python-magic, pdfplumber, httpx
**Frontend**: React 18, TypeScript, Vite, react-dropzone, zustand
**Infrastructure**: Docker Compose, Cloudflare Tunnel, Prometheus, Grafana
**Code Quality**: Ruff, BasedPyright strict, pytest 80%+ coverage

## Architecture Decisions

### ADR-001: React + FastAPI Microservices Architecture

**Status**: Accepted
**Summary**: Use React 18 frontend with FastAPI gateway to orchestrate file ingestion
**Rationale**:

- Familiar tech stack (existing Python/TypeScript expertise)
- Native async WebSocket support in FastAPI
- Clear separation: UI → orchestration → processing
- Horizontal scaling path for >100 users

**Key Design Decisions**:

- **Security**: Cloudflare Access JWT validation, magic byte MIME detection, 100MB/file limit
- **Error Handling**: Fail fast for user errors, graceful degradation for pipeline failures (3x retry)
- **WebSocket Resilience**: Event log in Redis for reconnect replay, graceful shutdown on SIGTERM
- **Redis HA**: AOF persistence (`appendfsync everysec`), 7-day TTL for events
- **Pipeline Adapter Pattern**: Abstract interface for extensibility (add new pipelines via config)

[Full ADR](./adr/adr-001-react-fastapi-architecture.md)

---

## Risk Management

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Cloudflare Access integration delays | M | H | Obtain credentials in Phase 0; bypass mode for local dev |
| External pipeline APIs unstable/undocumented | H | H | Mock APIs in tests; 2-day buffer for discovery |
| WebSocket scaling >100 connections | L | M | Load test early (Phase 3); fallback to polling |
| PDF classification accuracy <95% | M | M | Validate with sample dataset; manual re-route option |
| File upload size limits too restrictive | L | M | Validate with users; chunked upload in Phase 2 extension |
| Redis memory exhaustion | L | M | 7-day TTL; monitor memory usage |

## Success Metrics

**Operational**:

- Time to Ingest: 5+ min → <30s (6x improvement)
- Routing Accuracy: 80-85% → >95%
- User Onboarding: 2+ hours → <15 min
- Job Visibility: No real-time status → Live updates every 2-5s

**Technical**:

- File upload (10MB): <2s (p95)
- WebSocket latency: <2s (status change to client receipt)
- Concurrent users: 100+
- Job throughput: 1000+ files/hour
- Test coverage: ≥80%

## Dependencies & Requirements

**External**:

- Cloudflare Access pre-configured with audience tags
- External pipeline APIs (OCR, transcription, document processing, fusion) stable and documented
- Vector storage backends (Qdrant, Milvus) accessible

**Internal**:

- Docker Compose environment
- Redis 7+ with AOF persistence
- Python 3.12+, Node.js 18+ (frontend build)

## Next Steps

1. **Review this synthesized plan** for accuracy and completeness
2. **Start Phase 0**:

   ```bash
   git checkout -b feat/phase-0-foundation
   ```

3. **Track progress** with TodoWrite tool in Claude Code
4. **Complete phases** with conventional commits and PR workflow

## Sprint-Based Execution

This project plan is supported by detailed phase plans that break work into 3-4 hour sprints:

| Phase | Detailed Plan | Sprints | Total Hours |
| ----- | ------------- | ------- | ----------- |
| **Phase 0: Foundation** | [phase-0-foundation.md](./phase-0-foundation.md) | 10 sprints | 33 hours |
| **Phase 1: MVP Core** | [phase-1-mvp-core.md](./phase-1-mvp-core.md) | 24 sprints | 85 hours |
| **Phase 2: Enhancement** | [phase-2-enhancement.md](./phase-2-enhancement.md) | 10 sprints | 35 hours |
| **Phase 3: Polish** | [phase-3-polish.md](./phase-3-polish.md) | 10 sprints | 35 hours |

**Total Estimated**: 54 sprints, 188 hours across 6 weeks (with 52 hours buffer)

Each sprint includes:

- Clear goal and exit criteria
- Task breakdown with time estimates
- Testing requirements
- Integration points

---

## Architecture Pivot: Paperless-ngx Integration (2026-01-10)

> **Status**: Proposed | See [ADR-002](./adr/adr-002-paperless-ngx-integration.md)

### Rationale

After researching the open-source ecosystem, we propose integrating with **Paperless-ngx** as the user-facing document management system rather than building a custom React WebUI. This decision is driven by:

1. **Paperless-ngx** provides a mature, feature-rich document management UI
2. **Paperless-AI** demonstrates successful RAG integration patterns
3. **Docling** (IBM) offers superior OCR with layout-aware extraction

### New Architecture

```
┌─────────────────────────────────────┐
│     Paperless-ngx (User-Facing)     │
│  • Document upload, preview, tags   │
│  • Full-text search (Whoosh)        │
│  • User management                  │
└──────────────┬──────────────────────┘
               │ Webhook / API
               ▼
┌─────────────────────────────────────┐
│     RAG Processor (This Project)    │
│  • Docling OCR pipeline             │
│  • Hierarchical chunking            │
│  • Vector embedding generation      │
│  • Semantic search                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│     Vector Database (Qdrant)        │
│  • Semantic embeddings              │
│  • Metadata filtering               │
│  • Hybrid search (vector + BM25)    │
└─────────────────────────────────────┘
```

### Impact on Phases

| Original Phase | Updated Focus |
|----------------|---------------|
| Phase 0: Foundation | Add Paperless-ngx to Docker Compose, configure integration |
| Phase 1: MVP Core | Replace custom UI with Paperless webhook integration, Docling pipeline |
| Phase 2: Enhancement | Vector store indexing, hybrid search |
| Phase 3: Polish | RAG query API, metadata sync, documentation |

### Key Documents

- **Architecture Decision**: [ADR-002: Paperless-ngx Integration](./adr/adr-002-paperless-ngx-integration.md)
- **Technical Analysis**: [Paperless Integration Analysis](./paperless-integration-analysis.md)

---

## Document References

**Planning Documents**:

- [Project Vision & Scope](./project-vision.md): Problem statement, target users, scope boundaries, success metrics
- [Technical Specification](./tech-spec.md): Architecture, API endpoints, data model, security, performance
- [Development Roadmap](./roadmap.md): Phase overview with user stories and dependencies
- [Architecture Decisions](./adr/): ADR-001 (React + FastAPI), ADR-002 (Paperless-ngx Integration)
- [Paperless Integration Analysis](./paperless-integration-analysis.md): Deep dive technical analysis

**Phase Plans** (Sprint-Level Detail):

- [Phase 0: Foundation](./phase-0-foundation.md): 10 sprints - Docker Compose, CI/CD, dev environment
- [Phase 1: MVP Core](./phase-1-mvp-core.md): 24 sprints - Auth, upload, routing, queue, WebSocket
- [Phase 2: Enhancement](./phase-2-enhancement.md): 10 sprints - Vector store handoff, downloads, history
- [Phase 3: Polish](./phase-3-polish.md): 10 sprints - Testing, docs, performance, security, release
