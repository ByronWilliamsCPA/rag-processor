# ADR-001: React Frontend with FastAPI Gateway Architecture

> **Status**: Accepted
> **Date**: 2025-12-04

## TL;DR

We will use a React 18 frontend with FastAPI backend gateway architecture to provide a unified web interface for RAG pipeline ingestion, enabling seamless integration with existing Python-based processing pipelines while delivering a modern, responsive user experience.

## Context

### Problem

The RAG processing ecosystem consists of multiple specialized pipelines (Projects A-E) built in Python, each requiring file ingestion and job orchestration. Users need:

- Modern, responsive web interface for file upload and monitoring
- Real-time status updates during processing
- Integration with existing Python-based pipeline infrastructure
- Cloudflare Access authentication for secure access
- Minimal operational complexity for single-developer deployment

### Constraints

- **Technical**: Must integrate with existing Python-based Projects A-E APIs, Cloudflare Access authentication, Docker Compose deployment
- **Business**: Single developer resource, 4-6 week timeline, must leverage existing infrastructure

### Significance

This architectural decision determines the tech stack, deployment model, development workflow, and integration patterns for the entire WebUI system. The wrong choice could lead to:

- Difficult integration with Python pipeline infrastructure
- Poor developer productivity due to language/framework mismatch
- Complex deployment requiring multiple technology stacks
- Authentication integration challenges

## Decision

**We will use React 18 (TypeScript) for the frontend and FastAPI (Python 3.12+) for the API gateway because it provides the optimal balance of modern UX capabilities, seamless Python pipeline integration, and operational simplicity.**

### Rationale

1. **Python Ecosystem Alignment**: FastAPI allows gateway logic to be written in Python 3.12+, matching Projects A-E technology stack, enabling code reuse for file type detection, error handling, and API client patterns
2. **Modern Frontend Experience**: React 18 provides concurrent rendering, modern hooks, and extensive UI component libraries (TailwindCSS, Headless UI) for rapid development of drag-and-drop upload and real-time monitoring interfaces
3. **WebSocket Support**: Both React and FastAPI have first-class WebSocket support, critical for real-time job status updates
4. **Authentication Compatibility**: FastAPI middleware pattern directly supports the williaby/testing cloudflare-auth package without adaptation layers
5. **Single Developer Efficiency**: Developer already familiar with Python ecosystem reduces context-switching overhead

## Options Considered

### Option 1: React + FastAPI (Python) ✓

**Pros**:

- ✅ Native Python integration with Projects A-E (shared libraries, error handling, data models)
- ✅ FastAPI's automatic OpenAPI docs accelerate API development
- ✅ Built-in async/await support for WebSocket and external API calls
- ✅ Cloudflare auth middleware drops in directly (Python package)
- ✅ Single language (Python) for all backend services simplifies deployment

**Cons**:

- ❌ Two separate build processes (npm for React, Docker for FastAPI)
- ❌ CORS configuration required for local development

### Option 2: Next.js (Full-Stack React)

**Pros**:

- ✅ Single framework for frontend and API routes
- ✅ Server-side rendering for faster initial page loads
- ✅ API routes in TypeScript co-located with frontend

**Cons**:

- ❌ Node.js API routes require rewriting Python integration logic (file detection, pipeline clients)
- ❌ Cloudflare auth middleware not available in Node.js (would need custom JWT validation)
- ❌ Disconnected tech stack from Projects A-E (Python) creates maintenance burden
- ❌ Developer unfamiliar with Node.js ecosystem (learning curve)

### Option 3: Django + HTMX

**Pros**:

- ✅ Full Python stack with integrated admin panel
- ✅ Simpler deployment (single Django app)

**Cons**:

- ❌ HTMX lacks rich UI component ecosystem compared to React
- ❌ WebSocket support less mature than FastAPI
- ❌ Heavy framework overhead for primarily API gateway use case
- ❌ Limited real-time UI updates without additional complexity

## Consequences

### Positive

- ✅ **Rapid Backend Development**: FastAPI's automatic validation, serialization, and OpenAPI generation accelerate gateway development by ~30%
- ✅ **Code Reuse**: Python file type detection logic, Pydantic models, and exception handling can be shared between gateway and Projects A-E
- ✅ **Modern UX**: React ecosystem provides battle-tested components for file upload (react-dropzone), progress indicators, and WebSocket clients
- ✅ **Simplified Auth**: Cloudflare middleware integrates in <10 lines of code with no custom JWT handling

### Trade-offs

- ⚠️ **Dual Build Process**: Frontend (npm) and backend (Docker) require separate build steps—mitigated by Docker Compose orchestration
- ⚠️ **CORS Complexity**: Local development requires CORS configuration—mitigated by environment-specific settings and documented setup
- ⚠️ **TypeScript/Python Context Switching**: Developer must work in two languages—acceptable given clear separation of concerns (UI vs API)

### Technical Debt

- **Frontend State Management**: Initial implementation uses React Context; if state complexity grows, consider migrating to Zustand or Redux Toolkit (deferred to Phase 2)
- **API Client Generation**: Manually written TypeScript API client; consider OpenAPI code generation if API surface expands significantly (deferred)

## Implementation

### Components Affected

1. **Frontend (rag-ui/)**: React 18 + TypeScript + Vite build system, TailwindCSS for styling, react-dropzone for file upload, native WebSocket API for real-time updates
2. **API Gateway (gateway/)**: FastAPI application with cloudflare-auth middleware, Redis client for job queue, HTTP clients for Projects A-E, WebSocket server for status broadcasts
3. **Deployment**: Docker Compose with separate services for frontend (nginx-served static build) and gateway (uvicorn ASGI server)

### Testing Strategy

- **Unit**:
  - Frontend: Vitest + React Testing Library (component tests, mock WebSocket)
  - Gateway: pytest with FastAPI TestClient (endpoint tests, mock external services)
- **Integration**: E2E tests using Playwright covering file upload → routing → status updates → results retrieval workflow

## Validation

### Success Criteria

- [ ] Developer can run full stack (React dev server + FastAPI gateway + Redis) locally in <15 minutes following README
- [ ] File upload to job completion workflow completes in <5 seconds for test files
- [ ] WebSocket latency <500ms for status updates in local testing
- [ ] Frontend build produces <500KB gzipped bundle size
- [ ] Gateway handles 50 concurrent file uploads without errors

### Review Schedule

- **Initial**: End of Phase 0 (week 1) - validate local dev workflow and basic file upload
- **Ongoing**: Re-evaluate if WebSocket scaling becomes bottleneck (>100 concurrent connections) or state management complexity increases

## Related

- [Project Vision](../project-vision.md#constraints) - References React 18 and FastAPI as core technologies
- [Tech Spec](../tech-spec.md#technology-stack) - Detailed tech stack specifications
- [ADR-002](./adr-002-redis-job-queue.md) - Job queue technology choice (Redis + RQ)
- [ADR-003](./adr-003-cloudflare-auth.md) - Authentication strategy
