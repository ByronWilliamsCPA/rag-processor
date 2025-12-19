# RAG Processor WebUI - Integration Guide for Project A

> **Document Purpose**: Provide the Document & Image Preprocessing team (Project A) with the information needed to integrate with the RAG Processor WebUI gateway.
>
> **Last Updated**: 2025-12-19
> **Source Repository**: https://github.com/ByronWilliamsCPA/rag-processor

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Context](#architecture-context)
3. [API Contract Requirements](#api-contract-requirements)
4. [Data Formats & Schemas](#data-formats--schemas)
5. [File Routing Logic](#file-routing-logic)
6. [Performance Expectations](#performance-expectations)
7. [Security Considerations](#security-considerations)
8. [Integration Checklist](#integration-checklist)

---

## System Overview

The **RAG Processor WebUI** is a React + FastAPI gateway that provides:

- Unified file upload interface for end users
- Automatic file classification and pipeline routing
- Real-time job status via WebSocket
- Vector store handoff upon completion

**Your Role (Project A)**: Receive preprocessed document/image files from the gateway, process them, and expose results via HTTP endpoints.

### What the Gateway Handles (You Don't Need To)

| Responsibility | Handled By |
|----------------|------------|
| User authentication | Gateway (Cloudflare Access JWT) |
| File upload UI | Gateway (React frontend) |
| File type detection | Gateway (magic bytes + pdfplumber) |
| Pipeline routing | Gateway (classification logic) |
| Job queue management | Gateway (Redis + RQ) |
| Real-time status to users | Gateway (WebSocket) |
| Vector store handoff | Gateway (Qdrant/Milvus HTTP) |
| Retry logic | Gateway (3 attempts, exponential backoff) |

---

## Architecture Context

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAG Pipeline Ecosystem                          │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   WebUI      │      │  Project A   │      │  Project B   │      │  Project C   │
│  (Gateway)   │─────▶│  Preprocess  │─────▶│     OCR      │─────▶│    Post-     │
│              │      │  Doc/Image   │      │              │      │  Processing  │
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
       │                                                                  │
       │                                                                  │
       │              ┌──────────────┐                                    │
       └─────────────▶│  Project D   │◀───────────────────────────────────┘
                      │  Vector DB   │
                      │  (RAG Store) │
                      └──────────────┘
```

### Data Flow

1. **User uploads files** → WebUI gateway
2. **Gateway classifies files** → Determines routing (scanned PDF, born-digital, image, etc.)
3. **Gateway calls Project A** → `POST /process` with file + metadata
4. **Project A processes** → Returns job ID, exposes status endpoint
5. **Gateway polls status** → Every 5 seconds until complete
6. **On completion** → Gateway fetches results, hands off to downstream (B, C, or D)

---

## API Contract Requirements

### Required Endpoints

Your preprocessing service **must implement** these HTTP endpoints:

#### 1. Process Endpoint

```http
POST /process
Authorization: Bearer {shared_secret_token}
Content-Type: multipart/form-data

Form Fields:
  file         : binary    (required) - The file to process
  job_id       : string    (required) - UUID assigned by gateway
  priority     : string    (required) - "high" | "normal" | "low"
  callback_url : string    (optional) - Gateway callback URL (for future webhook support)
  metadata     : string    (optional) - JSON blob with additional context

Response (200 OK):
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "queued",
  "status_url": "/status/7c9e6679-7425-40de-944b-e07fc1f90ae7"
}

Error Response (4xx/5xx):
{
  "error": "Invalid file format",
  "detail": "Expected PDF, received PNG",
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

#### 2. Status Endpoint

```http
GET /status/{job_id}
Authorization: Bearer {shared_secret_token}

Response (200 OK):
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "processing",      // "queued" | "processing" | "completed" | "failed"
  "progress": 0.75,            // 0.0 to 1.0 (optional but recommended)
  "message": "Extracting text from page 12/16",  // Human-readable status (optional)
  "result_url": null,          // Populated when status == "completed"
  "error": null                // Populated when status == "failed"
}

Completed Response:
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "completed",
  "progress": 1.0,
  "result_url": "/results/7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "error": null
}

Failed Response:
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "failed",
  "progress": 0.45,
  "result_url": null,
  "error": "Memory limit exceeded processing large image"
}
```

#### 3. Results Endpoint

```http
GET /results/{job_id}
Authorization: Bearer {shared_secret_token}

Response: Varies by output format (see Data Formats section)
```

#### 4. Health Endpoint (Recommended)

```http
GET /health

Response (200 OK):
{
  "status": "healthy",
  "version": "1.2.3",
  "uptime_seconds": 3600
}
```

---

## Data Formats & Schemas

### Input: Files Sent to Project A

| File Type | Extensions | Classification | MIME Type |
|-----------|------------|----------------|-----------|
| Scanned PDF | `.pdf` | `scanned_pdf` | `application/pdf` |
| Born-Digital PDF | `.pdf` | `born_digital_pdf` | `application/pdf` |
| Images | `.png`, `.jpg`, `.jpeg` | `image` | `image/png`, `image/jpeg` |
| Office Docs | `.docx`, `.doc` | `office_document` | `application/vnd.openxmlformats-...` |
| Text Files | `.txt` | `text` | `text/plain` |

**Note**: The gateway uses magic byte scanning (not file extensions) to determine MIME types. Your service should validate the actual file content.

### Output: Results Format

Your `/results/{job_id}` endpoint should return **one of these formats**:

#### Option A: JSON Response (Recommended for Text Extraction)

```json
{
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "source_file": "document.pdf",
  "processing_time_ms": 1234,
  "output": {
    "text": "Extracted text content...",
    "pages": [
      {
        "page_number": 1,
        "text": "Page 1 content...",
        "confidence": 0.95
      }
    ],
    "metadata": {
      "page_count": 16,
      "detected_language": "en",
      "has_tables": true,
      "has_images": true
    }
  }
}
```

#### Option B: Binary Download (For Processed Files)

```http
GET /results/{job_id}
Authorization: Bearer {shared_secret_token}

Response Headers:
  Content-Type: application/pdf
  Content-Disposition: attachment; filename="processed_document.pdf"
  X-Processing-Time-Ms: 1234
  X-Page-Count: 16

Body: <binary file content>
```

#### Option C: Multi-File Archive (For Complex Outputs)

```http
GET /results/{job_id}
Authorization: Bearer {shared_secret_token}

Response Headers:
  Content-Type: application/zip
  Content-Disposition: attachment; filename="results_7c9e6679.zip"

Body: <ZIP archive containing>
  - extracted_text.json
  - images/page_001.png
  - images/page_002.png
  - tables/table_001.csv
  - metadata.json
```

---

## File Routing Logic

The gateway uses this logic to route files to preprocessing pipelines:

```python
def classify_file(file: UploadFile) -> tuple[FileClassification, Pipeline]:
    mime_type = detect_mime_type(file)  # Magic byte scanning

    if mime_type == "application/pdf":
        if is_scanned_pdf(file):  # pdfplumber text extraction check
            return (FileClassification.SCANNED_PDF, Pipeline.OCR)
        else:
            return (FileClassification.BORN_DIGITAL_PDF, Pipeline.DOC_PROCESSING)

    elif mime_type.startswith("image/"):
        return (FileClassification.IMAGE, Pipeline.OCR)

    elif mime_type.startswith("audio/"):
        return (FileClassification.AUDIO, Pipeline.TRANSCRIPTION)

    elif mime_type.startswith("video/"):
        return (FileClassification.VIDEO, Pipeline.TRANSCRIPTION)

    else:
        return (FileClassification.DOCUMENT, Pipeline.DOC_PROCESSING)
```

**For Project A**, you'll receive files classified as:
- `scanned_pdf` (scanned PDFs needing OCR preparation)
- `born_digital_pdf` (text-extractable PDFs)
- `image` (PNG, JPEG for preprocessing before OCR)
- `office_document` (DOCX, DOC for text extraction)
- `text` (TXT files, minimal processing)

---

## Performance Expectations

### Timeouts & Polling

| Parameter | Value | Notes |
|-----------|-------|-------|
| HTTP Request Timeout | 30 seconds | For initial `/process` call |
| Processing Timeout | 5 minutes | Max time before gateway marks job as failed |
| Status Polling Interval | 5 seconds | Gateway polls `/status/{job_id}` |
| Retry Attempts | 3 | On transient failures (5xx, network errors) |
| Retry Backoff | 2s, 4s, 8s | Exponential backoff between retries |

### Throughput Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Aggregate Throughput | 1000+ files/hour | Across all pipelines combined |
| Single File (10 pages) | <30 seconds | Typical document |
| Single File (100 pages) | <2 minutes | Large document |
| Status Response | <100ms | Lightweight status check |

### Resource Constraints

| Constraint | Limit |
|------------|-------|
| Max File Size | 100 MB per file |
| Max Batch Size | 500 MB total |
| Max Filename Length | 255 characters |
| Concurrent Jobs | Plan for 50-100 concurrent |

---

## Security Considerations

### Authentication

The gateway authenticates with your service using **Bearer token authentication**:

```http
Authorization: Bearer {PREPROCESSING_API_TOKEN}
```

- Token is configured via environment variable in both services
- Rotate tokens periodically (recommend 90-day rotation)
- Use different tokens for each environment (dev/staging/prod)

### Input Validation

**Your service should validate**:

1. **File size** - Reject files >100MB immediately
2. **MIME type** - Validate magic bytes match expected types
3. **Filename** - Sanitize for path traversal (`..`, `/`, `\`)
4. **Job ID** - Validate UUID format

### Network Security

- **MVP**: Gateway and preprocessing run on same Docker network (unencrypted)
- **Production**: Consider mTLS between services
- **Rate Limiting**: Gateway implements rate limiting; your service may add additional limits

### Sensitive Data

- **Never log file contents** - Log only metadata (filename, size, job_id)
- **Secure storage** - Use appropriate permissions for processed files
- **Cleanup** - Delete processed files after configurable TTL (default: 7 days)

---

## Integration Checklist

Use this checklist to verify your preprocessing service is ready for integration:

### API Implementation

- [ ] `POST /process` endpoint accepts multipart/form-data
- [ ] `GET /status/{job_id}` returns current processing status
- [ ] `GET /results/{job_id}` returns processed output
- [ ] `GET /health` returns service health (recommended)
- [ ] Bearer token authentication on all endpoints
- [ ] Proper HTTP status codes (202 for accepted, 200 for success, 4xx/5xx for errors)

### Status Responses

- [ ] Returns `status` field with values: `queued`, `processing`, `completed`, `failed`
- [ ] Returns `progress` field (0.0 to 1.0) for UI progress bars
- [ ] Returns `result_url` when `status == "completed"`
- [ ] Returns `error` message when `status == "failed"`

### Error Handling

- [ ] Graceful handling of invalid file types
- [ ] Graceful handling of oversized files
- [ ] Graceful handling of malformed requests
- [ ] Error responses include `job_id` for correlation

### Performance

- [ ] Status endpoint responds in <100ms
- [ ] Processing completes within 5-minute timeout
- [ ] Can handle 50+ concurrent jobs

### Observability

- [ ] Structured JSON logging (recommended)
- [ ] Correlation ID propagation (pass through `X-Correlation-ID` header)
- [ ] Metrics endpoint for monitoring (optional)

---

## Contact & Support

**Gateway Team Contact**: [Add your contact info]

**Repository**: https://github.com/ByronWilliamsCPA/rag-processor

**Key Documents**:
- [Project Vision](planning/project-vision.md)
- [Technical Specification](planning/tech-spec.md)
- [Architecture Decision Records](planning/adr/)

---

## Appendix: Example Integration

### Minimal Python Implementation

```python
from fastapi import FastAPI, UploadFile, Form, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid

app = FastAPI()
security = HTTPBearer()

# In-memory job store (use Redis in production)
jobs: dict[str, dict] = {}

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != "your-secret-token":
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials

@app.post("/process")
async def process_file(
    file: UploadFile,
    job_id: str = Form(...),
    priority: str = Form(...),
    token: str = Depends(verify_token)
):
    # Store job and start processing (async)
    jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "result_url": None,
        "error": None
    }
    # Trigger background processing here...
    return {
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/status/{job_id}"
    }

@app.get("/status/{job_id}")
async def get_status(job_id: str, token: str = Depends(verify_token)):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **jobs[job_id]}

@app.get("/results/{job_id}")
async def get_results(job_id: str, token: str = Depends(verify_token)):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if jobs[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    # Return processed results...
    return {"job_id": job_id, "output": {"text": "Extracted content..."}}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

*This document is generated from the RAG Processor WebUI codebase. For the latest version, see the source repository.*
