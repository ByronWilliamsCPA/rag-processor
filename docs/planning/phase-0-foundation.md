# Phase 0: Foundation - Detailed Plan

<!-- markdownlint-disable MD024 -->

> **Phase Duration**: Week 1 (5 working days, 40 hours)
> **Branch**: `feat/phase-0-foundation`
> **Status**: Planned
> **Updated**: 2025-12-05

## Overview

Establish development environment, Docker Compose infrastructure, and CI/CD pipeline to enable rapid feature development in subsequent phases.

**Parent Plan**: [PROJECT-PLAN.md](./PROJECT-PLAN.md#phase-0-foundation-week-1)

## Phase Objectives

- ✅ Developer can clone → run locally in <15 minutes
- ✅ All services start with single `docker-compose up` command
- ✅ CI pipeline passes on main branch (lint, test, type-check)
- ✅ Pre-commit hooks catch quality issues before commit
- ✅ Hot reload works for both frontend (Vite HMR) and backend (uvicorn --reload)

## Milestones

| Milestone | Target | Exit Criteria | Sprint |
| --------- | ------ | ------------- | ------ |
| M0.1: Docker Foundation | Day 1 | Redis + basic gateway running | S0.1, S0.2 |
| M0.2: Frontend Scaffold | Day 2 | React app with hot reload | S0.3, S0.4 |
| M0.3: CI Pipeline | Day 3 | GitHub Actions passing | S0.5, S0.6 |
| M0.4: Dev Experience | Day 4 | Pre-commit + docs complete | S0.7, S0.8 |
| M0.5: Phase Complete | Day 5 | All validation passing, PR ready | S0.9, S0.10 |

## Sprint Breakdown (3-4 hour sprints)

### Sprint 0.1: Docker Compose Base (3 hours)

**Goal**: Create Docker Compose with Redis and basic gateway service

**Tasks**:

1. Create `docker-compose.yml` with Redis service (1 hour)
   - Redis 7-alpine image
   - AOF persistence configuration (`--appendonly yes --appendfsync everysec`)
   - Docker volume for data persistence
   - Health check command

2. Create basic FastAPI gateway structure (1.5 hours)
   - Create `gateway/` directory
   - Create `gateway/Dockerfile` (multi-stage build)
   - Create `gateway/main.py` with basic FastAPI app
   - Add health check endpoint (`GET /health`)

3. Test Docker Compose startup (0.5 hours)
   - Run `docker-compose up`
   - Verify Redis accessible: `redis-cli ping`
   - Verify gateway health check: `curl localhost:8000/health`

**Exit Criteria**:

- [ ] `docker-compose up` starts Redis and gateway
- [ ] Gateway returns `{"status": "healthy"}` from `/health`
- [ ] Redis `PING` returns `PONG`

**Branch**: `feat/phase-0-foundation`

---

### Sprint 0.2: RQ Worker + Cloudflare Tunnel (3 hours)

**Goal**: Add RQ worker service and Cloudflare Tunnel for ingress

**Tasks**:

1. Add RQ worker to Docker Compose (1 hour)
   - Worker service using same gateway image
   - Command: `rq worker high default low`
   - Shared volumes with gateway for file access
   - Connect to Redis

2. Add Cloudflare Tunnel service (1 hour)
   - Cloudflared service in Docker Compose
   - Environment variable for `TUNNEL_TOKEN`
   - Network configuration
   - `.env.example` with placeholder for tunnel token

3. Test worker connectivity (1 hour)
   - Create test job in Redis
   - Verify worker picks up job
   - Check worker logs for successful connection

**Exit Criteria**:

- [ ] RQ worker starts and connects to Redis
- [ ] Cloudflared service starts (may fail without token, expected)
- [ ] Worker logs show "Listening on high, default, low"

---

### Sprint 0.3: UV Dependencies (3 hours)

**Goal**: Lock backend dependencies with UV

**Tasks**:

1. Add FastAPI dependencies to `pyproject.toml` (1 hour)
   - fastapi, uvicorn[standard], python-multipart
   - redis, rq, httpx
   - python-magic, pdfplumber
   - pydantic, pydantic-settings

2. Add dev dependencies (0.5 hours)
   - pytest, pytest-cov, pytest-asyncio
   - fakeredis (for testing)
   - respx (HTTP mocking)
   - ruff, basedpyright

3. Lock and sync (0.5 hours)
   - Run `uv lock`
   - Run `uv sync --all-extras`
   - Verify installation: `uv run python -c "import fastapi"`

4. Update gateway Dockerfile to use UV (1 hour)
   - Multi-stage build with UV
   - Copy only necessary files for prod
   - Set proper entrypoint

**Exit Criteria**:

- [ ] `uv.lock` file created
- [ ] `uv sync --all-extras` completes successfully
- [ ] All dependencies importable
- [ ] Gateway container builds successfully

---

### Sprint 0.4: Vite React Project (4 hours)

**Goal**: Scaffold React + TypeScript frontend with Vite

**Tasks**:

1. Create React app with Vite (1 hour)
   - Run `pnpm create vite rag-ui --template react-ts`
   - Move to `frontend/` or `rag-ui/` directory
   - Install dependencies: `pnpm install`

2. Add required frontend dependencies (0.5 hours)
   - react-dropzone (file upload)
   - zustand (state management)
   - tailwindcss (styling)

3. Configure TailwindCSS (0.5 hours)
   - Run `pnpm add -D tailwindcss postcss autoprefixer`
   - Initialize: `npx tailwindcss init -p`
   - Configure `tailwind.config.js`
   - Add Tailwind directives to CSS

4. Create frontend Dockerfile (1 hour)
   - Multi-stage: build stage + nginx serve stage
   - Build step: `pnpm run build`
   - Nginx config for SPA routing
   - Environment variable injection for `VITE_API_URL`

5. Add frontend to Docker Compose (1 hour)
   - rag-ui service
   - Build context: ./rag-ui
   - Expose port 80
   - Connect to rag-network

**Exit Criteria**:

- [ ] `pnpm run dev` starts dev server at localhost:3000
- [ ] Frontend container builds successfully
- [ ] `docker-compose up rag-ui` serves React app
- [ ] TailwindCSS styles apply correctly

---

### Sprint 0.5: GitHub Actions CI Workflow (3 hours)

**Goal**: Configure CI pipeline with quality gates

**Tasks**:

1. Create backend CI workflow (1.5 hours)
   - Create `.github/workflows/backend-ci.yml`
   - Jobs: lint (ruff), type-check (basedpyright), test (pytest)
   - Use UV setup action
   - Cache UV dependencies
   - Run on pull requests to main

2. Create frontend CI workflow (1 hour)
   - Create `.github/workflows/frontend-ci.yml`
   - Jobs: lint (eslint), type-check (tsc), test (vitest)
   - Use pnpm setup action
   - Cache pnpm store
   - Run on pull requests to main

3. Test CI locally (0.5 hours)
   - Create test PR
   - Verify all checks pass
   - Fix any failing jobs

**Exit Criteria**:

- [ ] Backend CI workflow runs on PR
- [ ] Frontend CI workflow runs on PR
- [ ] All jobs pass (lint, type-check, test)
- [ ] Checks display on PR page

---

### Sprint 0.6: Pre-commit Hooks (3 hours)

**Goal**: Install and configure pre-commit hooks

**Tasks**:

1. Configure pre-commit for backend (1 hour)
   - Verify `.pre-commit-config.yaml` exists
   - Add hooks: ruff (format + lint), basedpyright, markdownlint
   - Run `uv run pre-commit install`

2. Add frontend pre-commit hooks (1 hour)
   - Add ESLint hook
   - Add Prettier hook
   - Configure to run on staged files only

3. Test pre-commit (1 hour)
   - Make test changes to Python file
   - Make test changes to TypeScript file
   - Verify hooks run automatically on `git commit`
   - Fix any hook failures

**Exit Criteria**:

- [ ] Pre-commit installed: `pre-commit --version`
- [ ] Hooks run on `git commit`
- [ ] Ruff formats Python code automatically
- [ ] ESLint catches TypeScript issues

---

### Sprint 0.7: Local Development Guide (4 hours)

**Goal**: Write comprehensive README for local development

**Tasks**:

1. Update README.md with quick start (1.5 hours)
   - Prerequisites (Docker, UV, Node.js)
   - Clone and install steps
   - `docker-compose up` command
   - Environment variable setup (`.env` from `.env.example`)

2. Add development workflow section (1 hour)
   - Backend development (uvicorn --reload)
   - Frontend development (pnpm run dev)
   - Running tests
   - Pre-commit hooks

3. Add troubleshooting section (1 hour)
   - Common Docker issues
   - Port conflicts
   - Redis connection errors
   - Frontend proxy issues

4. Test documentation (0.5 hours)
   - Follow README from scratch in clean environment
   - Fix any unclear or missing steps

**Exit Criteria**:

- [ ] README has complete Quick Start section
- [ ] All commands in README execute successfully
- [ ] Troubleshooting covers common issues
- [ ] New developer can follow README in <15 min

---

### Sprint 0.8: Environment Configuration (3 hours)

**Goal**: Create environment variable templates and secrets management

**Tasks**:

1. Create `.env.example` template (1 hour)
   - All required environment variables with descriptions
   - Placeholder values
   - Sections: Cloudflare, Redis, Pipelines, Monitoring

2. Create Docker secrets configuration (1 hour)
   - `secrets/` directory structure (gitignored)
   - Example secret files
   - Documentation for generating secrets

3. Update Docker Compose for secrets (1 hour)
   - Add secrets configuration
   - Update services to use secrets
   - Test with example secrets

**Exit Criteria**:

- [ ] `.env.example` includes all variables
- [ ] Secrets documentation complete
- [ ] Docker Compose uses secrets properly
- [ ] Gateway reads environment variables correctly

---

### Sprint 0.9: Integration Testing (3 hours)

**Goal**: Verify all services work together

**Tasks**:

1. Test full Docker Compose stack (1 hour)
   - Start all services: `docker-compose up`
   - Verify gateway can connect to Redis
   - Verify RQ worker can process test job
   - Verify frontend can reach gateway (proxy)

2. Create basic integration test (1.5 hours)
   - Test file: `tests/integration/test_stack.py`
   - Test gateway health check
   - Test Redis connection
   - Test job submission to RQ

3. Run all tests in CI (0.5 hours)
   - Ensure integration tests pass in GitHub Actions
   - Add Docker Compose to CI if needed

**Exit Criteria**:

- [ ] All 5 services running simultaneously
- [ ] Gateway → Redis communication working
- [ ] Worker picks up jobs from queue
- [ ] Frontend proxies API requests to gateway
- [ ] Integration tests pass locally and in CI

---

### Sprint 0.10: Phase Completion & PR (4 hours)

**Goal**: Final validation, documentation, and phase completion PR

**Tasks**:

1. Run all quality checks (1 hour)
   - Backend: `uv run ruff check .`, `uv run basedpyright src/`
   - Frontend: `pnpm run lint`, `pnpm run typecheck`
   - Tests: `uv run pytest`, `pnpm run test`
   - Pre-commit: `uv run pre-commit run --all-files`

2. Update CHANGELOG.md (0.5 hours)
   - Add Phase 0 completion entry
   - List infrastructure components added

3. Create phase completion commit (0.5 hours)
   - Stage all changes
   - Commit with conventional commit format
   - Include detailed footer

4. Create PR for Phase 0 (1 hour)
   - Push branch to remote
   - Create PR with detailed description
   - Add checklist of deliverables
   - Request review (if applicable)

5. Address PR feedback and merge (1 hour)
   - Review CI results
   - Fix any failing checks
   - Merge to main

**Exit Criteria**:

- [ ] All quality checks passing
- [ ] CHANGELOG.md updated
- [ ] PR created and merged
- [ ] Phase 0 branch merged to main
- [ ] Ready to start Phase 1

---

## Phase 0 Deliverables Checklist

### Infrastructure

- [ ] Docker Compose with 5 services (cloudflared, gateway, worker, rag-ui, redis)
- [ ] All services start successfully
- [ ] Services can communicate (gateway → redis, worker → redis)
- [ ] Volumes configured for persistence (redis-data, upload-data, result-data)

### Backend

- [ ] UV dependencies locked in `uv.lock`
- [ ] FastAPI gateway with `/health` endpoint
- [ ] RQ worker configured with priority queues
- [ ] Environment variable configuration (`.env.example`)

### Frontend

- [ ] React 18 + TypeScript + Vite project scaffolded
- [ ] TailwindCSS configured
- [ ] Dev server with HMR working
- [ ] Production Dockerfile with Nginx

### CI/CD

- [ ] Backend CI workflow (lint, type-check, test)
- [ ] Frontend CI workflow (lint, type-check, test)
- [ ] Workflows run on PR to main
- [ ] All checks passing

### Developer Experience

- [ ] Pre-commit hooks installed and working
- [ ] README with complete quick start
- [ ] Local dev guide with troubleshooting
- [ ] Clone-to-running time <15 minutes

## Sprint Schedule

| Sprint | Days | Focus | Hours |
| ------ | ---- | ----- | ----- |
| S0.1 | Day 1 AM | Docker Compose Base | 3 |
| S0.2 | Day 1 PM | RQ Worker + Cloudflare Tunnel | 3 |
| S0.3 | Day 2 AM | UV Dependencies | 3 |
| S0.4 | Day 2 PM | Vite React Project | 4 |
| S0.5 | Day 3 AM | GitHub Actions CI Workflow | 3 |
| S0.6 | Day 3 PM | Pre-commit Hooks | 3 |
| S0.7 | Day 4 AM | Local Development Guide | 4 |
| S0.8 | Day 4 PM | Environment Configuration | 3 |
| S0.9 | Day 5 AM | Integration Testing | 3 |
| S0.10 | Day 5 PM | Phase Completion & PR | 4 |

**Total Estimated Hours**: 33 hours (with 7 hours buffer for Phase 0)

## Dependencies

**External**:

- Docker and Docker Compose installed
- UV installed (backend)
- pnpm installed (frontend)
- Git configured

**Internal**:

- None (first phase)

**Blocks**:

- Phase 1 (cannot start until dev environment ready)

## Validation Checklist

Before completing Phase 0, verify:

- [ ] **Docker Compose**: All 5 services start with `docker-compose up`
- [ ] **Gateway Health**: `curl http://localhost:8000/health` returns 200
- [ ] **Redis**: `docker exec -it rag_processor-redis-1 redis-cli ping` returns PONG
- [ ] **Frontend**: `curl http://localhost:3000` serves React app
- [ ] **CI**: GitHub Actions shows all checks passing
- [ ] **Pre-commit**: `git commit` triggers hooks successfully
- [ ] **Documentation**: Following README takes <15 minutes
- [ ] **Hot Reload**: Backend code changes reload automatically
- [ ] **Hot Reload**: Frontend code changes reload automatically
- [ ] **Tests**: `uv run pytest` passes (even if only placeholder tests)
- [ ] **Linting**: `uv run ruff check .` shows no errors
- [ ] **Type Checking**: `uv run basedpyright src/` passes

## Risk Mitigation

| Risk | Mitigation | Contingency |
| ---- | ---------- | ----------- |
| Docker Compose complexity exceeds 1 day | Use existing Docker Compose examples from similar projects | Simplify to 3 services (gateway, worker, redis) initially |
| Cloudflare Tunnel token unavailable | Implement bypass mode (`CLOUDFLARE_ENABLED=false`) for local dev | Defer Cloudflare integration to Phase 1 |
| UV dependency conflicts | Use specific version constraints | Lock known-working versions from cookiecutter template |
| Frontend build issues | Use official Vite React TypeScript template | Simplify to minimal config |

## Next Phase

After Phase 0 completion:

1. Merge `feat/phase-0-foundation` to main
2. Review [Phase 1 Plan](./phase-1-mvp-core.md)
3. Create branch: `git checkout -b feat/phase-1-mvp-core`
4. Begin Sprint 1.1: Cloudflare Access Authentication

## Related Documents

- [PROJECT-PLAN.md](./PROJECT-PLAN.md): Overall project plan
- [Tech Spec](./tech-spec.md#deployment): Docker Compose specification
- [ADR-001](./adr/adr-001-react-fastapi-architecture.md): Architecture decisions
- [Roadmap](./roadmap.md#phase-0-foundation-week-1): Phase overview
