# Sprint 1 Implementation Plan: Authentication Foundation

> **Sprint Duration**: 14 hours (Sprint 1.1-1.4)
> **Branch**: `claude/plan-first-sprint-01RLqB2VBp1QVA1Ap49N7vSR`
> **Status**: Planning
> **Created**: 2025-12-06

## Executive Summary

This document details the implementation plan for the first sprint of Phase 1, focusing on **User Authentication (US-001)** via Cloudflare Access JWT validation. This sprint establishes the security foundation that all subsequent MVP features depend upon.

## Prerequisites Assessment

### Phase 0 Infrastructure Gaps

Before starting Phase 1 sprints, the following Phase 0 gaps must be addressed:

| Component | Current State | Required State | Priority |
| --------- | ------------- | -------------- | -------- |
| Redis | Commented out in docker-compose.yml | Active with AOF persistence | **Critical** |
| RQ Worker | Not present | Running with priority queues | High |
| Cloudflare Tunnel | Not present | Optional for local dev (bypass mode) | Medium |
| Frontend | Template placeholders (`{{ cookiecutter.project_name }}`) | Project-specific | High |

### Recommended Pre-Sprint Setup (2-3 hours)

Before Sprint 1.1, complete these critical infrastructure tasks:

```bash
# 1. Enable Redis in docker-compose.yml
# 2. Add RQ worker service
# 3. Fix frontend template placeholders
# 4. Verify gateway → Redis connectivity
```

---

## Sprint 1.1: Cloudflare JWT Middleware (4 hours)

### Objective

Implement JWT validation middleware in FastAPI that validates Cloudflare Access tokens and extracts user identity.

### File Structure

```
src/rag_processor/
├── auth/
│   ├── __init__.py
│   ├── cloudflare.py      # JWT validation logic
│   ├── dependencies.py    # FastAPI dependencies
│   └── models.py          # User and token models
```

### Tasks

#### 1.1.1 Create CloudflareAuthMiddleware (2 hours)

**File**: `src/rag_processor/auth/cloudflare.py`

**Implementation Details**:

```python
# Key components to implement:
# 1. JWKS fetching from Cloudflare endpoint
# 2. Key caching (1 hour TTL)
# 3. JWT signature validation using PyJWT
# 4. Token claims extraction (email, user_id)
```

**Configuration Required** (`src/rag_processor/core/config.py`):

```python
# Add to Settings class:
cloudflare_team_domain: str = Field(default="", env="CLOUDFLARE_TEAM_DOMAIN")
cloudflare_audience_tag: str = Field(default="", env="CLOUDFLARE_AUDIENCE_TAG")
cloudflare_enabled: bool = Field(default=True, env="CLOUDFLARE_ENABLED")  # Bypass for local dev
```

**Dependencies to Add** (`pyproject.toml`):

```toml
"pyjwt[crypto]>=2.8.0",  # JWT validation with RSA support
"httpx>=0.26.0",          # Async HTTP client for JWKS fetch
```

#### 1.1.2 Register Middleware in FastAPI (1 hour)

**File**: `src/rag_processor/main.py` (create if not exists)

**Implementation**:

- Create FastAPI application factory
- Register CloudflareAuthMiddleware
- Add health router (existing)
- Configure CORS for frontend

#### 1.1.3 Write Middleware Tests (1 hour)

**File**: `tests/unit/test_auth_middleware.py`

**Test Cases**:

| Test | Description | Expected |
| ---- | ----------- | -------- |
| test_valid_jwt | Valid token with correct signature | User context in request.state |
| test_invalid_signature | Token with wrong signature | 401 Unauthorized |
| test_expired_token | Expired JWT | 401 Unauthorized |
| test_missing_token | No Cf-Access-Jwt-Assertion header | 401 Unauthorized |
| test_bypass_mode | CLOUDFLARE_ENABLED=false | Mock user context |

**Testing Approach**:

- Mock JWKS endpoint response
- Use pre-generated test tokens with known keys
- Test both happy path and error cases

### Exit Criteria

- [ ] Middleware validates JWT signature
- [ ] User context available in `request.state.user`
- [ ] Invalid tokens return 401 Unauthorized
- [ ] Bypass mode works for local development
- [ ] Tests pass with 100% coverage

---

## Sprint 1.2: get_current_user Dependency (3 hours)

### Objective

Create FastAPI dependency that provides current user context to endpoints.

### Tasks

#### 1.2.1 Implement get_current_user Dependency (1 hour)

**File**: `src/rag_processor/auth/dependencies.py`

```python
# Implementation outline:
from fastapi import Request, HTTPException, Depends
from rag_processor.auth.models import CloudflareUser

async def get_current_user(request: Request) -> CloudflareUser:
    """Extract authenticated user from request state."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

#### 1.2.2 Create User Models (1 hour)

**File**: `src/rag_processor/auth/models.py`

```python
# Models to implement:
class CloudflareUser(BaseModel):
    email: str
    user_id: str | None = None
    groups: list[str] = []
    issued_at: datetime
    expires_at: datetime

class TokenClaims(BaseModel):
    # JWT claims structure
    ...
```

#### 1.2.3 Add Protected Endpoint Example (0.5 hours)

**File**: `src/rag_processor/api/user.py`

```python
# Example endpoint:
@router.get("/me")
async def get_me(user: CloudflareUser = Depends(get_current_user)):
    return {"email": user.email, "user_id": user.user_id}
```

#### 1.2.4 Write Dependency Tests (0.5 hours)

**File**: `tests/unit/test_auth_dependencies.py`

**Test Cases**:

- Test with valid user in request state
- Test with missing user → 401
- Test user attributes passed correctly

### Exit Criteria

- [ ] `get_current_user()` returns user context
- [ ] Protected endpoints require authentication
- [ ] User email logged in audit fields
- [ ] Tests pass

---

## Sprint 1.3: Frontend Auth UI (4 hours)

### Objective

Display user email in React UI header and handle authentication state.

### File Structure

```
frontend/src/
├── hooks/
│   ├── useAuth.ts        # Authentication hook
│   └── useApi.ts         # API client (existing)
├── components/
│   ├── Header.tsx        # Header with user info
│   └── ProtectedRoute.tsx
├── store/
│   └── authStore.ts      # Zustand auth state
└── types/
    └── auth.ts           # TypeScript types
```

### Tasks

#### 1.3.1 Create useAuth Hook (1.5 hours)

**File**: `frontend/src/hooks/useAuth.ts`

**Implementation**:

```typescript
// Hook responsibilities:
// 1. Fetch user info from /api/v1/me on mount
// 2. Handle loading/error states
// 3. Store user in zustand state
// 4. Provide logout function (Cloudflare logout URL)
```

#### 1.3.2 Create Zustand Auth Store (0.5 hours)

**File**: `frontend/src/store/authStore.ts`

```typescript
// Store structure:
interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  setUser: (user: User | null) => void;
  logout: () => void;
}
```

#### 1.3.3 Create Header Component (1.5 hours)

**File**: `frontend/src/components/Header.tsx`

**Features**:

- Display user email when authenticated
- Loading spinner while fetching user
- Error state handling
- Logout button (links to Cloudflare logout)

#### 1.3.4 Update App Layout (0.5 hours)

**File**: `frontend/src/App.tsx`

- Remove template placeholders
- Add Header component
- Configure auth provider/hook usage

### Dependencies to Add

```json
{
  "zustand": "^4.4.0"
}
```

### Exit Criteria

- [ ] User email displayed in UI header
- [ ] Loading state handled gracefully
- [ ] Logout button functional
- [ ] Component tests pass

---

## Sprint 1.4: End-to-End Auth Test (3 hours)

### Objective

Create E2E test for complete authentication flow using Playwright.

### Tasks

#### 1.4.1 Set Up Playwright (1 hour)

**Installation**:

```bash
cd frontend
pnpm add -D @playwright/test
pnpm exec playwright install
```

**Configuration**: `frontend/playwright.config.ts`

```typescript
// Configure for:
// - Base URL pointing to dev server
// - Auth state fixtures
// - Screenshot on failure
```

#### 1.4.2 Write Auth E2E Test (1.5 hours)

**File**: `frontend/e2e/auth.spec.ts`

**Test Scenarios**:

| Test | Steps | Expected |
| ---- | ----- | -------- |
| Unauthenticated redirect | Navigate to app without token | Redirect to Cloudflare login |
| Authenticated user sees header | Navigate with valid token | Header shows email |
| Invalid token handling | Navigate with expired token | Error message displayed |

**Mocking Approach**:

For local E2E testing, use `CLOUDFLARE_ENABLED=false` bypass mode with mock user injection.

#### 1.4.3 Add Playwright to CI (0.5 hours)

**File**: `.github/workflows/e2e.yml`

```yaml
# Workflow:
# 1. Build frontend and backend
# 2. Start services with docker-compose
# 3. Run Playwright tests
# 4. Upload test artifacts
```

### Exit Criteria

- [ ] Playwright configured and installed
- [ ] E2E auth test passes locally
- [ ] E2E test passes in CI
- [ ] Test artifacts captured on failure

---

## Sprint 1 Summary

### Deliverables

| Sprint | Duration | Deliverable | Status |
| ------ | -------- | ----------- | ------ |
| 1.1 | 4h | Cloudflare JWT Middleware | Pending |
| 1.2 | 3h | get_current_user Dependency | Pending |
| 1.3 | 4h | Frontend Auth UI | Pending |
| 1.4 | 3h | E2E Auth Test | Pending |
| **Total** | **14h** | **User Authentication (US-001)** | |

### Dependencies Added

**Backend** (`pyproject.toml`):

```toml
"pyjwt[crypto]>=2.8.0",
"httpx>=0.26.0",
```

**Frontend** (`package.json`):

```json
"zustand": "^4.4.0",
"@playwright/test": "^1.40.0"
```

### New Files Created

**Backend**:

- `src/rag_processor/auth/__init__.py`
- `src/rag_processor/auth/cloudflare.py`
- `src/rag_processor/auth/dependencies.py`
- `src/rag_processor/auth/models.py`
- `src/rag_processor/api/user.py`
- `src/rag_processor/main.py`
- `tests/unit/test_auth_middleware.py`
- `tests/unit/test_auth_dependencies.py`

**Frontend**:

- `frontend/src/hooks/useAuth.ts`
- `frontend/src/store/authStore.ts`
- `frontend/src/components/Header.tsx`
- `frontend/src/types/auth.ts`
- `frontend/e2e/auth.spec.ts`
- `frontend/playwright.config.ts`

### Configuration Updates

**Environment Variables** (`.env.example`):

```bash
# Cloudflare Access Authentication
CLOUDFLARE_TEAM_DOMAIN=your-team.cloudflareaccess.com
CLOUDFLARE_AUDIENCE_TAG=your-audience-tag
CLOUDFLARE_ENABLED=true  # Set to false for local dev without Cloudflare
```

---

## Risk Mitigation

| Risk | Mitigation | Contingency |
| ---- | ---------- | ----------- |
| JWKS endpoint unavailable | Cache keys with 1h TTL | Fallback to public key file |
| Token format changes | Validate against Cloudflare docs | Add token version checking |
| Frontend auth state race | Use zustand with persist | Add retry logic |
| E2E flaky tests | Use bypass mode for CI | Increase timeouts |

---

## Next Sprint

After completing Sprint 1.1-1.4 (Authentication):

1. Proceed to **Sprint 1.5-1.8: Multi-File Upload**
2. Implement `POST /api/v1/ingest` endpoint
3. Create React drag-drop component
4. Integration with authentication

## Related Documents

- [Phase 1 Detailed Plan](./phase-1-mvp-core.md)
- [PROJECT-PLAN.md](./PROJECT-PLAN.md)
- [Tech Spec - API Endpoints](./tech-spec.md#4-api-specification)
- [ADR-001 - Security Model](./adr/adr-001-react-fastapi-architecture.md#security-model)
