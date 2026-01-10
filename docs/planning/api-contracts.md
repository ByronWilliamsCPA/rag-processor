---
title: "API Contracts: Inter-Service Communication"
schema_type: specification
status: draft
owner: core-maintainer
purpose: "Define clear contracts between RAG Processor, Paperless-ngx, and Vector Database."
tags:
  - api
  - contracts
  - integration
  - specification
component: Integration
source: "Architecture specification"
---

# API Contracts: Inter-Service Communication

> **Status**: Draft | **Version**: 1.0 | **Date**: 2026-01-10

## Overview

This document defines the **contracts** (data formats, endpoints, authentication) between all services in the RAG Processor architecture. All services MUST adhere to these contracts.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SERVICE BOUNDARIES                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐     Contract A      ┌─────────────────────────────────┐   │
│   │ Paperless   │ ─────────────────► │                                 │   │
│   │    -ngx     │                     │                                 │   │
│   │             │ ◄───────────────── │                                 │   │
│   └─────────────┘     Contract B      │       RAG PROCESSOR             │   │
│                                       │                                 │   │
│                                       │                                 │   │
│   ┌─────────────┐     Contract C      │                                 │   │
│   │   Client    │ ─────────────────► │                                 │   │
│   │    Apps     │ ◄───────────────── │                                 │   │
│   └─────────────┘     Contract D      │                                 │   │
│                                       └──────────────┬──────────────────┘   │
│                                                      │                       │
│                                              Contract E                      │
│                                                      │                       │
│                                                      ▼                       │
│                                       ┌─────────────────────────────────┐   │
│                                       │     VECTOR DATABASE (Qdrant)    │   │
│                                       └─────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Contract A: Paperless-ngx → RAG Processor (Webhooks)
Contract B: RAG Processor → Paperless-ngx (API Calls)
Contract C: Client Apps → RAG Processor (Query API)
Contract D: RAG Processor → Client Apps (Query Results)
Contract E: RAG Processor ↔ Vector Database (Indexing/Search)
```

---

## Contract A: Paperless-ngx → RAG Processor

### A.1 Document Consumed Webhook

Triggered when Paperless-ngx finishes processing a document.

**Endpoint**: `POST /api/v1/webhooks/paperless/document-consumed`

**Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | `application/json` |
| `X-Paperless-Signature` | Yes | HMAC-SHA256 signature of body |
| `X-Paperless-Tenant-ID` | Yes | Tenant identifier |
| `X-Paperless-Timestamp` | Yes | Unix timestamp (for replay protection) |

**Signature Verification**:

```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

**Request Body**:

```json
{
  "$schema": "https://rag-processor.example.com/schemas/webhook-document-consumed-v1.json",
  "event_type": "document.consumed",
  "event_id": "evt_550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-10T10:30:00Z",
  "tenant_id": "acme-corp",
  "paperless_instance_url": "https://docs.acme.example.com",
  "document": {
    "id": 123,
    "title": "Invoice 2024-001",
    "correspondent": {
      "id": 5,
      "name": "Globex Corporation"
    },
    "document_type": {
      "id": 2,
      "name": "Invoice"
    },
    "tags": [
      {"id": 1, "name": "business"},
      {"id": 3, "name": "2024"}
    ],
    "created": "2024-01-15",
    "added": "2026-01-10T10:30:00Z",
    "modified": "2026-01-10T10:30:00Z",
    "archive_serial_number": 20240115001,
    "original_filename": "invoice_globex_jan2024.pdf",
    "mime_type": "application/pdf",
    "page_count": 3,
    "has_archive_version": true,
    "content_preview": "First 500 characters of extracted text..."
  },
  "processing_hints": {
    "priority": "normal",
    "force_docling_ocr": false,
    "custom_prompt": null
  }
}
```

**Required Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | string | Always `"document.consumed"` |
| `event_id` | string | Unique event ID (UUID format) |
| `timestamp` | string | ISO 8601 timestamp |
| `tenant_id` | string | Tenant identifier |
| `paperless_instance_url` | string | Base URL of Paperless instance |
| `document.id` | integer | Paperless document ID |
| `document.title` | string | Document title |
| `document.mime_type` | string | MIME type of original file |

**Response** (Success):

```json
{
  "status": "accepted",
  "job_id": "job_7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "message": "Document queued for processing",
  "estimated_completion_seconds": 120
}
```

**Response** (Error):

```json
{
  "status": "error",
  "error_code": "INVALID_TENANT",
  "message": "Tenant 'unknown-corp' not found in registry",
  "request_id": "req_abc123"
}
```

**HTTP Status Codes**:

| Code | Meaning |
|------|---------|
| 202 | Accepted - Document queued |
| 400 | Bad Request - Invalid payload |
| 401 | Unauthorized - Invalid signature |
| 404 | Not Found - Unknown tenant |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error |

---

### A.2 Document Updated Webhook

Triggered when document metadata is updated in Paperless-ngx.

**Endpoint**: `POST /api/v1/webhooks/paperless/document-updated`

**Request Body**:

```json
{
  "event_type": "document.updated",
  "event_id": "evt_8b7d9f32-c1e4-4a89-b2c6-123456789abc",
  "timestamp": "2026-01-10T11:00:00Z",
  "tenant_id": "acme-corp",
  "paperless_instance_url": "https://docs.acme.example.com",
  "document": {
    "id": 123,
    "title": "Invoice 2024-001 (Updated)",
    "correspondent": {
      "id": 5,
      "name": "Globex Corporation"
    },
    "document_type": {
      "id": 2,
      "name": "Invoice"
    },
    "tags": [
      {"id": 1, "name": "business"},
      {"id": 3, "name": "2024"},
      {"id": 7, "name": "paid"}
    ],
    "created": "2024-01-15",
    "modified": "2026-01-10T11:00:00Z"
  },
  "changes": {
    "fields_changed": ["title", "tags"],
    "tags_added": [{"id": 7, "name": "paid"}],
    "tags_removed": [],
    "previous_title": "Invoice 2024-001"
  }
}
```

**Response**: Same as A.1

---

### A.3 Document Deleted Webhook

Triggered when a document is deleted from Paperless-ngx.

**Endpoint**: `POST /api/v1/webhooks/paperless/document-deleted`

**Request Body**:

```json
{
  "event_type": "document.deleted",
  "event_id": "evt_delete-uuid-here",
  "timestamp": "2026-01-10T12:00:00Z",
  "tenant_id": "acme-corp",
  "paperless_instance_url": "https://docs.acme.example.com",
  "document": {
    "id": 123,
    "title": "Invoice 2024-001"
  },
  "deletion_type": "permanent"
}
```

**Response**: Same as A.1, but job removes vectors from database.

---

## Contract B: RAG Processor → Paperless-ngx

### B.1 Fetch Document Content

Download the original or archive version of a document.

**Endpoint**: `GET {paperless_url}/api/documents/{id}/download/`

**Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Token {api_token}` |

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `original` | boolean | false | If true, download original file |

**Response**: Binary file content with `Content-Type` header.

---

### B.2 Fetch Document Metadata

Get full document metadata including custom fields.

**Endpoint**: `GET {paperless_url}/api/documents/{id}/?full_perms=true`

**Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Token {api_token}` |

**Response**:

```json
{
  "id": 123,
  "title": "Invoice 2024-001",
  "content": "Full extracted text content...",
  "correspondent": 5,
  "document_type": 2,
  "tags": [1, 3, 7],
  "created": "2024-01-15",
  "created_date": "2024-01-15",
  "modified": "2026-01-10T11:00:00Z",
  "added": "2026-01-10T10:30:00Z",
  "archive_serial_number": 20240115001,
  "original_file_name": "invoice_globex_jan2024.pdf",
  "archived_file_name": "2024-01-15 Invoice 2024-001.pdf",
  "owner": 1,
  "user_can_change": true,
  "is_shared_by_requester": false,
  "notes": [],
  "custom_fields": [
    {"field": 1, "value": null},
    {"field": 2, "value": null}
  ],
  "set_permissions": {
    "view": {"users": [1], "groups": []},
    "change": {"users": [1], "groups": []}
  },
  "__search_hit__": null
}
```

---

### B.3 Update Document Metadata

Update document metadata after RAG processing.

**Endpoint**: `PATCH {paperless_url}/api/documents/{id}/`

**Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Token {api_token}` |
| `Content-Type` | Yes | `application/json` |

**Request Body** (RAG Processor sends):

```json
{
  "custom_fields": [
    {
      "field": 1,
      "value": "2026-01-10T10:32:00Z"
    },
    {
      "field": 2,
      "value": 42
    },
    {
      "field": 3,
      "value": "text-embedding-3-small"
    },
    {
      "field": 4,
      "value": "job_7c9e6679-7425-40de-944b-e07fc1f90ae7"
    },
    {
      "field": 5,
      "value": true
    },
    {
      "field": 6,
      "value": 0.95
    }
  ],
  "tags": [1, 3, 7, 10, 11]
}
```

**Custom Field Mapping** (must be created in Paperless first):

| Field ID | Name | Type | Description |
|----------|------|------|-------------|
| 1 | `rag_processed_at` | DateTime | When RAG processing completed |
| 2 | `rag_chunk_count` | Integer | Number of chunks in vector store |
| 3 | `rag_embedding_model` | String | Embedding model used |
| 4 | `rag_job_id` | String | RAG Processor job ID |
| 5 | `rag_docling_processed` | Boolean | Whether Docling OCR was used |
| 6 | `rag_ocr_quality_score` | Float | OCR quality estimate (0-1) |

**Tag Mapping** (must be created in Paperless first):

| Tag Name | Description |
|----------|-------------|
| `rag-indexed` | Document has been indexed in vector store |
| `rag-docling` | Processed with Docling advanced OCR |
| `rag-error` | RAG processing failed |
| `rag-pending` | Awaiting RAG processing |

**Response**: Updated document object (same as B.2).

---

### B.4 Fetch Available Tags

Get all tags for validation and ID lookup.

**Endpoint**: `GET {paperless_url}/api/tags/`

**Response**:

```json
{
  "count": 15,
  "next": null,
  "previous": null,
  "results": [
    {"id": 1, "name": "business", "slug": "business", "colour": 1},
    {"id": 10, "name": "rag-indexed", "slug": "rag-indexed", "colour": 5}
  ]
}
```

---

### B.5 Fetch Custom Fields Schema

Get custom field definitions for ID lookup.

**Endpoint**: `GET {paperless_url}/api/custom_fields/`

**Response**:

```json
{
  "count": 6,
  "next": null,
  "previous": null,
  "results": [
    {"id": 1, "name": "rag_processed_at", "data_type": "date"},
    {"id": 2, "name": "rag_chunk_count", "data_type": "integer"},
    {"id": 3, "name": "rag_embedding_model", "data_type": "string"},
    {"id": 4, "name": "rag_job_id", "data_type": "string"},
    {"id": 5, "name": "rag_docling_processed", "data_type": "boolean"},
    {"id": 6, "name": "rag_ocr_quality_score", "data_type": "float"}
  ]
}
```

---

## Contract C: Client Apps → RAG Processor

### C.1 Authentication

All client API calls require authentication via **Authentik** (external OIDC provider).

> **Note**: Authentication and tenant provisioning are handled externally. RAG Processor only validates incoming JWTs.

**Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer {jwt_token}` (from Authentik) |
| `X-Tenant-ID` | Conditional | Required if not in JWT claims |

**JWT Claims** (expected from Authentik):

```json
{
  "sub": "user_12345",
  "email": "user@acme.example.com",
  "name": "John Doe",
  "groups": ["acme-corp-users"],
  "tenant_id": "acme-corp",
  "ak_proxy": {
    "user_attributes": {
      "tenant": "acme-corp"
    }
  },
  "iat": 1704880200,
  "exp": 1704883800,
  "iss": "https://auth.example.com/application/o/rag-processor/"
}
```

**Tenant Resolution** (in order of precedence):
1. `X-Tenant-ID` header (explicit)
2. `tenant_id` claim in JWT
3. `ak_proxy.user_attributes.tenant` (Authentik-specific)
4. First group matching pattern `{tenant}-users`

---

### C.2 Semantic Search Query

Search documents using natural language.

**Endpoint**: `POST /api/v1/search`

**Request Body**:

```json
{
  "query": "What are the payment terms for our Globex contracts?",
  "options": {
    "top_k": 10,
    "min_score": 0.5,
    "rerank": true,
    "include_content": true
  },
  "filters": {
    "document_types": ["Contract", "Invoice"],
    "correspondents": ["Globex Corporation"],
    "tags": ["business"],
    "date_range": {
      "field": "created",
      "start": "2023-01-01",
      "end": "2024-12-31"
    }
  }
}
```

**Request Schema**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | - | Natural language query |
| `options.top_k` | integer | No | 10 | Number of results |
| `options.min_score` | float | No | 0.0 | Minimum relevance score (0-1) |
| `options.rerank` | boolean | No | true | Apply cross-encoder reranking |
| `options.include_content` | boolean | No | true | Include chunk text in results |
| `filters.document_types` | string[] | No | [] | Filter by document type names |
| `filters.correspondents` | string[] | No | [] | Filter by correspondent names |
| `filters.tags` | string[] | No | [] | Filter by tag names (AND logic) |
| `filters.date_range.field` | string | No | - | `created` or `added` |
| `filters.date_range.start` | string | No | - | ISO date |
| `filters.date_range.end` | string | No | - | ISO date |

**Response**: See Contract D.1

---

### C.3 RAG Query (with LLM Generation)

Query documents and generate an answer using retrieved context.

**Endpoint**: `POST /api/v1/query`

**Request Body**:

```json
{
  "question": "What are the payment terms for our Globex contracts?",
  "options": {
    "top_k": 5,
    "model": "gpt-4o",
    "temperature": 0.1,
    "max_tokens": 1000,
    "include_sources": true
  },
  "filters": {
    "document_types": ["Contract"],
    "correspondents": ["Globex Corporation"]
  },
  "system_prompt": "You are a helpful assistant analyzing business documents. Be concise and cite sources."
}
```

**Request Schema**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `question` | string | Yes | - | User's question |
| `options.top_k` | integer | No | 5 | Chunks to retrieve for context |
| `options.model` | string | No | `gpt-4o` | LLM model for generation |
| `options.temperature` | float | No | 0.1 | LLM temperature |
| `options.max_tokens` | integer | No | 1000 | Max response tokens |
| `options.include_sources` | boolean | No | true | Include source citations |
| `filters` | object | No | {} | Same as C.2 |
| `system_prompt` | string | No | default | Custom system prompt |

**Response**: See Contract D.2

---

### C.4 Get Processing Job Status

Check status of a document processing job.

**Endpoint**: `GET /api/v1/jobs/{job_id}`

**Response**:

```json
{
  "job_id": "job_7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "completed",
  "tenant_id": "acme-corp",
  "document": {
    "paperless_id": 123,
    "paperless_url": "https://docs.acme.example.com/api/documents/123/",
    "title": "Invoice 2024-001"
  },
  "processing": {
    "started_at": "2026-01-10T10:30:05Z",
    "completed_at": "2026-01-10T10:32:00Z",
    "duration_seconds": 115,
    "stages": [
      {"name": "fetch_document", "status": "completed", "duration_ms": 1200},
      {"name": "classify_document", "status": "completed", "duration_ms": 50},
      {"name": "docling_ocr", "status": "completed", "duration_ms": 45000},
      {"name": "chunking", "status": "completed", "duration_ms": 200},
      {"name": "embedding", "status": "completed", "duration_ms": 5000},
      {"name": "indexing", "status": "completed", "duration_ms": 300},
      {"name": "update_paperless", "status": "completed", "duration_ms": 500}
    ]
  },
  "results": {
    "chunk_count": 42,
    "embedding_model": "text-embedding-3-small",
    "docling_used": true,
    "ocr_quality_score": 0.95
  },
  "error": null
}
```

**Job Status Values**:

| Status | Description |
|--------|-------------|
| `queued` | Job is waiting in queue |
| `processing` | Job is currently being processed |
| `completed` | Job finished successfully |
| `failed` | Job failed with error |
| `cancelled` | Job was cancelled |

---

### C.5 List Documents (Indexed)

List documents indexed in the vector store for this tenant.

**Endpoint**: `GET /api/v1/documents`

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Results per page (max 100) |
| `sort` | string | `-indexed_at` | Sort field (prefix `-` for desc) |
| `status` | string | - | Filter: `indexed`, `pending`, `error` |

**Response**:

```json
{
  "count": 156,
  "page": 1,
  "page_size": 20,
  "total_pages": 8,
  "results": [
    {
      "paperless_id": 123,
      "paperless_url": "https://docs.acme.example.com/documents/123/",
      "title": "Invoice 2024-001",
      "correspondent": "Globex Corporation",
      "document_type": "Invoice",
      "tags": ["business", "2024", "rag-indexed"],
      "chunk_count": 42,
      "indexed_at": "2026-01-10T10:32:00Z",
      "embedding_model": "text-embedding-3-small",
      "status": "indexed"
    }
  ]
}
```

---

### C.6 Re-index Document

Force re-indexing of a specific document.

**Endpoint**: `POST /api/v1/documents/{paperless_id}/reindex`

**Request Body**:

```json
{
  "force_docling": true,
  "priority": "high"
}
```

**Response**: Same as webhook response (A.1).

---

### C.7 Admin: List Tenants

Admin-only endpoint to list configured tenants.

**Endpoint**: `GET /api/v1/admin/tenants`

**Required Role**: `admin`

**Response**:

```json
{
  "tenants": [
    {
      "tenant_id": "acme-corp",
      "tenant_name": "Acme Corporation",
      "status": "active",
      "paperless_url": "https://docs.acme.example.com",
      "stats": {
        "documents_indexed": 156,
        "total_chunks": 4280,
        "last_activity": "2026-01-10T10:32:00Z"
      }
    }
  ]
}
```

---

## Contract D: RAG Processor → Client Apps

### D.1 Search Results Response

Response format for semantic search (C.2).

```json
{
  "query": "What are the payment terms for our Globex contracts?",
  "results": [
    {
      "score": 0.89,
      "rank": 1,
      "document": {
        "paperless_id": 123,
        "paperless_url": "https://docs.acme.example.com/documents/123/",
        "title": "Globex Master Services Agreement",
        "correspondent": "Globex Corporation",
        "document_type": "Contract",
        "tags": ["business", "contracts", "2024"],
        "created": "2024-01-15"
      },
      "chunk": {
        "chunk_id": "chunk_abc123",
        "chunk_index": 5,
        "page_number": 3,
        "section_path": ["Terms and Conditions", "Payment Terms"],
        "element_type": "paragraph",
        "content": "Payment is due within thirty (30) days of invoice date. Late payments shall accrue interest at 1.5% per month..."
      }
    }
  ],
  "metadata": {
    "total_results": 1,
    "search_time_ms": 145,
    "reranking_applied": true,
    "filters_applied": {
      "document_types": ["Contract"],
      "correspondents": ["Globex Corporation"]
    }
  }
}
```

**Result Object Schema**:

| Field | Type | Description |
|-------|------|-------------|
| `score` | float | Relevance score (0-1) |
| `rank` | integer | Position after reranking |
| `document.paperless_id` | integer | Paperless document ID |
| `document.paperless_url` | string | Direct link to document |
| `document.title` | string | Document title |
| `document.correspondent` | string | Correspondent name |
| `document.document_type` | string | Document type name |
| `document.tags` | string[] | Tag names |
| `document.created` | string | Document creation date |
| `chunk.chunk_id` | string | Unique chunk identifier |
| `chunk.chunk_index` | integer | Position within document |
| `chunk.page_number` | integer | Source page number |
| `chunk.section_path` | string[] | Hierarchical section path |
| `chunk.element_type` | string | `paragraph`, `table`, `heading`, `figure` |
| `chunk.content` | string | Chunk text content |

---

### D.2 RAG Query Response

Response format for RAG query with LLM generation (C.3).

```json
{
  "question": "What are the payment terms for our Globex contracts?",
  "answer": "According to the Globex Master Services Agreement, payment terms are **Net 30** - payment is due within thirty (30) days of invoice date. Late payments accrue interest at 1.5% per month. The agreement also specifies that disputed invoices must be raised within 15 days of receipt.",
  "sources": [
    {
      "document": {
        "paperless_id": 123,
        "paperless_url": "https://docs.acme.example.com/documents/123/",
        "title": "Globex Master Services Agreement",
        "correspondent": "Globex Corporation"
      },
      "chunks_used": [
        {
          "chunk_id": "chunk_abc123",
          "page_number": 3,
          "section": "Payment Terms",
          "relevance_score": 0.89
        },
        {
          "chunk_id": "chunk_def456",
          "page_number": 4,
          "section": "Invoice Disputes",
          "relevance_score": 0.76
        }
      ]
    }
  ],
  "metadata": {
    "model": "gpt-4o",
    "tokens_used": {
      "prompt": 1250,
      "completion": 120,
      "total": 1370
    },
    "retrieval_time_ms": 145,
    "generation_time_ms": 2100,
    "total_time_ms": 2245
  },
  "confidence": "high"
}
```

**Confidence Levels**:

| Level | Description |
|-------|-------------|
| `high` | Multiple relevant sources, high similarity scores |
| `medium` | Some relevant sources, moderate scores |
| `low` | Few/weak sources, model may be extrapolating |
| `none` | No relevant sources found |

---

### D.3 Error Response Format

Standard error response format for all endpoints.

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with ID 999 not found in tenant 'acme-corp'",
    "details": {
      "paperless_id": 999,
      "tenant_id": "acme-corp"
    },
    "request_id": "req_xyz789",
    "timestamp": "2026-01-10T10:35:00Z"
  }
}
```

**Standard Error Codes**:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTHENTICATION_REQUIRED` | 401 | Missing or invalid token |
| `AUTHORIZATION_DENIED` | 403 | User lacks required role |
| `TENANT_NOT_FOUND` | 404 | Unknown tenant ID |
| `DOCUMENT_NOT_FOUND` | 404 | Document not in vector store |
| `JOB_NOT_FOUND` | 404 | Unknown job ID |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `RATE_LIMITED` | 429 | Too many requests |
| `PAPERLESS_UNAVAILABLE` | 502 | Cannot reach Paperless instance |
| `VECTOR_DB_ERROR` | 503 | Vector database error |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Contract E: RAG Processor ↔ Vector Database

### E.1 Collection Schema (Qdrant)

Each tenant has a separate collection.

**Collection Name**: `tenant_{tenant_id}`

**Vector Configuration**:

```json
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "optimizers_config": {
    "memmap_threshold": 20000
  },
  "replication_factor": 1,
  "write_consistency_factor": 1
}
```

**Point (Document Chunk) Schema**:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "vector": [0.1, 0.2, ...],
  "payload": {
    "tenant_id": "acme-corp",
    "paperless_doc_id": 123,
    "paperless_url": "https://docs.acme.example.com/api/documents/123/",
    "document_title": "Globex Master Services Agreement",
    "correspondent": "Globex Corporation",
    "correspondent_id": 5,
    "document_type": "Contract",
    "document_type_id": 3,
    "tags": ["business", "contracts", "2024"],
    "tag_ids": [1, 5, 7],
    "created_date": "2024-01-15",
    "added_date": "2026-01-10",
    "chunk_index": 5,
    "chunk_type": "paragraph",
    "page_number": 3,
    "section_title": "Payment Terms",
    "section_path": ["Terms and Conditions", "Payment Terms"],
    "hierarchical_depth": 2,
    "text": "Payment is due within thirty (30) days...",
    "text_length": 156,
    "embedding_model": "text-embedding-3-small",
    "docling_version": "2.0.0",
    "indexed_at": "2026-01-10T10:32:00Z",
    "job_id": "job_7c9e6679-7425-40de-944b-e07fc1f90ae7"
  }
}
```

**Required Payload Fields**:

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| `tenant_id` | string | Yes | For tenant isolation |
| `paperless_doc_id` | integer | Yes | For document lookup |
| `document_title` | string | No | Display purposes |
| `correspondent` | string | Yes | Filter field |
| `document_type` | string | Yes | Filter field |
| `tags` | string[] | Yes | Filter field (array) |
| `created_date` | string | Yes | Filter field (date) |
| `chunk_index` | integer | Yes | Ordering within doc |
| `chunk_type` | string | Yes | Filter by element type |
| `page_number` | integer | Yes | Filter by page |
| `text` | string | No | Full chunk text |
| `indexed_at` | string | Yes | For freshness |

---

### E.2 Index Document Chunks

Upsert chunks for a document.

**Operation**: Qdrant `upsert`

```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

async def index_document_chunks(
    client: QdrantClient,
    tenant_id: str,
    chunks: list[DocumentChunk]
) -> None:
    collection = f"tenant_{tenant_id}"

    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector=chunk.embedding,
            payload=chunk.to_payload()
        )
        for chunk in chunks
    ]

    await client.upsert(
        collection_name=collection,
        points=points,
        wait=True
    )
```

---

### E.3 Delete Document Chunks

Remove all chunks for a document.

**Operation**: Qdrant `delete` with filter

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

async def delete_document_chunks(
    client: QdrantClient,
    tenant_id: str,
    paperless_doc_id: int
) -> None:
    collection = f"tenant_{tenant_id}"

    await client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="paperless_doc_id",
                    match=MatchValue(value=paperless_doc_id)
                )
            ]
        ),
        wait=True
    )
```

---

### E.4 Search with Filters

Semantic search with metadata filtering.

**Operation**: Qdrant `search`

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

async def search_documents(
    client: QdrantClient,
    tenant_id: str,
    query_vector: list[float],
    filters: SearchFilters,
    top_k: int = 10
) -> list[SearchResult]:
    collection = f"tenant_{tenant_id}"

    filter_conditions = []

    if filters.document_types:
        filter_conditions.append(
            FieldCondition(
                key="document_type",
                match=MatchAny(any=filters.document_types)
            )
        )

    if filters.correspondents:
        filter_conditions.append(
            FieldCondition(
                key="correspondent",
                match=MatchAny(any=filters.correspondents)
            )
        )

    if filters.tags:
        for tag in filters.tags:
            filter_conditions.append(
                FieldCondition(
                    key="tags",
                    match=MatchValue(value=tag)
                )
            )

    if filters.date_range:
        filter_conditions.append(
            FieldCondition(
                key="created_date",
                range=Range(
                    gte=filters.date_range.start,
                    lte=filters.date_range.end
                )
            )
        )

    results = await client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=Filter(must=filter_conditions) if filter_conditions else None,
        limit=top_k,
        with_payload=True
    )

    return [SearchResult.from_qdrant(r) for r in results]
```

---

## Data Models (Pydantic)

### Shared Models

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID


class ChunkType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    FIGURE = "figure"
    LIST_ITEM = "list_item"
    CODE = "code"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Correspondent(BaseModel):
    id: int
    name: str


class DocumentType(BaseModel):
    id: int
    name: str


class Tag(BaseModel):
    id: int
    name: str


class DocumentMetadata(BaseModel):
    """Document metadata from Paperless-ngx."""
    id: int
    title: str
    correspondent: Correspondent | None = None
    document_type: DocumentType | None = None
    tags: list[Tag] = Field(default_factory=list)
    created: str  # ISO date
    added: datetime
    modified: datetime
    archive_serial_number: int | None = None
    original_filename: str
    mime_type: str
    page_count: int | None = None


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    chunk_id: str
    chunk_index: int
    chunk_type: ChunkType
    page_number: int
    section_title: str | None = None
    section_path: list[str] = Field(default_factory=list)
    hierarchical_depth: int = 0
    text_length: int


class DocumentChunk(BaseModel):
    """A chunk of a document with its embedding."""
    chunk_id: str
    tenant_id: str
    paperless_doc_id: int
    document_metadata: DocumentMetadata
    chunk_metadata: ChunkMetadata
    text: str
    embedding: list[float]
    embedding_model: str
    indexed_at: datetime

    def to_payload(self) -> dict:
        """Convert to Qdrant payload format."""
        return {
            "tenant_id": self.tenant_id,
            "paperless_doc_id": self.paperless_doc_id,
            "paperless_url": f"https://docs.example.com/api/documents/{self.paperless_doc_id}/",
            "document_title": self.document_metadata.title,
            "correspondent": self.document_metadata.correspondent.name if self.document_metadata.correspondent else None,
            "correspondent_id": self.document_metadata.correspondent.id if self.document_metadata.correspondent else None,
            "document_type": self.document_metadata.document_type.name if self.document_metadata.document_type else None,
            "document_type_id": self.document_metadata.document_type.id if self.document_metadata.document_type else None,
            "tags": [t.name for t in self.document_metadata.tags],
            "tag_ids": [t.id for t in self.document_metadata.tags],
            "created_date": self.document_metadata.created,
            "added_date": self.document_metadata.added.date().isoformat(),
            "chunk_index": self.chunk_metadata.chunk_index,
            "chunk_type": self.chunk_metadata.chunk_type.value,
            "page_number": self.chunk_metadata.page_number,
            "section_title": self.chunk_metadata.section_title,
            "section_path": self.chunk_metadata.section_path,
            "hierarchical_depth": self.chunk_metadata.hierarchical_depth,
            "text": self.text,
            "text_length": len(self.text),
            "embedding_model": self.embedding_model,
            "indexed_at": self.indexed_at.isoformat(),
        }


class SearchFilters(BaseModel):
    """Filters for semantic search."""
    document_types: list[str] = Field(default_factory=list)
    correspondents: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    date_range: DateRange | None = None


class DateRange(BaseModel):
    field: str = "created"  # "created" or "added"
    start: str  # ISO date
    end: str  # ISO date


class SearchResult(BaseModel):
    """A single search result."""
    score: float
    rank: int
    document: DocumentMetadata
    chunk: ChunkMetadata
    content: str | None = None
```

---

## Versioning

All contracts are versioned via URL path prefix:

- Current: `/api/v1/...`
- Future: `/api/v2/...`

**Breaking Changes** require major version bump:
- Removing required fields
- Changing field types
- Removing endpoints
- Changing authentication method

**Non-Breaking Changes** can be added to current version:
- Adding optional fields
- Adding new endpoints
- Adding new filter options

---

## Rate Limiting

| Endpoint Type | Rate Limit | Window |
|--------------|------------|--------|
| Webhooks (A.x) | 100 req/min | Per tenant |
| Search (C.2) | 60 req/min | Per user |
| Query (C.3) | 20 req/min | Per user |
| Admin (C.7) | 30 req/min | Per user |
| Re-index (C.6) | 10 req/min | Per tenant |

**Rate Limit Headers**:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704880260
```

---

## References

- [ADR-002: Paperless-ngx Integration](./adr/adr-002-paperless-ngx-integration.md)
- [Paperless-ngx API Documentation](https://docs.paperless-ngx.com/api/)
- [Qdrant API Documentation](https://qdrant.tech/documentation/concepts/points/)
- [OpenAPI Specification](https://spec.openapis.org/oas/v3.1.0)
