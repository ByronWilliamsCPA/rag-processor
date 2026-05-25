# Agent Catalog

Subagents available for work in this repository.

## Specialized Agents

| Agent | Purpose | When to use |
|-------|---------|-------------|
| `devops-deployment-agent` | CI/CD audit and remediation | Workflow YAML changes, CI check failures |
| `repo-foundations-auditor` | Foundation file compliance | FOUND-* check remediation |
| `pre-commit-auditor` | Pre-commit hook compliance | PC-* check remediation |
| `claude-docs-auditor` | CLAUDE.md and settings compliance | CLAUDE-* check remediation |
| `ossf-compliance-auditor` | OpenSSF Scorecard and badge | OSSF-* check remediation |
| `general-compliance-auditor` | Freeform gap analysis | G-* general findings |
| `writing-style-editor` | Em-dash and AI pattern detection | Doc quality, CLAUDE-007 |

## Model Assignment

| Agent type | Model |
|-----------|-------|
| Read-only exploration (`Explore`) | Haiku 4.5 |
| Planning (`Plan`) | Inherit from caller |
| All others | Sonnet 4.6 (default) |
| Deep reasoning tasks | Opus 4.7 (specify in prompt) |

## Project-Specific Notes

- Non-Claude coding agents (Gemini CLI, Codex, etc.) should treat this file as the
  authoritative agent catalog and also read `CLAUDE.md` for project standards.
- All agents must follow the branch workflow rules in `CLAUDE.md` (never commit to `main`).
- Security-first development standards apply to all agents; see `CLAUDE.md` for details.
