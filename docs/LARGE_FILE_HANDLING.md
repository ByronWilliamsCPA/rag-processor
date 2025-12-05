# Large File Handling Strategy

> **Status**: Planning
> **Target**: Phase 1 (MVP) - 2GB streaming uploads
> **Future**: Phase 2 (Enhancement) - 5GB+ chunked uploads

## Problem Statement

The current 500MB file size limit is insufficient for audio/video processing:

- **1 hour WAV** (44.1kHz, 16-bit stereo): ~600MB
- **1 hour FLAC** (lossless): ~300-500MB
- **2+ hour podcast WAV**: 1.2GB+
- **Video files with audio tracks**: Often 1GB+

## Recommended Solution

### Phase 1: Streaming Upload (2GB Limit)

**Timeline**: Included in MVP roadmap (Phase 1, Weeks 2-4)
**Effort**: 1-2 days
**Benefits**:
- ✅ Supports most audio files (1-2 hour recordings)
- ✅ Minimal development effort
- ✅ No memory bloat (streaming to disk)
- ✅ No complex chunking protocol

**Implementation**:

```python
# gateway/src/gateway/api/upload.py
import aiofiles
from fastapi import UploadFile, HTTPException

MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

@app.post("/api/v1/ingest")
async def ingest_files(
    files: list[UploadFile],
    user: CloudflareUser = Depends(get_current_user)
):
    for file in files:
        if file.size and file.size > MAX_UPLOAD_SIZE:
            raise HTTPException(413, f"File exceeds 2GB limit")

        # Stream to disk (no full memory load)
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(8192):  # 8KB chunks
                await f.write(chunk)
```

**Cloudflare Tunnel Configuration**:

```yaml
# cloudflared config.yml
ingress:
  - hostname: rag-processor.example.com
    service: http://gateway:8000
    originRequest:
      connectTimeout: 30s
      http2Origin: true
      disableChunkedEncoding: false  # Allow 2GB uploads
```

### Phase 2: Chunked Resumable Upload (5GB+)

**Timeline**: Enhancement phase (Week 5)
**Effort**: 3-4 days
**Benefits**:
- ✅ Supports very large files (5GB+)
- ✅ Resume capability for interrupted uploads
- ✅ Better progress tracking
- ✅ Works with slow/unstable networks

**Architecture**:

```
CLIENT                        GATEWAY API                   STORAGE
  |                                |                            |
  |-- POST /upload/session ------->|                            |
  |<- {upload_id, chunk_size} -----|                            |
  |                                |                            |
  |-- POST /upload/{id}/chunk/1 -->|--- write chunk_001 ------->|
  |<- 201 Created -----------------|                            |
  |                                |                            |
  |-- POST /upload/{id}/chunk/2 -->|--- write chunk_002 ------->|
  |<- 201 Created -----------------|                            |
  |                                |                            |
  |-- POST /upload/{id}/finalize -->|--- merge chunks ---------->|
  |<- {batch_id, job_id} -----------|<-- complete file ----------|
```

**API Specification**:

```typescript
// Create upload session
POST /api/v1/upload/session
{
  "filename": "large_audio.wav",
  "total_size_bytes": 5368709120,  // 5GB
  "chunk_size_bytes": 52428800,    // 50MB chunks
  "content_type": "audio/wav"
}

Response 201:
{
  "upload_id": "upload_abc123",
  "chunk_size": 52428800,
  "total_chunks": 102,
  "expires_at": "2025-12-05T12:30:00Z"
}

// Upload chunk
POST /api/v1/upload/{upload_id}/chunk/{chunk_number}
Content-Type: application/octet-stream
Content-Range: bytes 0-52428799/5368709120

[binary chunk data]

Response 201:
{
  "upload_id": "upload_abc123",
  "chunk_number": 1,
  "chunks_received": 1,
  "total_chunks": 102,
  "next_chunk": 2
}

// Finalize upload
POST /api/v1/upload/{upload_id}/finalize
{
  "checksum": "sha256:abc123...",  // Optional verification
  "batch_metadata": {...}
}

Response 201:
{
  "batch_id": "batch_xyz789",
  "job_id": "job_def456",
  "status_url": "/api/v1/batch/batch_xyz789"
}
```

**Frontend Integration** (using uppy.io):

```typescript
import Uppy from '@uppy/core';
import Tus from '@uppy/tus';

const uppy = new Uppy({
  restrictions: {
    maxFileSize: 5 * 1024 * 1024 * 1024, // 5GB
  }
})
.use(Tus, {
  endpoint: '/api/v1/upload/session',
  chunkSize: 50 * 1024 * 1024, // 50MB chunks
  retryDelays: [0, 1000, 3000, 5000],
  removeFingerprintOnSuccess: true,
});

uppy.on('complete', (result) => {
  // Trigger finalization
  fetch(`/api/v1/upload/${result.upload_id}/finalize`, {
    method: 'POST'
  });
});
```

## Updated Planning Documents

### Changes Required

1. **Project Vision & Scope**
   ```markdown
   - File upload handling up to 2GB per file (MVP), with chunked upload support
     for larger files in Phase 2 (5GB+)
   ```

2. **Tech Spec - Performance Requirements**
   ```markdown
   | File Upload Latency | <2s for 10MB, <30s for 500MB, <5min for 2GB | Streaming upload |
   ```

3. **Roadmap - Add to Phase 2**
   ```markdown
   #### US-008: Large File Upload Support

   **As a** data engineer
   **I want** to upload audio/video files larger than 2GB
   **So that** I can process long-form content without splitting files

   **Acceptance Criteria**:
   - [ ] Files >500MB automatically use chunked upload
   - [ ] Upload resumes from last chunk if interrupted
   - [ ] Progress indicator shows chunk upload status
   ```

4. **Risk Register**
   ```markdown
   | Large file uploads (>2GB) exceed timeout limits | M | M | Implement chunked uploads in Phase 2; document size recommendations; add time estimates in UI |
   ```

## Testing Strategy

### Phase 1 (Streaming)
- Upload 100MB file → verify streaming (no full memory load)
- Upload 1GB file → verify timeout handling (should complete <10min on 10Mbps)
- Upload 2GB file → verify size limit enforcement
- Concurrent uploads (10 users × 500MB) → verify no memory exhaustion

### Phase 2 (Chunked)
- Upload 5GB file in 50MB chunks → verify assembly
- Interrupt upload at chunk 50 → verify resume from chunk 51
- Network failure mid-chunk → verify retry with exponential backoff
- Checksum validation → verify file integrity after assembly

## Monitoring & Metrics

Track these metrics to validate large file handling:

- **Upload duration distribution** (by file size)
- **Timeout rate** (uploads exceeding 30min)
- **Memory usage** (should stay flat regardless of file size)
- **Chunk upload retry rate** (Phase 2)
- **File size distribution** (understand actual user needs)

## Recommendation

**Start with Phase 1 (2GB streaming)** and defer chunked uploads until user feedback demands it. This provides:

- ✅ 4x increase over current 500MB limit
- ✅ Covers vast majority of audio files
- ✅ Minimal development time (1-2 days)
- ✅ Early user validation before complex chunking

---

**Status**: Draft - requires review and approval before implementation
**Owner**: Core maintainer
**Last Updated**: 2025-12-05
