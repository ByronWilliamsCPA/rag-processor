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

- **Fuzzing Infrastructure**: Added ClusterFuzzLite integration with Atheris
  - `fuzz_file_classifier.py` - Tests PDF classification with malformed input
  - `fuzz_file_detector.py` - Tests MIME type detection
  - `fuzz_jwt_validation.py` - Tests JWT header parsing
- **Workflow Fixes**: Resolved permission and concurrency issues in reusable workflows
  - Fixed CI concurrency deadlock with org workflow
  - Fixed SBOM permission requirements for artifact metadata
  - Fixed Security Analysis permissions for CodeQL

### Changed

- Updated `.env.example` with Redis, Cloudflare, and pipeline configuration
- Enhanced Dockerfile with `/data` directory creation for file storage
- Fixed `MutableHeaders.pop()` bug in security middleware

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
