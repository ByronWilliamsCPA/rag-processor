# ADR-002: Redis with RQ for Job Queue Management

> **Status**: Accepted
> **Date**: 2025-12-04

## TL;DR

We will use Redis with Python RQ (Redis Queue) for asynchronous job processing and queue management because it provides a lightweight, battle-tested solution that integrates seamlessly with FastAPI while supporting priority queues and job persistence required for multi-file batch processing.

## Context

### Problem

The gateway must handle asynchronous file processing across multiple pipelines (Projects A-E) with:

- Batch job submission (users upload 10-100 files simultaneously)
- Priority queue support (high/normal/low) for urgent processing
- Job persistence across gateway restarts
- Status tracking and progress reporting
- Retry logic for failed pipeline submissions

### Constraints

- **Technical**: Must integrate with FastAPI (Python), support WebSocket status broadcasts, run in Docker Compose
- **Business**: Single developer, must be operationally simple (no Kubernetes), <100 concurrent users in MVP

### Significance

Job queue choice impacts system reliability, scalability, and operational complexity. The wrong choice could lead to:

- Lost jobs during gateway restarts
- Poor observability into queue depth and processing times
- Complex deployment requiring external services (Kafka, RabbitMQ clusters)
- Difficulty implementing priority-based processing

## Decision

**We will use Redis 7+ with Python RQ because it provides exactly the feature set we need (persistence, priorities, retries, Python integration) without the operational overhead of a dedicated message broker.**

### Rationale

1. **Operational Simplicity**: Redis runs as a single Docker Compose service with persistence via AOF/RDB—no cluster management, no separate message broker
2. **Python-Native**: RQ is designed for Python, providing decorator-based job definitions and native FastAPI integration
3. **Persistence**: Redis persistence ensures jobs survive gateway restarts (critical for long-running pipeline processing)
4. **Priority Queues**: Built-in support for high/normal/low-priority queues via RQ's named queues
5. **Observability**: RQ provides job status tracking (queued/started/finished/failed) and failure metadata out of the box

## Options Considered

### Option 1: Redis + Python RQ ✓

**Pros**:

- ✅ Single dependency (Redis) for both queue and WebSocket pub/sub
- ✅ Python-native job definitions with type hints and Pydantic models
- ✅ Built-in retry logic with exponential backoff
- ✅ Job TTL support for automatic cleanup of old jobs
- ✅ <100 lines of code to implement full queue logic

**Cons**:

- ❌ Not suitable for >10,000 jobs/second (acceptable for MVP: <1000 files/hour)
- ❌ Limited distributed tracing compared to Celery

### Option 2: Celery + RabbitMQ

**Pros**:

- ✅ Industry standard for distributed task processing
- ✅ Advanced routing and workflow features
- ✅ Built-in monitoring (Flower)

**Cons**:

- ❌ Requires RabbitMQ (additional service to manage)
- ❌ Heavier operational footprint (Celery workers, RabbitMQ cluster)
- ❌ Overkill for <100 concurrent users
- ❌ More complex configuration (broker URLs, result backends, serialization)

### Option 3: In-Memory Queue (asyncio.Queue)

**Pros**:

- ✅ Zero external dependencies
- ✅ Simplest implementation

**Cons**:

- ❌ No persistence—jobs lost on restart (unacceptable)
- ❌ No priority queue support
- ❌ No retry logic
- ❌ Cannot scale beyond single gateway instance

## Consequences

### Positive

- ✅ **Fast Development**: RQ's decorator pattern allows job definition in ~5 lines per task
- ✅ **Unified Infrastructure**: Redis serves both job queue and WebSocket pub/sub, reducing service count
- ✅ **Production-Ready**: Redis persistence modes (AOF + RDB) ensure job durability
- ✅ **Easy Monitoring**: RQ's job metadata provides status without custom tracking

### Trade-offs

- ⚠️ **Throughput Limit**: RQ not optimized for >10K jobs/second—mitigated by batch processing design (1000 files/hour target well within limit)
- ⚠️ **Single Point of Failure**: Redis is not clustered in MVP—acceptable for development; production deployment should add Redis Sentinel or managed Redis (deferred)

### Technical Debt

- **No Distributed Tracing**: RQ lacks built-in OpenTelemetry support—if tracing becomes critical, consider adding manual span creation or evaluate Celery migration (deferred to Phase 3)
- **Job Result Storage**: RQ stores results in Redis (memory overhead)—consider TTL-based expiration or moving completed job results to PostgreSQL if Redis memory becomes constrained (deferred)

## Implementation

### Components Affected

1. **Gateway (gateway/)**: RQ job definitions, queue submission on file upload, job status queries for API endpoints
2. **Worker Process**: Separate RQ worker process (`rq worker`) consuming from priority queues (high, default, low)
3. **Redis Service**: Docker Compose service with persistence volume, AOF enabled

### Testing Strategy

- **Unit**: pytest with fakeredis for queue logic without real Redis dependency
- **Integration**: Test full cycle (submit job → worker processes → status update → WebSocket broadcast) with real Redis

## Validation

### Success Criteria

- [ ] 100-file batch queued and processed within 2 minutes (test with mock pipelines)
- [ ] High-priority jobs processed before low-priority jobs when queue is full
- [ ] Jobs persist across gateway restart (stop/start Docker Compose)
- [ ] Failed jobs automatically retry up to 3 times with exponential backoff
- [ ] Worker can process 10 concurrent jobs without Redis connection errors

### Review Schedule

- **Initial**: End of Phase 1 (week 4) - validate queue performance with realistic load
- **Ongoing**: Monitor Redis memory usage; re-evaluate if memory exceeds 2GB or throughput exceeds 5K jobs/hour

## Related

- [ADR-001](./adr-001-initial-architecture.md) - References Redis as job queue technology
- [Tech Spec](../tech-spec.md#architecture) - Details queue integration in component diagram
