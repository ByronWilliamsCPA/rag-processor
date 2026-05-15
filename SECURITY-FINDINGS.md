# Security Review — Findings

**Branch**: `claude/security-review-rag-WQL5P`
**Scope**: React frontend (`frontend/`), FastAPI backend (`src/rag_processor/`), GitHub
Actions workflows (`.github/workflows/`).
**Method**: Manual code review against the agreed checklist (XSS/data binding,
secrets in source, auth on every endpoint, CORS, file upload safety, path
traversal, injection, CI supply-chain hardening).

Each finding lists severity, where it lives, why it matters, and whether this PR
applies a fix or leaves a follow-up.

---

## Severity legend

| Tag | Meaning |
|-----|---------|
| **CRITICAL** | Direct data exposure / auth bypass exploitable today. |
| **HIGH** | Material risk under realistic conditions; should ship soon. |
| **MEDIUM** | Defense-in-depth gap; exploitable only with a second flaw. |
| **LOW** | Hygiene / hardening recommendation. |
| **INFO** | Verified safe; documented to prove the check was done. |

---

## 1. Frontend (React) — security checks

### 1.1 [INFO] No unsafe HTML rendering of user-controlled content

**Files reviewed**: `frontend/src/App.tsx`, `frontend/src/components/*.tsx`,
`frontend/src/hooks/*.ts`.

**Result**: Verified. There are no occurrences of `dangerouslySetInnerHTML`,
direct `.innerHTML` assignment, or `eval(`. Backend-controlled strings
(`response.message`, `job.filename`, `user.email`, `health.status`,
`health.version`, etc.) are rendered as JSX children, which React HTML-escapes
by default.

```bash
$ grep -r --include="*.tsx" --include="*.ts" "dangerouslySetInnerHTML\|innerHTML\|eval(" frontend/src/
(no matches)
```

The one place that interpolates a backend value into a DOM attribute is
`frontend/src/components/FileUpload.tsx:198` — `style={{ width: ${uploadProgress}% }}`
— which is a number from local state, not user-controlled text.

**Action**: None (verified safe).

---

### 1.2 [INFO] No hardcoded API keys or backend URLs in source

**Result**: Verified. The codebase reads API/WebSocket URLs from
`import.meta.env.VITE_API_URL` only (`useApi.ts:27-29`, `useAuth.ts:12`,
`useUpload.ts:10`, `useWebSocket.ts:169-171`). `frontend/.env.example` lists the
expected env vars; no secrets are committed. No tokens of `[A-Za-z0-9_-]{20,}`
length appear in `frontend/src/`.

**Action**: None (verified safe).

---

### 1.3 [HIGH] WebSocket auth token is passed in the URL query string

**File**: `frontend/src/hooks/useWebSocket.ts:175-182` and
`src/rag_processor/websocket/router.py:120` (`Query(default=None, alias="token")`).

```ts
// frontend/src/hooks/useWebSocket.ts
const params = new URLSearchParams();
if (token) {
  params.set('token', token);
}
```

The Cloudflare Access JWT is appended as `?token=…` on the
`wss://…/ws/batch/{id}?token=…` URL. URLs (including query strings) get logged
in nginx/CDN access logs, are stored in browser history, and may leak via
`Referer` on subsequent navigations. The token is bearer-equivalent for the
session it's valid for.

Why not "just use a header"? Browsers cannot set custom headers on the
`WebSocket` constructor. The accepted patterns are:

1. Have the server set an `HttpOnly` session cookie before the WS upgrade
   (Cloudflare Access already does this for the application domain).
2. Accept the WS upgrade, then require the client to send an auth message as
   the first frame and close the socket if it doesn't arrive within a few
   seconds.

**Action — applied (defense-in-depth)**: Added owner-check on the WebSocket
endpoint (see §2.1) so even if the token is exposed, only the batch owner can
attach. Token-in-URL itself is **left as a follow-up** because moving it off the
URL touches both client and server message protocols.

---

### 1.4 [MEDIUM] Bearer token in `localStorage`

**File**: `frontend/src/hooks/useApi.ts:41-43, 57`.

```ts
const token = localStorage.getItem('auth_token')
if (token) {
  config.headers.Authorization = `Bearer ${token}`
}
```

`localStorage` is reachable from any script that executes in the document; an
XSS-able vulnerability anywhere in the app or in a dependency would
exfiltrate the token. The real auth path in this app is Cloudflare Access via
`HttpOnly` cookies (`withCredentials: true` in `useAuth.ts` and `useUpload.ts`),
so the `auth_token` codepath in `useApi.ts` appears to be unused legacy code
from the template.

**Action — left as follow-up**: Recommend removing the localStorage interceptor
entirely, or moving any future token to an `HttpOnly` cookie. Out of scope for
this security-only PR because deletion may affect template alignment.

---

## 2. Backend (FastAPI) — auth, CORS, uploads, path traversal

### 2.1 [CRITICAL] Broken object-level authorization on batch/job/WebSocket reads (OWASP A01)

**Files**: `src/rag_processor/api/batch.py` and
`src/rag_processor/websocket/router.py`.

Before this PR:

```python
# api/batch.py
@router.get("/{batch_id}", ...)
async def get_batch(batch_id: UUID) -> BatchDetailResponse:
    batch, jobs = get_batch_status(batch_id)
    if batch is None:
        raise HTTPException(404, ...)
    # returns batch regardless of who owns it
```

`CloudflareAuthMiddleware` enforces *authentication* on `/api/v1/batch/...`
(it's not in `PUBLIC_PATHS`), but it does **not** enforce *authorization*. Any
authenticated Cloudflare Access user could read any other user's batch — and
the WebSocket endpoint had the same gap. Batch IDs are UUIDv4 (≈122 bits of
entropy), so this isn't easily enumerable, but they appear in URLs, logs, and
WebSocket connection paths, so leakage is plausible. `Batch` already stores
`created_by_user_id` / `created_by_email`, so the data needed to check
ownership is present.

**Fix — applied** (`src/rag_processor/api/batch.py`,
`src/rag_processor/websocket/router.py`):

- Both REST endpoints now declare `user: CloudflareUser = Depends(get_current_user)`
  and call a new helper `_user_owns_batch(batch, user)` that matches on
  `created_by_user_id` (preferred) and falls back to `created_by_email`.
- WebSocket endpoint replicates the same check before accepting the upgrade.
- Non-owners receive a 404 (REST) / `WS_1008_POLICY_VIOLATION` (WS) instead of
  403 so we don't confirm the batch exists. The attempt is logged with
  `requester_email` and `owner_email` for incident response.

---

### 2.2 [HIGH] CORS configuration was hardcoded; needed env-driven override

**File**: `src/rag_processor/main.py`.

Before:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", ...],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins` was **not** `*`, so the CORS-with-credentials footgun was
avoided in the committed code. But:

1. There was no way to set production origins without editing source.
2. `allow_methods=["*"]` and `allow_headers=["*"]` with credentials is broader
   than needed (FastAPI/Starlette translates `*` to `Access-Control-Allow-*: *`,
   which browsers reject under `credentials: include`; but the policy is still
   sloppy and depends on browser behaviour to be safe).

**Fix — applied** (`src/rag_processor/main.py`,
`src/rag_processor/core/config.py`):

- Added `Settings.cors_allowed_origins`, defaulting to the same dev origins.
  Production sets `RAG_PROCESSOR_CORS_ALLOWED_ORIGINS` as a JSON array
  (`["https://app.example.com"]`).
- `main.py` now reads from settings and **raises at startup** if `"*"` appears
  in the list, so an insecure-by-misconfiguration deploy fails fast instead of
  silently allowing any origin.
- Replaced `allow_methods=["*"]` with the explicit HTTP method list the API
  uses, and `allow_headers=["*"]` with the explicit headers the frontend sends
  (including `Cf-Access-Jwt-Assertion` for the JWT header path).

---

### 2.3 [HIGH] `cloudflare_enabled=false` silently authenticates everyone as a fixed dev user

**File**: `src/rag_processor/auth/cloudflare.py:113-117`.

Before:

```python
if not settings.cloudflare_enabled:
    request.state.user = self._get_bypass_user()
    return await call_next(request)
```

`_get_bypass_user()` returns
`CloudflareUser(email="dev@localhost", user_id="dev-user-001", groups=["developers"])`.
The default is `True`, so this is a developer convenience, not an immediate
exposure — but the failure mode (an env-var typo in prod that flips it to
`false`) is catastrophic and silent: every request becomes the "developers"
user.

**Fix — applied**: Bypass mode now emits a `CRITICAL` log on every request
when active, including the request path. Anyone scraping logs (or alerting on
CRITICAL) will see the production misconfiguration immediately.

**Follow-up recommendation**: Add a runtime guard that refuses to start with
`cloudflare_enabled=false` unless an explicit `RAG_PROCESSOR_ALLOW_AUTH_BYPASS=1`
is also set. Left out of this PR to avoid breaking the existing dev/test flow
(which relies on the flag).

---

### 2.4 [INFO] File upload endpoint — validation, sanitization, safe storage

**File**: `src/rag_processor/api/ingest.py`.

Verified the upload pipeline:

- **Auth**: `Depends(get_current_user)` is present (line 212).
- **Size limit**: `settings.max_file_size_bytes` (100 MB default), checked in
  `validate_file` (line 154). FastAPI also enforces multipart size via Starlette.
- **Type validation**: MIME type comes from libmagic (`detect_mime_type`,
  content-based), not from the client-supplied `Content-Type` or extension —
  good. Allow-list is `settings.allowed_mime_types`.
- **Filename sanitization**: `sanitize_filename` (line 95) uses
  `Path(filename).name` to strip path components, then a regex
  `[^\w\s\-.]` → `_`, then length cap, then a not-empty / not-`.`/`..` check.
  This resists `../etc/passwd`, NULs, and Windows-style paths.
- **Storage**: Files are saved under `Path(settings.upload_dir) / str(batch.batch_id) / safe_filename`.
  The directory component is a server-generated UUID, so a hostile filename
  cannot collide with another batch. Duplicate-name handling appends `_1`, `_2`
  rather than overwriting (line 266-270).

**Action**: None (verified safe).

---

### 2.5 [MEDIUM] `validate_file` reads the entire upload into memory before size check

**File**: `src/rag_processor/api/ingest.py:150-160`.

```python
content = await file.read()
await file.seek(0)
if len(content) > settings.max_file_size_bytes:
    errors.append(...); return content, "", errors
```

A 1 GB upload (or an attacker sending `Content-Length: huge`) is fully buffered
in memory **before** the size check rejects it. With `MAX_FILE_SIZE_MB=100` and
many concurrent uploads, this is a memory-pressure DoS vector.

**Recommendation**: Stream-read in chunks and abort once
`bytes_read > max_file_size_bytes`. Starlette's `UploadFile.read(size)`
supports chunked reads. Also consider setting a request body limit via an ASGI
middleware (e.g., `starlette.middleware.Middleware` with a max-body wrapper).

**Action — left as follow-up**: Non-trivial refactor; the immediate exposure is
bounded by the rate limiter (60 rpm/IP by default) and the existing 100 MB
per-file cap.

---

### 2.6 [LOW] Health endpoint leaks Python version (info disclosure)

**File**: `src/rag_processor/api/health.py:36`.

`HealthStatus.python_version` defaults to `sys.version.split()[0]` and is
served publicly at `/health/live` (in `PUBLIC_PATHS`). Useful for ops; useful
for attackers correlating CVEs to a specific runtime.

**Recommendation**: Drop `python_version` from the public response (or gate it
behind an admin-only health endpoint). Low priority — Python versions are easy
to fingerprint from error pages anyway.

**Action — left as follow-up**.

---

### 2.7 [INFO] No file-content GET endpoint, so no path-traversal read exposure

Searched for endpoints that return file content from disk:

```bash
$ grep -rn "FileResponse\|send_from_directory\|StreamingResponse.*open" src/
(no matches)
```

The only filesystem reads are inside the worker (`process_job_task`), which is
not user-routable. **No path-traversal on read** because there's no read
endpoint at all.

**Action**: None.

---

## 3. A03 — Injection

### 3.1 [INFO] No SQL / ORM queries in this service

```bash
$ grep -rn "execute\|cursor\.execute\|\.sql\|SELECT\|INSERT" src/rag_processor/
# only hits: utility docstrings, a Sentry SqlalchemyIntegration reference
```

The gateway persists state in Redis via `rag_processor.queue.redis_store` (key/value
HGET/HSET; values are typed strings; no `EVAL`/Lua scripts with user input). No
SQL injection surface in this repo.

---

### 3.2 [INFO] No LLM prompt construction in this service

The processor is a **gateway**: it accepts file uploads, validates them, and
hands them off to downstream pipelines. There is no chat/RAG-query endpoint
here; `grep -rn "prompt\|openai\|anthropic" src/` returns nothing. Prompt
injection is therefore out of scope for this repository and must be reviewed in
whichever service consumes the routed files (`Pipeline.OCR`,
`Pipeline.DOC_PROCESSING`, etc.).

**Action**: None for this repo. Owner of downstream pipelines should run a
separate prompt-injection review against the consumer that builds LLM prompts
from RAG retrieval results.

---

## 4. GitHub Actions hardening

### 4.1 [HIGH] `sonarsource/sonarqube-quality-gate-action@master` — unpinned, mutable ref

**File**: `.github/workflows/sonarcloud.yml:119`.

`@master` resolves to whatever the upstream maintainer pushes, which is a
classic supply-chain risk: a compromise of the upstream repo immediately runs
with this workflow's `SONAR_TOKEN`.

**Fix — applied**: Pinned to
`sonarsource/sonarqube-quality-gate-action@cf038b0e0cdecfa9e56c198bbb7d21d751d62c3b # v1.2.0`.

---

### 4.2 [MEDIUM] `actions/dependency-review-action@v4` — float-tag, not SHA

**File**: `.github/workflows/dependency-review.yml:33`.

Major-version float-tags (`@v4`) can be moved by the maintainer to any commit
under the v4 line. Less dangerous than `@master` but still mutable.

**Fix — applied**: Pinned to
`actions/dependency-review-action@2031cfc080254a8a887f58cffee85186f0e49e48 # v4.9.0`.

---

### 4.3 [LOW] Missing `harden-runner` in two workflows

**Files**: `.github/workflows/dependency-review.yml`,
`.github/workflows/sonarcloud.yml`.

`step-security/harden-runner` is already used by the other workflows
(`ci.yml`, `cifuzzy.yml`, `codeql.yml`, `pr-validation.yml`,
`release-sign.yml`, `slsa-provenance.yml`). The two workflows above were
missing it.

**Fix — applied**: Added a "Harden runner" step with
`egress-policy: audit` to both workflows (`check-secrets` and `sonarcloud`
jobs in `sonarcloud.yml`; the single job in `dependency-review.yml`).

---

### 4.4 [INFO] Permissions blocks — all workflows scoped

Spot-check: every top-level workflow file declares a `permissions:` block.
None default to the GitHub-issued read+write token; most use `contents: read`
plus the minimum extra scopes required (`security-events: write` for SARIF,
`pull-requests: write` for PR comments, `id-token: write` for OIDC).

**Action**: None.

---

### 4.5 [LOW] Reusable workflows referenced by mutable `@main`

**Files**: `.github/workflows/ci.yml:32`, `codecov.yml:26`,
`container-security.yml:42`, `coverage.yml:26`, `docs.yml:32`,
`mutation-testing.yml:43`, `performance-regression.yml:79`,
`publish-pypi.yml:20`, `python-compatibility.yml:44`, `qlty.yml:18`,
`release.yml:47`, `sbom.yml:41`, `scorecard.yml:29`,
`security-analysis.yml:35`, `slsa-provenance.yml:101`.

All caller workflows reference org-owned reusable workflows by
`ByronWilliamsCPA/.github/.github/workflows/...@main`. The `pr-validation.yml`
already pins to a specific SHA — the others should follow.

**Action — left as follow-up**: SHA-pinning these tightens supply chain but
requires a maintenance process to bump the SHA when the org template changes.
`pr-validation.yml:35` shows the pattern: `...@b29a870cb21a8f913e5c6c5f08740a4bdd94d0ca  # main`.

---

## Summary of fixes applied in this PR

| # | File | Severity | Change |
|---|------|----------|--------|
| 1 | `src/rag_processor/api/batch.py` | CRITICAL | Add auth dependency + ownership check on `GET /batch/{batch_id}` and `GET /batch/job/{job_id}`. Return 404 on non-owner. |
| 2 | `src/rag_processor/websocket/router.py` | CRITICAL | Add ownership check before accepting WS upgrade for `/ws/batch/{batch_id}`. |
| 3 | `src/rag_processor/core/config.py` | HIGH | New `cors_allowed_origins` setting (env-overridable via `RAG_PROCESSOR_CORS_ALLOWED_ORIGINS`). |
| 4 | `src/rag_processor/main.py` | HIGH | Read CORS origins from settings; fail startup on `"*"`; replace `allow_methods=["*"]` / `allow_headers=["*"]` with explicit lists. |
| 5 | `src/rag_processor/auth/cloudflare.py` | HIGH | Log `CRITICAL` on every request when `cloudflare_enabled=False`. |
| 6 | `.github/workflows/sonarcloud.yml` | HIGH | Pin `sonarsource/sonarqube-quality-gate-action@master` → SHA `cf038b0e…` (v1.2.0). Add `harden-runner` to both jobs. |
| 7 | `.github/workflows/dependency-review.yml` | MEDIUM | Pin `actions/dependency-review-action@v4` → SHA `2031cfc0…` (v4.9.0). Add `harden-runner`. |

## Follow-ups (not in this PR)

- §1.3: Move WebSocket auth token off the URL onto an `HttpOnly` cookie or
  post-accept message.
- §1.4: Delete the unused `localStorage` bearer-token interceptor in
  `useApi.ts`.
- §2.3: Guard `cloudflare_enabled=False` behind an explicit
  `RAG_PROCESSOR_ALLOW_AUTH_BYPASS=1` to make production bypass a two-flag
  decision.
- §2.5: Stream-read uploads and abort over `max_file_size_bytes` instead of
  buffering the whole body.
- §2.6: Drop Python version from public `/health/live` responses.
- §4.5: SHA-pin org-owned reusable workflow callouts.
