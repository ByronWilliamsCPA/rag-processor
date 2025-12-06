# Project Vision & Scope: RAG Processor WebUI

> **Status**: Active | **Version**: 1.0 | **Updated**: 2025-12-04

## TL;DR

RAG Processor WebUI is a React-based frontend that serves as the unified ingestion interface for a multi-pipeline RAG (Retrieval-Augmented Generation) system. It provides authenticated users with drag-and-drop file upload, automatic routing to specialized processing pipelines (image, audio, OCR, fusion), real-time job monitoring via WebSocket, and configurable handoff to downstream vector storage systems.

## Problem Statement

### Pain Point

RAG systems require preprocessing files (documents, images, audio) before they can be embedded and stored in vector databases. Currently, the processing pipeline ecosystem (Projects A-E) lacks a unified interface, forcing users to:

- Manually determine which pipeline to use for each file type
- Submit files through separate CLI tools or APIs for each pipeline
- Track job status across multiple systems without real-time visibility
- Manually coordinate handoff between preprocessing and vector storage systems

This creates friction, errors from misrouting, and operational complexity that slows down RAG system development and deployment.

### Target Users

- **Primary**: Data engineers and ML engineers building RAG applications who need to ingest diverse document types into vector databases
- **Context**: Development and production environments where documents (PDFs, images, audio files, Office documents) must be preprocessed before embedding. Users need to batch-process files efficiently, monitor progress in real-time, and ensure processed outputs reach the correct vector storage backend.

### Success Metrics

- **Time to Ingest**: 5+ minutes (manual pipeline selection) → <30 seconds (automatic routing)
- **Routing Errors**: 15-20% misclassified files → <2% error rate
- **User Onboarding**: 2+ hours to understand pipeline ecosystem → <15 minutes with unified UI
- **Job Visibility**: No real-time status (check logs/APIs manually) → Live WebSocket updates every 2-5 seconds

## Solution Overview

### Core Value

RAG Processor WebUI eliminates operational friction by providing a single, authenticated interface that automatically routes files to the correct preprocessing pipeline, monitors job progress in real-time, and delivers processed outputs to configurable vector storage backends—reducing ingestion time by 90% while improving accuracy.

### Key Capabilities (MVP)

1. **Authenticated File Upload**: Cloudflare Access-secured drag-and-drop interface supporting multi-file batch uploads with automatic content-type detection (PDFs, images, audio, Office documents) to ensure only authorized users can ingest data
2. **Intelligent Pipeline Routing**: Automatic classification and routing to specialized pipelines (Project A for scanned PDFs/images with IQA, Project E for audio/video, Project B for born-digital documents, Project C for fusion) based on magic bytes, MIME types, and PDF text extraction analysis
3. **Real-Time Job Monitoring**: WebSocket-based live status updates showing per-job and per-batch progress, estimated completion times, error reporting, and visual progress indicators without requiring page refreshes
4. **Configurable Vector Storage Handoff**: Flexible integration with multiple Project D variants (vector database backends) via a registration API, allowing users to select target systems per batch and automatically deliver processed outputs to the chosen backend

## Scope Definition

### In Scope (MVP)

- ✅ **Cloudflare Access Authentication**: JWT validation middleware, user attribution for audit trails, session management
- ✅ **Multi-File Upload Interface**: Drag-and-drop zone, file type validation, batch creation, upload progress indicators
- ✅ **Automatic Content Detection**: Magic byte scanning, MIME type validation, PDF classification (scanned vs born-digital), file extension fallback
- ✅ **Pipeline Routing Logic**: Route to Project A (image IQA + OCR), Project E (audio transcription), Project B (Docling processing), Project C (fusion pipeline)
- ✅ **Job Queue Management**: Redis-backed job queue with priority support (low/normal/high), batch grouping, job lifecycle tracking (queued → processing → completed → failed)
- ✅ **Real-Time Status WebSocket**: Per-batch WebSocket connections with JWT authentication, status updates, error notifications, estimated completion times
- ✅ **Project D Integration**: Target registration API, configurable handoff per batch, delivery confirmation tracking
- ✅ **Basic Error Handling**: Unsupported file type rejection, upload size limits, failed job retry mechanism, user-facing error messages

### Out of Scope

- ❌ **RAG Query Interface**: User-facing RAG query/chat interfaces are handled by downstream systems (Project D or external applications), not this ingestion UI
- ❌ **Pipeline Implementation Details**: Internal workings of Projects A-E (image quality assessment, Deepgram audio transcription, Docling document processing, fusion logic) are external dependencies
- ❌ **Identity Provider Management**: Cloudflare Access configuration, OAuth provider setup, user provisioning are managed externally via Cloudflare dashboard
- 🔄 **Advanced Analytics Dashboard**: Job statistics, processing time analytics, cost tracking (deferred to Phase 2)
- 🔄 **Bulk Upload via S3/API**: Direct S3 bucket monitoring, programmatic bulk ingestion API (deferred to Phase 2)
- 🔄 **Custom Pipeline Configuration**: User-defined preprocessing rules, custom pipeline creation (deferred to future)

## Constraints

### Technical

- **Platform**: Web application (React 18 frontend, FastAPI backend gateway)
- **Language**: Python 3.12+ for backend services, TypeScript for frontend
- **Performance**:
  - WebSocket latency < 2 seconds for status updates
  - File upload handling up to 500MB per file
  - Support 100+ concurrent users
  - Batch processing throughput: 1000+ files/hour (aggregate across pipelines)
- **Authentication**: Must integrate with existing Cloudflare Access infrastructure (williaby/testing cloudflare-auth middleware)
- **Deployment**: Docker Compose for initial deployment, Cloudflare Tunnel for secure ingress
- **Browser Support**: Modern evergreen browsers (Chrome 90+, Firefox 88+, Edge 90+, Safari 14+)

### Business

- **Timeline**: MVP completion target: 4-6 weeks from kickoff
- **Resources**: Single developer (leveraging existing pipeline infrastructure from Projects A-E)
- **Dependencies**: Requires Projects A-E APIs to be stable and documented, Cloudflare Access pre-configured
- **Operational**: Must maintain <5 second TTFB (time to first byte) for UI responsiveness, 99% uptime for ingestion gateway

## Assumptions to Validate

- [ ] **Pipeline API Stability**: Projects A-E provide stable HTTP APIs with documented request/response formats and error codes
- [ ] **Cloudflare Access Configuration**: Cloudflare Access is already configured with appropriate application audience tags and williaby/testing middleware is compatible with current infrastructure
- [ ] **File Size Distribution**: Typical file sizes are <100MB (with 500MB max), fitting within single HTTP request upload limits without requiring multipart chunking
- [ ] **User Volume**: Peak concurrent users will not exceed 100 during MVP phase, allowing for straightforward Redis queue management without horizontal scaling
- [ ] **Network Reliability**: Internal Docker network communication between gateway and Projects A-E is reliable (<1% packet loss), justifying synchronous HTTP calls for job submission
- [ ] **WebSocket Scaling**: Single WebSocket server instance can handle 100 concurrent connections without requiring dedicated message broker (e.g., Redis Pub/Sub)

## Related Documents

- [Architecture Decisions](adr/README.md)
  - [ADR-001: Initial Architecture](adr/adr-001-initial-architecture.md)
- [Technical Spec](tech-spec.md)
- [Development Roadmap](roadmap.md)
- [WebUI Specification](../webui_spec.md) (original requirements document)
