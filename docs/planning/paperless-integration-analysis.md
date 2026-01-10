---
title: "Paperless-ngx Integration Analysis"
schema_type: analysis
status: draft
owner: core-maintainer
purpose: "Deep dive technical analysis of Paperless-ngx, Paperless-AI, and Docling integration for RAG pipeline."
tags:
  - analysis
  - integration
  - paperless
  - docling
  - rag
component: Research
source: "Technical research"
---

# Paperless-ngx Integration Analysis

> **Status**: Draft | **Date**: 2026-01-10

## Executive Summary

This document provides a comprehensive technical analysis of integrating Paperless-ngx as the user-facing document management system with our RAG Processor project using IBM's Docling for advanced OCR and document processing.

**Key Findings:**

1. **Paperless-ngx** uses Whoosh (lexical search), NOT vector embeddings - semantic search must be added externally
2. **Paperless-AI** demonstrates a viable integration pattern with ChromaDB + BM25 hybrid search
3. **Docling** provides superior OCR with hierarchical chunking that preserves document structure
4. The optimal architecture uses Paperless-ngx for document management and a separate RAG Processor for vector indexing

---

## 1. Paperless-ngx Deep Dive

### 1.1 Document Ingestion Pipeline

Paperless-ngx supports five ingestion methods:

| Method | Description | Best For |
|--------|-------------|----------|
| **Consumption Directory** | Monitored folder (inotify/polling) | Automated batch ingestion |
| **Web UI Upload** | Drag-drop interface | Interactive single uploads |
| **REST API** | `POST /api/documents/post_document/` | Programmatic ingestion |
| **Email Integration** | Automatic email attachment fetching | Inbox automation |
| **Scanner Integration** | Direct scanner-to-Paperless | Physical document digitization |

#### Consumption Pipeline Stages

```
File arrives in consume folder
          │
          ▼
┌─────────────────────────────────────┐
│  Stage 1: Preflight Checks          │
│  • File existence validation        │
│  • MD5 checksum duplicate check     │
│  • Directory creation               │
│  • ASN uniqueness validation        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Stage 2: Workflow Triggers         │
│  • Match consumption triggers       │
│  • Apply metadata overrides         │
│  • Execute pre-consume scripts      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Stage 3: Main Consumption          │
│  • MIME type detection              │
│  • OCR processing (OCRmyPDF)        │
│  • Content extraction               │
│  • Date parsing                     │
│  • Thumbnail generation             │
│  • Database commit                  │
│  • File storage                     │
│  • Post-consume script execution    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Stage 4: Classifier                │
│  • Auto-suggest correspondent       │
│  • Auto-suggest document type       │
│  • Auto-suggest tags                │
└─────────────────────────────────────┘
```

### 1.2 OCR Configuration (OCRmyPDF + Tesseract)

Key configuration options relevant to our integration:

```bash
# Language configuration (combine with +)
PAPERLESS_OCR_LANGUAGE=eng+deu+fra

# OCR mode
PAPERLESS_OCR_MODE=skip  # skip | redo | force
# - skip: Only OCR if no text layer detected
# - redo: Replace existing text
# - force: Always rasterize and OCR

# Output format
PAPERLESS_OCR_OUTPUT_TYPE=pdfa-2  # pdf | pdfa | pdfa-1 | pdfa-2 | pdfa-3

# Performance tuning
PAPERLESS_TASK_WORKERS=2          # Parallel Celery workers
PAPERLESS_THREADS_PER_WORKER=1    # Threads per worker
PAPERLESS_WORKER_TIMEOUT=1800     # 30 min timeout

# Image processing
PAPERLESS_OCR_DESKEW=true         # Auto-correct skew
PAPERLESS_OCR_ROTATE_PAGES=true   # Auto-rotate
PAPERLESS_OCR_CLEAN=clean         # Preprocessing
```

**Limitation**: Tesseract is character-based OCR without layout understanding. It cannot:
- Preserve table structure
- Identify figures and their relationships to text
- Maintain hierarchical document structure
- Extract structured data from forms

### 1.3 Search Capabilities (Whoosh)

Paperless uses **Whoosh** for full-text search, which is keyword-based (BM25-like), NOT vector/semantic.

**Index Fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `title` | Text | Document title |
| `content` | Text | Full extracted text |
| `correspondent` | Text | Sender/recipient |
| `tag` | Text | All tags |
| `type` | Text | Document type |
| `notes` | Text | User annotations |
| `custom_fields` | Text | Custom field values |
| `created` | DateTime | Document date |
| `modified` | DateTime | Last modified |
| `added` | DateTime | Ingestion date |
| `asn` | Numeric | Archive serial number |

**Search Syntax**:

```
# Basic search
GET /api/documents/?query=invoice

# Field-specific
GET /api/documents/?query=correspondent:acme

# Boolean operators
GET /api/documents/?query=invoice AND (acme OR globex)

# Range queries
GET /api/documents/?query=created:[2024-01-01 TO 2024-12-31]

# Similar documents (Whoosh's MLT)
GET /api/documents/?more_like_id=123
```

**Key Limitation**: No semantic understanding. "car insurance" won't find "vehicle coverage" unless both terms appear.

### 1.4 REST API Reference

#### Document Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/documents/` | GET | List documents (paginated) |
| `/api/documents/{id}/` | GET | Get document details |
| `/api/documents/{id}/` | PATCH | Update metadata |
| `/api/documents/{id}/` | DELETE | Delete document |
| `/api/documents/{id}/download/` | GET | Download original |
| `/api/documents/{id}/download_archive/` | GET | Download archive version |
| `/api/documents/{id}/preview/` | GET | Get preview image |
| `/api/documents/{id}/thumbnail/` | GET | Get thumbnail |
| `/api/documents/{id}/metadata/` | GET | Get extended metadata |
| `/api/documents/{id}/suggestions/` | GET | Get auto-classification suggestions |
| `/api/documents/{id}/notes/` | GET/POST | Document notes |
| `/api/documents/post_document/` | POST | Upload new document |
| `/api/documents/bulk_edit/` | POST | Batch operations |

#### Upload Example

```python
import httpx

PAPERLESS_URL = "http://paperless:8000"
PAPERLESS_TOKEN = "your_api_token"

async def upload_document(file_path: Path, metadata: dict | None = None):
    """Upload a document to Paperless-ngx."""
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f)}
            data = {}
            if metadata:
                if "title" in metadata:
                    data["title"] = metadata["title"]
                if "correspondent" in metadata:
                    data["correspondent"] = metadata["correspondent"]
                if "document_type" in metadata:
                    data["document_type"] = metadata["document_type"]
                if "tags" in metadata:
                    data["tags"] = ",".join(str(t) for t in metadata["tags"])

            response = await client.post(
                f"{PAPERLESS_URL}/api/documents/post_document/",
                headers={"Authorization": f"Token {PAPERLESS_TOKEN}"},
                files=files,
                data=data,
            )
            response.raise_for_status()
            return response.json()  # Returns task UUID
```

#### Webhook Configuration

Paperless-ngx supports webhooks for document lifecycle events:

1. Navigate to **Settings** → **Workflows** → **Webhooks**
2. Create webhook:
   - **Trigger**: Document consumed
   - **URL**: `http://rag-processor:8000/api/v1/webhook/paperless`
   - **Headers**: `Authorization: Bearer <token>`

Webhook payload:

```json
{
  "document": {
    "id": 123,
    "title": "Invoice 2024-001",
    "correspondent": 5,
    "document_type": 2,
    "tags": [1, 3, 7],
    "created": "2024-01-15",
    "added": "2024-01-15T10:30:00Z",
    "content": "Full text content..."
  },
  "trigger": "document_consumed",
  "timestamp": "2024-01-15T10:30:15Z"
}
```

### 1.5 Custom Fields

Custom fields allow extending document metadata for RAG integration:

```python
# Create custom field via API
async def create_custom_field(name: str, data_type: str):
    """
    data_type options:
    - string, url, date, boolean
    - integer, float, monetary
    - documentlink
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAPERLESS_URL}/api/custom_fields/",
            headers={"Authorization": f"Token {PAPERLESS_TOKEN}"},
            json={"name": name, "data_type": data_type},
        )
        return response.json()

# Recommended fields for RAG integration
RAG_CUSTOM_FIELDS = [
    {"name": "rag_processed_at", "data_type": "date"},
    {"name": "chunk_count", "data_type": "integer"},
    {"name": "embedding_model", "data_type": "string"},
    {"name": "rag_job_id", "data_type": "string"},
    {"name": "docling_processed", "data_type": "boolean"},
    {"name": "ocr_quality_score", "data_type": "float"},
]
```

---

## 2. Paperless-AI Analysis

### 2.1 Architecture Overview

Paperless-AI consists of two services:

```
┌─────────────────────────────────────────────────────────────┐
│          Node.js Service (Port 3000)                        │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Express.js  │  │ Paperless   │  │ AI Service Factory  │ │
│  │ Web Server  │  │ API Client  │  │ (Ollama/OpenAI/etc) │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ SQLite Database                                         ││
│  │ • processed_documents • history_documents               ││
│  │ • original_documents  • openai_metrics                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────┐
│          Python RAG Service (Port 8000)                     │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ FastAPI     │  │ ChromaDB    │  │ BM25 Index          │ │
│  │ Server      │  │ Vector Store│  │ (rank-bm25)         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ sentence-transformers: paraphrase-multilingual-MiniLM   ││
│  │ Cross-encoder: ms-marco-MiniLM-L-6-v2                   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Hybrid Search Implementation

Paperless-AI's search combines:

1. **Semantic Search (70%)**: ChromaDB vector similarity
2. **Keyword Search (30%)**: BM25 on tokenized corpus
3. **Reranking**: Cross-encoder for final ordering

```python
# Simplified hybrid search algorithm (from Paperless-AI)
def hybrid_search(query: str, k: int = 10):
    # 1. Semantic search
    query_embedding = embed(query)
    semantic_results = chromadb.query(
        query_embeddings=[query_embedding],
        n_results=k * 2  # Over-fetch for fusion
    )

    # 2. BM25 search
    tokenized_query = preprocess(query)
    bm25_scores = bm25.get_scores(tokenized_query)
    bm25_results = get_top_k(bm25_scores, k * 2)

    # 3. Score fusion (weighted)
    combined = {}
    for doc_id, score in semantic_results:
        combined[doc_id] = 0.7 * normalize(score)
    for doc_id, score in bm25_results:
        combined[doc_id] = combined.get(doc_id, 0) + 0.3 * normalize(score)

    # 4. Cross-encoder reranking
    candidates = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:k*2]
    reranked = cross_encoder.predict([(query, get_text(doc_id)) for doc_id, _ in candidates])

    return sorted(zip(candidates, reranked), key=lambda x: x[1], reverse=True)[:k]
```

### 2.3 Lessons Learned

**What Paperless-AI Does Well**:

1. Clean separation of concerns (Node.js UI/API, Python ML)
2. Graceful fallbacks (if ChromaDB fails, use BM25 only)
3. Incremental indexing via document hashing
4. Multi-language stopword handling

**Limitations to Address**:

1. ChromaDB may not scale for large document sets (consider Qdrant/Milvus)
2. No hierarchical chunking (just splits on paragraphs)
3. Sentence-transformer embeddings are smaller models
4. No document structure preservation (tables, figures)

---

## 3. Docling Deep Dive

### 3.1 Document Processing Pipeline

Docling uses a multi-stage pipeline:

```
Input Document (PDF, DOCX, PPTX, HTML, Images)
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: Document Loading                                  │
│  • File format detection                                    │
│  • PDF parsing / Office document extraction                 │
│  • Image conversion                                         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: Layout Analysis (DocLayNet)                       │
│  • Page segmentation                                        │
│  • Element classification:                                  │
│    - Text blocks, Headings, Paragraphs                     │
│    - Tables, Figures, Captions                             │
│    - Lists, Code blocks, Formulas                          │
│  • Reading order detection                                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: OCR (if needed)                                   │
│  • Tesseract / EasyOCR / RapidOCR                          │
│  • Character recognition                                    │
│  • Text extraction from images                              │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 4: Structure Recognition                             │
│  • Table structure extraction (rows, columns, cells)        │
│  • List hierarchy detection                                 │
│  • Heading level inference                                  │
│  • Section grouping                                         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 5: DoclingDocument Construction                      │
│  • Hierarchical document tree                               │
│  • Metadata attachment                                      │
│  • Cross-references                                         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage 6: Export                                            │
│  • Markdown (LLM-optimized)                                │
│  • JSON (lossless, machine-readable)                       │
│  • HTML (web display)                                       │
│  • DocTags (preserves formulas, code)                      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Output Formats

#### JSON Format (Recommended for RAG)

```json
{
  "name": "invoice_2024_001.pdf",
  "origin": {
    "filename": "invoice_2024_001.pdf",
    "mimetype": "application/pdf",
    "binary_hash": "a1b2c3d4...",
    "uri": "file:///data/invoice_2024_001.pdf"
  },
  "pages": [
    {
      "page_no": 1,
      "size": {"width": 612, "height": 792},
      "image": null
    }
  ],
  "body": {
    "children": [
      {
        "type": "heading",
        "level": 1,
        "text": "INVOICE",
        "prov": [{"page_no": 1, "bbox": [100, 700, 200, 720]}]
      },
      {
        "type": "paragraph",
        "text": "Invoice Number: INV-2024-001",
        "prov": [{"page_no": 1, "bbox": [100, 650, 300, 670]}]
      },
      {
        "type": "table",
        "num_rows": 4,
        "num_cols": 3,
        "data": [
          ["Item", "Quantity", "Price"],
          ["Widget A", "10", "$100.00"],
          ["Widget B", "5", "$75.00"],
          ["Total", "", "$175.00"]
        ],
        "prov": [{"page_no": 1, "bbox": [100, 400, 500, 600]}]
      }
    ]
  },
  "groups": [
    {
      "type": "section",
      "name": "Header",
      "children_refs": ["heading-1", "paragraph-1"]
    },
    {
      "type": "section",
      "name": "Line Items",
      "children_refs": ["table-1"]
    }
  ]
}
```

#### Markdown Format (LLM-friendly)

```markdown
# INVOICE

Invoice Number: INV-2024-001
Date: January 15, 2024
Customer: Acme Corporation

## Line Items

| Item | Quantity | Price |
|------|----------|-------|
| Widget A | 10 | $100.00 |
| Widget B | 5 | $75.00 |
| **Total** | | **$175.00** |

## Payment Terms

Payment is due within 30 days of invoice date.
```

### 3.3 Chunking Strategies

#### HierarchicalChunker

Preserves document structure by creating chunks at semantic boundaries:

```python
from docling.chunking import HierarchicalChunker

chunker = HierarchicalChunker()
chunks = chunker.chunk(docling_document)

# Example output
for chunk in chunks:
    print(f"Type: {chunk.meta.doc_items[0].label}")  # heading, paragraph, table
    print(f"Page: {chunk.meta.doc_items[0].prov[0].page_no}")
    print(f"Section: {chunk.meta.headings}")  # Parent headings
    print(f"Text: {chunk.text[:100]}...")
```

Chunk metadata includes:
- Document ID and source file
- Page numbers
- Bounding boxes
- Parent section headings (hierarchical path)
- Element type (heading, paragraph, table, figure)

#### HybridChunker (Recommended)

Combines hierarchical awareness with token-based splitting:

```python
from docling.chunking import HybridChunker
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=512,  # Match embedding model context
    merge_peers=True,  # Combine small adjacent chunks
)

chunks = chunker.chunk(docling_document)
```

### 3.4 Integration Example

```python
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from pathlib import Path

async def process_document_with_docling(file_path: Path) -> list[dict]:
    """Process a document with Docling and return chunks with metadata."""

    # Initialize converter
    converter = DocumentConverter()

    # Convert document
    result = converter.convert(file_path)
    docling_doc = result.document

    # Initialize chunker
    chunker = HybridChunker(max_tokens=512)

    # Generate chunks
    chunks = []
    for i, chunk in enumerate(chunker.chunk(docling_doc)):
        chunk_data = {
            "chunk_index": i,
            "text": chunk.text,
            "metadata": {
                "source_file": file_path.name,
                "page_numbers": list({
                    item.prov[0].page_no
                    for item in chunk.meta.doc_items
                    if item.prov
                }),
                "section_headings": chunk.meta.headings,
                "element_types": list({
                    item.label for item in chunk.meta.doc_items
                }),
                "char_count": len(chunk.text),
            }
        }
        chunks.append(chunk_data)

    return chunks


# Example usage
chunks = await process_document_with_docling(Path("/data/invoice.pdf"))
for chunk in chunks:
    print(f"Chunk {chunk['chunk_index']}: {chunk['text'][:50]}...")
    print(f"  Pages: {chunk['metadata']['page_numbers']}")
    print(f"  Section: {chunk['metadata']['section_headings']}")
```

### 3.5 Performance Considerations

| Configuration | CPU Time | GPU Time | Notes |
|---------------|----------|----------|-------|
| Full pipeline | Baseline | ~50% faster | Includes all features |
| Disable OCR | -60% | -50% | For born-digital PDFs |
| Disable table structure | -16% | -24% | If tables not needed |
| Disable both | -75% | -70% | Fastest, text-only |

**Recommendation**: Use document classification to route:
- Born-digital PDFs → Fast path (no OCR, basic extraction)
- Scanned PDFs → Full Docling pipeline with OCR
- Image-heavy PDFs → Full pipeline with table/figure extraction

---

## 4. Integration Architecture Recommendation

### 4.1 Recommended Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Document Management** | Paperless-ngx | Mature, feature-rich, active community |
| **OCR Pipeline** | Docling | Layout-aware, hierarchical chunking |
| **Embeddings** | OpenAI `text-embedding-3-small` or `all-MiniLM-L6-v2` | Cost vs quality trade-off |
| **Vector Store** | Qdrant or Milvus | Scalable, production-ready |
| **Keyword Search** | Elasticsearch or BM25 | Hybrid search component |
| **LLM** | GPT-4o / Claude / Ollama | RAG generation |

### 4.2 Deployment Architecture

```yaml
# docker-compose.yml (simplified)
services:
  # Paperless-ngx stack
  paperless:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    environment:
      PAPERLESS_URL: https://docs.example.com
      PAPERLESS_OCR_LANGUAGE: eng
      PAPERLESS_CONSUMER_POLLING: 60
    volumes:
      - paperless_data:/usr/src/paperless/data
      - paperless_media:/usr/src/paperless/media
      - paperless_consume:/usr/src/paperless/consume

  paperless_redis:
    image: redis:7-alpine

  paperless_db:
    image: postgres:15-alpine

  # RAG Processor stack
  rag_processor:
    build: ./rag-processor
    environment:
      PAPERLESS_URL: http://paperless:8000
      PAPERLESS_TOKEN: ${PAPERLESS_TOKEN}
      QDRANT_URL: http://qdrant:6333
      EMBEDDING_MODEL: text-embedding-3-small
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - paperless
      - qdrant
      - redis

  rag_worker:
    build: ./rag-processor
    command: rq worker docling embedding indexing
    environment:
      <<: *rag-env

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_storage:/qdrant/storage

  redis:
    image: redis:7-alpine
```

### 4.3 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. INGESTION                                                            │
│                                                                         │
│    User → Paperless-ngx upload → Consumption → OCRmyPDF                 │
│                                        │                                │
│                                        ▼                                │
│                            Post-consume webhook                         │
│                                        │                                │
│                                        ▼                                │
│                              RAG Processor                              │
└─────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. PROCESSING                                                           │
│                                                                         │
│    Fetch document from Paperless API                                    │
│                    │                                                    │
│                    ▼                                                    │
│    Classify: Scanned PDF? Image-heavy? Born-digital?                   │
│                    │                                                    │
│         ┌─────────┴─────────┐                                          │
│         ▼                   ▼                                          │
│    [Scanned/Image]    [Born-digital]                                   │
│    Docling full       Text extraction                                   │
│    pipeline           only                                              │
│         │                   │                                          │
│         └─────────┬─────────┘                                          │
│                   ▼                                                     │
│         Hierarchical chunking                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. INDEXING                                                             │
│                                                                         │
│    Generate embeddings (OpenAI / sentence-transformers)                 │
│                    │                                                    │
│                    ▼                                                    │
│    Store in Qdrant with metadata:                                       │
│    • paperless_doc_id, title, correspondent                            │
│    • chunk_index, page_number, section_path                            │
│    • element_type (heading, paragraph, table)                          │
│                    │                                                    │
│                    ▼                                                    │
│    Update Paperless custom fields:                                      │
│    • rag_processed_at, chunk_count, embedding_model                    │
└─────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. RETRIEVAL (Query time)                                               │
│                                                                         │
│    User query → Embedding → Qdrant similarity search                    │
│                                        │                                │
│                                        ▼                                │
│                           Optional: BM25 keyword search                 │
│                                        │                                │
│                                        ▼                                │
│                           Cross-encoder reranking                       │
│                                        │                                │
│                                        ▼                                │
│                        Top-k chunks with Paperless IDs                  │
│                                        │                                │
│                                        ▼                                │
│                           LLM generation with context                   │
│                                        │                                │
│                                        ▼                                │
│                    Response with Paperless document links               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

- [ ] Deploy Paperless-ngx with Docker Compose
- [ ] Configure custom fields for RAG metadata
- [ ] Implement Paperless API client in RAG Processor
- [ ] Create webhook endpoint
- [ ] Basic document classification (scanned vs born-digital)

### Phase 2: Docling Integration (Weeks 3-4)

- [ ] Integrate Docling document converter
- [ ] Implement HybridChunker with metadata preservation
- [ ] Set up Qdrant vector database
- [ ] Create embedding generation pipeline
- [ ] Build RQ workers for async processing

### Phase 3: Search & Retrieval (Weeks 5-6)

- [ ] Implement vector similarity search
- [ ] Add BM25 keyword search component
- [ ] Integrate cross-encoder reranking
- [ ] Build RAG query API
- [ ] Create search result formatting with Paperless links

### Phase 4: Polish & Production (Weeks 7-8)

- [ ] Metadata synchronization with Paperless
- [ ] Error handling and retry logic
- [ ] Monitoring and observability
- [ ] Documentation and deployment guides
- [ ] Load testing and optimization

---

## 6. Open Questions

1. **Vector Database Selection**: Qdrant vs Milvus vs PGVector - need to evaluate based on expected document volume
2. **Embedding Model**: OpenAI (cost) vs open-source (latency/quality trade-off)
3. **Chat Interface**: Build custom or use existing tools (Chainlit, Streamlit)?
4. **Multi-tenancy**: Single Paperless instance or per-tenant isolation?
5. **Backup Strategy**: How to handle vector store backups in sync with Paperless?

---

## References

- [Paperless-ngx Documentation](https://docs.paperless-ngx.com/)
- [Paperless-ngx API Reference](https://docs.paperless-ngx.com/api/)
- [Docling Documentation](https://docling-project.github.io/docling/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [ADR-002: Paperless-ngx Integration](./adr/adr-002-paperless-ngx-integration.md)
