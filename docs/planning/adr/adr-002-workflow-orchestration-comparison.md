---
title: "ADR-002: Workflow Orchestration Tool Comparison"
schema_type: planning
status: draft
owner: core-maintainer
purpose: "Compare Temporal, Airflow, Prefect, and Dagster for RAG Processor workflow orchestration needs."
tags:
  - planning
  - architecture
  - decisions
  - orchestration
component: Strategy
source: "Architecture evaluation"
---

> **Status**: Draft
> **Date**: 2026-01-09

## TL;DR

Comparing Temporal, Apache Airflow, Prefect, and Dagster for workflow orchestration in RAG Processor WebUI. Current Redis + RQ approach remains recommended for MVP due to simplicity, but Temporal emerges as the best option for future scaling of complex, long-running file processing workflows.

## Context

### Current Architecture

RAG Processor currently uses **Redis + RQ** for job queue management (see [ADR-001](./adr-001-react-fastapi-architecture.md)):

```text
[React SPA] → [FastAPI Gateway] → [Redis + RQ] → [RQ Workers] → [External Pipelines]
```

### Evaluation Drivers

1. **Scaling concerns**: Will Redis + RQ handle 10x growth (1000 concurrent users, 10,000 files/hour)?
2. **Workflow complexity**: Future multi-step pipelines may require sophisticated orchestration
3. **Reliability**: Long-running audio/video processing (10+ minutes) needs durable execution
4. **Observability**: Need better visibility into workflow execution and failure analysis

### Project Constraints

- Single developer with Python expertise
- Docker Compose deployment (self-hosted)
- MVP timeline: 4-6 weeks
- No managed service budget
- Target: 100+ concurrent users, 1000+ files/hour initially

## Comparison Matrix

| Criteria | Redis + RQ | Temporal | Airflow | Prefect | Dagster |
|----------|------------|----------|---------|---------|---------|
| **Primary Focus** | Simple job queue | Durable execution | DAG scheduling | Modern pipelines | Data assets |
| **Paradigm** | Task queue | Code-first workflows | DAG-based | Task-based | Asset-centric |
| **Dynamic Workflows** | Manual | Excellent | Limited | Good | Good |
| **Long-running Jobs** | Basic | Excellent | Poor | Good | Good |
| **Learning Curve** | Very Low | Moderate | Moderate | Low | Moderate |
| **Operational Complexity** | Low | Moderate | High | Moderate | Moderate |
| **Python SDK Quality** | Good | Excellent | Excellent | Excellent | Excellent |
| **Self-hosted Viable** | Yes | Yes | Yes | Yes | Yes |
| **Resource Requirements** | Minimal | Moderate | High | Moderate | Moderate |
| **Real-time Updates** | Manual impl | Built-in | Polling | Built-in | Built-in |
| **Retry/Failure Handling** | Basic | Excellent | Good | Good | Good |
| **State Persistence** | Redis only | Durable by design | Database | Database | Database |

## Detailed Analysis

### 1. Apache Airflow

**Overview**: The most mature and widely adopted workflow orchestration platform, originally developed at Airbnb. Uses DAG (Directed Acyclic Graph) definitions for workflow scheduling.

**Architecture**:
```text
[Scheduler] → [Metadata DB] → [Executor] → [Workers]
      ↓
  [Web UI]
```

**Strengths**:
- Mature ecosystem with 1000+ operators and integrations
- Strong community support and documentation
- Excellent for scheduled batch ETL workflows
- Built-in monitoring and alerting
- Robust DAG visualization

**Weaknesses**:
- **Heavyweight**: Requires PostgreSQL/MySQL + Redis/RabbitMQ + multiple components
- **DAG-centric**: Workflows must be defined as static DAGs; dynamic workflows require workarounds
- **Not event-driven**: Designed for scheduled execution, not real-time file processing
- **Learning curve**: Complex configuration and deployment
- **Resource-intensive**: 2-4GB RAM minimum for scheduler + web server

**Fit for RAG Processor**:
- ❌ **Poor fit**: File upload triggers (event-driven) don't align with Airflow's scheduled DAG paradigm
- ❌ Over-engineered for simple file routing workflows
- ❌ No native WebSocket support for real-time status updates
- ⚠️ Could work but would require significant adaptation

**Best for**: Scheduled batch ETL, data warehouse workflows, complex multi-step data pipelines with dependencies

---

### 2. Prefect

**Overview**: Modern, Pythonic workflow orchestration designed as an Airflow alternative. Emphasizes ease of use and dynamic workflows.

**Architecture**:
```text
[Prefect Server/Cloud] ← [Agents] → [Flow Runs]
         ↓
     [PostgreSQL]
```

**Strengths**:
- **Pythonic API**: Decorator-based, intuitive syntax (`@flow`, `@task`)
- **Dynamic workflows**: Easy parameterization and conditional logic
- **Hybrid execution**: Run locally, self-hosted, or Prefect Cloud
- **Modern UI**: Clean interface for monitoring
- **Good failure handling**: Automatic retries, caching, notifications

**Code Example**:
```python
from prefect import flow, task

@task(retries=3, retry_delay_seconds=10)
async def classify_file(file_path: str) -> str:
    # Classify file type (PDF, image, audio)
    return detected_type

@task
async def route_to_pipeline(file_path: str, file_type: str) -> dict:
    # Route to appropriate pipeline
    return pipeline_result

@flow(name="file-ingestion")
async def process_file(file_path: str):
    file_type = await classify_file(file_path)
    result = await route_to_pipeline(file_path, file_type)
    return result
```

**Weaknesses**:
- **Server required**: Needs Prefect Server (PostgreSQL + server process) or Prefect Cloud
- **Agent architecture**: Separate agent process polls for work (not push-based)
- **Overhead**: More infrastructure than Redis + RQ for simple workflows
- **Less mature than Airflow**: Smaller ecosystem, fewer integrations

**Fit for RAG Processor**:
- ✅ Pythonic and easy to adopt
- ✅ Good async support aligns with FastAPI
- ⚠️ Additional infrastructure (Prefect Server + PostgreSQL) vs current Redis-only
- ⚠️ Agent polling model less ideal for real-time updates (would still need WebSocket layer)
- ⚠️ Moderate fit: Would work but adds complexity without major benefits for MVP scope

**Best for**: ML pipelines, data science workflows, teams wanting modern Airflow alternative

---

### 3. Dagster

**Overview**: Asset-centric orchestration platform focused on data engineering. Treats data assets (tables, files, models) as first-class citizens rather than tasks.

**Architecture**:
```text
[Dagster Daemon] → [Dagit Web UI] → [User Code Deployment]
        ↓
  [PostgreSQL]
```

**Strengths**:
- **Asset-centric**: Model data lineage and dependencies naturally
- **Strong typing**: Pydantic-like type system for inputs/outputs
- **Excellent testing**: First-class testing support, easy local development
- **Software engineering focus**: Modular, testable, type-safe
- **Built-in data quality**: Freshness policies, partitioning, sensors

**Code Example**:
```python
from dagster import asset, AssetExecutionContext

@asset
def raw_document(context: AssetExecutionContext, file_path: str) -> bytes:
    """Ingest raw document from upload."""
    with open(file_path, "rb") as f:
        return f.read()

@asset
def classified_document(raw_document: bytes) -> dict:
    """Classify document type."""
    return {"type": detect_type(raw_document), "content": raw_document}

@asset
def processed_document(classified_document: dict) -> dict:
    """Route and process through appropriate pipeline."""
    return route_to_pipeline(classified_document)
```

**Weaknesses**:
- **Asset paradigm shift**: Requires rethinking workflows as data dependencies
- **Learning curve**: Concepts like partitions, sensors, resources take time
- **Infrastructure overhead**: Daemon + Dagit + PostgreSQL required
- **Less suited for orchestration-only**: Overkill if just routing to external services

**Fit for RAG Processor**:
- ✅ Would model file → processed_document → vector_embedding lineage well
- ⚠️ Asset-centric model is philosophically different from current task queue approach
- ⚠️ Overhead for MVP: Would require significant refactoring
- ⚠️ External pipeline calls are awkward in asset model (side effects)
- ❌ Over-engineered for current scope

**Best for**: Data platforms, data mesh architectures, teams with data engineering focus, complex data lineage needs

---

### 4. Temporal

**Overview**: Durable execution platform for building reliable, long-running workflows. Code-first approach where workflows survive crashes, restarts, and failures.

**Architecture**:
```text
[Temporal Server] → [Workers] → [Workflow + Activities]
        ↓
   [PostgreSQL/MySQL/Cassandra]
```

**Strengths**:
- **Durable by design**: Workflow state automatically persisted and recovered
- **Code-first**: Write workflows as regular Python functions, SDK handles durability
- **Excellent for long-running**: Multi-minute/hour/day workflows handled naturally
- **Dynamic workflows**: Full programming language flexibility (loops, conditionals)
- **Multi-language**: Go, Java, Python, TypeScript SDKs (can mix in one workflow)
- **Built-in retry/timeout**: Sophisticated retry policies, cancellation, signals
- **Real-time updates**: Workflow queries and signals for status updates

**Code Example**:
```python
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

@activity.defn
async def classify_file(file_path: str) -> str:
    """Classify file type - this is an Activity (can fail, will retry)."""
    return await detect_file_type(file_path)

@activity.defn
async def submit_to_pipeline(file_path: str, pipeline: str) -> dict:
    """Submit to external pipeline API with automatic retry."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"http://{pipeline}/process", files={"file": open(file_path, "rb")})
        return response.json()

@activity.defn
async def poll_pipeline_status(pipeline_job_id: str) -> dict:
    """Poll pipeline until complete."""
    # Temporal handles the polling loop durably
    return await check_status(pipeline_job_id)

@workflow.defn
class FileIngestionWorkflow:
    @workflow.run
    async def run(self, file_path: str) -> dict:
        # Classify file
        file_type = await workflow.execute_activity(
            classify_file,
            file_path,
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # Route to pipeline
        pipeline = self.route_to_pipeline(file_type)

        # Submit and wait for completion
        job = await workflow.execute_activity(
            submit_to_pipeline,
            args=[file_path, pipeline],
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Wait for pipeline completion (could be minutes)
        result = await workflow.execute_activity(
            poll_pipeline_status,
            job["job_id"],
            schedule_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(seconds=60),
        )

        return result

    @workflow.query
    def get_status(self) -> dict:
        """Query current workflow status - called via WebSocket."""
        return {"current_step": self.current_step, "progress": self.progress}

    @workflow.signal
    async def cancel_processing(self):
        """Signal to cancel workflow."""
        self.cancelled = True
```

**Weaknesses**:
- **Learning curve**: Workflow/Activity distinction, determinism rules take time
- **Infrastructure**: Temporal Server requires PostgreSQL/MySQL + server process
- **Overkill for simple queues**: More complex than Redis + RQ for basic job dispatch
- **Debugging**: Replay-based debugging requires understanding execution model

**Fit for RAG Processor**:
- ✅ **Excellent fit for long-running processing**: Audio/video transcription (10+ minutes) naturally handled
- ✅ **Built-in durability**: Pipeline failures auto-recovered without custom code
- ✅ **Query/Signal support**: Real-time status via `workflow.query` aligns with WebSocket needs
- ✅ **Multi-step workflows**: File → classify → route → process → handoff modeled naturally
- ✅ **Python SDK**: Async-native, works well with FastAPI
- ⚠️ **Infrastructure overhead**: Requires Temporal Server + database
- ⚠️ **Learning curve**: Would need 1-2 weeks to learn Temporal patterns
- ⚠️ **Over-engineered for MVP**: Current Redis + RQ sufficient for initial 100 users

**Best for**: Mission-critical business processes, microservice orchestration, long-running workflows, AI/ML pipelines with GPU processing

---

### 5. Current Approach: Redis + RQ (Baseline)

**Overview**: Lightweight Python job queue using Redis as message broker. Simple, minimal infrastructure.

**Strengths**:
- **Simplicity**: Minimal learning curve, quick to implement
- **Low overhead**: Single Redis container, no additional database
- **Python-native**: Familiar patterns, easy debugging
- **MVP-appropriate**: Sufficient for 100 users, 1000 files/hour

**Weaknesses**:
- **No durable execution**: Crashed jobs may lose state
- **Manual retry logic**: Must implement retry/backoff
- **Limited visibility**: No built-in workflow monitoring
- **Scale limits**: Single Redis instance bottleneck

**Fit for RAG Processor**:
- ✅ Already implemented and working
- ✅ Meets MVP requirements
- ⚠️ May need replacement at 10x scale

## Decision Matrix by Use Case

| Use Case | Recommended Tool | Rationale |
|----------|------------------|-----------|
| **MVP (100 users, simple workflows)** | Redis + RQ | Already implemented, meets requirements |
| **Scale to 1000+ users** | Temporal | Durable execution handles long-running jobs |
| **Scheduled batch processing** | Airflow | Best for scheduled DAG workflows |
| **ML pipeline orchestration** | Prefect or Dagster | Better ML-specific features |
| **Data lineage focus** | Dagster | Asset-centric model ideal for data engineering |
| **Mission-critical reliability** | Temporal | Built for durability and fault tolerance |

## Recommendation

### Phase 1: MVP (Current)

**Keep Redis + RQ**. The current architecture is appropriate for:
- 100 concurrent users target
- 1000 files/hour throughput
- Simple file → pipeline → result workflows
- 4-6 week MVP timeline

### Phase 2: Growth (Future)

**Evaluate Temporal** when:
- User load approaches 500+ concurrent
- File throughput exceeds 5000/hour
- Long-running workflows (>10 minutes) become common
- Multi-step workflows with complex failure handling needed
- Need for real-time workflow queries (built-in Temporal feature)

### Migration Path

```text
Current:   FastAPI → Redis + RQ → RQ Workers
Future:    FastAPI → Temporal Client → Temporal Workers
```

**Migration effort estimate**: 2-3 weeks to replace RQ with Temporal, including:
- Temporal Server deployment (Docker Compose addition)
- Workflow/Activity definitions
- Worker implementation
- FastAPI integration for workflow queries/signals

## Consequences

### If Staying with Redis + RQ

**Positive**:
- ✅ No additional learning required
- ✅ Minimal infrastructure
- ✅ Faster MVP delivery

**Trade-offs**:
- ⚠️ Must implement custom retry/timeout logic
- ⚠️ No built-in workflow visibility
- ⚠️ May need migration when scaling

### If Adopting Temporal (Future)

**Positive**:
- ✅ Durable execution for long-running jobs
- ✅ Built-in retry, timeout, cancellation
- ✅ Real-time workflow queries for WebSocket status
- ✅ Multi-language support if expanding team

**Trade-offs**:
- ⚠️ 1-2 week learning curve
- ⚠️ Additional infrastructure (Temporal Server + PostgreSQL)
- ⚠️ More complex debugging (replay-based)

## Validation

### Decision Review Triggers

Re-evaluate this decision if:
- [ ] User load exceeds 300 concurrent users
- [ ] File throughput exceeds 3000/hour sustained
- [ ] Long-running job failures exceed 5% without recovery
- [ ] WebSocket status update requirements become complex
- [ ] Multi-step workflow complexity increases significantly

## Related Documents

- [ADR-001: React + FastAPI Architecture](./adr-001-react-fastapi-architecture.md)
- [Tech Spec](../tech-spec.md): Current architecture details
- [Roadmap](../roadmap.md): Phase-based implementation plan

## Sources

- [Top Open Source Workflow Orchestration Tools in 2025](https://www.bytebase.com/blog/top-open-source-workflow-orchestration-tools/)
- [9 Real-World Generative AI Use Cases Powered by Temporal](https://temporal.io/blog/temporal-use-case-roundup-generative-ai)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [Temporal vs Airflow: Which Orchestrator Fits Your Workflows?](https://www.zenml.io/blog/temporal-vs-airflow)
- [Top 11 Airflow Alternatives](https://hevodata.com/learn/airflow-alternatives/)
- [8 Alternatives to Airflow](https://www.windmill.dev/blog/airflow-alternatives)
- [Top 5 Airflow Alternatives for Data Orchestration](https://www.datacamp.com/blog/airflow-alternatives)
