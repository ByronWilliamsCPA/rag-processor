# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Renovate covers the npm frontend**: added `npm` to `enabledManagers` in
  `renovate.json` so `frontend/package.json` and `frontend/package-lock.json`
  are managed (previously only `pep621` and `github-actions` were enabled,
  leaving the frontend's npm vulnerabilities unmanaged). The `npm` datasource
  was added to both security `packageRules` so frontend CVEs receive the same
  priority and labels as Python, and a "npm dependencies" grouping rule keeps
  frontend update PRs batched.

### Removed (BREAKING)

- **Python 3.10 support dropped** (2026-05-24): codebase now uses `StrEnum`
  (introduced in Python 3.11) in `src/rag_processor/models/batch.py`,
  `src/rag_processor/models/job.py`, and `src/rag_processor/websocket/events.py`.
  `requires-python` in `pyproject.toml` raised from `>=3.10,<3.15` to
  `>=3.11,<3.15`. CI Python Compatibility Matrix updated to test 3.11/3.12/3.13.
  See `docs/PYTHON_COMPATIBILITY.md` for migration notes.

### Fixed

- **WebSocket `ConnectionManager` concurrency (C3)**: `broadcast` now iterates a
  snapshot of the connection set, so a concurrent connect/disconnect during an
  awaited send can no longer raise "Set changed size during iteration". The
  manager uses a plain `dict` with non-resurrecting cleanup (`.get`/`.pop`) in
  `broadcast` and `disconnect`, so a batch emptied/removed by a concurrent
  disconnect is not silently recreated as an empty set (key leak).
- **Event bridge listener resilience**: the Redis pub/sub `EventBridge` no longer
  dies silently on an unexpected message. `_relay` drops valid-but-non-object
  JSON payloads instead of raising `AttributeError`; the listener wraps each
  relay in a resilience boundary so one bad event (or a client disconnect during
  broadcast) is logged and skipped rather than killing the task; `_cleanup` uses
  separate suppress blocks so the connection handle is always closed (no leak per
  reconnect); and the listener task carries a done-callback that records an
  unexpected exit and clears `running` so it stops reporting a false healthy
  state. The reconnect backoff now resets only on a cleanly relayed event, not on
  a bare subscription acknowledgement.
- **`broadcast` tolerates abrupt client disconnects**: `ConnectionManager.broadcast`
  now also catches `WebSocketDisconnect` (which subclasses only `Exception`), so a
  client dropping mid-broadcast prunes that client instead of aborting delivery to
  the remaining clients and propagating to the caller.
- **Rate-limit tracking-table bound (H6 hardening)**: `max_tracked_ips` is now
  enforced on insert in `RateLimitMiddleware.dispatch`, not only during the
  time-gated periodic cleanup. This keeps the cap effective under a flood of
  distinct client IPs once `rate_limit_trust_proxy` is enabled. Non-IP values in
  the trusted proxy header are rejected (fall back to the peer address) so they
  cannot be injected as tracking keys.
- **CI unblock (RUF100)**: removed `# noqa: ASYNC240` from
  `src/rag_processor/api/ingest.py:404`; ASYNC240 is a preview-only ruff rule
  and the noqa was flagged as unused. Inline comment retained as rationale for
  future re-introduction once preview mode is enabled.
- **CLAUDE.md cross-references**: corrected 6 broken paths from
  `~/.claude/.claude/rules/` (typo) to `~/.claude/rules/`.

### Added

#### WebSocket & Rate Limiting (Tier 2)

- **Proxy-aware rate limiting (H6)**: `RateLimitMiddleware` can resolve the
  client IP from a configured header via the new default-off
  `rate_limit_trust_proxy` and `rate_limit_client_ip_header`
  (default `CF-Connecting-IP`) settings. Default-off is deliberate: the header
  is only trusted behind a proxy that overwrites it, otherwise clients could
  spoof it to evade per-IP limits. Behind Cloudflare this makes per-IP limiting
  effective again instead of keying every request on the proxy IP.

#### Ingestion Pipeline & Architecture Review

- **Background ingestion pipeline** wired end-to-end: uploaded batches/jobs are
  persisted to Redis and enqueued to RQ, gated behind the new default-off
  `RAG_PROCESSOR_ENQUEUE_ENABLED` setting so deployments without an RQ worker
  keep accepting uploads. Enqueue is all-or-nothing (partial failures roll back
  Redis state and cancel enqueued jobs); the worker records failures
  best-effort and skips jobs whose parent batch has disappeared.
- **Unified synchronous Redis client** (`core/redis.py`) with shared, lazily
  built (thread-safe) connection pools and graceful shutdown, replacing
  per-module client construction. Async handlers use non-blocking
  `get_batch_status_async` / `get_job_status_async` wrappers.
- **Consolidated Cloudflare JWT validation**: HTTP-middleware and WebSocket
  paths share one JWKS loader (with single-flight refresh lock) and decode
  helper, so both enforce the same RS256 + audience + issuer checks and clock-skew leeway.
- **Domain exception hierarchy wired into FastAPI** via an exception handler
  mapping `ProjectBaseError` subclasses to HTTP responses.
- **Real-time event delivery to WebSocket clients** via a new
  `EventBridge` (`websocket/bridge.py`) that subscribes to the Redis
  `batch:*:events` pub/sub channels and relays each event to the locally
  connected clients. Started and stopped in the application lifespan; degrades
  gracefully when Redis is unavailable and reconnects with bounded exponential
  backoff after transient outages. Previously, worker events were published to
  Redis but never reached browsers (clients saw only the initial snapshot and
  `last_event_id` replay).
- **Application factory** (`create_app()` in `main.py`) is now the single source
  of truth for middleware ordering and CORS, replacing the import-time global
  app construction. The `FileRouter` is injected via `Depends(get_file_router)`
  (`api/dependencies.py`) instead of a module-level singleton, giving tests an
  override seam.

### Fixed (Architecture Review follow-up)

- **Duplicate CORS middleware removed**: `add_security_middleware` no longer
  registers a second, conflicting `CORSMiddleware` (empty origins,
  `allow_headers=["*"]`) on top of the application's own. It now configures CORS
  only when the caller explicitly supplies `allowed_origins`; `create_app` owns
  CORS for the gateway.
- **Docker Compose Redis wiring**: the `app` and `worker` services only received
  `REDIS_URL`/`LOG_LEVEL`, but application code reads the `RAG_PROCESSOR_`-prefixed
  settings, so both silently fell back to `redis_host=localhost` and never
  reached the `redis` service. Added `RAG_PROCESSOR_REDIS_*` (plus log/enqueue)
  variables to both services and switched the worker to the `rq worker` console
  script.

#### Phase 0: Foundation Infrastructure

- **FastAPI Gateway**: Main application entry point (`src/rag_processor/main.py`)
  - Health check endpoints (`/health/live`, `/health/ready`, `/health/startup`)
  - CORS middleware for frontend integration
  - Correlation ID middleware for distributed tracing
  - Security headers middleware (OWASP compliance)
- **Docker Compose Services**:
  - Redis with AOF persistence for job queue and caching
  - RQ worker for background job processing (high/default/low queues)
  - Cloudflared tunnel for secure ingress
  - PostgreSQL database
  - React frontend with hot reload
- **File Storage Infrastructure**:
  - Upload and result data volumes
  - `/data/uploads` and `/data/results` directories in container
- **RAG Pipeline Dependencies**:
  - RQ (Redis Queue) for job management
  - httpx for async HTTP client
  - python-magic for file type detection
  - pdfplumber for PDF text extraction

#### CI/CD Improvements

- **OpenAPI Schema Export** (`scripts/export_openapi.py`): offline schema
  generation via `app.openapi()` without a live server; post-processes the
  schema to add the Cloudflare Access JWT security scheme and per-operation
  `security` blocks so generated clients reflect the authentication contract
- **Postman Collection** (`docs/api/postman-collection.json`): API contract
  tests covering health probes, user, ingest, and batch endpoints with
  request/response assertions
- **Newman CI Workflow** (`.github/workflows/postman-api-tests.yml`): runs
  the Postman collection against a locally-spawned FastAPI instance with a
  Redis service on every push and pull request to `main`

- **Fuzzing Infrastructure**: Added ClusterFuzzLite integration with Atheris
  - `fuzz_file_classifier.py` - Tests PDF classification with malformed input
  - `fuzz_file_detector.py` - Tests MIME type detection
  - `fuzz_jwt_validation.py` - Tests JWT header parsing
- **Workflow Fixes**: Resolved permission and concurrency issues in reusable workflows
  - Fixed CI concurrency deadlock with org workflow
  - Fixed SBOM permission requirements for artifact metadata
  - Fixed Security Analysis permissions for CodeQL

#### Phase 1: Test Coverage and CI Completeness

- **Playwright E2E CI job**: Added `playwright-e2e` job to `.github/workflows/ci.yml`
  - Runs `frontend/e2e/auth.spec.ts` authentication flow tests on every PR and push to `main`
  - Uploads Playwright HTML report as a CI artifact (7-day retention)
  - `ci-gate` now requires both `ci` and `playwright-e2e` to pass before merge
- **Unit test coverage**: Three new unit test modules to close Phase 1 coverage gaps
  - `tests/unit/test_time_utils.py`: full coverage for `rag_processor.utils.time_utils`
  - `tests/unit/test_middleware_security.py`: security headers, rate limiting, SSRF prevention
  - `tests/unit/test_auth_cloudflare.py`: Cloudflare JWT verification and JWKS cache behavior
- **Vitest/Playwright conflict resolved**: `frontend/vitest.config.ts` now has an explicit
  `include` pattern restricting Vitest to `src/` so it no longer collects Playwright E2E specs

### Fixed

- **Test infrastructure gaps** (`fix/phase-1-completion`):
  - Added `anyio[trio]` as an explicit dev dependency so `@pytest.mark.anyio`
    tests in `test_auth_cloudflare.py` are not silently skipped if the
    transitive dependency is dropped
  - Narrowed `SecurityConfig.test_frozen` assertion from
    `(AttributeError, TypeError)` to `dataclasses.FrozenInstanceError` for a
    precise contract check; added `test_frozen_raises_on_bool_mutation` case
  - Updated skipped WebSocket test reason to reference issue #44
  - Applied `ruff format` to `test_middleware_security.py` (missed before commit)
  - Resolved rebase conflicts with `main` across `test_time_utils.py`,
    `test_middleware_security.py`, `test_auth_cloudflare.py`, and `ci.yml`

### Changed

- Updated `.env.example` with Redis, Cloudflare, and pipeline configuration
- Enhanced Dockerfile with `/data` directory creation for file storage
- Fixed `MutableHeaders.pop()` bug in security middleware
- **TruffleHog pre-commit hook** (`.pre-commit-config.yaml`): scoped to staged
  files via `trufflehog filesystem` instead of `trufflehog git --since-commit HEAD`,
  which was producing false positives from fetched remote branches in the local
  object store. Hook entry now uses an explicit `if/then/else` so that
  TruffleHog's `--fail` exit code propagates correctly; the previous
  `(command -v ... && trufflehog ...) || echo "not installed"` parse silently
  swallowed real secret detections. Resolves observation #4 from the skill
  observation log; part of the fleet-wide TruffleHog rollout.

### Added (Testing)

- Integration tests for gateway health endpoints
- Integration tests for CORS headers and correlation IDs
- Integration tests for OpenAPI documentation endpoints
- Unit tests for Redis operations using fakeredis
- Unit tests for RQ-style queue patterns

### Documentation

- Added "Local Development with Docker" section to README
- Docker Compose quick start guide
- Service verification instructions
- Troubleshooting guide

## [0.1.0] - TBD

### Added

- Initial project structure with Poetry package management
- Pydantic v2 JSON schema validation
- Structured logging with structlog and rich console output
- Pre-commit hooks (Ruff format, Ruff lint, BasedPyright, Bandit, Safety)
- Comprehensive test suite with pytest
- GitHub Actions CI/CD pipeline with quality gates
- CLI tool foundation
- License

### Documentation

- README with project overview and quick start
- CONTRIBUTING guidelines with development workflow
- References to ByronWilliamsCPA org-level Security Policy
- References to ByronWilliamsCPA org-level Code of Conduct

### Infrastructure

- Poetry dependency management with lock file
- pytest test framework with coverage reporting
- GitHub issue tracking and templates
- Automated dependency security scanning (Safety, Bandit)
- Code quality enforcement (Ruff, BasedPyright)
- CI/CD pipeline with multiple quality gates

### Security

- Bandit security linting
- Safety dependency vulnerability scanning
- Pre-commit hooks for security validation

[Unreleased]: https://github.com/ByronWilliamsCPA/rag_processor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ByronWilliamsCPA/rag_processor/releases/tag/v0.1.0
