# RAG Pipeline Web UI

## Technical Implementation Specification

**Version 1.1** | December 2024
*Includes: Cloudflare Access Authentication*
*Document Status: Draft*

---

## Document Information

| Field | Value |
|-------|-------|
| Document Title | RAG Pipeline Web UI Technical Specification |
| Version | 1.1 (Authentication Update) |
| Status | Draft |
| Last Updated | December 2024 |
| Authentication | Cloudflare Access via williaby/testing middleware |
| Related Projects | Project A (Image), Project E (Audio), Project B (OCR), Project C (Fusion), Project D (Vector) |

---

## 1. Executive Summary

This document specifies the technical implementation for the RAG Pipeline Web UI, a unified ingestion interface that routes files to the appropriate preprocessing pipeline and collects processed outputs for downstream RAG systems.

### 1.1 Purpose

The Web UI serves as the single entry point for all document and audio ingestion into the RAG pipeline. It provides file upload capabilities, automatic routing based on content type, job queue management, real-time status monitoring, and a clean handoff interface to multiple Project D variants.

### 1.2 Key Features

- Cloudflare Access authentication with Zero Trust security model
- Multi-file upload with drag-and-drop support
- Automatic file type detection and pipeline routing
- Job queue management with priority support
- Real-time pipeline status via WebSocket
- Output collection from Project C
- Configurable handoff to Project D variants
- Full audit trail with user attribution

### 1.3 Out of Scope

- RAG query interface (handled by downstream systems)
- Project D implementation details (system-specific)
- Identity provider management (handled by Cloudflare Access)

---

## 2. Authentication & Security

### 2.1 Overview

The Web UI uses Cloudflare Access for authentication, leveraging the existing Zero Trust infrastructure. Authentication is handled by the cloudflare-auth middleware from the williaby/testing repository, providing JWT validation, user identification, and audit capabilities.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUTHENTICATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

   User Browser
       │
       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                    CLOUDFLARE ACCESS                               │
   │                                                                    │
   │  • Google OAuth / Identity Provider                               │
   │  • Email whitelist / domain restrictions                          │
   │  • MFA enforcement (if configured)                                │
   │  • Session management                                             │
   │                                                                    │
   │  Adds headers:                                                    │
   │  • Cf-Access-Jwt-Assertion: <signed JWT>                         │
   │  • Cf-Access-Authenticated-User-Email: user@domain.com           │
   └───────────────────────────────────────────────────────────────────┘
       │
       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                    CLOUDFLARE TUNNEL                               │
   │                    (cloudflared container)                         │
   └───────────────────────────────────────────────────────────────────┘
       │
       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                    RAG PIPELINE GATEWAY                            │
   │                                                                    │
   │  ┌─────────────────────────────────────────────────────────────┐  │
   │  │           CloudflareAuthMiddleware                          │  │
   │  │           (from williaby/testing)                           │  │
   │  │                                                             │  │
   │  │  • Validates Cf-Access-Jwt-Assertion header                │  │
   │  │  • Verifies signature against Cloudflare certs             │  │
   │  │  • Checks audience tag matches application                 │  │
   │  │  • Creates CloudflareUser object                           │  │
   │  │  • Attaches user to request.state                          │  │
   │  │  • Skips excluded paths (/health, /metrics)                │  │
   │  └─────────────────────────────────────────────────────────────┘  │
   │                           │                                        │
   │                           ▼                                        │
   │  ┌─────────────────────────────────────────────────────────────┐  │
   │  │               Protected Application Routes                  │  │
   │  │               (user: CloudflareUser available)              │  │
   │  └─────────────────────────────────────────────────────────────┘  │
   └───────────────────────────────────────────────────────────────────┘
       │
       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                INTERNAL DOCKER NETWORK                             │
   │                (No authentication required)                        │
   │                                                                    │
   │   Gateway ──► Project A/E/B/C/D (service-to-service)              │
   └───────────────────────────────────────────────────────────────────┘
```

### 2.2 Middleware Integration

The authentication middleware is sourced from the williaby/testing repository and integrated as a package dependency.

#### 2.2.1 Installation

```toml
# gateway/pyproject.toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "cloudflare-auth @ git+https://github.com/williaby/testing.git",
    # ... other dependencies
]
```

#### 2.2.2 Gateway Setup

```python
# gateway/src/gateway/main.py
from fastapi import FastAPI, Depends
from cloudflare_auth import setup_cloudflare_auth, CloudflareUser
from cloudflare_auth.middleware import get_current_user

app = FastAPI(title="RAG Pipeline Gateway")

# Setup Cloudflare authentication
setup_cloudflare_auth(
    app,
    excluded_paths=[
        "/health",              # Health checks (Docker/K8s probes)
        "/metrics",             # Prometheus metrics
        "/docs",                # OpenAPI docs (remove in production)
        "/openapi.json",        # OpenAPI schema
        "/api/v1/targets/register",  # Internal Project D registration
    ]
)

@app.post("/api/v1/ingest")
async def ingest_files(
    files: list[UploadFile],
    user: CloudflareUser = Depends(get_current_user)
):
    """Upload files - requires Cloudflare Access authentication."""
    batch = await create_batch(
        files=files,
        created_by=user.email,      # Audit trail
        user_id=user.user_id,
    )
    return batch
```

### 2.3 Environment Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `CLOUDFLARE_TEAM_DOMAIN` | Yes | Your Cloudflare team domain (e.g., myteam.cloudflareaccess.com) |
| `CLOUDFLARE_AUDIENCE_TAG` | Yes | Application audience tag from Cloudflare dashboard |
| `CLOUDFLARE_ENABLED` | No | Enable/disable auth (default: true, set false for local dev) |
| `ALLOWED_EMAIL_DOMAINS` | No | Comma-separated list of allowed email domains |
| `ENVIRONMENT` | No | Environment: dev, staging, or prod (default: dev) |

### 2.4 User Model

The CloudflareUser object is available in all authenticated routes via dependency injection.

```python
class CloudflareUser:
    email: str              # User's email address
    user_id: str            # Unique user identifier
    email_domain: str       # Domain portion of email
    claims: CloudflareJWTClaims  # Full JWT claims

    def has_email_domain(self, domain: str) -> bool:
        """Check if user's email matches a specific domain."""

class CloudflareJWTClaims:
    email: str
    iss: str                # Issuer (Cloudflare Access URL)
    aud: list[str]          # Audience tags
    sub: str                # Subject (user ID)
    iat: int                # Issued at timestamp
    exp: int                # Expiration timestamp

    def get_audience_list(self) -> list[str]
    @property
    def issued_at(self) -> datetime
    @property
    def expires_at(self) -> datetime
```

### 2.5 WebSocket Authentication

WebSocket connections require separate token handling since headers aren't available after the initial handshake.

```python
# gateway/src/gateway/websocket.py
from fastapi import WebSocket
from cloudflare_auth import CloudflareJWTValidator

validator = CloudflareJWTValidator()

@app.websocket("/ws/batch/{batch_id}")
async def websocket_batch_updates(websocket: WebSocket, batch_id: str):
    # Extract JWT from query param (passed by frontend)
    token = websocket.query_params.get("cf_access_token")

    if not token:
        await websocket.close(code=4001, reason="Missing authentication")
        return

    try:
        claims = validator.validate_token(token)
        user_email = claims.email
    except ValueError as e:
        await websocket.close(code=4003, reason="Invalid token")
        return

    await websocket.accept()
    # Proceed with authenticated WebSocket connection
```

#### 2.5.1 Frontend WebSocket Connection

```typescript
// rag-ui/src/hooks/useWebSocket.ts
export function useBatchWebSocket(batchId: string) {
  const [status, setStatus] = useState<BatchStatus | null>(null);

  useEffect(() => {
    // Cloudflare Access injects token in cookie
    const cfToken = getCookie('CF_Authorization');

    const ws = new WebSocket(
      `${WS_URL}/ws/batch/${batchId}?cf_access_token=${cfToken}`
    );

    ws.onmessage = (event) => setStatus(JSON.parse(event.data));
    return () => ws.close();
  }, [batchId]);

  return status;
}
```

### 2.6 Audit Trail

All jobs include user attribution for audit and compliance purposes.

```python
class Job(BaseModel):
    job_id: str
    batch_id: str
    filename: str
    # ... existing fields ...

    # Audit fields (populated from CloudflareUser)
    created_by_email: str      # user.email
    created_by_user_id: str    # user.user_id
    created_at: datetime

class Batch(BaseModel):
    batch_id: str
    created_by_email: str
    created_by_user_id: str
    created_at: datetime
    jobs: list[Job]
```

### 2.7 Local Development

For local development without Cloudflare Access, disable authentication:

```bash
# .env.local
CLOUDFLARE_ENABLED=false

# The middleware will bypass authentication and create a mock user:
# email: dev@localhost
# user_id: dev-user-local
```

---

## 3. Architecture Overview

### 3.1 System Context

The Web UI operates as the ingestion layer between authenticated users and the RAG pipeline. It coordinates with Projects A through C for processing and provides a standardized handoff interface to Project D variants.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                      WEB UI (rag-ui)                             │  │
│   │                                                                  │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │  │
│   │  │  Upload  │  │   Job    │  │  Status  │  │     Handoff      │ │  │
│   │  │   Zone   │  │  Queue   │  │ Monitor  │  │   Configurator   │ │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
                              ┌──────┴──────┐
                              │   Gateway   │ ◄── CloudflareAuthMiddleware
                              │    API      │
                              └──────┬──────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
        ┌──────────┐          ┌──────────┐          ┌──────────┐
        │Project A │          │Project E │          │Project B │
        │ (Image)  │          │ (Audio)  │          │  (OCR)   │
        └────┬─────┘          └────┬─────┘          └────┬─────┘
             │                     │                     │
             └──────────────┬──────┴─────────────────────┘
                            │
                            ▼
                      ┌──────────┐
                      │Project C │
                      │ (Fusion) │
                      └────┬─────┘
                           │
              ┌────────────┴────────────┐
              │      HANDOFF LAYER      │
              │   (Standardized API)    │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌──────────┐     ┌──────────┐     ┌──────────┐
   │Project D │     │Project D │     │Project D │
   │ Variant A│     │ Variant B│     │ Variant C│
   └──────────┘     └──────────┘     └──────────┘
```

### 3.2 Component Overview

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| Cloudflare Access | Identity provider, OAuth, session management | Cloudflare Zero Trust |
| Cloudflare Tunnel | Secure ingress, no exposed ports | cloudflared |
| Frontend | User interface, file upload, status display | React 18, TypeScript, TailwindCSS |
| API Gateway | Auth validation, routing, job management | FastAPI, cloudflare-auth middleware |
| Job Queue | Async job processing, priority management | Redis + RQ (Redis Queue) |
| WebSocket Server | Real-time status updates | FastAPI WebSocket |
| Handoff Service | Project D routing and delivery | FastAPI, configurable backends |

---

## 4. File Routing Logic

### 4.1 Content Type Detection

The system uses a multi-stage detection approach to determine the appropriate pipeline for each uploaded file.

#### 4.1.1 Detection Priority

1. Magic bytes (file signature) - Most reliable
2. MIME type from upload headers
3. File extension - Fallback only

#### 4.1.2 File Type to Pipeline Mapping

| File Type | Extensions | Pipeline | Notes |
|-----------|------------|----------|-------|
| Audio | .mp3, .wav, .m4a, .flac, .ogg, .aac | Project E | Deepgram transcription |
| Video (audio track) | .mp4, .mov, .avi, .mkv, .webm | Project E | Audio extraction first |
| Scanned PDF | .pdf (image-based) | Project A | IQA + OCR |
| Born-digital PDF | .pdf (text-based) | Project B | Direct Docling |
| Images | .jpg, .png, .tiff, .bmp, .webp | Project A | IQA assessment |
| Office Documents | .docx, .xlsx, .pptx | Project B | Direct Docling |
| Plain Text | .txt, .md, .rst, .csv | Project B | Minimal processing |
| Email | .eml, .msg | Project B | Extract + attachments |

#### 4.1.3 PDF Classification Logic

PDFs require special handling to determine if they are scanned (image-based) or born-digital (text-based):

```python
def classify_pdf(pdf_path: Path) -> Literal['scanned', 'born_digital', 'mixed']:
    """
    Classify PDF based on text extraction ratio.

    Returns:
        'scanned': < 10% extractable text (route to Project A)
        'born_digital': > 90% extractable text (route to Project B)
        'mixed': 10-90% (route to Project A for safety)
    """
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        text_pages = 0

        for page in pdf.pages:
            text = page.extract_text() or ''
            if len(text.strip()) > 50:
                text_pages += 1

        ratio = text_pages / total_pages

        if ratio < 0.1:
            return 'scanned'
        elif ratio > 0.9:
            return 'born_digital'
        else:
            return 'mixed'
```

---

## 5. API Specifications

### 5.1 Gateway API Endpoints

#### 5.1.1 File Upload

`POST /api/v1/ingest`

Upload one or more files for processing. Requires Cloudflare Access authentication.

**Request:** multipart/form-data

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| files | File[] | Yes | One or more files to process |
| priority | string | No | Job priority: low, normal, high (default: normal) |
| target_project_d | string | No | Target Project D variant ID for handoff |
| metadata | JSON | No | Custom metadata to attach to job |
| callback_url | string | No | Webhook URL for completion notification |

**Response:** application/json

```json
{
  "batch_id": "batch_abc123",
  "created_by": "user@domain.com",
  "jobs": [
    {
      "job_id": "job_xyz789",
      "filename": "document.pdf",
      "file_type": "application/pdf",
      "classification": "born_digital",
      "routed_to": "project-b",
      "status": "queued",
      "priority": "normal",
      "created_at": "2024-12-03T10:30:00Z",
      "created_by_email": "user@domain.com",
      "estimated_duration_seconds": 45
    }
  ],
  "total_files": 1,
  "status_url": "/api/v1/batch/batch_abc123/status",
  "websocket_url": "ws://host/ws/batch/batch_abc123"
}
```

---

## 6. Deployment Configuration

### 6.1 Docker Compose Services

```yaml
# docker-compose.yml (authentication-relevant excerpt)

services:
  # Cloudflare Tunnel for secure ingress
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: rag-cloudflared
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      - rag-network

  # API Gateway with Cloudflare Auth
  gateway:
    build:
      context: .
      dockerfile: gateway/Dockerfile
    container_name: rag-gateway
    restart: unless-stopped
    expose:
      - "8000"  # Not published externally - accessed via tunnel
    environment:
      # Cloudflare Access Authentication
      CLOUDFLARE_TEAM_DOMAIN: ${CLOUDFLARE_TEAM_DOMAIN}
      CLOUDFLARE_AUDIENCE_TAG: ${CLOUDFLARE_AUDIENCE_TAG}
      CLOUDFLARE_ENABLED: ${CLOUDFLARE_ENABLED:-true}
      ALLOWED_EMAIL_DOMAINS: ${ALLOWED_EMAIL_DOMAINS:-}
      ENVIRONMENT: ${ENVIRONMENT:-prod}

      # Internal service URLs (no auth needed)
      PROJECT_A_URL: http://project-a:8000
      PROJECT_E_URL: http://project-e:8000
      PROJECT_B_URL: http://project-b:8000
      PROJECT_C_URL: http://project-c:8000
      PROJECT_D_URL: http://project-d:8000
      REDIS_URL: redis://redis:6379
    volumes:
      - ${RAG_DATA_PATH}/uploads:/data/uploads
    networks:
      - rag-network
    depends_on:
      redis:
        condition: service_healthy

  # Frontend (served through tunnel)
  rag-ui:
    build:
      context: ./rag-ui
    container_name: rag-ui
    restart: unless-stopped
    expose:
      - "3000"  # Not published externally
    environment:
      VITE_API_URL: /api  # Relative, proxied through tunnel
      VITE_WS_URL: /ws
    networks:
      - rag-network

networks:
  rag-network:
    driver: bridge
```

### 6.2 Environment File

```bash
# .env

# ===========================================
# CLOUDFLARE ACCESS AUTHENTICATION
# ===========================================
CLOUDFLARE_TEAM_DOMAIN=your-team.cloudflareaccess.com
CLOUDFLARE_AUDIENCE_TAG=your-audience-tag-from-dashboard
CLOUDFLARE_ENABLED=true
ALLOWED_EMAIL_DOMAINS=yourdomain.com,contractor.com
ENVIRONMENT=prod

# ===========================================
# CLOUDFLARE TUNNEL
# ===========================================
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token

# ===========================================
# PATHS
# ===========================================
RAG_DATA_PATH=/mnt/user/rag-pipeline
```

---

## Appendix A: API Quick Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /health | No | Health check |
| GET | /metrics | No | Prometheus metrics |
| POST | /api/v1/ingest | Yes | Upload files |
| GET | /api/v1/batch/{id}/status | Yes | Get batch status |
| GET | /api/v1/job/{id} | Yes | Get job details |
| GET | /api/v1/job/{id}/results | Yes | Get processed results |
| POST | /api/v1/job/{id}/handoff | Yes | Trigger handoff |
| GET | /api/v1/targets | Yes | List Project D targets |
| POST | /api/v1/targets/register | No* | Register target |
| WS | /ws/batch/{id} | Yes** | Real-time updates |

\* Internal network only (excluded from auth)
\** Token passed via query parameter

---

*— End of Document —*
