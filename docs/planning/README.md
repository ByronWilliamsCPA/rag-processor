---
title: "Project Planning Documents"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Index of project planning documentation."
tags:
  - planning
  - documentation
component: Context
source: "Project initialization"
---

This directory contains the essential planning documents for RAG Processor.

## Quick Start

The planning documents already exist. Start with [project-vision.md](./project-vision.md) and
[tech-spec.md](./tech-spec.md), then use [PROJECT-PLAN.md](./PROJECT-PLAN.md) and [roadmap.md](./roadmap.md) for
sequencing. For where the code stands against the Foundry pipeline, see the
[Level 1 architecture](../architecture/diagrams/level-1/index.md).

## Documents

| Document | Purpose | Status |
|----------|---------|--------|
| [project-vision.md](./project-vision.md) | What & Why | Generated |
| [tech-spec.md](./tech-spec.md) | How to build | Generated |
| [roadmap.md](./roadmap.md) | Implementation plan | Generated |
| [adr/](./adr/) | Architecture decisions | Generated (ADR-001) |
| [PROJECT-PLAN.md](./PROJECT-PLAN.md) | Synthesized plan | Generated |

## Using Documents During Development

### Starting a Session

```text
Load context from:
- project-vision.md sections 2-3
- adr/adr-001-*.md
- tech-spec.md section [relevant section]

Then implement [feature].
```

### Validating Code

```text
Review this code against:
- tech-spec.md section 6 (security)
- adr/adr-002-*.md (relevant decision)

Flag any violations.
```

### Updating Documents

Update documents when:

- **Roadmap**: After completing tasks
- **ADR**: When making architectural decisions
- **Tech Spec**: When architecture changes
- **PVS**: When scope changes

## Document Relationships

```text
┌─────────────────────────────┐
│   Project Vision & Scope    │  ← WHAT & WHY
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Architecture Decisions     │  ← KEY CHOICES
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Technical Specification    │  ← HOW
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Development Roadmap        │  ← WHEN
└─────────────────────────────┘
```

## More Information

- Skill instructions: `.claude/skills/project-planning/SKILL.md`
- Document templates: `.claude/skills/project-planning/templates/`
- Detailed guidance: `.claude/skills/project-planning/reference/`
