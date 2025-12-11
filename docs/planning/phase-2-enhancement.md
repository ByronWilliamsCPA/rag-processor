---
title: "Phase 2: Enhancement - Detailed Plan"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Define the detailed sprint plan for Phase 2 enhancement features."
tags:
  - planning
  - enhancement
  - implementation
component: Strategy
source: "Derived from roadmap.md Phase 2"
---

<!-- markdownlint-disable MD024 -->

> **Phase Duration**: Week 5 (5 working days, 40 hours)
> **Branch**: `feat/phase-2-enhancement`
> **Status**: Planned
> **Updated**: 2025-12-05

## Overview

Add vector storage handoff integration and improve user experience with result download and batch management features.

**Parent Plan**: [PROJECT-PLAN.md](./PROJECT-PLAN.md#phase-2-enhancement-week-5)

## Phase Objectives

- ✅ Completed batches automatically handed off to registered vector storage target
- ✅ Users can download processed results as ZIP archives
- ✅ Batch history page shows last 50 batches with status filter
- ✅ Error messages include actionable next steps

## Milestones

| Milestone | Target | Exit Criteria | Sprints |
| --------- | ------ | ------------- | ------- |
| M2.1: Vector Store Registration | Day 1 | Target registration API working | S2.1, S2.2 |
| M2.2: Handoff Logic | Day 2 | Automatic handoff on batch completion | S2.3, S2.4 |
| M2.3: Result Download | Day 3 | ZIP download with metadata | S2.5, S2.6 |
| M2.4: Batch History | Day 4 | History UI with filters | S2.7, S2.8 |
| M2.5: Phase Complete | Day 5 | All enhancements tested, PR ready | S2.9, S2.10 |

## Sprint Breakdown (3-4 hour sprints)

### User Story 6: Vector Store Handoff (Days 1-2 - Sprints 2.1-2.4)

#### Sprint 2.1: Target Registration API (4 hours)

**Goal**: Internal API to register vector storage targets

**Tasks**:

1. Create VectorStoreTarget model (1 hour)
   - target_id (UUID)
   - name (e.g., "Qdrant Production")
   - type (qdrant | milvus)
   - url, api_key (encrypted)
   - collection_name

2. Implement POST /api/v1/targets/register (1.5 hours)
   - Internal endpoint (no auth for MVP)
   - Validate target configuration
   - Store in Redis hash: `vector_store_target:{id}`
   - Return target_id

3. Implement GET /api/v1/targets (1 hour)
   - List all registered targets
   - Used in upload UI dropdown
   - Return name and target_id only (no API keys)

4. Write API tests (0.5 hours)
   - Test target registration
   - Test listing targets
   - Test invalid configuration → 400

**Exit Criteria**:

- [ ] Target registration endpoint works
- [ ] Targets stored in Redis
- [ ] Listing endpoint returns targets
- [ ] Tests pass

---

#### Sprint 2.2: Target Selection UI (3 hours)

**Goal**: Frontend dropdown to select vector store target

**Tasks**:

1. Create TargetSelector component (1.5 hours)
   - Fetch targets from /api/v1/targets
   - Dropdown component (or select)
   - Default to first target
   - Handle no targets available

2. Integrate with upload form (1 hour)
   - Add target selection to upload flow
   - Include target_vector_store in upload request
   - Store in batch metadata

3. Write component tests (0.5 hours)
   - Test dropdown renders targets
   - Test selection included in upload
   - Mock targets API

**Exit Criteria**:

- [ ] Dropdown displays registered targets
- [ ] Selected target included in upload
- [ ] Component tests pass

---

#### Sprint 2.3: Handoff Logic (4 hours)

**Goal**: Trigger vector store handoff on batch completion

**Tasks**:

1. Create VectorStoreHandoff service (2 hours)
   - Load target configuration from Redis
   - POST processed results to vector store API
   - Support Qdrant and Milvus protocols
   - Handle authentication (Bearer token)

2. Add completion hook to worker (1 hour)
   - After all jobs complete, check batch status
   - If target_vector_store set, trigger handoff
   - Update batch metadata with handoff status
   - Publish handoff event to WebSocket

3. Write handoff tests (1 hour)
   - Test Qdrant handoff success
   - Test Milvus handoff success
   - Test handoff failure → retry
   - Mock vector store APIs

**Exit Criteria**:

- [ ] Handoff triggers on batch completion
- [ ] Qdrant integration works
- [ ] Milvus integration works
- [ ] Tests pass

---

#### Sprint 2.4: Manual Handoff Retry (3 hours)

**Goal**: UI to manually retry failed handoffs

**Tasks**:

1. Implement POST /api/v1/batch/{id}/handoff (1.5 hours)
   - Manually trigger handoff
   - Check batch completion first
   - Return handoff status

2. Add retry button to UI (1 hour)
   - Show on failed handoff status
   - Call handoff endpoint on click
   - Update UI with new status

3. Write retry tests (0.5 hours)
   - Test manual retry success
   - Test retry on incomplete batch → 400
   - Test UI button interaction

**Exit Criteria**:

- [ ] Manual handoff endpoint works
- [ ] Retry button appears on failed handoffs
- [ ] Retry updates status
- [ ] Tests pass

---

### User Story 7: Result Download (Day 3 - Sprints 2.5-2.6)

#### Sprint 2.5: Result Download API (4 hours)

**Goal**: Endpoint to download processed results

**Tasks**:

1. Implement GET /api/v1/job/{id}/result (2 hours)
   - Load job from Redis
   - Check job status (must be completed)
   - Stream file from `/data/results/{batch_id}/{job_id}/`
   - Set proper content-disposition header

2. Implement GET /api/v1/batch/{id}/results (1.5 hours)
   - Create ZIP archive of all job results
   - Include metadata.json with job details
   - Stream ZIP (don't load all in memory)
   - Use Python zipfile with streaming

3. Write download tests (0.5 hours)
   - Test single job download
   - Test batch ZIP download
   - Test job not found → 404
   - Test incomplete job → 400

**Exit Criteria**:

- [ ] Single job download works
- [ ] Batch ZIP download works
- [ ] Large files stream correctly
- [ ] Tests pass

---

#### Sprint 2.6: Download UI (3 hours)

**Goal**: Download buttons in React UI

**Tasks**:

1. Add download button to job list (1.5 hours)
   - Show on completed jobs
   - Download single result on click
   - Progress indicator while downloading

2. Add batch download button (1 hour)
   - Show when batch completed
   - Download ZIP of all results
   - Display download progress

3. Write component tests (0.5 hours)
   - Test buttons appear on completed jobs/batches
   - Test download initiated on click
   - Mock download API

**Exit Criteria**:

- [ ] Download buttons appear correctly
- [ ] Downloads initiate on click
- [ ] Progress indicators work
- [ ] Component tests pass

---

### Batch History (Day 4 - Sprints 2.7-2.8)

#### Sprint 2.7: Batch History API (3 hours)

**Goal**: Endpoint to list user's past batches

**Tasks**:

1. Implement GET /api/v1/batches (2 hours)
   - List batches for current user
   - Filter by status (query param)
   - Pagination (offset/limit)
   - Sort by created_at desc
   - Load from Redis (scan for user's batches)

2. Optimize Redis storage (0.5 hours)
   - Add index: `user:{user_id}:batches` (set of batch_ids)
   - Update on batch creation
   - Use for fast user batch lookup

3. Write history tests (0.5 hours)
   - Test listing batches
   - Test filtering by status
   - Test pagination
   - Test empty results

**Exit Criteria**:

- [ ] Batch listing endpoint works
- [ ] Filtering by status works
- [ ] Pagination works
- [ ] Tests pass

---

#### Sprint 2.8: Batch History UI (4 hours)

**Goal**: React page displaying batch history

**Tasks**:

1. Create BatchHistory component (2 hours)
   - Table with batch_id, created_at, status, file count
   - Status filter dropdown
   - Pagination controls
   - Click batch → navigate to status page

2. Add routing (0.5 hours)
   - Add /history route
   - Add link in navigation

3. Polish UI (1 hour)
   - Status badges with colors
   - Relative timestamps
   - Loading states
   - Empty state message

4. Write component tests (0.5 hours)
   - Test table renders batches
   - Test filtering
   - Test pagination
   - Mock batch API

**Exit Criteria**:

- [ ] History page displays batches
- [ ] Filtering and pagination work
- [ ] Clicking batch navigates to details
- [ ] Component tests pass

---

### Enhancement Polish (Day 5 - Sprints 2.9-2.10)

#### Sprint 2.9: Enhanced Error Messages (3 hours)

**Goal**: Improve error messages with actionable suggestions

**Tasks**:

1. Create error message catalog (1.5 hours)
   - Map error codes to user-friendly messages
   - Include suggested actions
   - Add links to documentation

2. Update error responses (1 hour)
   - Include suggested_action field
   - Include help_url field
   - Update all error handlers

3. Update UI error display (0.5 hours)
   - Show suggested action
   - Show help link
   - Improve error styling

**Exit Criteria**:

- [ ] All errors have suggested actions
- [ ] Help URLs included
- [ ] UI displays helpful error messages

---

#### Sprint 2.10: Phase 2 PR & Merge (4 hours)

**Goal**: Complete Phase 2 and merge to main

**Tasks**:

1. Run quality checks (1 hour)
   - All linting, type-checking, tests
   - Pre-commit on all files
   - E2E tests

2. Update documentation (1 hour)
   - Update README with new features
   - Add handoff configuration guide
   - Update CHANGELOG

3. Create PR (1.5 hours)
   - Comprehensive description
   - Screenshots of new features
   - Test plan

4. Merge (0.5 hours)
   - Address feedback
   - Merge to main

**Exit Criteria**:

- [ ] All checks passing
- [ ] Documentation updated
- [ ] PR merged
- [ ] Phase 2 complete

---

## Phase 2 Deliverables Checklist

### Vector Store Handoff

- [ ] VectorStoreTarget model
- [ ] POST /api/v1/targets/register endpoint
- [ ] GET /api/v1/targets endpoint
- [ ] Target selection dropdown in upload UI
- [ ] Automatic handoff on batch completion
- [ ] Manual handoff retry
- [ ] Handoff status display in UI
- [ ] Qdrant integration working
- [ ] Milvus integration working
- [ ] Handoff tests

### Result Download

- [ ] GET /api/v1/job/{id}/result endpoint
- [ ] GET /api/v1/batch/{id}/results endpoint (ZIP)
- [ ] Streaming for large files
- [ ] Download buttons in UI
- [ ] Download progress indicators
- [ ] Download tests

### Batch History

- [ ] GET /api/v1/batches endpoint
- [ ] Status filtering
- [ ] Pagination
- [ ] Batch history UI page
- [ ] Navigation link
- [ ] History tests

### UX Improvements

- [ ] Enhanced error messages
- [ ] Suggested actions in errors
- [ ] Help URLs in error responses
- [ ] Improved error styling in UI

## Sprint Schedule

| Sprint | Day | Focus | Hours |
| ------ | --- | ----- | ----- |
| S2.1 | Mon AM | Target Registration API | 4 |
| S2.2 | Mon PM | Target Selection UI | 3 |
| S2.3 | Tue AM | Handoff Logic | 4 |
| S2.4 | Tue PM | Manual Handoff Retry | 3 |
| S2.5 | Wed AM | Result Download API | 4 |
| S2.6 | Wed PM | Download UI | 3 |
| S2.7 | Thu AM | Batch History API | 3 |
| S2.8 | Thu PM | Batch History UI | 4 |
| S2.9 | Fri AM | Enhanced Error Messages | 3 |
| S2.10 | Fri PM | Phase 2 PR & Merge | 4 |

**Total Estimated Hours**: 35 hours (with 5 hours buffer)

## Dependencies

**Requires**:

- Phase 1 complete (job queue, WebSocket working)

**Blocks**:

- Phase 3 (polish requires complete feature set)

## Validation Checklist

Before completing Phase 2:

- [ ] **Vector Store Handoff**: Automatic and manual handoff working
- [ ] **Target Registration**: At least 2 vector stores registered (Qdrant, Milvus)
- [ ] **Result Download**: Single job and batch ZIP downloads work
- [ ] **Batch History**: Displays last 50 batches with filters
- [ ] **Error UX**: All errors have helpful messages
- [ ] **Tests**: Handoff, download, history tests passing
- [ ] **CI**: All checks passing

## Risk Mitigation

| Risk | Mitigation | Sprint |
| ---- | ---------- | ------ |
| Vector store APIs differ significantly | Abstract interface (VectorStoreClient), concrete implementations | S2.1 |
| ZIP creation memory issues for large batches | Use streaming ZIP (zipfile with generator) | S2.5 |
| Batch history slow with many batches | Use Redis index (user:{id}:batches set), pagination | S2.7 |

## Next Phase

After Phase 2:

1. Merge `feat/phase-2-enhancement` to main
2. Review [Phase 3 Plan](./phase-3-polish.md)
3. Create branch: `git checkout -b docs/phase-3-polish`
4. Begin Sprint 3.1: Test Coverage Analysis

## Related Documents

- [PROJECT-PLAN.md](./PROJECT-PLAN.md): Overall project plan
- [Roadmap](./roadmap.md#phase-2-enhancement-week-5): Phase overview
- [Tech Spec](./tech-spec.md): API specifications
- [ADR-001](./adr/adr-001-react-fastapi-architecture.md): Vector storage interface
