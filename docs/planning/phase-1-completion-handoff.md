---
title: "Phase 1 Completion Handoff"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Handoff to a second team to close the remaining Phase 1 gaps and satisfy all acceptance criteria."
component: Development-Tools
source: "Phase 1 completion planning"
tags:
  - ci_cd
  - mvp
  - testing
---

**Project**: rag-processor
**Repository**: [github.com/ByronWilliamsCPA/rag-processor](https://github.com/ByronWilliamsCPA/rag-processor)
**Branch**: `main`
**Prepared by**: Byron Williams / Claude Code
**Date**: 2026-05-23

---

## Summary

Phase 1 MVP Core is functionally complete. All five user stories are
implemented: Cloudflare JWT authentication, multi-file upload, automatic
pipeline routing, Redis job queue, and WebSocket real-time status updates.
334 backend tests pass with 82.95% coverage.

Three gaps remain before Phase 1 can be formally closed:

1. **Vitest accidentally collects Playwright E2E specs** (one-line config fix)
2. **Playwright E2E tests are not in CI** (sprint S1.4 exit criterion)
3. **Three backend modules have coverage below the 80% floor** (targeted test additions)

No architecture or application logic changes are needed. All work is
test-infrastructure and test-addition only.

---

## What Is Already Working

These items are verified passing and require no action:

- **CI workflow** (`ci.yml`): 334 backend tests, 82.95% coverage, all checks pass
- **Authentication**: `CloudflareAuthMiddleware` + `get_current_user` dependency fully
  implemented and tested
- **File Upload API**: `POST /api/v1/ingest` with magic byte MIME validation,
  100 MB limit, batch and job creation
- **Pipeline Routing**: `FileTypeDetector`, `PDFClassifier`, `FileRouter` all
  implemented and tested
- **Redis Job Queue**: RQ priority queues (high / default / low), AOF persistence,
  retry logic (3x exponential backoff), `GET /api/v1/batch/{id}` and
  `GET /api/v1/job/{id}` endpoints
- **WebSocket**: `/ws/batch/{batch_id}` endpoint with JWT auth, connection manager,
  event replay from Redis on reconnect, `useWebSocket` React hook
- **Frontend unit tests**: 29 Vitest tests across `App.test.tsx`,
  `Header.test.tsx`, `FileUpload.test.tsx` -- all passing
- **Frontend build**: TypeScript compiles clean, ESLint passes with 0 warnings
- **BasedPyright**: 0 errors (strict mode)
- **Ruff**: all checks passed (scoped to `src/`)

---

## Gap 1: Vitest collects `e2e/auth.spec.ts`

**Severity**: Medium. Breaks `npx vitest run` with no test-path scope.

**Symptom**: Running `npx vitest run` from the repo root (or from
`frontend/`) without a path argument causes Vitest to collect
`e2e/auth.spec.ts`. The file imports from `@playwright/test`, which
conflicts with Vitest's internal test API. The run fails with:

```text
Error: Playwright Test did not expect test.describe() to be called here.
```

The underlying cause is that `vitest.config.ts` has no `include` or `exclude`
pattern that excludes the `e2e/` directory. Playwright tests must be run via
`npx playwright test`, not through Vitest.

**Verification command**:

```bash
cd frontend
npx vitest run          # currently: 1 test file fails
npx vitest run src/     # currently: 3 test files pass (workaround)
```

### Fix: Exclude `e2e/` from Vitest

In `frontend/vitest.config.ts`, add `'e2e/**'` to the `exclude` list inside
the `test` block:

```typescript
// Before
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html', 'lcov'],
        exclude: [
          'node_modules/',
          'src/test/',
          'src/client/',
          '**/*.d.ts',
          '**/*.config.*',
        ],
      },
    },
  })
)
```

```typescript
// After -- add include and e2e coverage exclusion
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html', 'lcov'],
        exclude: [
          'node_modules/',
          'src/test/',
          'src/client/',
          'e2e/',
          '**/*.d.ts',
          '**/*.config.*',
        ],
      },
    },
  })
)
```

After this change, `npx vitest run` without a path argument will collect only
`src/` tests and all three test files will pass.

---

## Gap 2: Playwright E2E tests are not in CI

**Severity**: Medium. Sprint S1.4 exit criterion requires E2E tests to pass
in CI. The `e2e/auth.spec.ts` tests exist locally but are not wired into any
GitHub Actions workflow.

**Playwright config**: `frontend/playwright.config.ts` defines the
test directory as `e2e/` and a webServer pointing to
`http://localhost:3000`. The server must be running before Playwright connects.

**Verification**:

```bash
# Run locally (requires dev server started separately)
npm run dev &
npx playwright test
```

### Fix: Add a Playwright job to `ci.yml`

Add a new job to `.github/workflows/ci.yml` that:

1. Installs Node dependencies and Playwright browsers
2. Starts the Vite dev server in the background
3. Runs `npx playwright test`
4. Uploads the Playwright HTML report as an artifact

Minimal job skeleton (adjust the `needs:` and `if:` gates to match the
existing CI structure):

```yaml
playwright-e2e:
  name: Playwright E2E
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: frontend
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
    - run: npx playwright install --with-deps chromium
    - run: npx playwright test
      env:
        BASE_URL: http://localhost:3000
        CLOUDFLARE_ENABLED: 'false'
    - uses: actions/upload-artifact@v4
      if: always()
      with:
        name: playwright-report
        path: frontend/playwright-report/
        retention-days: 7
```

Set `CLOUDFLARE_ENABLED=false` so the app runs in bypass mode and the auth
tests use `dev@localhost` without a real Cloudflare Access token.

The Playwright config already has a `webServer` block that starts the dev
server automatically when the `BASE_URL` environment variable is set, so no
separate start step is needed once the config is confirmed.

---

## Gap 3: Three backend modules below the 80% coverage floor

**Severity**: Medium. The overall coverage gate (80%) passes because other
modules offset these three. The project-level standard requires 80% per
module on security-critical paths.

| Module | Coverage | Missing lines |
| ------ | -------- | ------------- |
| `middleware/security.py` | 36% | 88 of 153 stmts |
| `auth/cloudflare.py` | 60% | 44 of 123 stmts |
| `utils/time_utils.py` | 0% | 12 of 12 stmts |

### 3a: `middleware/security.py` (36%)

**File**: [src/rag_processor/middleware/security.py](../../src/rag_processor/middleware/security.py)

The uncovered lines (85, 110, 151-157, 170-197, 215-263, 322-330, 342-356,
368-374, 386-392, 403-404, 415-418, 431-442, 453-460, 477-479, 533, 537, 541,
562) are primarily:

- Individual security header getter/setter methods (`csp_policy`, `hsts_max_age`,
  `x_frame_options`, etc.)
- The `add_security_middleware()` convenience function
- The `SecurityConfig.from_env()` factory

**Tests to add** (target file:
`tests/unit/test_middleware_security.py`):

```python
# Test SecurityConfig.from_env() picks up environment variables
def test_security_config_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://example.com")
    config = SecurityConfig.from_env()
    assert "https://example.com" in config.cors_allowed_origins

# Test add_security_middleware() wires middleware into the app
def test_add_security_middleware_attaches_to_app():
    app = FastAPI()
    add_security_middleware(app)
    # Verify middleware stack contains SecurityMiddleware

# Test each security header method round-trips correctly
@pytest.mark.parametrize("method,value", [
    ("csp_policy", "default-src 'self'"),
    ("hsts_max_age", 63072000),
    ("x_frame_options", "SAMEORIGIN"),
])
def test_security_header_setters(method, value):
    config = SecurityConfig()
    setattr(config, method, value)
    assert getattr(config, method) == value
```

### 3b: `auth/cloudflare.py` (60%)

**File**: [src/rag_processor/auth/cloudflare.py](../../src/rag_processor/auth/cloudflare.py)

The uncovered lines (55, 63-64, 145-147, 204-205, 229-244, 258-260, 301-341)
are primarily:

- JWKS key download failure path (`_fetch_jwks` when `httpx` raises)
- The `CloudflareUser.from_claims()` constructor
- The bypass mode path (`CLOUDFLARE_ENABLED=false` used in tests but not all
  branches of the bypass guard are exercised)
- The full JWKS key parsing loop (lines 301-341: iterating and importing
  RSA public keys from JWK format)

**Tests to add** (add to `tests/unit/test_auth_cloudflare.py`):

```python
# JWKS fetch failure
async def test_fetch_jwks_network_failure(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("unreachable"))
    middleware = CloudflareAuthMiddleware(app=..., ...)
    with pytest.raises(AuthenticationError):
        await middleware._fetch_jwks()

# from_claims factory
def test_cloudflare_user_from_claims():
    claims = {"email": "user@test.com", "sub": "abc123"}
    user = CloudflareUser.from_claims(claims)
    assert user.email == "user@test.com"
    assert user.user_id == "abc123"

# JWK parsing round-trip with a real RSA key
def test_jwks_key_parsing():
    from cryptography.hazmat.primitives.asymmetric import rsa
    # generate a test RSA key, convert to JWK format,
    # feed to _parse_jwks_key(), assert result is usable for JWT verify
    ...
```

### 3c: `utils/time_utils.py` (0%)

**File**: [src/rag_processor/utils/time_utils.py](../../src/rag_processor/utils/time_utils.py)

This file was added to provide Python 3.10 compatible UTC helpers
(`UTC`, `utc_now()`, `from_timestamp()`, `parse_iso_datetime()`). It has
zero tests. Add a new file `tests/unit/test_time_utils.py`:

```python
from datetime import datetime, timezone

from rag_processor.utils.time_utils import (
    UTC,
    from_timestamp,
    parse_iso_datetime,
    utc_now,
)


def test_utc_constant():
    assert UTC is timezone.utc


def test_utc_now_is_timezone_aware():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc


def test_from_timestamp_round_trip():
    ts = 1700000000.0
    dt = from_timestamp(ts)
    assert dt.tzinfo == timezone.utc
    assert dt.timestamp() == ts


def test_parse_iso_datetime_with_z_suffix():
    result = parse_iso_datetime("2024-01-15T10:30:00Z")
    assert result.tzinfo == timezone.utc
    assert result.hour == 10


def test_parse_iso_datetime_with_offset():
    result = parse_iso_datetime("2024-01-15T10:30:00+00:00")
    assert result.tzinfo is not None


def test_parse_iso_datetime_invalid_raises():
    with pytest.raises((ValueError, TypeError)):
        parse_iso_datetime("not-a-date")
```

---

## Minor Issue: One Skipped Test

**File**: [tests/unit/test_websocket_router.py](../../tests/unit/test_websocket_router.py), line 390

```text
SKIPPED [1]: Module-level Redis import happens before patches can be applied
```

The skip comment in the test file explains: `get_batch_status` is imported at
the module level from `queue.jobs`, which triggers a real Redis connection
attempt before `fakeredis` patches can be applied.

**Fix**: Defer the import inside the function being tested, or use
`importlib.reload()` inside the test after patching. This is a low-risk
mechanical fix. If the full fix is out of scope, document the skip with a
GitHub issue reference so it does not age silently.

---

## Acceptance Criteria

Phase 1 is complete when all of the following pass in a single CI run on
`main`:

| Check | Current | Target |
| ----- | ------- | ------ |
| CI (backend tests + coverage) | passing | passing |
| Frontend Vitest (no-path-arg) | failing | passing |
| Playwright E2E in CI | not in CI | passing |
| `middleware/security.py` coverage | 36% | ≥80% |
| `auth/cloudflare.py` coverage | 60% | ≥80% |
| `utils/time_utils.py` coverage | 0% | ≥80% |
| Skipped test | 1 skipped | 0 skipped (or tracked issue) |

Verify with:

```bash
# Backend
uv run pytest tests/ -q --cov=src --cov-fail-under=80

# Frontend (should pass without scoping to src/)
npx vitest run

# E2E (requires dev server or CI webServer)
npx playwright test
```

---

## Order of Operations

1. Fix `frontend/vitest.config.ts` to exclude `e2e/` and add `include` pattern
   (Gap 1 -- one-line change, no functional risk)
2. Add `tests/unit/test_time_utils.py` (Gap 3c -- simplest, self-contained)
3. Add security middleware tests to reach ≥80% on
   `middleware/security.py` (Gap 3a)
4. Add Cloudflare auth tests to reach ≥80% on `auth/cloudflare.py` (Gap 3b)
5. Add Playwright job to `ci.yml` (Gap 2 -- requires dev server plumbing)
6. Fix or document the skipped websocket test (minor)

Items 2, 3, and 4 are independent and can be developed in parallel. Item 5
depends on Item 1 being resolved first (so the CI vitest step passes cleanly
before adding another test job).

---

## Context for the Receiving Team

### Environment setup

```bash
# Python (backend)
uv sync --all-extras
uv run pytest tests/ -q               # 334 pass, 1 skip

# Frontend
cd frontend
npm ci
npx vitest run src/                   # 29 pass (scope to src/ as workaround)
```

### Running coverage

```bash
# Backend per-module breakdown
uv run pytest tests/ --cov=src --cov-report=term-missing | grep -E "security|cloudflare|time_utils"

# Frontend
cd frontend && npx vitest run src/ --coverage
```

### Commit requirements

All commits must be conventional commits and must pass pre-commit hooks:

```bash
pre-commit run --all-files   # before committing
```

Examples of valid commit messages for this handoff:

```text
test: add coverage for security middleware
test: add coverage for cloudflare auth JWKS paths
test: add time_utils unit tests
fix(frontend): exclude e2e dir from vitest collection
ci: add playwright e2e job to ci.yml
```

### What NOT to change

Do not modify any application source code in `src/`, `docker-compose.yml`,
or existing passing tests. Changes for this handoff are limited to:

- `frontend/vitest.config.ts` (one-line addition)
- `tests/unit/test_time_utils.py` (new file)
- `tests/unit/test_middleware_security.py` (additions only)
- `tests/unit/test_auth_cloudflare.py` (additions only)
- `.github/workflows/ci.yml` (new job block only)

---

## Questions

Direct questions about this handoff to Byron Williams (`byron@williamscpa.dev`)
or open an issue on the repository with the label `phase-1`.
