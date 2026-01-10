---
title: "ADR-002: Paperless-ngx Integration with Docling OCR Pipeline"
schema_type: adr
status: proposed
owner: core-maintainer
purpose: "Document the decision to integrate with Paperless-ngx as the user-facing document management system while leveraging Docling for advanced OCR processing."
tags:
  - adr
  - architecture
  - integration
  - paperless
  - docling
component: Integration
source: "Architecture decision"
---

# ADR-002: Paperless-ngx Integration with Docling OCR Pipeline

## Status

**Proposed** | Date: 2026-01-10

## Context

The RAG Processor project was initially designed as a standalone ingestion pipeline with a custom React WebUI. However, two significant open-source projects have emerged that could accelerate development and provide a better user experience:

1. **Paperless-ngx**: A mature, feature-rich document management system with an excellent UI, OCR capabilities, and extensive community support.

2. **Paperless-AI**: An extension that adds AI-powered auto-tagging, classification, and RAG-based semantic search to Paperless-ngx.

3. **Docling (IBM)**: An advanced document processing library with superior OCR, layout-aware extraction, and hierarchical chunking strategies optimized for RAG.

### Problem Statement

Building a custom WebUI duplicates effort when Paperless-ngx already provides:
- Authenticated document upload interface
- Document preview and thumbnail generation
- Tag, correspondent, and document type management
- Comprehensive REST API
- Active community and ongoing development

However, Paperless-ngx has limitations:
- Uses **Whoosh** for full-text search (lexical, not semantic)
- OCR engine (OCRmyPDF + Tesseract) lacks layout-aware extraction
- No native support for hierarchical document chunking
- Limited multi-modal document processing (no audio/video)

### Research Findings

#### Paperless-ngx Architecture

| Component | Technology | Details |
|-----------|-----------|---------|
| **Backend** | Django (Python) | Document management application |
| **Task Queue** | Celery + Redis | Background document processing |
| **OCR Engine** | OCRmyPDF + Tesseract | Configurable multi-language support |
| **Search Index** | Whoosh | Full-text search (NOT vector database) |
| **Database** | SQLite/PostgreSQL/MariaDB | Django ORM |
| **API** | Django REST Framework | RESTful endpoints with versioning |

**Key Integration Points**:
- `POST /api/documents/post_document/` - Upload documents
- `GET /api/documents/{id}/` - Retrieve document metadata
- `PATCH /api/documents/{id}/` - Update metadata
- Pre/post-consume scripts for custom processing hooks
- Workflow triggers for automation

#### Paperless-AI Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Vector Store** | ChromaDB | Semantic search embeddings |
| **Keyword Search** | BM25 (rank-bm25) | Lexical search component |
| **Embeddings** | sentence-transformers | `paraphrase-multilingual-MiniLM-L12-v2` |
| **Reranking** | Cross-Encoder | `ms-marco-MiniLM-L-6-v2` |
| **LLM Integration** | Ollama/OpenAI/Azure | Document analysis and tagging |

**Hybrid Search Strategy**:
- 70% semantic search (ChromaDB vector similarity)
- 30% BM25 keyword search
- Cross-encoder reranking for final results

#### Docling Capabilities

| Feature | Capability | Benefit |
|---------|-----------|---------|
| **Output Formats** | Markdown, JSON, HTML, DocTags | Flexible downstream integration |
| **Structure Preservation** | Hierarchical document tree | Sections, tables, figures with relationships |
| **OCR Engines** | Tesseract, EasyOCR, RapidOCR, macOS | Multi-engine fallback |
| **Layout Analysis** | DocLayNet vision models | 30x faster than traditional OCR |
| **Chunking** | HierarchicalChunker, HybridChunker | RAG-optimized with metadata preservation |
| **Framework Support** | LangChain, LlamaIndex, Haystack | Native integrations |

## Decision

**Adopt a hybrid architecture where:**

1. **Paperless-ngx** serves as the primary user-facing document management system
2. **RAG Processor** provides advanced Docling-based OCR and document processing
3. **Vector storage** is managed by RAG Processor (not Paperless-AI) for tighter control
4. Documents flow bidirectionally between systems

### Rejected Alternatives

#### Alternative 1: Fork Paperless-AI

**Rejected because:**
- Paperless-AI's RAG service is tightly coupled to its Node.js architecture
- Would require maintaining a fork with significant divergence
- ChromaDB may not meet enterprise scalability requirements

#### Alternative 2: Replace Paperless OCR with Docling

**Rejected because:**
- Requires modifying Paperless-ngx internals
- Would break on upgrades
- Paperless OCR is sufficient for basic text extraction

#### Alternative 3: Standalone RAG Processor (Original Plan)

**Rejected because:**
- Duplicates document management UI
- Requires building user management, preview, thumbnails from scratch
- Longer time to production

## Multi-Tenancy Architecture

### Constraint: Paperless-ngx Has No Native Multi-Tenancy

Research confirms that **Paperless-ngx was not designed for multi-tenancy**. Key limitations:

| Limitation | Impact |
|------------|--------|
| **Shared Search Index** | All users share Whoosh index - document existence leaks across tenants |
| **Global Tags/Correspondents** | Metadata is not scoped per tenant |
| **File Duplicate Detection** | Same file uploaded by different clients triggers duplicate error |
| **API Token Scope** | Tokens inherit all permissions of owner - no granular scoping |
| **Consumption Templates** | Cannot filter by uploader - all uploads get same automation |

### Decision: Separate Paperless Instances Per Client

For client isolation, we adopt **one Paperless-ngx instance per client** with RAG Processor as the central orchestration layer.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAG PROCESSOR GATEWAY                           │
│                      (Central Tenant Router)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    Tenant Router                                  │  │
│   │  • Authentication (OIDC/OAuth)                                   │  │
│   │  • Tenant identification from JWT claims                         │  │
│   │  • API request routing                                           │  │
│   │  • Query federation across tenants (admin only)                  │  │
│   └───────────────────────────────┬──────────────────────────────────┘  │
│                                   │                                      │
│           ┌───────────────────────┼───────────────────────┐             │
│           │                       │                       │             │
│           ▼                       ▼                       ▼             │
│   ┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐    │
│   │ Tenant A      │     │ Tenant B        │     │ Tenant C        │    │
│   │ Config        │     │ Config          │     │ Config          │    │
│   │               │     │                 │     │                 │    │
│   │ • API URL     │     │ • API URL       │     │ • API URL       │    │
│   │ • API Token   │     │ • API Token     │     │ • API Token     │    │
│   │ • Vector NS   │     │ • Vector NS     │     │ • Vector NS     │    │
│   └───────┬───────┘     └───────┬─────────┘     └───────┬─────────┘    │
│           │                     │                       │               │
└───────────┼─────────────────────┼───────────────────────┼───────────────┘
            │                     │                       │
            ▼                     ▼                       ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│  Paperless-ngx    │  │  Paperless-ngx    │  │  Paperless-ngx    │
│  (Tenant A)       │  │  (Tenant B)       │  │  (Tenant C)       │
│                   │  │                   │  │                   │
│  • Separate DB    │  │  • Separate DB    │  │  • Separate DB    │
│  • Separate files │  │  • Separate files │  │  • Separate files │
│  • Own users      │  │  • Own users      │  │  • Own users      │
└─────────┬─────────┘  └─────────┬─────────┘  └─────────┬─────────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         VECTOR DATABASE (Qdrant)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│   │ Collection:     │  │ Collection:     │  │ Collection:     │        │
│   │ tenant_a        │  │ tenant_b        │  │ tenant_c        │        │
│   │                 │  │                 │  │                 │        │
│   │ • Embeddings    │  │ • Embeddings    │  │ • Embeddings    │        │
│   │ • Metadata      │  │ • Metadata      │  │ • Metadata      │        │
│   │ • Isolated      │  │ • Isolated      │  │ • Isolated      │        │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Tenant Configuration Model

```python
from pydantic import BaseModel, SecretStr
from enum import Enum

class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PROVISIONING = "provisioning"

class TenantConfig(BaseModel):
    """Configuration for a single tenant's Paperless-ngx instance."""
    tenant_id: str                          # Unique identifier (e.g., "acme-corp")
    tenant_name: str                        # Display name
    status: TenantStatus

    # Paperless-ngx connection
    paperless_url: str                      # e.g., "https://docs.acme.example.com"
    paperless_api_token: SecretStr          # API token for this instance
    paperless_webhook_secret: SecretStr     # Webhook signature verification

    # Vector database isolation
    vector_collection: str                  # e.g., "tenant_acme_corp"

    # Resource limits
    max_documents: int | None = None        # Document quota
    max_storage_gb: float | None = None     # Storage quota

    # Feature flags
    docling_enabled: bool = True            # Use advanced OCR
    audio_transcription: bool = False       # Whisper integration


class TenantRegistry:
    """Registry of all tenant configurations."""

    def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        """Look up tenant by ID."""
        ...

    def get_tenant_by_domain(self, domain: str) -> TenantConfig | None:
        """Look up tenant by Paperless instance domain."""
        ...

    def get_tenant_from_jwt(self, jwt_claims: dict) -> TenantConfig | None:
        """Extract tenant from JWT claims (e.g., organization claim)."""
        ...
```

### Authentication Strategy

> **Decision**: Authentication is handled externally via **Authentik**. RAG Processor only validates JWTs.

**Architecture**:

```
User → Authentik (OIDC) → JWT with tenant claim → RAG Processor (validates JWT)
                                                          │
                                                          ▼
                                               Route to tenant's Paperless
                                               (using stored service token)
```

**RAG Processor Responsibilities**:
- Validate JWT signature against Authentik JWKS endpoint
- Extract tenant ID from JWT claims
- Look up tenant configuration (Paperless URL, API token)
- Route requests to correct Paperless instance

**Out of Scope** (handled externally):
- User provisioning
- Tenant provisioning
- Authentik configuration
- SSO setup for Paperless instances

### Deployment Pattern: Docker Compose Per Tenant

Each tenant gets an isolated Docker Compose stack:

```yaml
# docker-compose.tenant-a.yml
services:
  paperless:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    environment:
      PAPERLESS_URL: https://docs.tenant-a.example.com
      PAPERLESS_DBHOST: postgres-tenant-a
      PAPERLESS_REDIS: redis://redis-tenant-a:6379
    networks:
      - tenant-a-internal
      - rag-processor-shared

  postgres-tenant-a:
    image: postgres:15-alpine
    volumes:
      - tenant-a-db:/var/lib/postgresql/data
    networks:
      - tenant-a-internal

  redis-tenant-a:
    image: redis:7-alpine
    networks:
      - tenant-a-internal

networks:
  tenant-a-internal:
    internal: true
  rag-processor-shared:
    external: true

volumes:
  tenant-a-db:
  tenant-a-data:
  tenant-a-media:
```

### Resource Considerations

| Component | Per-Tenant Overhead | Notes |
|-----------|---------------------|-------|
| Paperless-ngx | ~500MB RAM | Django + Celery workers |
| PostgreSQL | ~100MB RAM | Per-tenant database |
| Redis | ~50MB RAM | Can potentially share with prefix |
| Vector Collection | Variable | Based on document count |

**Scaling Recommendation**: For >10 tenants, consider Kubernetes with per-tenant namespaces.

### Cross-Tenant Queries (Admin Only)

For administrative dashboards or global search (with proper authorization):

```python
async def federated_search(
    query: str,
    tenant_ids: list[str],  # Must be authorized
    top_k: int = 10
) -> list[SearchResult]:
    """Search across multiple tenant vector stores."""
    results = []
    for tenant_id in tenant_ids:
        tenant = registry.get_tenant(tenant_id)
        tenant_results = await vector_db.search(
            collection=tenant.vector_collection,
            query=query,
            limit=top_k
        )
        results.extend(tenant_results)

    # Re-rank combined results
    return rerank(results, query)[:top_k]
```

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    Paperless-ngx WebUI                            │  │
│   │  • Document Upload (drag-drop, consume folder, email)            │  │
│   │  • Document Preview & Thumbnails                                  │  │
│   │  • Tag/Correspondent/DocType Management                           │  │
│   │  • Full-text Search (Whoosh)                                      │  │
│   │  • User Authentication & Permissions                              │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ Webhook / API
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      RAG PROCESSOR GATEWAY                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────────────────┐   │
│   │ Webhook       │  │ Periodic      │  │ Direct Upload             │   │
│   │ Listener      │  │ Scanner       │  │ API                       │   │
│   └───────┬───────┘  └───────┬───────┘  └─────────────┬─────────────┘   │
│           │                  │                        │                  │
│           └──────────────────┼────────────────────────┘                  │
│                              │                                           │
│                              ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    Document Classifier                            │  │
│   │  • MIME detection, PDF analysis (scanned vs born-digital)        │  │
│   │  • Audio/Video detection                                          │  │
│   │  • Multi-modal routing                                            │  │
│   └───────────────────────────────┬──────────────────────────────────┘  │
│                                   │                                      │
│           ┌───────────────────────┼───────────────────────┐             │
│           │                       │                       │             │
│           ▼                       ▼                       ▼             │
│   ┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐    │
│   │ Docling       │     │ Audio/Video     │     │ Pass-through    │    │
│   │ Pipeline      │     │ Pipeline        │     │ (born-digital)  │    │
│   │               │     │                 │     │                 │    │
│   │ • Layout OCR  │     │ • Whisper       │     │ • Text extract  │    │
│   │ • Table ext.  │     │ • Transcription │     │ • Metadata      │    │
│   │ • Hierarchical│     │ • Diarization   │     │                 │    │
│   │   chunking    │     │                 │     │                 │    │
│   └───────┬───────┘     └───────┬─────────┘     └───────┬─────────┘    │
│           │                     │                       │               │
│           └─────────────────────┼───────────────────────┘               │
│                                 │                                        │
│                                 ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    Embedding Generator                            │  │
│   │  • sentence-transformers / OpenAI embeddings                      │  │
│   │  • Metadata preservation from Docling chunks                      │  │
│   │  • Batch processing with rate limiting                            │  │
│   └───────────────────────────────┬──────────────────────────────────┘  │
│                                   │                                      │
└───────────────────────────────────┼──────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌─────────────────────────────┐    ┌─────────────────────────────────────┐
│     VECTOR DATABASE         │    │     PAPERLESS-NGX (Writeback)       │
├─────────────────────────────┤    ├─────────────────────────────────────┤
│                             │    │                                      │
│  • Qdrant / Milvus /        │    │  PATCH /api/documents/{id}/          │
│    PGVector / Weaviate      │    │  • Custom fields (chunk_count,       │
│  • Semantic search          │    │    embedding_model, processed_at)    │
│  • Metadata filtering       │    │  • Tags (rag-indexed, docling-ocr)   │
│  • Hybrid search (BM25+vec) │    │  • Enhanced content (Docling MD)     │
│                             │    │                                      │
└─────────────────────────────┘    └─────────────────────────────────────┘
```

### Data Flow

#### Flow 1: New Document Ingestion (Webhook)

```
User uploads to Paperless-ngx
         │
         ▼
Paperless consumption pipeline (OCRmyPDF)
         │
         ▼
Post-consume webhook → RAG Processor
         │
         ▼
Fetch document content + metadata from Paperless API
         │
         ▼
Docling processing (if scanned/image-heavy PDF)
         │
         ├─── Hierarchical chunks with metadata
         │
         ▼
Generate embeddings
         │
         ├─── Store in vector database
         │
         ▼
Update Paperless metadata (custom fields, tags)
```

#### Flow 2: Advanced OCR Request

```
User requests advanced OCR for document
         │
         ▼
RAG Processor downloads original file from Paperless
         │
         ▼
Docling full processing:
  • Layout analysis (DocLayNet)
  • Table extraction
  • Figure detection
  • Hierarchical chunking
         │
         ▼
Generate Docling JSON/Markdown output
         │
         ▼
Update Paperless with:
  • Enhanced content (Docling markdown in content field)
  • Custom fields (structure metadata)
  • Tags (docling-processed)
         │
         ▼
Embed all chunks into vector store
```

#### Flow 3: RAG Query

```
User submits query via RAG Processor API (or chat UI)
         │
         ▼
Hybrid search:
  • Vector similarity (embeddings)
  • BM25 keyword matching
  • Cross-encoder reranking
         │
         ▼
Retrieve top-k chunks with metadata
         │
         ├─── Include Paperless document IDs
         │
         ▼
Fetch full document context from Paperless if needed
         │
         ▼
LLM generation with retrieved context
         │
         ▼
Response with source citations (Paperless URLs)
```

### API Integration Specification

#### Paperless-ngx → RAG Processor

**Webhook Endpoint** (RAG Processor receives):

```http
POST /api/v1/webhook/paperless
Content-Type: application/json
Authorization: Bearer <rag_processor_api_key>

{
  "document_id": 123,
  "document_url": "http://paperless:8000/api/documents/123/",
  "event": "document_consumed",
  "title": "Invoice 2024-001",
  "correspondent": "Acme Corp",
  "document_type": "Invoice",
  "tags": ["business", "2024"],
  "created": "2024-01-15T10:30:00Z"
}
```

**Response**:

```json
{
  "status": "queued",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "estimated_completion": "2024-01-15T10:32:00Z"
}
```

#### RAG Processor → Paperless-ngx

**Fetch Document**:

```http
GET /api/documents/123/download/
Authorization: Token <paperless_api_token>
```

**Update Metadata**:

```http
PATCH /api/documents/123/
Authorization: Token <paperless_api_token>
Content-Type: application/json

{
  "custom_fields": [
    {"field": 1, "value": "2024-01-15T10:32:00Z"},  // rag_processed_at
    {"field": 2, "value": 42},                       // chunk_count
    {"field": 3, "value": "text-embedding-3-small"}, // embedding_model
    {"field": 4, "value": "550e8400-..."}           // rag_job_id
  ],
  "tags": [5, 8, 12]  // Add rag-indexed, docling-processed tags
}
```

### Paperless-ngx Custom Fields Setup

Create these custom fields in Paperless-ngx for RAG integration:

| Field Name | Type | Purpose |
|------------|------|---------|
| `rag_processed_at` | DateTime | When RAG indexing completed |
| `chunk_count` | Integer | Number of chunks in vector store |
| `embedding_model` | String | Model used for embeddings |
| `rag_job_id` | String | RAG Processor job ID for tracing |
| `docling_processed` | Boolean | Whether Docling OCR was applied |
| `ocr_quality_score` | Float | Estimated OCR quality (0-1) |

### Vector Database Schema

```python
# Chunk document schema (Qdrant example)
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],  # embedding vector
  "payload": {
    # Paperless metadata
    "paperless_doc_id": 123,
    "paperless_url": "http://paperless:8000/api/documents/123/",
    "title": "Invoice 2024-001",
    "correspondent": "Acme Corp",
    "document_type": "Invoice",
    "tags": ["business", "2024"],
    "created": "2024-01-15T10:30:00Z",

    # Docling chunk metadata
    "chunk_index": 5,
    "chunk_type": "paragraph",  # paragraph, table, figure, heading
    "page_number": 2,
    "section_title": "Payment Terms",
    "parent_section": "Contract Details",
    "hierarchical_path": ["Contract Details", "Payment Terms"],

    # Content
    "text": "Payment is due within 30 days...",
    "text_length": 156,

    # Processing metadata
    "processed_at": "2024-01-15T10:32:00Z",
    "embedding_model": "text-embedding-3-small",
    "docling_version": "2.0.0"
  }
}
```

## Consequences

### Positive

1. **Faster Time to Production**: Leverage Paperless-ngx's mature UI instead of building from scratch
2. **Better User Experience**: Paperless-ngx has years of UX refinement for document management
3. **Community Support**: Active community for Paperless-ngx troubleshooting
4. **Superior OCR**: Docling provides layout-aware extraction that Tesseract cannot match
5. **Flexible Vector Store**: Choose vector database based on requirements (Qdrant, Milvus, PGVector)
6. **Clean Separation**: Document management (Paperless) vs RAG intelligence (RAG Processor)

### Negative

1. **External Dependency**: Reliant on Paperless-ngx project continuing development
2. **Integration Complexity**: Two systems to deploy and maintain
3. **Data Synchronization**: Need to keep Paperless and vector store in sync
4. **Duplicate Storage**: Documents stored in both Paperless and potentially cached in RAG Processor

### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Paperless-ngx API changes | Low | Medium | Pin versions, integration tests |
| Webhook reliability | Medium | Medium | Periodic scanner as backup |
| Data sync drift | Medium | High | Reconciliation job, checksums |
| Docling performance at scale | Low | Medium | Batch processing, worker scaling |
| Multi-tenant resource overhead | Medium | High | Kubernetes scaling, shared components where safe |
| Cross-tenant data leakage | Low | Critical | Strict tenant isolation, separate collections, audit logging |
| Tenant provisioning complexity | Medium | Medium | Terraform/Pulumi automation, tenant templates |
| Authentication token management | Medium | High | Secret rotation, HashiCorp Vault integration |

## Implementation Plan

> **Scope Note**: Authentication (Authentik) and tenant provisioning are handled externally.

### Phase 1: Foundation (Single Tenant)

- [ ] Implement Paperless API client in RAG Processor
- [ ] Create webhook endpoint for document consumption events
- [ ] Implement webhook signature verification
- [ ] Implement periodic scanner as webhook backup
- [ ] JWT validation against Authentik JWKS
- [ ] Tenant configuration loading (environment/config file)

### Phase 2: Docling Pipeline

- [ ] Integrate Docling for advanced OCR processing
- [ ] Implement document classification (scanned vs born-digital)
- [ ] Build hierarchical chunking with metadata preservation
- [ ] Build embedding generation pipeline
- [ ] Configure Qdrant vector database

### Phase 3: RAG Service

- [ ] Implement semantic search with filters
- [ ] Add BM25 keyword search component
- [ ] Implement cross-encoder reranking
- [ ] Build RAG query API with LLM generation
- [ ] Create search/query response formatting

### Phase 4: Multi-Tenancy Support

- [ ] Implement tenant registry (config-based)
- [ ] Add tenant routing middleware (from JWT claims)
- [ ] Create per-tenant vector collections in Qdrant
- [ ] Per-tenant Paperless API token management
- [ ] Tenant isolation validation

### Phase 5: Metadata Sync & Operations

- [ ] Paperless custom fields for RAG metadata
- [ ] Document update sync (re-indexing on changes)
- [ ] Document deletion sync (remove from vector store)
- [ ] Per-tenant reconciliation jobs
- [ ] Monitoring and health checks

## References

- [API Contracts](../api-contracts.md) - Inter-service communication contracts
- [Paperless Integration Analysis](../paperless-integration-analysis.md) - Technical deep dive
- [Paperless-ngx GitHub](https://github.com/paperless-ngx/paperless-ngx)
- [Paperless-ngx Documentation](https://docs.paperless-ngx.com/)
- [Paperless-AI GitHub](https://github.com/clusterzx/paperless-ai)
- [Docling Documentation](https://docling-project.github.io/docling/)
- [Docling GitHub](https://github.com/docling-project/docling)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Authentik Documentation](https://goauthentik.io/docs/)
- [ADR-001: React-FastAPI Architecture](./adr-001-react-fastapi-architecture.md)
