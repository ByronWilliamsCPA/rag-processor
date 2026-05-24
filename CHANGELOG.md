# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

- **Claude Code settings `$schema` URL** (`fix/claude-settings-schema-url`):
  - Corrected `$schema` in `.claude/settings.json` from `claude-code-config.json`
    (which returns HTTP 404 at schemastore.org) to the valid
    `claude-code-settings.json`
  - The wrong slug caused Claude Code's settings parser to silently reject the
    file, disabling `permissions.allow` / `permissions.deny` enforcement
- **REUSE compliance**: added `.markdownlintignore` and `.secrets.baseline` to
  the CC0-1.0 annotation block in `REUSE.toml` so all 288 project files now
  carry copyright/licensing metadata (was 286/288)
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
